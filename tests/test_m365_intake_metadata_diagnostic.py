"""Fictional metadata only; no identity, network, content or business store."""
import contextlib
import ast
import hashlib
import io
import json
from pathlib import Path
import tempfile
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import m365_intake_metadata_diagnostic as diagnostic

SOURCE = "7b79b2845aaa6e2bf738e0c115c10b73e4c97dd3"
OLD = "5dff59b381a0c455f99c6f15d0e2a37c273f4056"
PRIVATE = "FICTIONAL_PRIVATE_SENTINEL"


class Intake:
    def __init__(self):
        self.config = SimpleNamespace(drive_id=PRIVATE + "DRIVE")
        self.rows = [{"id": PRIVATE + "ITEM", "name": PRIVATE + ".pdf", "size": 321, "etag": PRIVATE + "ETAG"}]
        self._listed_folder_ids = {PRIVATE + "PARENT"}
        self._listed_items = {r["id"]: r.copy() for r in self.rows}
        self.calls = []
        self.mutate = lambda current: None
        self.status = 200
        self.client = SimpleNamespace(get=self.get, close=lambda: None)

    def list_files(self, **kwargs):
        self.calls.append(("list", kwargs))
        return self.rows

    def _headers(self):
        return {"Authorization": PRIVATE + "TOKEN"}

    def get(self, url, **kwargs):
        self.calls.append(("metadata", kwargs))
        assert url.startswith(diagnostic.GRAPH_ROOT + "/drives/") and "/content" not in url
        assert kwargs["params"] == {"$select": "id,name,size,eTag,parentReference,file"}
        assert kwargs["timeout"] == 8.0
        row = next(r for r in self.rows if url.endswith("/" + r["id"]))
        current = {"id": row["id"], "name": row["name"], "size": row["size"],
                   "eTag": row["etag"], "parentReference": {"id": PRIVATE + "PARENT"}}
        self.mutate(current)
        return SimpleNamespace(status_code=self.status, json=lambda: current)

    def read_listed_document(self, *args, **kwargs):
        raise AssertionError("CONTENT_METHOD_MUST_NOT_BE_CALLED")

    _read_allowed_item = read_listed_document


