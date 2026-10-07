"""Fictional-only, content-free checks for the one-time knowledge retry probe."""

import importlib.util
from pathlib import Path


path = Path(__file__).resolve().parents[1] / "tools" / "knowledge_large_retry_probe.py"
spec = importlib.util.spec_from_file_location("knowledge_retry_probe", path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


assert probe.summary([]) == {"match_count": 0, "unique_match": False}
assert probe.summary([{}] * 6) == {"match_count": 6, "unique_match": False}
assert probe.category("Knowledge upload status was ambiguous") == "upload_range"
assert probe.category("Knowledge upload session could not be created") == "session_creation"
assert probe.category("Approved knowledge file could not be written") == "destination_write"
assert probe.category("Private title / arbitrary exception") == "unclassified"

fictional_row = {
    "status": "Automatic Retry Required",
    "review_rationale": "Knowledge upload status was ambiguous / private title",
    "destination_item_id": "fictional-destination-id",
    "source_archive_item_id": "",
}
result = probe.summary([fictional_row])
assert result == {
    "match_count": 1,
    "unique_match": True,
    "status": "Automatic Retry Required",
    "failure_category": "upload_range",
    "has_destination": True,
    "has_archive": False,
}
assert "private title" not in str(result)
assert "fictional-destination-id" not in str(result)
fictional_row["review_rationale"] = "private title"
assert probe.summary([fictional_row])["failure_category"] == "unclassified"
fictional_row["status"] = "private status"
assert probe.summary([fictional_row])["status"] == "Other"
print("Knowledge retry probe fictional-only checks passed")

