#!/usr/bin/env python3
"""Live, bounded acceptance for the deployed governed Microsoft 365 intake."""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse

from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, GRAPH_ROOT


def main() -> None:
    config = GovernedM365Config.from_environment()
    config.validate()
    intake = GovernedM365Intake(config)

    drive_response = intake.client.get(
        f"{GRAPH_ROOT}/drives/{config.drive_id}",
        headers=intake._headers(),
        params={"$select": "id,driveType,webUrl"},
    )
    if drive_response.status_code != 200:
        raise RuntimeError("M365_INTAKE_DRIVE_METADATA_FAILED")
    drive = drive_response.json()
    if str(drive.get("id", "")) != config.drive_id:
        raise RuntimeError("M365_INTAKE_DRIVE_ID_MISMATCH")
    web_url = urlparse(str(drive.get("webUrl", "")))
    if web_url.scheme != "https" or not (web_url.hostname or "").lower().endswith(".sharepoint.com"):
        raise RuntimeError("M365_INTAKE_DRIVE_TRUST_FAILED")

    files = intake.list_files()
    if not files:
        raise RuntimeError("M365_INTAKE_NO_ACCEPTANCE_FILE")
    sample = min(files, key=lambda item: (item["size"] == 0, item["size"], item["id"]))
    content = intake.read_file(sample["id"])
    if len(content) != sample["size"]:
        raise RuntimeError("M365_INTAKE_CONTENT_SIZE_MISMATCH")

    print(
        "M365_LIVE_INTAKE_PASS "
        f"drive_type={str(drive.get('driveType', 'unknown'))[:32]} "
        f"file_count={len(files)} sample_bytes={len(content)} "
        f"sample_sha256={hashlib.sha256(content).hexdigest()}"
    )


if __name__ == "__main__":
    main()
