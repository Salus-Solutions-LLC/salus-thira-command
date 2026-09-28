from public_protection_advisor import _capability_results, _package_recommendation, _result


QUESTIONS = [
    {
        "key": "authority",
        "text": "Is incident authority documented?",
        "domain": "Leadership",
        "capabilities": ["Operational Coordination"],
        "services": ["planning"],
        "weight": 2.0,
    }
]


def test_unknown_is_an_information_gap_and_does_not_generate_service_need():
    answers = {"authority": {"answer_state": "Unknown"}}
    rows, areas = _capability_results(QUESTIONS, answers)
    authority = next(row for row in rows if row["capability"] == "Operational Coordination")
    assert authority["need_score"] is None
    assert authority["information_gap"] is True
    assert areas["Response"] is None
    result = _result(QUESTIONS, answers)
    assert result["priority_capabilities"] == []
    assert result["information_gap_count"] == 1
    package = _package_recommendation(QUESTIONS, answers, {})
    assert package["primary_service"]["level"] == 1
    assert package["services"] == []


def test_reported_need_changes_priority_but_not_first_package():
    answers = {"authority": {"answer_state": "No"}}
    rows, areas = _capability_results(QUESTIONS, answers)
    authority = next(row for row in rows if row["capability"] == "Operational Coordination")
    assert authority["need_score"] == 100
    assert areas["Response"] == 100
    package = _package_recommendation(QUESTIONS, answers, {})
    assert package["primary_service"]["level"] == 1
    assert package["primary_service"]["key"] == "integrated_level_1"
    assert package["services"][0]["key"] == "planning"
    assert "Level 2 if qualified Level 1" in package["sequence"][1]
