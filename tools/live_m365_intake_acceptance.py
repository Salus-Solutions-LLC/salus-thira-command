#!/usr/bin/env python3
"""Live, bounded acceptance for deployed governed Microsoft 365 intake and extraction."""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
from urllib.parse import urlparse

from salcapa_image_ocr_processing import _decode_image
from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, GRAPH_ROOT


_REQUIRED_FAMILIES = {"word", "excel", "powerpoint", "pdf", "image"}
_TEXT_EXTENSIONS = {"txt", "md", "csv", "tsv", "json", "xml"}
_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff", "bmp", "webp"}


def _family(name: str) -> str | None:
    suffix = PurePosixPath(name).suffix.lower().lstrip(".")
    if suffix == "docx":
        return "word"
    if suffix == "xlsx":
        return "excel"
    if suffix == "pptx":
        return "powerpoint"
    if suffix == "pdf":
        return "pdf"
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    if suffix in _TEXT_EXTENSIONS:
        return "text"
    return None


def main() -> None:
    config = GovernedM365Config.from_environment()
    config.validate()
    if config.max_file_bytes != 100 * 1024 * 1024:
        raise RuntimeError("M365_INTAKE_100MB_LIMIT_NOT_ACTIVE")
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
    if not any("/" in str(item.get("relative_path", "")) for item in files):
        raise RuntimeError("M365_INTAKE_NO_NESTED_FILE")

    samples: dict[str, dict] = {}
    for item in files:
        family = _family(str(item.get("name", "")))
        if family and int(item.get("size", 0)) > 0:
            current = samples.get(family)
            if current is None or (int(item["size"]), str(item["id"])) < (
                int(current["size"]), str(current["id"])
            ):
                samples[family] = item

    missing = sorted(_REQUIRED_FAMILIES - samples.keys())
    if missing:
        raise RuntimeError("M365_INTAKE_MISSING_REPRESENTATIVE_FORMATS:" + ",".join(missing))

    accepted = []
    for family in sorted(samples):
        sample = samples[family]
        document = intake.read_document(
            str(sample["id"]), access_classification="Salus Internal"
        )
        if document.relative_path != sample["relative_path"]:
            raise RuntimeError("M365_INTAKE_RELATIVE_PATH_MISMATCH")
        if document.sha256 != hashlib.sha256(document.content).hexdigest():
            raise RuntimeError("M365_INTAKE_HASH_MISMATCH")
        if not document.etag or not document.last_modified or not document.web_url:
            raise RuntimeError("M365_INTAKE_PROVENANCE_INCOMPLETE")
        text, method, _truncated, processor, processor_version = _decode_image(
            document.content, document.name, document.mime_type
        )
        if not text.strip() or not method or not processor or not processor_version:
            raise RuntimeError(f"M365_{family.upper()}_EXTRACTION_EMPTY")
        accepted.append(
            f"{family}:{len(document.content)}:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
        )

    sample = min(files, key=lambda item: (item["size"] == 0, item["size"], item["id"]))
    content = intake.read_file(sample["id"])
    if len(content) != sample["size"]:
        raise RuntimeError("M365_INTAKE_CONTENT_SIZE_MISMATCH")

    print(
        "M365_LIVE_GOVERNED_EXTRACTION_PASS "
        f"drive_type={str(drive.get('driveType', 'unknown'))[:32]} "
        f"file_count={len(files)} nested=true max_file_bytes={config.max_file_bytes} "
        f"families={','.join(item.split(':', 1)[0] for item in accepted)} "
        f"sample_bytes={len(content)} sample_sha256={hashlib.sha256(content).hexdigest()}"
    )


if __name__ == "__main__":
    main()
