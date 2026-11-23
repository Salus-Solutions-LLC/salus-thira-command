import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.planning_failure_evidence import configuration_evidence, marker_evidence


class FailureEvidenceTests(unittest.TestCase):
    def resource(self):
        return {"identity": {"type": "UserAssigned"}, "properties": {
            "template": {"containers": [{"name": "worker", "env": [
                {"name": "A", "value": "private-alpha"},
                {"name": "B", "secretRef": "private-secret-name"}]}]},
            "configuration": {"secrets": [{"name": "one", "value": "private-secret-value"}]}}}

    def test_partial_run_retains_failure_without_inventing_completion(self):
        result = marker_evidence("TASK_KNOWLEDGE_NEW_RECEIPTS_CREATED=3\nTASK_KNOWLEDGE_FAILURE_STAGE=membership_postquery\nTASK_KNOWLEDGE_FAILURE_TYPE=RuntimeError")
        self.assertEqual(result["records"]["TASK_KNOWLEDGE_NEW_RECEIPTS_CREATED"], "3")
        self.assertNotIn("TASK_KNOWLEDGE_COMPLETE", result["records"])

    def test_rejects_raw_source_text_and_arbitrary_marker_values(self):
        result = marker_evidence("private document text\nTASK_KNOWLEDGE_FAILURE_STAGE=private-document-name\nTASK_KNOWLEDGE_OTHER=private-secret-value")
        self.assertEqual(result["records"], {})
        self.assertEqual(result["rejected_marker_count"], 2)
        self.assertNotIn("private", json.dumps(result))

    def test_conflicting_duplicates_are_explicit(self):
        result = marker_evidence("TASK_KNOWLEDGE_COMPLETE=0\nTASK_KNOWLEDGE_COMPLETE=1")
        self.assertEqual(result["conflicting_keys"], ["TASK_KNOWLEDGE_COMPLETE"])

    def test_same_configuration_passes(self):
        self.assertTrue(configuration_evidence(self.resource(), self.resource())["strict_equal"])

    def test_named_array_reorder_is_visible_and_still_fails_strict_check(self):
        before = self.resource()
        after = copy.deepcopy(before)
        after["properties"]["template"]["containers"][0]["env"].reverse()
        result = configuration_evidence(before, after)
        self.assertFalse(result["strict_equal"])
        self.assertTrue(result["named_array_order_only"])
        self.assertEqual(result["differing_sections"], ["template"])

    def test_value_change_cannot_be_dismissed_as_order(self):
        after = self.resource()
        after["properties"]["template"]["containers"][0]["env"][0]["value"] = "changed-private-value"
        result = configuration_evidence(self.resource(), after)
        self.assertFalse(result["strict_equal"])
        self.assertFalse(result["named_array_order_only"])
        self.assertNotIn("private", json.dumps(result))

    def test_missing_projection_cannot_pass(self):
        with self.assertRaises(ValueError):
            configuration_evidence({}, {})

    def test_missing_log_writes_explicit_failure_record(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audit" / "markers.json"
            result = subprocess.run([sys.executable, "tools/planning_failure_evidence.py", "markers",
                "--input", str(Path(directory) / "missing"), "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(json.loads(output.read_text())["accepted"])
            self.assertEqual(result.stdout, "")

    def test_empty_log_cannot_report_collected_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "empty.log"
            source.write_text("")
            output = Path(directory) / "markers.json"
            result = subprocess.run([sys.executable, "tools/planning_failure_evidence.py", "markers",
                "--input", str(source), "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(output.read_text())["records"], {})


if __name__ == "__main__":
    unittest.main()
