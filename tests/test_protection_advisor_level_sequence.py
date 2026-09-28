from public_protection_advisor import _package_recommendation, _questions, _result


def test_high_need_still_begins_with_integrated_level_one():
    questions = _questions("Private business")
    answers = {question["key"]: {"answer_state": "No"} for question in questions}
    result = _result(questions, answers)
    package = _package_recommendation(questions, answers, {})

    assert package["primary_service"]["title"] == "Integrated SalCAPA Assessment"
    assert package["primary_service"]["level"] == 1
    assert package["sequence"][0] == "Integrated SalCAPA Assessment — Level 1"
    assert all(service["level"] == 1 for service in package["services"])
    assert result["preliminary_hypothesis"]["reported_basis"]
    assert len(result["preliminary_hypothesis"]["checklist"]) == 3