class MetadataDiagnosticTests(unittest.TestCase):
    def test_no_source_write_or_content_entrypoint_in_diagnostic(self):
        tree = ast.parse(Path(diagnostic.__file__).read_text(encoding="utf-8"))
        forbidden = {"post", "put", "patch", "delete", "execute", "executescript",
                     "read_listed_document", "_read_allowed_item", "download_document"}
        self.assertFalse({n.func.attr for n in ast.walk(tree)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)} & forbidden)

    def test_source_and_listing_pins_match_governed_candidate(self):
        source = (diagnostic.ROOT / "salcapa_m365_intake.py").read_bytes().replace(b"\r\n", b"\n")
        method = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == "list_files")
        module = ast.Module(body=[method], type_ignores=[])
        self.assertEqual(hashlib.sha256(source).hexdigest(), diagnostic.PINS[SOURCE][0])
        self.assertEqual(hashlib.sha256(ast.dump(module, include_attributes=False).encode()).hexdigest(), diagnostic.PINS[SOURCE][1])

    def run_probe(self, intake=None, source=SOURCE, retain=None, **kwargs):
        intake = intake or Intake()
        self.receipts = []
        def store(payload):
            self.receipts.append(payload)
            return payload
        with patch.object(diagnostic, "fingerprint", return_value=diagnostic.PINS[source][:2]):
            return diagnostic.diagnose(
                intake, source_commit=source, image_digest=diagnostic.PINS[source][2],
                execution_id="run-123-attempt-1", retain=retain or store, **kwargs)

    def assert_private(self, receipt):
        encoded = json.dumps(receipt)
        self.assertNotIn(PRIVATE, encoded)
        self.assertNotIn('"size": 321', encoded)

    def test_stable_and_no_source_content_or_writes(self):
        intake = Intake()
        result = self.run_probe(intake)
        receipt = json.loads(self.receipts[0])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["compared_count"], 1)
        self.assertEqual({c[0] for c in intake.calls}, {"list", "metadata"})
        self.assert_private(receipt)
        self.assert_private(result)
        self.assertIsNone(receipt["failure_stage"])
        self.assertNotIn("candidate_ref", json.dumps(result))

    def test_each_predicate_and_simultaneous_mismatches_fail(self):
        changes = {
            "id": lambda c: c.update(id="DIFFERENT"),
            "name": lambda c: c.update(name="DIFFERENT"),
            "etag": lambda c: c.update(eTag="DIFFERENT"),
            "size": lambda c: c.update(size=999),
            "parent_boundary": lambda c: c.update(parentReference={"id": "OUTSIDE"}),
            "listed_snapshot": lambda c: None,
        }
        for key, change in changes.items():
            with self.subTest(predicate=key):
                intake = Intake()
                intake.mutate = change
                if key == "listed_snapshot":
                    intake._listed_items.clear()
                with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "CONSISTENCY_MISMATCH") as caught:
                    self.run_probe(intake)
                flags = json.loads(self.receipts[0])["observations"][0]["mismatches"]
                self.assertEqual(flags, {k: k == key for k in diagnostic.KEYS})
                self.assertEqual(caught.exception.summary["status"], "failed")
                self.assert_private(json.loads(self.receipts[0]))
        intake = Intake()
        intake.mutate = lambda c: [f(c) for f in changes.values()]
        intake._listed_items.clear()
        with self.assertRaises(diagnostic.DiagnosticFailure):
            self.run_probe(intake)
        self.assertTrue(all(json.loads(self.receipts[0])["observations"][0]["mismatches"].values()))

    def test_run_scoped_correlation(self):
        self.run_probe()
        first = json.loads(self.receipts[0])["observations"][0]["candidate_ref"]
        self.run_probe()
        second = json.loads(self.receipts[0])["observations"][0]["candidate_ref"]
        self.assertNotEqual(first, second)

    def test_pending_sample_bound_and_archive_family_selection(self):
        intake = Intake()
        intake.rows = [{"id": PRIVATE + str(n), "name": PRIVATE + ".pdf", "size": n + 1, "etag": PRIVATE} for n in range(60)]
        intake._listed_items = {r["id"]: r.copy() for r in intake.rows}
        result = self.run_probe(intake)
        self.assertEqual((result["listed_count"], result["selected_count"], result["compared_count"]), (60, 50, 50))
        self.assertEqual(intake.calls[0], ("list", {"pending_only": True, "max_files": 500}))
        intake.rows += [{"id": PRIVATE + "text", "name": PRIVATE + ".txt", "size": 1, "etag": PRIVATE}]
        intake._listed_items = {r["id"]: r.copy() for r in intake.rows}
        result = self.run_probe(intake, subtree="processed")
        self.assertEqual(result["compared_count"], 2)
        self.assertEqual({r["family"] for r in json.loads(self.receipts[0])["observations"]}, {"pdf", "text"})

    def test_empty_listing_is_explicit_failure(self):
        intake = Intake()
        intake.rows = []
        with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "NO_ITEMS"):
            self.run_probe(intake)
        self.assertEqual(json.loads(self.receipts[0])["compared_count"], 0)

    def test_cli_prints_aggregates_only_and_sanitizes_cleanup_failure(self):
        intake = Intake()
        fake_module = SimpleNamespace(
            GovernedM365Config=SimpleNamespace(from_environment=lambda: None),
            GovernedM365Intake=lambda config: intake)
        for cleanup_fails in [False, True]:
            with self.subTest(cleanup_fails=cleanup_fails), tempfile.TemporaryDirectory() as directory:
                def close():
                    if cleanup_fails:
                        raise ValueError(PRIVATE + "CLOSE")
                intake.client.close = close
                output = io.StringIO()
                with patch.dict("sys.modules", {"salcapa_m365_intake": fake_module}), \
                     patch.object(diagnostic, "fingerprint", return_value=diagnostic.PINS[SOURCE][:2]), \
                     contextlib.redirect_stdout(output):
                    code = diagnostic.main([
                        "--receipt", str(Path(directory) / "receipt.json"), "--source-commit", SOURCE,
                        "--image-digest", diagnostic.PINS[SOURCE][2], "--execution-id", "run-123-attempt-1"])
                self.assertNotIn(PRIVATE, output.getvalue())
                self.assertNotIn("candidate_ref", output.getvalue())
                public = json.loads(output.getvalue())
                self.assertEqual(code, int(cleanup_fails))
                self.assertEqual(public["code"], "CLIENT_CLEANUP_FAILED" if cleanup_fails else "COMPLETE")

    def test_old_archive_rejected_before_source_access(self):
        intake = Intake()
        with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "ARCHIVE_BOUND_UNSUPPORTED"):
            self.run_probe(intake, source=OLD, subtree="processed")
        self.assertEqual(intake.calls, [])
        self.assertEqual(json.loads(self.receipts[0])["status"], "failed")

    def test_non_200_and_missing_metadata_fail_without_content(self):
        for status in [404, 500]:
            with self.subTest(status=status):
                intake = Intake()
                intake.status = status
                with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "METADATA_FAILED"):
                    self.run_probe(intake)
                receipt = json.loads(self.receipts[0])
                self.assertEqual(receipt["observations"][0]["http_status"], status)
                self.assertIsNone(receipt["observations"][0]["mismatches"])
        intake = Intake()
        intake.mutate = lambda c: c.clear()
        with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "CONSISTENCY_MISMATCH"):
            self.run_probe(intake)

    def test_sensitive_provider_exception_is_redacted(self):
        intake = Intake()
        def fail(*args, **kwargs):
            raise ValueError(PRIVATE + "PROVIDER_RESPONSE")
        intake.client.get = fail
        with self.assertRaises(diagnostic.DiagnosticFailure) as caught:
            self.run_probe(intake)
        self.assertNotIn(PRIVATE, "".join(traceback.format_exception(caught.exception)))
        self.assert_private(json.loads(self.receipts[0]))

    def test_retention_failure_and_changed_readback_never_succeed(self):
        def fail(payload):
            raise OSError(PRIVATE)
        for store in [fail, lambda payload: b"different", lambda payload: None]:
            with self.subTest(retain=store):
                with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "RECEIPT_RETENTION_FAILED"):
                    self.run_probe(retain=store)

    def test_timeout_is_incomplete_even_with_no_mismatch(self):
        ticks = iter([0, 46])
        with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "TIME_BOUND_REACHED"):
            self.run_probe(clock=lambda: next(ticks))
        receipt = json.loads(self.receipts[0])
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["compared_count"], 0)

    def test_unknown_source_fails_before_network(self):
        intake = Intake()
        with patch.object(diagnostic, "fingerprint", return_value=("unexpected", "unexpected")):
            with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "SOURCE_INCOMPATIBLE"):
                diagnostic.diagnose(intake, source_commit=SOURCE, image_digest=diagnostic.PINS[SOURCE][2],
                                    execution_id="run-123-attempt-1", retain=lambda payload: payload)
        self.assertEqual(intake.calls, [])

    def test_invalid_limits_fail_before_network(self):
        for kwargs in [{"listing_limit": 501}, {"sample_limit": 51}, {"listing_limit": True}]:
            intake = Intake()
            with self.assertRaisesRegex(diagnostic.DiagnosticFailure, "INVALID_CONFIGURATION"):
                self.run_probe(intake, **kwargs)
            self.assertEqual(intake.calls, [])

    def test_exclusive_private_file_readback_and_repository_denial(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "receipt.json"
            sink = diagnostic.private_file_sink(destination)
            self.assertEqual(sink(b'{"status":"fictional"}\n'), destination.read_bytes())
            with self.assertRaises(FileExistsError):
                sink(b"replace")
            with self.assertRaises(diagnostic.DiagnosticFailure):
                diagnostic.private_file_sink(destination)
            (Path(directory) / ".git").write_text("fictional worktree marker")
            with self.assertRaises(diagnostic.DiagnosticFailure):
                diagnostic.private_file_sink(Path(directory) / "second.json")
        with self.assertRaises(diagnostic.DiagnosticFailure):
            diagnostic.private_file_sink(diagnostic.ROOT / "forbidden-receipt.json")


if __name__ == "__main__":
    unittest.main()
