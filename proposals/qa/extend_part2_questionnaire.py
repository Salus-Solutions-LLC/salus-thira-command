"""Align the local Part 2 Word review copy with the consented follow-up questions."""

import ast
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "public_protection_advisor.py"
TARGET = ROOT / "proposals/qa/questionnaire_candidates/Protection Advisor Part 2 Questionnaire.docx"


def literal_assignment(name):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise ValueError(f"Missing source assignment: {name}")


def main():
    version = literal_assignment("QUESTIONNAIRE_VERSION")
    screened = literal_assignment("PART1_SCREEN_TEXT")
    full = literal_assignment("QUESTION_BLUEPRINTS")
    followups = [row for row in full if row[0] not in screened]
    if version != "SPA-PUBLIC-QUESTIONNAIRE-2.3.0" or len(followups) != 19:
        raise ValueError("Part 2 source boundary changed; review the Word revision.")
    document = Document(TARGET)
    paragraphs = document.paragraphs
    already = [p for p in paragraphs if p.text == "Additional readiness questions after Part 1"]
    if not already:
        if sum("SPA-PUBLIC-QUESTIONNAIRE-2.2.0" in p.text for p in paragraphs) != 1:
            raise ValueError("Expected original Part 2 review copy was not found.")
        anchor = next(p for p in paragraphs if p.text == "Organization and decision profile")
        anchor.insert_paragraph_before("Additional readiness questions after Part 1", style="Heading 1")
        anchor.insert_paragraph_before(
            "Your nine Part 1 answers carry forward. After you sign in and consent, answer the "
            "following 19 additional questions from current knowledge. Choose Not Sure, Does Not Apply, "
            "or Prefer Not to Answer rather than guessing. Salus still validates reported capability "
            "during an authorized assessment."
        )
        choices = (
            "☐ Yes, recently tested   ☐ Yes, documented, not recently tested\n"
            "☐ Some parts are in place   ☐ No, not in place\n"
            "☐ Not sure   ☐ Does not apply   ☐ Prefer not to answer"
        )
        for index, row in enumerate(followups, 1):
            anchor.insert_paragraph_before(f"{index}. {row[1]}", style="Heading 2")
            anchor.insert_paragraph_before(choices)
        anchor.insert_paragraph_before(
            "The completed Part 1 and Part 2 answers give Salus a preliminary map of the 32 core "
            "capabilities across five mission areas. This map remains self-reported, not a verified "
            "readiness or compliance determination."
        )
    elif len(already) != 1:
        raise ValueError("Duplicate Part 2 follow-up section found.")
    for p in document.paragraphs:
        if "SPA-PUBLIC-QUESTIONNAIRE-2.2.0" in p.text:
            p.text = p.text.replace("SPA-PUBLIC-QUESTIONNAIRE-2.2.0", version)
        if "29 September 2026  |  Working review copy" in p.text:
            p.text = p.text.replace("29 September 2026", "01 October 2026")
        if p.text.startswith("Part 2 follows account sign-in and express consent"):
            p.text = (
                "Part 2 follows account sign-in and express consent to retain identifiable contact "
                "information. It adds 19 readiness questions to the nine Part 1 answers, then asks "
                "about the operation you want Salus to assess. It supports a preliminary package "
                "discussion, not an issued SalCAPA™ assessment."
            )
        if p.text.startswith("Annual revenue range:"):
            p.paragraph_format.keep_with_next = True
    document.save(TARGET)
    print(TARGET)


if __name__ == "__main__":
    main()
