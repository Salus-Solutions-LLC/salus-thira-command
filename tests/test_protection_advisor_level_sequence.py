from public_protection_advisor import _capability_results, _package_recommendation, _questions, _result


def test_high_need_still_begins_with_integrated_level_one():
    questions = _questions("Private business")
    answers = {question["key"]: {"answer_state": "No"} for question in questions}
    result = _result(questions, answers)
    package = _package_recommendation(questions, answers, {})

    assert package["primary_service"]["title"] == "Level 1 SalCAPA™ Package"
    assert package["primary_service"]["level"] == 1
    assert package["sequence"][0] == "Level 1 SalCAPA™ package — four coordinated reports"
    assert all(service["level"] >= 1 for service in package["services"])
    assert result["preliminary_hypothesis"]["reported_basis"]
    assert len(result["preliminary_hypothesis"]["checklist"]) == 3


def test_unknown_remains_a_gap_without_inventing_need_or_a_service():
    questions = _questions("Private business")
    answers = {question["key"]: {"answer_state": "Unknown"} for question in questions}
    rows, areas = _capability_results(questions, answers)
    assert all(row["need_score"] is None for row in rows)
    assert all(score is None for score in areas.values())
    result = _result(questions, answers)
    assert result["priority_capabilities"] == []
    assert "cannot be inferred" in result["preliminary_hypothesis"]["working_assumption"]
    package = _package_recommendation(questions, answers, {})
    assert package["primary_service"]["level"] == 1
    assert package["services"] == []
