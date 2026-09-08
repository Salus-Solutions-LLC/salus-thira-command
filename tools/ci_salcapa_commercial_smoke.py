#!/usr/bin/env python3
"""Acceptance checks for Issue #154 estimates, actuals, forecasts, and reporting."""
import copy
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "commercial.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime
from salcapa_commercial import DEFAULT_RULES


def main() -> None:
    client = TestClient(salcapa_runtime.app)
    director = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Commercial Planner", "X-Salus-Clearance": "Highly Sensitive",
    }
    administrator = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "System Administrator",
        "X-Salus-User": "Commercial Approver", "X-Salus-Clearance": "Highly Sensitive",
    }
    member = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
        "X-Salus-User": "Protected Member", "X-Salus-Clearance": "Standard",
    }
    other = {
        "X-Salus-Tenant": "2", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Other Tenant", "X-Salus-Clearance": "Highly Sensitive",
    }

    assert client.get("/api/system/mode").json()["version"] == "3.85"
    assert client.get("/api/salcapa/commercial/catalog", headers=member).status_code == 403
    catalog = client.get("/api/salcapa/commercial/catalog", headers=director)
    assert catalog.status_code == 200, catalog.text
    body = catalog.json()
    assert body["initial_planning_defaults"]["loaded_labor_cost_cents_per_hour"] == 9000
    assert body["initial_planning_defaults"]["technology_planning_allowance_cents"]["Tier 1"] == 400
    assert body["guidance"]["consequence"].startswith("A recommendation is not a charge")
    assert body["guidance"]["actual_cost_truth"].startswith("When actual provider")
    assert body["rate_override_precedence"] == [
        "Product Line", "Investigative Domain", "Tier", "Monitoring Service",
        "Protected Member", "Engagement",
    ]
    assert "Monthly" in body["monitoring_services"]
    assert body["management_report_groups"] == [
        "Product Line", "Investigative Domain", "Tier", "Engagement", "Pricing Method",
    ]
    assert body["guidance"]["report_purpose"].startswith("Review current approved")
    assert "not financial statements" in body["guidance"]["report_uncertainty"]

    forged = client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "Forged card", "status": "Approved", "rules": DEFAULT_RULES,
    })
    assert forged.status_code == 422
    created = client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "Fictional demonstration planning defaults", "effective_from": "2026-09-08",
        "rules": DEFAULT_RULES,
    })
    assert created.status_code == 200, created.text
    card = created.json()
    card_id = card["id"]
    assert card["status"] == "Draft" and card["version_no"] == 1
    assert len(card["content_sha256"]) == 64
    assert client.post(
        f"/api/salcapa/commercial/rate-cards/{card_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit governed assumptions for independent review."},
    ).status_code == 200
    same_actor = client.post(
        f"/api/salcapa/commercial/rate-cards/{card_id}/transition", headers=director,
        json={"status": "Approved", "reason": "Attempt self-approval."},
    )
    assert same_actor.status_code == 409
    approved = client.post(
        f"/api/salcapa/commercial/rate-cards/{card_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Independent review confirms bounded planning defaults."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "Approved"
    assert client.get("/api/salcapa/commercial/rate-cards", headers=member).status_code == 403

    invalid_override_rules = copy.deepcopy(DEFAULT_RULES)
    invalid_override_rules["rate_overrides"] = [{
        "name": "Unsupported field", "scope_level": "Product Line",
        "selector": {"product_line": "SalINTEL Investigation"},
        "values": {"customer_price_cents": 1}, "reason": "Unsupported direct price control.",
    }]
    assert client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "Invalid override field", "rules": invalid_override_rules,
    }).status_code == 422
    cross_member_rules = copy.deepcopy(DEFAULT_RULES)
    cross_member_rules["rate_overrides"] = [{
        "name": "Wrong member", "scope_level": "Protected Member",
        "selector": {"protected_member_id": 2},
        "values": {"rounding_increment_cents": 1000},
        "reason": "Cross-member override must be rejected.",
    }]
    assert client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "Cross-member override", "rules": cross_member_rules,
    }).status_code == 422
    invalid_engagement_rules = copy.deepcopy(DEFAULT_RULES)
    invalid_engagement_rules["rate_overrides"] = [{
        "name": "Unknown engagement", "scope_level": "Engagement",
        "selector": {"engagement_id": 999999},
        "values": {"standard_bill_rate_cents_per_hour": 27500},
        "reason": "Unknown engagement must not receive an override.",
    }]
    assert client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "Unknown engagement override", "rules": invalid_engagement_rules,
    }).status_code == 422

    estimate_payload = {
        "rate_card_id": card_id,
        "product_line": "SalINTEL Investigation",
        "domain_key": "personnel-assessment",
        "investigation_tier": "Tier 1",
        "complexity": "Standard",
        "pricing_method": "Suggested Fixed Fee",
        "customer_summary": "Fictional demonstration of a bounded Tier 1 personnel investigation.",
        "internal_basis": "Demonstration planning basis; actual labor and provider costs remain unrecorded.",
    }
    assert client.post("/api/salcapa/commercial/estimates", headers=member, json=estimate_payload).status_code == 403
    estimate = client.post("/api/salcapa/commercial/estimates", headers=director, json=estimate_payload)
    assert estimate.status_code == 200, estimate.text
    item = estimate.json()
    estimate_id = item["id"]
    calc = item["calculation"]
    assert calc["human_hours"] == "2.000"
    assert calc["human_hours_basis"] == "Authorized domain override"
    assert calc["technology_planning_allowance_cents"] == 400
    assert calc["estimated_loaded_labor_cost_cents"] == 18000
    assert calc["customer_labor_equivalent_cents"] == 50000
    assert calc["contingency_cents"] == 7560
    assert calc["recommended_customer_price_cents"] == 60000
    assert calc["estimated_internal_cost_cents"] == 18400
    assert calc["actual_cost_status"] == "Not Recorded"
    assert item["creates_charge"] is False and item["creates_invoice"] is False
    assert len(item["content_sha256"]) == 64

    assert client.get("/api/salcapa/commercial/estimates", headers=member).json() == []
    submitted = client.post(
        f"/api/salcapa/commercial/estimates/{estimate_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit immutable estimate for independent price review."},
    )
    assert submitted.status_code == 200, submitted.text
    self_approve = client.post(
        f"/api/salcapa/commercial/estimates/{estimate_id}/transition", headers=director,
        json={"status": "Approved", "reason": "Attempt self-approval.", "approved_customer_price_cents": 62500},
    )
    assert self_approve.status_code == 409
    missing_price = client.post(
        f"/api/salcapa/commercial/estimates/{estimate_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Price omitted."},
    )
    assert missing_price.status_code == 422
    approved_estimate = client.post(
        f"/api/salcapa/commercial/estimates/{estimate_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Independent commercial approval.",
              "approved_customer_price_cents": 62500},
    )
    assert approved_estimate.status_code == 200, approved_estimate.text
    assert approved_estimate.json()["approved_customer_price_cents"] == 62500
    assert client.get("/api/salcapa/commercial/estimates", headers=member).json() == []
    wrong_release = client.post(
        f"/api/salcapa/commercial/estimates/{estimate_id}/transition", headers=director,
        json={"status": "Released", "reason": "Wrong actor."},
    )
    assert wrong_release.status_code == 409
    released = client.post(
        f"/api/salcapa/commercial/estimates/{estimate_id}/transition", headers=administrator,
        json={"status": "Released", "reason": "Release approved customer-facing terms."},
    )
    assert released.status_code == 200, released.text
    member_rows = client.get("/api/salcapa/commercial/estimates", headers=member).json()
    assert len(member_rows) == 1
    assert member_rows[0]["approved_customer_price_cents"] == 62500
    assert member_rows[0]["creates_charge"] is False and member_rows[0]["creates_invoice"] is False
    for forbidden in ("internal_basis", "estimated_internal_cost_cents", "estimated_margin_cents",
                      "estimated_margin_basis_points", "rate_snapshot", "calculation"):
        assert forbidden not in member_rows[0]
    assert client.get("/api/salcapa/commercial/estimates", headers=other).json() == []
    assert client.post(
        f"/api/salcapa/commercial/estimates/{estimate_id}/transition", headers=other,
        json={"status": "Released", "reason": "Cross-tenant attempt."},
    ).status_code == 404

    # Salus-only actual-cost records retain independent review and correction lineage.
    time_payload = {
        "estimate_id": estimate_id,
        "person_name": "Demonstration Investigator",
        "role_name": "Investigator",
        "work_date": "2026-09-08",
        "minutes": 90,
        "work_category": "Research",
        "commercial_treatment": "Billable",
        "notes": "Fictional demonstration research work awaiting independent review.",
    }
    assert client.post("/api/salcapa/commercial/time-entries", headers=member, json=time_payload).status_code == 403
    forged_time = dict(time_payload, status="Approved")
    assert client.post("/api/salcapa/commercial/time-entries", headers=director, json=forged_time).status_code == 422
    time_created = client.post("/api/salcapa/commercial/time-entries", headers=director, json=time_payload)
    assert time_created.status_code == 200, time_created.text
    time_entry = time_created.json()
    time_id = time_entry["id"]
    assert time_entry["calculated_cost_cents"] == 13500
    assert time_entry["loaded_rate_cents_per_hour"] == 9000
    assert time_entry["creates_charge"] is False and time_entry["creates_invoice"] is False
    assert client.post(
        f"/api/salcapa/commercial/time-entries/{time_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit the work record for independent review."},
    ).status_code == 200
    assert client.post(
        f"/api/salcapa/commercial/time-entries/{time_id}/transition", headers=director,
        json={"status": "Approved", "reason": "Attempt self-approval."},
    ).status_code == 409
    assert client.post(
        f"/api/salcapa/commercial/time-entries/{time_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Independent review confirms the work record."},
    ).status_code == 200

    actual_cost_payload = {
        "estimate_id": estimate_id,
        "cost_category": "Technology / Data",
        "cost_basis": "Metered Actual",
        "amount_cents": 925,
        "provider_or_payee": "Demonstration research provider",
        "source_reference": "usage-record-demo-001",
        "usage_units": "Fictional metered usage",
        "unit_rate_version": "Demonstration rate 1",
        "incurred_at": "2026-09-08T14:30:00Z",
        "commercial_treatment": "Included",
        "notes": "Fictional metered cost used only for governed acceptance testing.",
    }
    cost_created = client.post("/api/salcapa/commercial/cost-entries", headers=director, json=actual_cost_payload)
    assert cost_created.status_code == 200, cost_created.text
    cost_id = cost_created.json()["id"]
    assert cost_created.json()["recognized_actual_cost_cents"] == 925
    assert client.post(
        f"/api/salcapa/commercial/cost-entries/{cost_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit metered cost for independent review."},
    ).status_code == 200
    assert client.post(
        f"/api/salcapa/commercial/cost-entries/{cost_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Source record supports the metered cost."},
    ).status_code == 200

    allowance_payload = dict(
        actual_cost_payload,
        cost_basis="Planning Allowance",
        amount_cents=500,
        source_reference="allowance-demo-001",
        usage_units="",
        unit_rate_version="",
        notes="Planning allowance retained separately from actual cost.",
    )
    allowance = client.post("/api/salcapa/commercial/cost-entries", headers=director, json=allowance_payload)
    assert allowance.status_code == 200, allowance.text
    allowance_id = allowance.json()["id"]
    assert allowance.json()["recognized_actual_cost_cents"] == 0
    assert client.post(
        f"/api/salcapa/commercial/cost-entries/{allowance_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit allowance classification for review."},
    ).status_code == 200
    assert client.post(
        f"/api/salcapa/commercial/cost-entries/{allowance_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Confirm this remains a planning allowance, not actual cost."},
    ).status_code == 200

    unavailable_payload = dict(
        actual_cost_payload,
        cost_basis="Unavailable",
        amount_cents=1,
        source_reference="",
        usage_units="",
        unit_rate_version="",
        notes="Actual provider cost is not available.",
    )
    assert client.post(
        "/api/salcapa/commercial/cost-entries", headers=director, json=unavailable_payload
    ).status_code == 422
    unavailable_payload["amount_cents"] = 0
    unavailable = client.post(
        "/api/salcapa/commercial/cost-entries", headers=director, json=unavailable_payload
    )
    assert unavailable.status_code == 200, unavailable.text
    unavailable_id = unavailable.json()["id"]
    for status, headers, reason in (
        ("Submitted", director, "Submit unavailable-cost classification for review."),
        ("Approved", administrator, "Confirm that no actual amount is available or inferred."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/cost-entries/{unavailable_id}/transition", headers=headers,
            json={"status": status, "reason": reason},
        ).status_code == 200

    assert client.get(
        f"/api/salcapa/commercial/estimates/{estimate_id}/actuals", headers=member
    ).status_code == 403
    assert client.get(
        f"/api/salcapa/commercial/estimates/{estimate_id}/actuals", headers=other
    ).status_code == 404
    actuals = client.get(
        f"/api/salcapa/commercial/estimates/{estimate_id}/actuals", headers=administrator
    )
    assert actuals.status_code == 200, actuals.text
    summary = actuals.json()
    assert summary["actual_cost_status"] == "Partial Actuals"
    assert summary["approved_time_cost_cents"] == 13500
    assert summary["approved_direct_actual_cost_cents"] == 925
    assert summary["recognized_actual_cost_to_date_cents"] == 14425
    assert summary["approved_estimated_or_allowance_cost_cents"] == 500
    assert summary["approved_unavailable_cost_record_count"] == 1
    assert summary["variance_to_estimated_internal_cost_cents"] == 14425 - 18400
    assert summary["creates_charge"] is False and summary["creates_invoice"] is False

    correction_payload = dict(time_payload, supersedes_entry_id=time_id, minutes=120,
                              notes="Corrected fictional work duration with retained lineage.")
    correction = client.post("/api/salcapa/commercial/time-entries", headers=director, json=correction_payload)
    assert correction.status_code == 200, correction.text
    correction_id = correction.json()["id"]
    assert client.post(
        f"/api/salcapa/commercial/time-entries/{correction_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit correction for independent review."},
    ).status_code == 200
    assert client.post(
        f"/api/salcapa/commercial/time-entries/{correction_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Correction evidence supports 120 minutes."},
    ).status_code == 200
    duplicate_correction = client.post(
        "/api/salcapa/commercial/time-entries", headers=director, json=correction_payload
    )
    assert duplicate_correction.status_code == 409
    corrected_summary = client.get(
        f"/api/salcapa/commercial/estimates/{estimate_id}/actuals", headers=administrator
    ).json()
    assert corrected_summary["approved_time_cost_cents"] == 18000
    assert corrected_summary["recognized_actual_cost_to_date_cents"] == 18925
    active_time = {row["id"]: row["active_approved_record"] for row in corrected_summary["time_entries"]}
    assert active_time[time_id] is False and active_time[correction_id] is True

    # Forecasts snapshot the approved cost record, explain uncertainty, and require independent review.
    forecast_payload = {
        "estimate_id": estimate_id,
        "as_of_date": "2026-09-08",
        "forecast_through_date": "2026-09-30",
        "confidence_state": "Reasonably Supported",
        "unavailable_cost_handling": "Excluded pending evidence",
        "remaining_labor_minutes": 60,
        "additional_remaining_direct_cost_cents": 2000,
        "assumptions": "One hour of review remains after the fictional demonstration research.",
        "known_constraints": "One provider cost remains unavailable and requires supporting evidence.",
    }
    assert client.post("/api/salcapa/commercial/forecasts", headers=member, json=forecast_payload).status_code == 403
    forged_forecast = dict(forecast_payload, status="Approved")
    assert client.post(
        "/api/salcapa/commercial/forecasts", headers=director, json=forged_forecast
    ).status_code == 422
    invalid_dates = dict(forecast_payload, forecast_through_date="2026-09-01")
    assert client.post(
        "/api/salcapa/commercial/forecasts", headers=director, json=invalid_dates
    ).status_code == 422
    stale_forecast = client.post(
        "/api/salcapa/commercial/forecasts", headers=director, json=forecast_payload
    )
    assert stale_forecast.status_code == 200, stale_forecast.text
    stale_id = stale_forecast.json()["id"]
    assert stale_forecast.json()["recognized_actual_cost_to_date_cents"] == 18925
    assert stale_forecast.json()["approved_provisional_cost_cents"] == 500
    assert stale_forecast.json()["forecast_remaining_labor_cost_cents"] == 9000
    assert stale_forecast.json()["forecast_to_complete_cents"] == 11500
    assert stale_forecast.json()["forecast_at_completion_cents"] == 30425
    assert stale_forecast.json()["completeness_state"] == "Evidence Needed"
    assert stale_forecast.json()["creates_charge"] is False
    assert client.post(
        f"/api/salcapa/commercial/forecasts/{stale_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit the dated forecast for independent review."},
    ).status_code == 200
    assert client.post(
        f"/api/salcapa/commercial/forecasts/{stale_id}/transition", headers=director,
        json={"status": "Approved", "reason": "Attempt self-approval."},
    ).status_code == 409

    later_cost_payload = dict(
        actual_cost_payload,
        amount_cents=100,
        source_reference="usage-record-demo-002",
        notes="Later fictional metered cost that makes the submitted forecast stale.",
    )
    later_cost = client.post(
        "/api/salcapa/commercial/cost-entries", headers=director, json=later_cost_payload
    )
    assert later_cost.status_code == 200, later_cost.text
    later_cost_id = later_cost.json()["id"]
    for status, headers, reason in (
        ("Submitted", director, "Submit the later metered record for review."),
        ("Approved", administrator, "The later provider record supports the cost."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/cost-entries/{later_cost_id}/transition", headers=headers,
            json={"status": status, "reason": reason},
        ).status_code == 200
    stale_approval = client.post(
        f"/api/salcapa/commercial/forecasts/{stale_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Attempt approval after source costs changed."},
    )
    assert stale_approval.status_code == 409

    current_forecast = client.post(
        "/api/salcapa/commercial/forecasts", headers=director, json=forecast_payload
    )
    assert current_forecast.status_code == 200, current_forecast.text
    current_id = current_forecast.json()["id"]
    assert current_forecast.json()["recognized_actual_cost_to_date_cents"] == 19025
    assert current_forecast.json()["forecast_at_completion_cents"] == 30525
    assert current_forecast.json()["variance_to_estimated_internal_cost_cents"] == 12125
    assert current_forecast.json()["projected_contribution_cents"] == 31975
    for status, headers, reason in (
        ("Submitted", director, "Submit the current source-grounded forecast."),
        ("Approved", administrator, "Independent review confirms the dated planning judgment."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/forecasts/{current_id}/transition", headers=headers,
            json={"status": status, "reason": reason},
        ).status_code == 200
    assert client.get(
        f"/api/salcapa/commercial/estimates/{estimate_id}/forecasts", headers=member
    ).status_code == 403
    assert client.get(
        f"/api/salcapa/commercial/estimates/{estimate_id}/forecasts", headers=other
    ).status_code == 404
    forecasts = client.get(
        f"/api/salcapa/commercial/estimates/{estimate_id}/forecasts", headers=administrator
    )
    assert forecasts.status_code == 200, forecasts.text
    forecast_rows = forecasts.json()
    assert len(forecast_rows) == 2
    assert next(row for row in forecast_rows if row["id"] == current_id)["active_approved_forecast"] is True
    assert all("not a final cost" in row["interpretation"] for row in forecast_rows)

    revision_payload = dict(
        forecast_payload,
        supersedes_forecast_id=current_id,
        as_of_date="2026-09-09",
        remaining_labor_minutes=30,
        additional_remaining_direct_cost_cents=1000,
        assumptions="Thirty minutes of review and one bounded direct cost remain.",
    )
    revision = client.post(
        "/api/salcapa/commercial/forecasts", headers=director, json=revision_payload
    )
    assert revision.status_code == 200, revision.text
    revision_id = revision.json()["id"]
    assert revision.json()["forecast_to_complete_cents"] == 6000
    assert revision.json()["forecast_at_completion_cents"] == 25025
    for status, headers, reason in (
        ("Submitted", director, "Submit the revised forecast for review."),
        ("Approved", administrator, "Independent review confirms the revised planning judgment."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/forecasts/{revision_id}/transition", headers=headers,
            json={"status": status, "reason": reason},
        ).status_code == 200
    assert client.post(
        "/api/salcapa/commercial/forecasts", headers=director, json=revision_payload
    ).status_code == 409
    revised_rows = client.get(
        f"/api/salcapa/commercial/estimates/{estimate_id}/forecasts", headers=administrator
    ).json()
    active_forecasts = {row["id"]: row["active_approved_forecast"] for row in revised_rows}
    assert active_forecasts[current_id] is False and active_forecasts[revision_id] is True

    # A later card cannot rewrite the immutable estimate snapshot.
    changed_rules = copy.deepcopy(DEFAULT_RULES)
    changed_rules["standard_bill_rate_cents_per_hour"] = 30000
    changed_rules["rate_overrides"] = [
        {
            "name": "Investigation product guidance", "scope_level": "Product Line",
            "selector": {"product_line": "SalINTEL Investigation"},
            "values": {
                "standard_bill_rate_cents_per_hour": 26000,
                "loaded_labor_cost_cents_per_hour": 9500,
            },
            "reason": "Fictional product-line planning guidance.",
        },
        {
            "name": "Personnel domain guidance", "scope_level": "Investigative Domain",
            "selector": {"domain_key": "Personnel-Assessment"},
            "values": {
                "standard_bill_rate_cents_per_hour": 27000,
                "loaded_labor_cost_cents_per_hour": 10000,
                "human_hours": "3",
            },
            "reason": "Fictional domain workload and rate basis.",
        },
        {
            "name": "Tier 1 contingency", "scope_level": "Tier",
            "selector": {"investigation_tier": "Tier 1"},
            "values": {"fixed_fee_contingency_basis_points": 1000},
            "reason": "Fictional tier-specific contingency guidance.",
        },
        {
            "name": "Monthly research allowance", "scope_level": "Monitoring Service",
            "selector": {"monitoring_service": "Monthly"},
            "values": {"technology_planning_allowance_cents": 1200},
            "reason": "Fictional monthly service allowance.",
        },
        {
            "name": "Protected Member rounding", "scope_level": "Protected Member",
            "selector": {"protected_member_id": 1},
            "values": {"rounding_increment_cents": 1000},
            "reason": "Fictional member-specific commercial convention.",
        },
    ]
    successor = client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "Fictional future planning defaults", "effective_from": "2027-01-01",
        "supersedes_id": card_id, "rules": changed_rules,
    })
    assert successor.status_code == 200, successor.text
    internal_rows = client.get("/api/salcapa/commercial/estimates", headers=administrator).json()
    assert internal_rows[0]["rate_snapshot"]["version_no"] == 1
    assert internal_rows[0]["calculation"]["recommended_customer_price_cents"] == 60000
    successor_id = successor.json()["id"]
    for status, headers, reason in (
        ("Submitted", director, "Submit the governed hierarchy for independent review."),
        ("Approved", administrator, "Independent review confirms the bounded hierarchy."),
    ):
        response = client.post(
            f"/api/salcapa/commercial/rate-cards/{successor_id}/transition", headers=headers,
            json={"status": status, "reason": reason},
        )
        assert response.status_code == 200, response.text
    hierarchy_payload = dict(
        estimate_payload,
        rate_card_id=successor_id,
        monitoring_service="Monthly",
        customer_summary="Fictional demonstration of governed pricing precedence.",
        internal_basis="Each matching scope is applied in the approved most-specific order.",
    )
    hierarchy_estimate = client.post(
        "/api/salcapa/commercial/estimates", headers=director, json=hierarchy_payload
    )
    assert hierarchy_estimate.status_code == 200, hierarchy_estimate.text
    hierarchy_calc = hierarchy_estimate.json()["calculation"]
    assert hierarchy_calc["human_hours"] == "3.000"
    assert hierarchy_calc["estimated_loaded_labor_cost_cents"] == 30000
    assert hierarchy_calc["customer_labor_equivalent_cents"] == 81000
    assert hierarchy_calc["technology_planning_allowance_cents"] == 1200
    assert hierarchy_calc["contingency_cents"] == 8220
    assert hierarchy_calc["rounding_increment_cents"] == 1000
    assert hierarchy_calc["recommended_customer_price_cents"] == 90000
    assert hierarchy_calc["estimated_internal_cost_cents"] == 31200
    assert hierarchy_calc["estimated_margin_cents"] == 58800
    resolution = hierarchy_calc["rate_resolution"]
    assert resolution["effective_values"]["standard_bill_rate_cents_per_hour"] == 27000
    assert resolution["effective_values"]["loaded_labor_cost_cents_per_hour"] == 10000
    assert [item["scope_level"] for item in resolution["applied_overrides"]] == [
        "Product Line", "Investigative Domain", "Tier", "Monitoring Service", "Protected Member",
    ]
    assert resolution["human_authority_required"] is True

    # Management reporting is Salus-only, period-bounded, revision-safe, and explicit about uncertainty.
    report_path = (
        "/api/salcapa/commercial/management-report"
        "?start_date=2026-09-08&end_date=2026-09-09&group_by=Product%20Line"
    )
    assert client.get(report_path, headers=member).status_code == 403
    other_report = client.get(report_path, headers=other)
    assert other_report.status_code == 200, other_report.text
    assert other_report.json()["groups"] == []
    assert other_report.json()["totals"]["support_state"] == "Awaiting Validation"
    assert client.get(
        "/api/salcapa/commercial/management-report"
        "?start_date=2026-09-10&end_date=2026-09-09", headers=administrator,
    ).status_code == 422
    assert client.get(
        "/api/salcapa/commercial/management-report"
        "?start_date=2025-09-01&end_date=2026-09-09", headers=administrator,
    ).status_code == 422
    report_response = client.get(report_path, headers=administrator)
    assert report_response.status_code == 200, report_response.text
    report = report_response.json()
    assert report["scope"] == {
        "protected_member_id": 1,
        "start_date": "2026-09-08",
        "end_date": "2026-09-09",
        "group_by": "Product Line",
    }
    assert report["support_state"] == "Evidence Needed"
    assert "not a financial statement" in report["interpretation"]
    assert report["creates_charge"] is False and report["creates_invoice"] is False
    assert report["authorizes_scope"] is False
    assert len(report["groups"]) == 1
    management = report["groups"][0]
    assert management["group"] == "SalINTEL Investigation"
    assert management["active_estimate_count"] == 1
    assert management["new_estimate_count"] == 1
    assert management["released_estimate_count"] == 1
    assert management["approved_customer_price_cents"] == 62500
    assert management["estimated_internal_cost_cents"] == 18400
    assert management["approved_estimated_contribution_cents"] == 44100
    assert management["period_time_minutes"] == 120
    assert management["period_time_cost_cents"] == 18000
    assert management["period_direct_actual_cost_cents"] == 1025
    assert management["period_recognized_actual_cost_cents"] == 19025
    assert management["period_provisional_cost_cents"] == 500
    assert management["period_unavailable_cost_record_count"] == 1
    assert management["current_approved_forecast_count"] == 1
    assert management["current_forecast_at_completion_cents"] == 25025
    assert management["current_projected_contribution_cents"] == 37475
    assert management["support_state"] == "Evidence Needed"
    assert report["totals"]["period_recognized_actual_cost_cents"] == 19025

    csv_report = client.get(report_path + "&export=csv", headers=administrator)
    assert csv_report.status_code == 200, csv_report.text
    assert csv_report.headers["content-disposition"].endswith(
        'filename="salcapa-commercial-2026-09-08-2026-09-09.csv"'
    )
    assert csv_report.text.startswith("group,support_state,active_estimate_count")
    assert "SalINTEL Investigation,Evidence Needed,1,1,1,62500,18400,44100" in csv_report.text

    conn = salcapa_runtime.core.db()
    records = salcapa_runtime.core.collect_tenant_records(conn, 1)
    conn.close()
    assert len(records["salcapa_rate_cards"]) == 2
    assert len(records["salcapa_commercial_estimates"]) == 2
    assert len(records["salcapa_time_entries"]) == 2
    assert len(records["salcapa_cost_entries"]) == 4
    assert len(records["salcapa_commercial_forecasts"]) == 3
    assert salcapa_runtime.core.validate_records(records, 1) == []
    tampered = copy.deepcopy(records)
    tampered["salcapa_commercial_estimates"][0]["recommended_customer_price_cents"] = 1
    # The summary column is governed too: this must fail because it disagrees with the signed snapshot.
    assert salcapa_runtime.core.validate_records(tampered, 1) != []
    tampered_actual = copy.deepcopy(records)
    tampered_actual["salcapa_cost_entries"][0]["recognized_actual_cost_cents"] = 1
    assert salcapa_runtime.core.validate_records(tampered_actual, 1) != []
    tampered_forecast = copy.deepcopy(records)
    tampered_forecast["salcapa_commercial_forecasts"][0]["forecast_at_completion_cents"] = 1
    assert salcapa_runtime.core.validate_records(tampered_forecast, 1) != []

    # Direct persisted tampering is rejected before any lifecycle action.
    conn = salcapa_runtime.core.db()
    conn.execute(
        "UPDATE salcapa_commercial_estimates SET calculation_json=? WHERE id=?",
        (json.dumps({"forged": True}), estimate_id),
    )
    conn.commit()
    conn.close()
    compromised = client.get("/api/salcapa/commercial/estimates", headers=administrator)
    assert compromised.status_code == 409

    print("SALCAPA_COMMERCIAL_PASS")


if __name__ == "__main__":
    main()
