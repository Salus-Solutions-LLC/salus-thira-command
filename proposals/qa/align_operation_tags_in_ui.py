"""Align the three embedded Part 2 JavaScript record paths with operation tags.

This edits only the draft source candidate. It leaves already issued profile
snapshots and production sessions untouched.
"""

from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "public_protection_advisor.py"


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    changes = (
        (
            "function draftFields(){return {",
            "function selectedOperationTags(){return [...document.querySelectorAll('input[name=\"operationTag\"]:checked')].map(x=>x.value)}\nfunction draftFields(){return {",
        ),
        (
            "annual_revenue_range:revenueRange.value,specific_activities:",
            "annual_revenue_range:revenueRange.value,covered_operation_tags:selectedOperationTags(),specific_activities:",
        ),
        (
            "(d.specific_activities||[]).forEach(v=>{const el=[...document.querySelectorAll('input[name=\"activity\"]')].find(x=>x.value===v);if(el)el.checked=true});syncAdvisorCardChoices()",
            "(d.specific_activities||[]).forEach(v=>{const el=[...document.querySelectorAll('input[name=\"activity\"]')].find(x=>x.value===v);if(el)el.checked=true});document.querySelectorAll('input[name=\"operationTag\"]').forEach(el=>{el.checked=(d.covered_operation_tags||[]).includes(el.value)});syncAdvisorCardChoices()",
        ),
    )
    expected_counts = (1, 2, 1)
    for (old, new), expected in zip(changes, expected_counts):
        if text.count(new) == expected:
            continue
        assert text.count(old) == expected, (old[:80], text.count(old))
        text = text.replace(old, new)
    SOURCE.write_text(text, encoding="utf-8", newline="")


if __name__ == "__main__":
    main()
