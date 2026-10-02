"""Make fictional boundary-length variants of the four candidate Word templates.

These are layout fixtures, not completed reports or Protected Member records.
"""

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "level_band_templates"
OUTPUT = ROOT / "qa" / "template_boundary_stress"
NAME = "Cedar Valley Regional Childcare, Building Supply, Transportation and Community Services Cooperative"
OPERATION = (
    "Three geographically separate facilities, a shared distribution function, "
    "weekend childcare program and contracted transport operations; excludes the "
    "separately owned warehouse, third-party vehicles and offsite events"
)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for product in ("SalINTEL", "SalTHIRA", "SalOPS", "SalCAPA"):
        source = TEMPLATES / f"{product} Level Band Template Candidate.docx"
        target = OUTPUT / f"{product} Level 3C boundary stress.docx"
        with ZipFile(source) as original, ZipFile(target, "w") as result:
            for info in original.infolist():
                data = original.read(info.filename)
                if info.filename == "word/document.xml":
                    xml = data.decode("utf-8")
                    assert "[Protected Member customer name]" in xml
                    assert "[path]" in xml
                    xml = xml.replace("[Protected Member customer name]", NAME)
                    xml = xml.replace("[path]", "3C")
                    xml = xml.replace("[covered operation and included/excluded units]", OPERATION)
                    data = xml.encode("utf-8")
                result.writestr(info, data)
            result.comment = original.comment
        with ZipFile(target) as check:
            assert check.testzip() is None
        print(product, target, sha256(target.read_bytes()).hexdigest().upper())


if __name__ == "__main__":
    main()
