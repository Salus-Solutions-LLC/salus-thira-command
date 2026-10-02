"""Revise the same local Part 2 Word review copy for SAL-D081 roles."""

from hashlib import sha256
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "proposals/qa/questionnaire_candidates/Protection Advisor Part 2 Questionnaire.docx"
EXPECTED_SOURCE = "3FD0978D6D0A8A4AE1FF38D452E8AAA3B543DE11384B1855642018A2369A8C6B"
EXPECTED_INTERMEDIATE = "EC121452516AA1676731E18BE68B20CEF4EA312DB6BFF4B6F2F906A53118E6A1"


def main() -> None:
    current = sha256(TARGET.read_bytes()).hexdigest().upper()
    if current not in {EXPECTED_SOURCE, EXPECTED_INTERMEDIATE}:
        document = Document(TARGET)
        if sum("Who can coordinate authorized records and access?" in p.text for p in document.paragraphs) == 1:
            print(current)
            return
        raise ValueError(f"Unexpected Part 2 review-copy version: {current}")
    document = Document(TARGET)
    if current == EXPECTED_SOURCE:
        anchors = [p for p in document.paragraphs if p.text.startswith("Role or decision group that can authorize the next step")]
        assert len(anchors) == 1
        anchor = anchors[0]
        anchor.text = "Role or group that can decide whether to engage Salus for Level 1 (optional; name not required):  _________________________________________________"
        following = next(p for p in document.paragraphs if p.text.startswith("Potential investment range"))
        following.insert_paragraph_before(
            "Who can coordinate authorized records and access? (optional; role or team, no name required):  _________________________________________________"
        )
        following.insert_paragraph_before(
            "You may finish Part 2 if either role is unknown. The scope receipt will show a task to assign that role. "
            "Salus confirms decision and disclosure authority before agreement or file transfer."
        )
    summary = [p for p in document.paragraphs if p.text.startswith("Your draft scope receipt names the requested operation")]
    assert len(summary) == 1
    summary[0].text = summary[0].text.replace(
        "decision role, five steps", "decision role, records coordinator, five steps"
    )
    document.save(TARGET)
    print(sha256(TARGET.read_bytes()).hexdigest().upper())


if __name__ == "__main__":
    main()
