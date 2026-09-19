#!/usr/bin/env python3
"""Representative governed-ingestion acceptance across supported document families."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("M365 exact-folder intake", "ci_m365_governed_intake_smoke.py", "M365_GOVERNED_INTAKE_PASS"),
    ("M365 immutable persistence", "ci_m365_material_ingestion_smoke.py", "M365_MATERIAL_INGESTION_PASS"),
    ("Text extraction and independent review", "ci_m365_extraction_lineage_smoke.py", "M365_EXTRACTION_LINEAGE_PASS"),
    ("Word, Excel, and PowerPoint extraction", "ci_salcapa_office_processing_smoke.py", "SALCAPA_OFFICE_PROCESSING_PASS"),
    ("PDF extraction", "ci_salcapa_pdf_processing_smoke.py", "SALCAPA_PDF_PROCESSING_PASS"),
    ("Image OCR extraction", "ci_salcapa_image_ocr_processing_smoke.py", "SALCAPA_IMAGE_OCR_PROCESSING_SMOKE_PASS"),
    ("Source change and controlled reprocessing", "ci_m365_source_change_reprocessing_smoke.py", "M365_SOURCE_CHANGE_REPROCESSING_PASS"),
    ("SalINTEL reviewed-source indexing", "ci_salintel_material_index_smoke.py", "SALINTEL_MATERIAL_INDEX_PASS"),
    ("SalTHIRA attributed evidence routing", "ci_salthira_material_evidence_routing_smoke.py", "SALTHIRA_MATERIAL_EVIDENCE_ROUTING_PASS"),
)


def main() -> None:
    accepted = []
    for label, script_name, marker in CASES:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / script_name)],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
            check=False,
        )
        if completed.returncode != 0 or marker not in completed.stdout:
            raise AssertionError(
                f"{label} acceptance failed ({script_name}):\n{completed.stdout[-4000:]}"
            )
        accepted.append(label)
    assert len(accepted) == len(CASES)
    print("M365_MULTIFORMAT_GOVERNED_INGESTION_PASS")
    for label in accepted:
        print(f"ACCEPTED: {label}")


if __name__ == "__main__":
    main()
