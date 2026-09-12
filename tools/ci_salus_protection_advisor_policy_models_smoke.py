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
