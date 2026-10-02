"""A provisional band must not turn inconsistent scope answers into a price cue."""

from salus_package_path import suggest_provisional_level_1_path


def test_consistent_scope_answers_support_only_their_own_band():
    cases = (
        ("One", "No", "No", "A"),
        ("Two", "Yes", "No", "B"),
        ("Group", "Not sure", "Yes", "C"),
    )
    for units, separate, group, expected in cases:
        result = suggest_provisional_level_1_path({
            "decision_units": units,
            "separate_findings": separate,
            "group_priorities": group,
        })
        assert result["band"] == expected
        assert result["status"] == "Provisional — Salus scope review required"


def test_conflicting_or_incomplete_scope_answers_require_review():
    cases = (
        ("One", "Yes", "No"),
        ("One", "No", "Yes"),
        ("Two", "No", "No"),
        ("Two", "Yes", "Yes"),
        ("Group", "Yes", "No"),
        ("Not sure", "Yes", "No"),
        ("Not sure", "No", "Yes"),
    )
    for units, separate, group in cases:
        result = suggest_provisional_level_1_path({
            "decision_units": units,
            "separate_findings": separate,
            "group_priorities": group,
        })
        assert result["band"] == ""
        assert result["label"] == "Level 1 band to confirm"
        assert "price" in result["next_step"]
