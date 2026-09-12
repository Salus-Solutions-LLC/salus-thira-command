from __future__ import annotations

import json
import os

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
