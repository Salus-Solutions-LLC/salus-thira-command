import hashlib
import importlib.util
import pathlib
import sys
import types
import unittest


try:
    import salus_scan_inventory  # noqa: F401
except ModuleNotFoundError:
    # The standalone candidate uses a stub; repository CI imports the real module.
    sys.modules["salus_scan_inventory"] = types.SimpleNamespace(
        compare_quarantine_versions=lambda ledger, azure, max_versions: {
            "unlinked_versions": [], "missing_versions": [],
            "size_mismatches": [], "hold_mismatches": [],
        },
        list_azure_quarantine_versions=lambda container: [],
    )
path = pathlib.Path(__file__).resolve().parents[1] / "tools" / "private_exception_disposition.py"
spec = importlib.util.spec_from_file_location("candidate", path)
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


class DispositionQualificationTest(unittest.TestCase):
    def setUp(self):
        self.account = "https://fictionalblob.blob.core.windows.net"
        self.ledger = []
        self.azure = []
        self.deleted = set()
        self.rows = []
        for index, name in enumerate(sorted(candidate.EXPECTED_CLEANUP_NAMES)):
            version = f"deleted-v{index}"
            self.deleted.add((name, version))
            self.rows.append(self.row("Unlinked", name, version, None))
        for index in range(2):
            name, version = f"tenant-7/test-{index}", f"active-v{index}"
            self.ledger.append({"tenant_id": 7, "blob_name": name,
                                "blob_version_id": version, "size_bytes": 10,
                                "legal_hold": 0})
            self.azure.append({"name": name, "version_id": version,
                               "size_bytes": 10, "legal_hold": False})
            self.rows.append(self.row("HoldMismatch", name, version, 7))

    def row(self, kind, name, version, tenant):
        key = hashlib.sha256(
            f"{self.account}\0{kind}\0{name}\0{version}".encode()).hexdigest()
        return {"exception_key": key, "account_url": self.account,
                "exception_type": kind, "blob_name": name,
                "blob_version_id": version, "candidate_tenant_id": tenant,
                "status": "Open", "assigned_to": "", "disposition": ""}

    def qualify(self):
        return candidate.qualify(self.rows, self.ledger, self.azure,
                                 self.deleted, self.account)

    def test_only_exact_four_qualify(self):
        self.assertEqual(len(self.qualify()), 4)

    def test_unsupported_cleanup_path_is_rejected(self):
        self.rows[0] = self.row("Unlinked", "unrelated/file.txt", "deleted-v0", None)
        with self.assertRaises(ValueError):
            self.qualify()

    def test_missing_deleted_exact_version_is_rejected(self):
        self.deleted.pop()
        with self.assertRaises(ValueError):
            self.qualify()

    def test_changed_hold_scope_is_rejected(self):
        self.rows[2]["candidate_tenant_id"] = 8
        with self.assertRaises(ValueError):
            self.qualify()

    def test_existing_disposition_is_rejected(self):
        self.rows[0]["disposition"] = "previous review"
        with self.assertRaises(ValueError):
            self.qualify()

    def test_incomplete_set_is_rejected(self):
        self.rows.pop()
        with self.assertRaises(ValueError):
            self.qualify()


if __name__ == "__main__":
    unittest.main()

