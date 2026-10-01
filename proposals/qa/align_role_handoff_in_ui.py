"""Align existing Part 2 draft, submit, resume and receipt UI role paths."""

from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "public_protection_advisor.py"


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    changes = (
        (
            "decision_authority:decisionAuthority.value,investment_range:investmentRange.value",
            "decision_authority:decisionAuthority.value,records_coordinator_role:recordsCoordinatorRole.value,investment_range:investmentRange.value",
            2,
        ),
        (
            'decision_authority:"decisionAuthority",investment_range:"investmentRange"',
            'decision_authority:"decisionAuthority",records_coordinator_role:"recordsCoordinatorRole",investment_range:"investmentRange"',
            1,
        ),
        (
            "escapeAdvisorHtml(r.decision_owner)+'</p><p><strong>Next:</strong> '",
            "escapeAdvisorHtml(r.decision_owner)+'</p><p><strong>Records coordinator:</strong> '+escapeAdvisorHtml(r.records_coordinator)+'</p><p><strong>Next:</strong> '",
            1,
        ),
    )
    for old, new, count in changes:
        if text.count(new) == count:
            continue
        assert text.count(old) == count, (old[:80], text.count(old))
        text = text.replace(old, new)
    SOURCE.write_text(text, encoding="utf-8", newline="")


if __name__ == "__main__":
    main()
