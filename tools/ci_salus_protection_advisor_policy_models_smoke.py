from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database as database_support
from pydantic import ValidationError

import salus_protection_advisor as advisor


def main() -> None:
    conn = database_support.connect_database()
    try:
        installed = advisor.install_fictional_policy_bundle(
            conn,
            released_by="Fictional Internal Acceptance",
            released_at="2026-09-12T13:00:00Z",
        )
        repeated = advisor.install_fictional_policy_bundle(
            conn,
            released_by="Fictional Internal Acceptance",
            released_at="2026-09-12T13:00:00Z",
        )
        assert installed["content_sha256"] == repeated["content_sha256"]
        assert installed["has_routes"] is False
        assert installed["has_contact_fields"] is False
        assert installed["has_protected_member_access"] is False
        assert installed["creates_binding_event"] is False

        loaded = advisor.load_fictional_policy_bundle(conn)
        assert loaded["content_sha256"] == installed["content_sha256"]
        assert set(loaded["components"]) == set(advisor.POLICY_TABLES)
        assert loaded["data_boundary"] == advisor.DATA_BOUNDARY
        assert loaded["fictional_only"] is True

        notice = advisor.install_fictional_consent_notice(
            conn, released_at="2026-09-12T15:39:00Z"
        )
        repeated_notice = advisor.install_fictional_consent_notice(
            conn, released_at="2026-09-12T15:39:00Z"
        )
        assert notice["content_sha256"] == repeated_notice["content_sha256"]
        assert notice["notice_version"] == advisor.CONSENT_NOTICE_VERSION
        assert notice["authorized_fields"] == list(advisor.CONSENTED_FIELDS)
        assert notice["retention_days"] == 30
        assert all(notice[flag] is False for flag in (
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release", "has_routes",
        ))
        loaded_notice = advisor.load_fictional_consent_notice(conn)
        assert loaded_notice["content_sha256"] == notice["content_sha256"]
        assert "@example.com" not in json.dumps(loaded_notice).casefold()

        for kind, table in advisor.POLICY_TABLES.items():
            rows = list(conn.execute(f"SELECT * FROM {table}"))
            assert len(rows) == 1, (kind, len(rows))
            row = rows[0]
            assert row["status"] == advisor.POLICY_STATUS
            assert row["data_boundary"] == advisor.DATA_BOUNDARY
            assert int(row["fictional_only"]) == 1
            assert advisor.content_sha256(row["snapshot_json"]) == row["content_sha256"]
            columns = {column["name"] for column in conn.execute(f"PRAGMA table_info({table})")}
            assert "tenant_id" not in columns
            assert not any(name.startswith("contact") for name in columns)
            assert "protected_member_id" not in columns

        bundle_rows = list(conn.execute("SELECT * FROM advisor_policy_bundles"))
        assert len(bundle_rows) == 1
        assert advisor.content_sha256(bundle_rows[0]["snapshot_json"]) == bundle_rows[0]["content_sha256"]

        definitions = {item.policy_kind: item for item in advisor.policy_definitions()}
        questionnaire = definitions["Questionnaire"].payload
        assert questionnaire["contact_requested_only_for_save_or_submit"] is True
        assert questionnaire["branching_rule"].startswith("Only explicitly displayed")
        assert {state for state in questionnaire["answer_states"]} == {
            "Answered", "Unknown", "Declined", "Not Applicable"
        }
        question_dimensions = {
            dimension
            for question in questionnaire["questions"]
            for dimension in question["dimension_links"]
        }
        assert question_dimensions == set(advisor.DIMENSIONS)

        recommendation = definitions["Recommendation Policy"].payload
        assert [item["name"] for item in recommendation["dimensions"]] == list(advisor.DIMENSIONS)
        assert recommendation["capability_areas"] == list(advisor.CAPABILITY_AREAS)
        assert recommendation["investigation_level_mapping"] == advisor.INVESTIGATION_LEVELS
        assert recommendation["size_only_decision_prohibited"] is True
        assert recommendation["hidden_answer_scoring_prohibited"] is True
        assert recommendation["binding_effect"] is False
        assert recommendation["creates_charge"] is False
        assert recommendation["creates_contract"] is False
        assert recommendation["creates_membership"] is False
        assert recommendation["creates_protected_member"] is False

        catalogue = definitions["Package Catalogue"].payload
        packages = catalogue["packages"]
        assert len(packages) == 4
        assert len({item["package_key"] for item in packages}) == len(packages)
        assert all(item["includes"] and item["excludes"] and item["capacity_ceiling"] for item in packages)
        assert "Organization size alone never selects a package." in catalogue["selection_principles"]

        price_policy = definitions["Public Price Policy"].payload
        assert price_policy["range_rules"]["rounded_values_only"] is True
        assert price_policy["range_rules"]["single_exact_price_prohibited"] is True
        assert price_policy["qualified_salus_review_required"] is True
        assert price_policy["commercial_events_created"] == []
        assert set(price_policy["forbidden_public_fields"]) == set(advisor.FORBIDDEN_PUBLIC_FIELDS)

        fixtures = advisor.fictional_cases()
        assert len(fixtures) == 4
        assert len({case["case_key"] for case in fixtures}) == 4
        assert all("Fictional" in case["display_name"] for case in fixtures)
        assert {case["answers"]["organization_type"] for case in fixtures} == {
            "Small Business", "Multi-location Business", "Critical Infrastructure", "Public Agency"
        }
        assert {case["answers"]["investigation_depth"] for case in fixtures} == set(advisor.INVESTIGATION_LEVELS)
        assert any(case["answers"]["locations"] == 1 for case in fixtures)
        assert any(case["answers"]["locations"] > 100 for case in fixtures)
        fixtures[0]["display_name"] = "Changed locally"
        assert advisor.fictional_cases()[0]["display_name"].startswith("Fictional")

        safe = {
            "currency": "USD",
            "range_minimum": 1000,
            "range_maximum": 2000,
            "cadence": "One-time",
            "assumptions": ["Fictional internal acceptance"],
            "preliminary_notice": "Qualified Salus review is required.",
        }
        advisor.assert_safe_public_projection(safe)
        assert advisor.public_projection_violations(
            {"range_minimum": 1000, "internal_cost": 500, "detail": {"margin": "hidden"}}
        ) == ["internal_cost", "margin"]
        try:
            advisor.assert_safe_public_projection({"role_rate": 100})
        except ValueError:
            pass
        else:
            raise AssertionError("internal pricing field was not rejected")

        try:
            advisor.AdvisorPolicyDefinition(
                policy_kind="Questionnaire",
                version_key="SPA-QUESTIONNAIRE-2.0.0",
                effective_date="12 September 2026",
                authority="Fictional test",
                payload={},
                unexpected=True,
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("unexpected policy fields were not rejected")

        evaluations = advisor.prepare_all_fictional_evaluations(
            conn, created_at="2026-09-12T13:35:00Z"
        )
        repeated_evaluations = advisor.prepare_all_fictional_evaluations(
            conn, created_at="2026-09-12T13:36:00Z"
        )
        assert [item["content_sha256"] for item in evaluations] == [
            item["content_sha256"] for item in repeated_evaluations
        ]
        assert len(evaluations) == 4
        assert len({item["evaluation_key"] for item in evaluations}) == 4
        expected_packages = {
            "SPA-FICTIONAL-JUNIPER-TABLE": "SPA-PKG-FOUNDATION",
            "SPA-FICTIONAL-MERIDIAN-REGIONAL": "SPA-PKG-INTEGRATED",
            "SPA-FICTIONAL-HARBORLIGHT-UTILITY": "SPA-PKG-COMPLEX-MISSION",
            "SPA-FICTIONAL-SUMMIT-METRO": "SPA-PKG-COMPLEX-MISSION",
        }
        fixture_answers = {case["case_key"]: set(case["answers"]) for case in advisor.fictional_cases()}
        for evaluation in evaluations:
            case_key = evaluation["case"]["case_key"]
            assert evaluation["status"] == advisor.EVALUATION_STATUS
            assert evaluation["fictional_only"] is True
            assert evaluation["preliminary"] is True
            assert evaluation["data_boundary"] == advisor.DATA_BOUNDARY
            assert evaluation["adapter_version"] == advisor.EVALUATION_ADAPTER_VERSION
            assert evaluation["policy_bundle_sha256"] == installed["content_sha256"]
            assert len(evaluation["commercial_estimate_snapshot_sha256"]) == 64
            assert len(evaluation["rate_card_snapshot_sha256"]) == 64
            assert set(evaluation["dimensions"]) == set(advisor.DIMENSIONS)
            assert evaluation["recommended_package"]["package_key"] == expected_packages[case_key]
            assert evaluation["authority"].startswith("A qualified Salus reviewer")
            assert all(evaluation[flag] is False for flag in (
                "creates_charge", "creates_contract", "creates_membership",
                "creates_protected_member", "creates_disclosure", "has_routes",
            ))
            advisor.assert_safe_public_projection(evaluation["public_price"])
            assert evaluation["public_price"]["one_time_range_minimum"] <= evaluation["public_price"]["one_time_range_maximum"]
            assert evaluation["public_price"]["recurring_range_minimum"] <= evaluation["public_price"]["recurring_range_maximum"]
            for review in evaluation["dimensions"].values():
                assert review["classification"] == "Preliminary Inference"
                assert review["state"] in {
                    "Evidence Needed", "Limited Indication",
                    "Developing Indication", "Material Indication",
                }
                assert set(review["basis_question_keys"]) <= fixture_answers[case_key]
                assert set(review["reported_information"]) == set(review["basis_question_keys"])
                assert review["uncertainty"]

            loaded_evaluation = advisor.load_fictional_evaluation(
                conn, evaluation["evaluation_key"]
            )
            assert loaded_evaluation["content_sha256"] == evaluation["content_sha256"]

        evaluation_rows = list(conn.execute("SELECT * FROM advisor_fictional_evaluation_snapshots"))
        assert len(evaluation_rows) == 4
        evaluation_columns = {
            column["name"]
            for column in conn.execute("PRAGMA table_info(advisor_fictional_evaluation_snapshots)")
        }
        assert "tenant_id" not in evaluation_columns
        assert "protected_member_id" not in evaluation_columns
        assert not any(name.startswith("contact") for name in evaluation_columns)
        evaluation_serialized = json.dumps(evaluations).casefold()
        for forbidden in (
            "tenant_id", "protected_member_id", "contact_email", "payment",
            "invoice", "internal_cost", "role_rate", "margin",
        ):
            assert forbidden not in evaluation_serialized

        evaluation_session = advisor.start_fictional_session(
            conn,
            "SPA-FICTIONAL-JUNIPER-TABLE",
            created_at="2026-09-12T15:20:00Z",
        )
        evaluation_token = evaluation_session["session_token"]
        required_submissions = (
            ("organization_type", "Answered", "Small Business"),
            ("mission", "Unknown", None),
            ("locations", "Answered", 1),
            ("jurisdictions", "Answered", 1),
            ("people_exposed", "Answered", "Under 100"),
            ("capability_posture", "Answered", "Mixed and partly documented"),
            (
                "reported_concerns",
                "Answered",
                ["Severe weather", "Utility interruption", "Workplace violence"],
            ),
            ("recent_change", "Answered", "No"),
            ("investigation_depth", "Answered", "Initial Pass"),
        )
        for offset, (question_key, answer_state, value) in enumerate(required_submissions, start=1):
            advisor.append_fictional_answer_revision(
                conn,
                evaluation_token,
                advisor.FictionalAnswerSubmission(
                    question_key=question_key,
                    answer_state=answer_state,
                    value=value,
                ),
                created_at=f"2026-09-12T15:{20 + offset:02d}:00Z",
            )
        session_evaluation = advisor.prepare_session_fictional_evaluation(
            conn, evaluation_token, created_at="2026-09-12T15:35:00Z"
        )
        repeated_session_evaluation = advisor.prepare_session_fictional_evaluation(
            conn, evaluation_token, created_at="2026-09-12T15:36:00Z"
        )
        assert session_evaluation["content_sha256"] == repeated_session_evaluation["content_sha256"]
        assert session_evaluation["answer_revision"] == len(required_submissions)
        assert session_evaluation["recommended_package"]["package_key"] == "SPA-PKG-FOUNDATION"
        assert session_evaluation["recommended_investigation_depth"] == "Initial Pass"
        assert session_evaluation["preliminary"] is True
        assert session_evaluation["answer_states"]["mission"]["answer_state"] == "Unknown"
        assert session_evaluation["dimensions"]["Consequence"]["basis_answer_revision_keys"]
        assert session_evaluation["dimensions"]["Consequence"]["explicit_non_answer_states"]["mission"] == "Unknown"
        assert len(session_evaluation["governing_versions"]) == 4

        loaded_session_evaluation = advisor.load_session_fictional_evaluation(
            conn, session_evaluation["evaluation_key"]
        )
        assert loaded_session_evaluation["content_sha256"] == session_evaluation["content_sha256"]
        recommendation = advisor.retrieve_session_fictional_recommendation(
            conn,
            evaluation_token,
            session_evaluation["evaluation_key"],
            as_of="2026-09-12T15:36:30Z",
        )
        assert recommendation["result_heading"] == "Your Salus Recommendation"
        assert recommendation["primary_package"]["package_key"] == "SPA-PKG-FOUNDATION"
        assert recommendation["recommended_investigation_depth"] == "Initial Pass"
        assert recommendation["preliminary"] is True
        assert recommendation["fictional_only"] is True
        assert recommendation["may_stop"] is True
        assert recommendation["may_revise"] is True
        assert recommendation["may_save_or_submit"] is True
        assert recommendation["save_or_submit_notice"].startswith(
            "Fictional contact details are requested only"
        )
        assert all(recommendation[flag] is False for flag in (
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure", "has_routes",
        ))
        advisor.assert_safe_public_projection(recommendation)
        recommendation_text = json.dumps(recommendation).casefold()
        for hidden in (
            "session_key", "session_token", "rate_card_snapshot_sha256",
            "internal_cost", "role_rate", "margin", "tenant_id",
            "protected_member_id", "contact_email",
        ):
            assert hidden not in recommendation_text

        advisor.append_fictional_answer_revision(
            conn,
            evaluation_token,
            advisor.FictionalAnswerSubmission(
                question_key="recent_change",
                answer_state="Unknown",
            ),
            created_at="2026-09-12T15:37:00Z",
        )
        try:
            advisor.retrieve_session_fictional_recommendation(
                conn,
                evaluation_token,
                session_evaluation["evaluation_key"],
                as_of="2026-09-12T15:37:30Z",
            )
        except advisor.PolicyIntegrityError:
            pass
        else:
            raise AssertionError("a stale session recommendation remained current")
        revised_evaluation = advisor.prepare_session_fictional_evaluation(
            conn, evaluation_token, created_at="2026-09-12T15:38:00Z"
        )
        assert revised_evaluation["evaluation_key"] != session_evaluation["evaluation_key"]
        revised_recommendation = advisor.retrieve_session_fictional_recommendation(
            conn,
            evaluation_token,
            revised_evaluation["evaluation_key"],
            as_of="2026-09-12T15:38:30Z",
        )
        assert revised_recommendation["dimensions"]["Urgency"]["explicit_non_answer_states"]["recent_change"] == "Unknown"

        contacts = advisor.fictional_prospect_contacts()
        juniper_contact = contacts["SPA-FICTIONAL-JUNIPER-TABLE"]
        submission = advisor.FictionalProspectSubmission(
            action="Submit for Salus Review",
            affirmative_consent=True,
            notice_version=advisor.CONSENT_NOTICE_VERSION,
            authorized_fields=advisor.CONSENTED_FIELDS,
            **juniper_contact,
        )
        prospect_result = advisor.record_fictional_consent_and_prospect(
            conn,
            evaluation_token,
            revised_evaluation["evaluation_key"],
            submission,
            consented_at="2026-09-12T15:40:00Z",
        )
        assert prospect_result["status"] == "Submitted — Fictional; Awaiting Salus Review"
        assert prospect_result["awaiting_salus_review"] is True
        assert prospect_result["created_display"] == "12 September 2026 15:40 UTC"
        assert all(prospect_result[flag] is False for flag in (
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release",
        ))
        consent = advisor.load_fictional_consent(conn, prospect_result["consent_key"])
        assert consent["evaluation_key"] == revised_evaluation["evaluation_key"]
        assert consent["affirmative_consent"] is True
        assert consent["authorized_fields"] == list(advisor.CONSENTED_FIELDS)
        consent_text = json.dumps(consent).casefold()
        assert juniper_contact["contact_email"] not in consent_text
        assert juniper_contact["contact_name"].casefold() not in consent_text

        prospect = advisor.load_fictional_prospect(conn, prospect_result["prospect_key"])
        assert prospect["contact_email"].endswith("@example.com")
        assert prospect["contact_name"].startswith("Fictional ")
        assert prospect["classification"] == "Fictional Prospect-Reported Information"
        assert prospect["recommendation"]["may_save_or_submit"] is True
        assert prospect["recommendation"]["evaluation_key"] == revised_evaluation["evaluation_key"]
        assert all(prospect[flag] is False for flag in (
            "creates_charge", "creates_contract", "creates_membership",
            "creates_protected_member", "creates_disclosure",
            "authorizes_customer_release",
        ))
        advisor.assert_safe_public_projection(prospect["recommendation"])
        assert list(conn.execute(
            "SELECT * FROM advisor_answer_revisions WHERE session_key=?",
            (evaluation_session["session_key"],),
        )) == []
        try:
            advisor.load_fictional_session(
                conn, evaluation_token, as_of="2026-09-12T15:40:01Z"
            )
        except advisor.SessionAccessError:
            pass
        else:
            raise AssertionError("submitted prospect token remained active")
        try:
            advisor.record_fictional_consent_and_prospect(
                conn,
                evaluation_token,
                revised_evaluation["evaluation_key"],
                submission,
                consented_at="2026-09-12T15:40:01Z",
            )
        except advisor.SessionAccessError:
            pass
        else:
            raise AssertionError("fictional prospect submission was replayable")

        submitted_audit = advisor.verify_fictional_session_audit(
            conn, evaluation_session["session_key"]
        )
        assert submitted_audit[-1]["event_type"] == "Prospect Submitted"
        assert submitted_audit[-1]["contains_answer_content"] is False
        assert submitted_audit[-1]["contains_contact_information"] is False
        assert juniper_contact["contact_email"] not in json.dumps(submitted_audit).casefold()

        consent_row = conn.execute(
            "SELECT snapshot_json FROM advisor_consents WHERE consent_key=?",
            (prospect_result["consent_key"],),
        ).fetchone()
        assert juniper_contact["contact_email"] not in consent_row["snapshot_json"].casefold()

        conn.execute(
            "UPDATE advisor_consents SET snapshot_json=? WHERE consent_key=?",
            ("{}", prospect_result["consent_key"]),
        )
        try:
            advisor.load_fictional_consent(conn, prospect_result["consent_key"])
        except advisor.PolicyIntegrityError:
            pass
        else:
            raise AssertionError("tampered fictional consent was accepted")
        finally:
            conn.rollback()
        assert advisor.load_fictional_consent(
            conn, prospect_result["consent_key"]
        )["consent_key"] == prospect_result["consent_key"]

        conn.execute(
            "UPDATE advisor_prospects SET payload_json=? WHERE prospect_key=?",
            ("{}", prospect_result["prospect_key"]),
        )
        try:
            advisor.load_fictional_prospect(conn, prospect_result["prospect_key"])
        except advisor.PolicyIntegrityError:
            pass
        else:
            raise AssertionError("tampered fictional prospect was accepted")
        finally:
            conn.rollback()
        assert advisor.load_fictional_prospect(
            conn, prospect_result["prospect_key"]
        )["prospect_key"] == prospect_result["prospect_key"]

        for invalid in (
            {
                "action": "Submit for Salus Review",
                "affirmative_consent": False,
                "notice_version": advisor.CONSENT_NOTICE_VERSION,
                "authorized_fields": advisor.CONSENTED_FIELDS,
                **juniper_contact,
            },
            {
                "action": "Submit for Salus Review",
                "affirmative_consent": True,
                "notice_version": advisor.CONSENT_NOTICE_VERSION,
                "authorized_fields": ("contact_email",),
                **juniper_contact,
            },
            {
                "action": "Submit for Salus Review",
                "affirmative_consent": True,
                "notice_version": advisor.CONSENT_NOTICE_VERSION,
                "authorized_fields": advisor.CONSENTED_FIELDS,
                "organization_display_name": "Actual Organization",
                "contact_name": "Actual Person",
                "contact_email": "actual@real-domain.test",
            },
        ):
            try:
                advisor.FictionalProspectSubmission(**invalid)
            except ValidationError:
                pass
            else:
                raise AssertionError("invalid fictional consent submission was accepted")

        for table in (
            "advisor_consent_notice_versions", "advisor_consents", "advisor_prospects",
        ):
            columns = {
                column["name"] for column in conn.execute(f"PRAGMA table_info({table})")
            }
            assert "tenant_id" not in columns
            assert "protected_member_id" not in columns
            assert "payment" not in columns
            assert "credential" not in columns

        incomplete_session = advisor.start_fictional_session(
            conn,
            "SPA-FICTIONAL-MERIDIAN-REGIONAL",
            created_at="2026-09-12T15:20:00Z",
        )
        try:
            advisor.prepare_session_fictional_evaluation(
                conn,
                incomplete_session["session_token"],
                created_at="2026-09-12T15:21:00Z",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("missing required answer states did not fail closed")
        try:
            advisor.retrieve_session_fictional_recommendation(
                conn,
                incomplete_session["session_token"],
                revised_evaluation["evaluation_key"],
                as_of="2026-09-12T15:39:00Z",
            )
        except advisor.SessionAccessError:
            pass
        else:
            raise AssertionError("another fictional session retrieved the recommendation")

        session_evaluation_rows = list(conn.execute(
            "SELECT * FROM advisor_session_evaluation_snapshots"
        ))
        assert len(session_evaluation_rows) == 2
        session_evaluation_columns = {
            column["name"]
            for column in conn.execute(
                "PRAGMA table_info(advisor_session_evaluation_snapshots)"
            )
        }
        assert "tenant_id" not in session_evaluation_columns
        assert "protected_member_id" not in session_evaluation_columns
        assert not any(name.startswith("contact") for name in session_evaluation_columns)

        tampered_session_evaluation_key = revised_evaluation["evaluation_key"]
        conn.execute(
            "UPDATE advisor_session_evaluation_snapshots SET snapshot_json=? WHERE evaluation_key=?",
            ("{}", tampered_session_evaluation_key),
        )
        try:
            advisor.load_session_fictional_evaluation(
                conn, tampered_session_evaluation_key
            )
        except advisor.PolicyIntegrityError:
            pass
        else:
            raise AssertionError("tampered session evaluation was accepted")
        finally:
            conn.rollback()
        assert advisor.load_session_fictional_evaluation(
            conn, tampered_session_evaluation_key
        )["evaluation_key"] == tampered_session_evaluation_key

        session = advisor.start_fictional_session(
            conn,
            "SPA-FICTIONAL-JUNIPER-TABLE",
            created_at="2026-09-12T15:00:00Z",
        )
        assert len(session["session_token"]) >= 40
        assert session["status"] == "Active"
        assert session["fictional_only"] is True
        assert session["contact_information_required"] is False
        assert session["has_protected_member_access"] is False
        assert session["expires_at"] == "2026-09-12T17:00:00Z"
        token = session["session_token"]
        session_row = conn.execute(
            "SELECT * FROM advisor_sessions WHERE session_key=?",
            (session["session_key"],),
        ).fetchone()
        assert session_row["current_token_sha256"] == advisor.content_sha256(token)
        assert session_row["current_token_sha256"] != token
        assert advisor.load_fictional_session(
            conn, token, as_of="2026-09-12T15:01:00Z"
        )["latest_answer_revision"] == 0

        answer_one = advisor.append_fictional_answer_revision(
            conn,
            token,
            advisor.FictionalAnswerSubmission(
                question_key="organization_type",
                answer_state="Answered",
                value="Small Business",
            ),
            created_at="2026-09-12T15:02:00Z",
        )
        assert answer_one["classification"] == "Prospect-Reported Fictional Information"
        advisor.append_fictional_answer_revision(
            conn,
            token,
            advisor.FictionalAnswerSubmission(
                question_key="mission",
                answer_state="Unknown",
            ),
            created_at="2026-09-12T15:03:00Z",
        )
        advisor.append_fictional_answer_revision(
            conn,
            token,
            advisor.FictionalAnswerSubmission(
                question_key="organization_type",
                answer_state="Unknown",
            ),
            created_at="2026-09-12T15:04:00Z",
        )
        advisor.append_fictional_answer_revision(
            conn,
            token,
            advisor.FictionalAnswerSubmission(
                question_key="organization_type",
                answer_state="Answered",
                value="Small Business",
            ),
            created_at="2026-09-12T15:05:00Z",
        )
        current_answers = advisor.current_fictional_answers(
            conn, token, as_of="2026-09-12T15:06:00Z"
        )
        assert current_answers["organization_type"]["answer_state"] == "Answered"
        assert current_answers["organization_type"]["value"] == "Small Business"
        assert current_answers["organization_type"]["revision_number"] == 4
        assert current_answers["mission"]["answer_state"] == "Unknown"
        assert current_answers["mission"]["value"] is None
        revision_rows = list(conn.execute(
            "SELECT * FROM advisor_answer_revisions WHERE session_key=?",
            (session["session_key"],),
        ))
        assert len(revision_rows) == 4
        assert {int(row["revision_number"]) for row in revision_rows} == {1, 2, 3, 4}

        try:
            advisor.append_fictional_answer_revision(
                conn,
                token,
                advisor.FictionalAnswerSubmission(
                    question_key="organization_type",
                    answer_state="Answered",
                    value="Public Agency",
                ),
                created_at="2026-09-12T15:07:00Z",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("non-fixture answer content was accepted")

        try:
            advisor.FictionalAnswerSubmission(
                question_key="mission",
                answer_state="Unknown",
                value="hidden value",
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("a non-answered state retained a value")

        rotated = advisor.rotate_fictional_session(
            conn, token, rotated_at="2026-09-12T15:10:00Z"
        )
        rotated_token = rotated["session_token"]
        assert rotated_token != token
        assert rotated["session_key"] == session["session_key"]
        try:
            advisor.load_fictional_session(
                conn, token, as_of="2026-09-12T15:11:00Z"
            )
        except advisor.SessionAccessError:
            pass
        else:
            raise AssertionError("superseded session token was replayed")
        assert advisor.load_fictional_session(
            conn, rotated_token, as_of="2026-09-12T15:11:00Z"
        )["latest_answer_revision"] == 4

        deleted = advisor.delete_fictional_session(
            conn, rotated_token, deleted_at="2026-09-12T15:12:00Z"
        )
        assert deleted["status"] == "Deleted"
        assert deleted["answer_content_deleted"] is True
        assert deleted["contact_information_retained"] is False
        assert deleted["protected_member_record_created"] is False
        assert list(conn.execute(
            "SELECT * FROM advisor_answer_revisions WHERE session_key=?",
            (session["session_key"],),
        )) == []
        try:
            advisor.load_fictional_session(
                conn, rotated_token, as_of="2026-09-12T15:13:00Z"
            )
        except advisor.SessionAccessError:
            pass
        else:
            raise AssertionError("deleted session remained accessible")

        expiring = advisor.start_fictional_session(
            conn,
            "SPA-FICTIONAL-MERIDIAN-REGIONAL",
            created_at="2026-09-12T15:00:00Z",
        )
        advisor.append_fictional_answer_revision(
            conn,
            expiring["session_token"],
            advisor.FictionalAnswerSubmission(
                question_key="organization_type",
                answer_state="Answered",
                value="Multi-location Business",
            ),
            created_at="2026-09-12T15:01:00Z",
        )
        expired_keys = advisor.expire_fictional_sessions(
            conn, as_of="2026-09-12T17:00:00Z"
        )
        assert expired_keys == [expiring["session_key"]]
        assert list(conn.execute(
            "SELECT * FROM advisor_answer_revisions WHERE session_key=?",
            (expiring["session_key"],),
        )) == []
        try:
            advisor.load_fictional_session(
                conn, expiring["session_token"], as_of="2026-09-12T17:01:00Z"
            )
        except advisor.SessionAccessError:
            pass
        else:
            raise AssertionError("expired session remained accessible")

        for session_key in (session["session_key"], expiring["session_key"]):
            audit = advisor.verify_fictional_session_audit(conn, session_key)
            assert audit
            assert all(event["contains_answer_content"] is False for event in audit)
            assert all(event["contains_contact_information"] is False for event in audit)
            assert all(event["creates_protected_member"] is False for event in audit)
        assert advisor.verify_fictional_session_audit(
            conn, session["session_key"]
        )[-1]["event_type"] == "Session Deleted"
        assert advisor.verify_fictional_session_audit(
            conn, expiring["session_key"]
        )[-1]["event_type"] == "Session Expired"

        lifecycle_tables = (
            "advisor_sessions", "advisor_session_tokens",
            "advisor_answer_revisions", "advisor_audit_events",
        )
        for table in lifecycle_tables:
            columns = {
                column["name"] for column in conn.execute(f"PRAGMA table_info({table})")
            }
            assert "tenant_id" not in columns
            assert "protected_member_id" not in columns
            assert not any(name.startswith("contact") for name in columns)
        token_rows = list(conn.execute("SELECT token_sha256 FROM advisor_session_tokens"))
        assert token_rows
        assert all(row["token_sha256"] not in {token, rotated_token, expiring["session_token"]} for row in token_rows)

        try:
            advisor.start_fictional_session(
                conn,
                "SPA-FICTIONAL-NOT-RELEASED",
                created_at="2026-09-12T15:00:00Z",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("unreleased fictional session case was accepted")
        try:
            advisor.start_fictional_session(
                conn,
                "SPA-FICTIONAL-JUNIPER-TABLE",
                created_at="2026-09-12 15:00:00",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("timezone-free lifecycle time was accepted")

        exposure_low = {dimension: 0 for dimension in advisor.DIMENSIONS}
        exposure_high = dict(exposure_low)
        exposure_low["Exposure"] = 1
        exposure_high["Exposure"] = 3
        assert advisor._select_package(exposure_low, "Initial Pass") == "SPA-PKG-FOUNDATION"
        assert advisor._select_package(exposure_high, "Initial Pass") == "SPA-PKG-FOUNDATION"

        try:
            advisor.prepare_fictional_evaluation(
                conn, "SPA-FICTIONAL-NOT-RELEASED", created_at="2026-09-12T13:35:00Z"
            )
        except ValueError:
            pass
        else:
            raise AssertionError("an ungoverned fictional case was accepted")

        try:
            advisor.FictionalCommercialCandidate(
                package_key="SPA-PKG-FOUNDATION",
                commercial_estimate_snapshot_sha256="a" * 64,
                rate_card_snapshot_sha256="b" * 64,
                one_time_range_minimum=2000,
                one_time_range_maximum=1000,
                recurring_range_minimum=0,
                recurring_range_maximum=0,
                recurring_cadence="Annual",
                implementation_period="Fictional",
                assumptions=("Fictional",),
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("invalid commercial range was accepted")

        tampered_key = evaluations[0]["evaluation_key"]
        conn.execute(
            "UPDATE advisor_fictional_evaluation_snapshots SET snapshot_json=? WHERE evaluation_key=?",
            ("{}", tampered_key),
        )
        try:
            advisor.load_fictional_evaluation(conn, tampered_key)
        except advisor.PolicyIntegrityError:
            pass
        else:
            raise AssertionError("tampered fictional evaluation was accepted")
        finally:
            conn.rollback()
        assert advisor.load_fictional_evaluation(conn, tampered_key)["evaluation_key"] == tampered_key

        collision = advisor.AdvisorPolicyDefinition(
            policy_kind="Questionnaire",
            version_key="SPA-QUESTIONNAIRE-1.0.0",
            effective_date="12 September 2026",
            authority="Fictional conflicting authority",
            payload={"conflict": True},
        )
        try:
            advisor._insert_immutable_snapshot(
                conn, collision, "Fictional Internal Acceptance", "2026-09-12T13:00:00Z"
            )
        except advisor.PolicyIntegrityError:
            pass
        else:
            raise AssertionError("immutable policy version collision was not rejected")

        serialized = json.dumps(loaded).casefold()
        for forbidden in ("tenant_id", "protected_member_id", "contact_email", "payment", "invoice"):
            assert forbidden not in serialized
        assert os.environ.get("SALUS_AUTH_MODE", "prototype") in {"prototype", "entra", "production", "disabled"}
    finally:
        conn.close()

    print("SALUS_PROTECTION_ADVISOR_POLICY_MODELS_PASS")


if __name__ == "__main__":
    main()
