"""No-cloud checks for the private scanner acceptance candidate's safety gates."""

import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "private_scanner_acceptance_candidate",
    Path(__file__).resolve().parents[1] / "tools" / "private_scanner_acceptance.py",
)
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


class PrivateScannerCandidateChecks(unittest.TestCase):
    def setUp(self):
        self.safe_env = {
            "SALUS_ACCEPTANCE_PRIVATE_JOB": "1",
            "SALUS_AUTH_MODE": "session",
            "SALUS_PACKAGE_COMMERCIAL_WORKFLOW_ENABLED": "1",
            "SALUS_PACKAGE_SCAN_MODE": "defender",
            "SALUS_ENV": "dev",
            "SALUS_DB_BACKEND": "postgres",
            "AZURE_CLIENT_ID": "fictional-identity-id",
            "SALUS_SCAN_QUARANTINE_URL": "https://fictional.blob.core.windows.net",
            "SALUS_ACCEPTANCE_EXPECTED_QUARANTINE_URL": "https://fictional.blob.core.windows.net",
            "SALUS_ACCEPTANCE_JOB_NAME": "salcapa-dev-b48224-scan-test",
        }

    def test_azure_job_name_fits_container_apps_limit(self):
        self.assertLess(len(self.safe_env["SALUS_ACCEPTANCE_JOB_NAME"]), 32)

    def test_private_job_preflight_requires_every_boundary(self):
        with patch.dict(os.environ, self.safe_env, clear=True):
            candidate.guarded_environment()
            for key in self.safe_env:
                with self.subTest(key=key):
                    with patch.dict(os.environ, {key: ""}):
                        with self.assertRaises(RuntimeError):
                            candidate.guarded_environment()

    def test_test_payloads_are_bounded_and_distinct(self):
        fixtures = dict(candidate._test_files("fictional1"))
        self.assertEqual(set(fixtures), {"clean", "eicar"})
        self.assertEqual(len(fixtures["eicar"]), 68)
        self.assertLess(len(fixtures["clean"]), 1024)
        self.assertNotEqual(fixtures["clean"], fixtures["eicar"])

    def test_run_id_cannot_be_reused_as_a_path_or_query(self):
        class NeverOpenDatabase:
            def db(self):
                raise AssertionError("invalid ID must fail before DB access")
        for bad in ("../other", "member@example", "short", "A" * 10):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    candidate.seed_fictional_scope(NeverOpenDatabase(), bad)


if __name__ == "__main__":
    unittest.main()

