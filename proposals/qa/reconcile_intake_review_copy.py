"""Correct stale statements in the existing internal Advisor-to-Level-1 worksheet.

The expected hash prevents accidental editing of a different review version.
This does not change live Protection Advisor fields or issue a Member form.
"""

from hashlib import sha256
from pathlib import Path

from docx import Document


TARGET = Path(__file__).parent / "questionnaire_candidates" / "Protection_Advisor_Level_1_Intake_Revision_DRAFT.docx"
EXPECTED_SOURCE = {
    "9CAF9E74BACF2C86608C9C4765D5F85C863462CA8C69AE21BBE188671157F8CC",
    "D8ED4D10E9884A9B8B5B18A305C0E68AA7C77B52F20A4888E388437C63AC80AD",
}
EXPECTED_RESULT = "6A30BD2E3B861DEFEFC239CB1D4CD7046B70C6123EADA1FC8406927C40284CED"


def revise() -> None:
    current = sha256(TARGET.read_bytes()).hexdigest().upper()
    if current == EXPECTED_RESULT:
        print(current)
        return
    assert current in EXPECTED_SOURCE, "Unexpected intake review-copy version"
    doc = Document(TARGET)
    changes = {
        1: "SALUS INTERNAL CONFIDENTIAL  |  Working review copy  |  01 October 2026",
        2: "Purpose. This internal worksheet tracks the Protection Advisor to Level 1 handoff under the approved Level × band business model. It is a review copy, not the live questionnaire, Member intake form or a completed SalCAPA™ assessment.",
        4: "Current-state finding. Draft source questionnaire SPA-PUBLIC-QUESTIONNAIRE-2.3.0 presents nine anonymous common questions in Part 1. After sign-in and consent, Part 2 carries those answers forward and asks 19 more common questions, then records a provisional decision boundary. Earlier 2.2.0 sessions retain their original wording. These changes passed source tests but have not been released to the live Protection Advisor. The live intake and package paths remain locked.",
        6: "Keep Part 1 short, anonymous and educational: nine common questions, applicable conditional prompts, no document upload and clear Not sure, Does not apply and Prefer not to answer choices. Do not assign all-32-capability or five-area numeric ratings from nine answers.",
        7: "Explain the result plainly: these answers may reveal topics to discuss; unasked capabilities remain unassessed. Offer a voluntary Part 2 scope and readiness profile, not an automatic purchase or a claim of verified readiness.",
        8: "Offer two separate choices: discuss a Level 1 SalCAPA™ package or ask about an applicable Salus service. Each needs its own scope, authority and price review.",
        10: "After sign-in and consent, Part 2 completes the common readiness map and asks only for a provisional covered operation, decision units, comparison or group-priority need, decision owner and basic timing. Revenue and investment range remain optional. Detailed files wait until agreement and secure transfer.",
        11: "Proposed covered-operation tags include child care, office, retail or wholesale, warehouse or distribution, manufacturing, agriculture or animal care, property association, construction or field work, health or human services, education, food or events, public or critical infrastructure, and mobile or remote work. The current draft activity list does not fully implement this two-layer classification; it needs an exact field, mapping and Word/web parity review.",
        12: "Treat the selected path as provisional. Salus confirms included and excluded units, predecessor status, Access eligibility, authority, price and schedule in a correctable one-page receipt and later signed agreement. A receipt is not a verified finding, quote or purchase.",
        13: "A qualified Level 1 package is the first paid assessment. A Level 2 package follows a qualified Level 1 for the same boundary; Level 3 follows a qualified Level 2. Separately authorized SalOPS™ implementation can follow a Level 1 finding without buying the next level.",
        20: "Compare this exact Word copy, questionnaire source, Part 1 print, Part 2 screen/PDF/DOCX and scope receipt question by question. Preserve earlier session versions and one governed submission/report identity. Correct mismatches before publication.",
        21: "Test anonymous Part 1, signed-in Part 2 carry-forward and save/resume, optional-field treatment, covered-operation routing, unknown answers, privacy, accessibility and nonexpert comprehension on the exact candidate.",
        22: "Verify the provisional path, eligible $1,500 Level 1A Access terms, quote-pending other paths, four reports, scope exclusions, uncertainty and separate services in every Member-facing format. Do not infer risk or price from revenue, headcount or an operation tag alone.",
        26: "Part 1 provides an anonymous educational screen without uploads. Part 2 provides a consented preliminary scope and readiness profile and a correctable one-page receipt. Salus validates the band, Access eligibility, fee, dates, handling and authorized decision owner in a signed agreement before paid work or document transfer.",
    }
    for index, new in changes.items():
        paragraph = doc.paragraphs[index]
        assert len(paragraph.runs) == 1, (index, len(paragraph.runs))
        paragraph.runs[0].text = new
    # The companion Member request carries the complete first-packet list.
    # Keeping that duplicated paragraph here creates an otherwise empty third
    # page and risks drift between the two controlled copies.
    duplicate = doc.paragraphs[27]
    assert duplicate.text.startswith("The initial Level 1 request is a short organization chart")
    duplicate._element.getparent().remove(duplicate._element)
    doc.save(TARGET)
    print(sha256(TARGET.read_bytes()).hexdigest().upper())


if __name__ == "__main__":
    revise()
