from public_protection_advisor import _capability_results, _package_recommendation, _part2_questions, _questions, _result


def test_high_need_still_begins_with_integrated_level_one_a():
    questions = _questions("Private business")
    answers = {question["key"]: {"answer_state": "No"} for question in questions}
    result = _result(questions, answers)
    package = _package_recommendation(questions, answers, {})

    assert package["primary_service"]["title"] == "Level 1A SalCAPA™ Package"
    assert package["primary_service"]["level"] == 1
    assert package["sequence"][0] == "Level 1A first — four coordinated reports for one named unit"
    assert "Level 1B/C only after qualified Level 1A" in package["sequence"][1]
    assert "Level 1A first" in package["notice"]
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


def test_short_public_screen_does_not_invent_capability_scores():
    questions = _questions("Business")
    assert len(questions) == 9
    answers = {question["key"]: {"answer_state": "No"} for question in questions}
    rows, areas = _capability_results(questions, answers)
    assert len(rows) == 32
    assert all(row["need_score"] is None and row["information_gap"] for row in rows)
    assert all(score is None for score in areas.values())
    result = _result(questions, answers)
    assert result["attention_count"] == 9
    assert result["priority_capabilities"] == []


def test_sector_prompts_follow_consent_and_do_not_lengthen_anonymous_part_one():
    for org_type, sector_keys in (
        ("Faith-Based Organization", {"volunteer_roles", "public_access"}),
        ("School or Educational Institution", {"reunification", "public_access"}),
        ("Government or Public Institution", {"public_access"}),
        ("Event Venue or Hospitality", {"public_access"}),
    ):
        first = _questions(org_type)
        second = _part2_questions(org_type)
        assert len(first) == 9
        assert not sector_keys.intersection({question["key"] for question in first})
        assert all(question["part2_new"] for question in second if question["key"] in sector_keys)


def test_old_questionnaire_session_keeps_its_original_questions():
    questions = _questions("Business", "SPA-PUBLIC-QUESTIONNAIRE-2.2.0")
    assert len(questions) == 28
    assert questions[0]["text"].startswith("Do you maintain a current list")


def test_consented_second_part_completes_framework_without_reasking_first_part():
    first = _questions("Business")
    second = _part2_questions("Business")
    assert len(first) == 9
    assert len(second) == 28
    assert {q["key"] for q in first} <= {q["key"] for q in second}
    assert all(next(q for q in second if q["key"] == item["key"])["text"] == item["text"] for item in first)
    answers = {q["key"]: {"answer_state": "Unknown"} for q in second}
    answers[second[0]["key"]] = {"answer_state": "No"}
    rows, areas = _capability_results(second, answers)
    assert len(rows) == 32
    assert any(row["need_score"] is not None for row in rows)
    assert set(areas) == {"Prevention", "Protection", "Mitigation", "Response", "Recovery"}
