"""Update the existing Part 2 Word review identity for the two-layer scope profile."""

import ast
from hashlib import sha256
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "proposals/qa/questionnaire_candidates/Protection Advisor Part 2 Questionnaire.docx"
EXPECTED_SOURCE = "665646A3DE7086A82171DCF88712F18B43552D95124A1A81751763CF40AF7646"
EXPECTED_INTERMEDIATE = "AD5C6219F2C57F8F02C8F66882D78B198818D1562AD2A19BD5EC9C27704C9671"
EXPECTED_RESULT = "3FD0978D6D0A8A4AE1FF38D452E8AAA3B543DE11384B1855642018A2369A8C6B"


def main() -> None:
    current = sha256(TARGET.read_bytes()).hexdigest().upper()
    if current == EXPECTED_RESULT:
        print(current)
        return
    if current not in {EXPECTED_SOURCE, EXPECTED_INTERMEDIATE}:
        raise ValueError(f"Unexpected Part 2 review-copy version: {current}")
    doc = Document(TARGET)
    paragraphs = doc.paragraphs
    exact = {p.text: p for p in paragraphs}
    if current == EXPECTED_SOURCE:
        assert "Covered operation tags" not in exact
        anchor = exact["How many operations need their own decision?  _________________________________________________"]
        anchor.insert_paragraph_before("Covered operation tags", style="Heading 2")
        anchor.insert_paragraph_before(
            "What work happens in the operation you want assessed? Optional—mark any that apply. "
            "These descriptions help tailor later questions and records; they do not set a risk rating, band or price."
        )
        source = ast.parse((ROOT / "public_protection_advisor.py").read_text(encoding="utf-8"))
        matches = [node for node in source.body if isinstance(node, ast.Assign) and
                   any(isinstance(target, ast.Name) and target.id == "COVERED_OPERATION_TAGS"
                       for target in node.targets)]
        assert len(matches) == 1
        tags = ast.literal_eval(matches[0].value)
        assert len(tags) == 13
        for tag in sorted(tags):
            anchor.insert_paragraph_before("☐ " + tag)

        replacements = {
        "Annual revenue range:  _________________________________________________":
            "Annual revenue or operating-budget range (optional; does not set your package or fee):  _________________________________________________",
        "Investment range:  _________________________________________________":
            "Potential investment range (optional):  _________________________________________________",
        "Decision authority:  _________________________________________________":
            "Role or decision group that can authorize the next step (name not required):  _________________________________________________",
        "Specific activities": "Activities and operating conditions",
        "Mark all that apply. These categories tailor the assessment and service discussion.":
            "Mark any that apply. These conditions help Salus ask relevant follow-up questions; they are separate from the covered-operation tags above.",
        }
        for old, new in replacements.items():
            assert sum(p.text == old for p in doc.paragraphs) == 1, old
            next(p for p in doc.paragraphs if p.text == old).text = new
        for prefix in ("Under $1 million;", "Under $10,000;"):
            matches = [p for p in doc.paragraphs if p.text.startswith("Choices: " + prefix)]
            assert len(matches) == 1, prefix
            matches[0].text = matches[0].text.replace("Choices: ", "Choices: Skip; ", 1)
    path_heading = next(p for p in doc.paragraphs if p.text == "Your possible Level 1 path")
    path_heading.paragraph_format.page_break_before = False
    doc.save(TARGET)
    print(sha256(TARGET.read_bytes()).hexdigest().upper())


if __name__ == "__main__":
    main()
