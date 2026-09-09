#!/usr/bin/env python3
"""Acceptance checks for Issue #154 commercial governance, including WIP review."""
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

    assert client.get("/api/system/mode").json()["version"] == "3.98"
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
    assert "without claiming recognized revenue" in body["guidance"]["report_recurring"]
    assert "only from evidence-qualified groups" in body["guidance"]["report_comparison"]

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
    assert report["recognizes_revenue"] is False and report["recognizes_margin"] is False
    assert report["recurring_commercial_position"]["recognizes_revenue"] is False
    assert report["comparative_contribution_positions"][0]["comparison_state"] == "Evidence Needed"
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

    # Protected Membership preserves the commercial relationship / investigation-depth distinction.
    catalog_body = client.get("/api/salcapa/commercial/catalog", headers=director).json()
    assert catalog_body["membership_arrangements"] == [
        "Transactional", "Subscription Membership", "Hybrid",
    ]
    assert "investigative depth only" in catalog_body["guidance"]["membership_distinction"]
    assert catalog_body["guidance"]["membership_consequence"].startswith(
        "Recording use or reaching a capacity limit does not create a charge"
    )
    assert client.get(
        "/api/salcapa/commercial/membership/plans", headers=member
    ).status_code == 403
    invalid_tier_name = client.post(
        "/api/salcapa/commercial/membership/plans", headers=director, json={
            "name": "Tier 1 Membership", "arrangement": "Hybrid",
            "effective_from": "2026-09-01", "entitlements": [{
                "key": "monitoring-cycles", "label": "Monitoring cycles",
                "product_line": "SalINTEL Ongoing Monitoring",
                "service_scope": "Governed monitoring cycles within an approved profile.",
                "treatment": "Included", "capacity_type": "Direct Quantity",
                "included_quantity": 2, "unit": "cycles", "rollover": False,
                "member_description": "Two approved monitoring cycles during the term.",
            }],
            "member_summary": "Invalid investigation-tier membership name.",
            "internal_basis": "Must fail because membership level is not investigation depth.",
        },
    )
    assert invalid_tier_name.status_code == 422
    plan_payload = {
        "name": "Fictional Protected Membership", "arrangement": "Hybrid",
        "effective_from": "2026-09-01",
        "entitlements": [
            {
                "key": "monitoring-cycles", "label": "Ongoing Monitoring cycles",
                "product_line": "SalINTEL Ongoing Monitoring",
                "service_scope": "Governed monitoring cycles within separately approved profiles.",
                "treatment": "Included", "capacity_type": "Direct Quantity",
                "included_quantity": 2, "unit": "cycles", "rollover": False,
                "member_description": "Two reviewed monitoring cycles during the term.",
            },
            {
                "key": "service-credits", "label": "Salus service credits",
                "product_line": "Special Project",
                "service_scope": "Optional credits applied only after authorized service selection.",
                "treatment": "Credit Eligible", "capacity_type": "Service Credits",
                "included_quantity": 5, "unit": "credits", "rollover": True,
                "rollover_limit": 2,
                "member_description": "Five governed service credits with bounded rollover.",
            },
            {
                "key": "tier-one-investigations", "label": "Tier 1 investigations",
                "product_line": "SalINTEL Investigation",
                "service_scope": "Tier 1 defines investigation depth; it is not a membership level.",
                "treatment": "Included", "capacity_type": "Direct Quantity",
                "included_quantity": 2, "unit": "investigations", "rollover": False,
                "member_description": "Two separately authorized Tier 1 investigations.",
            },
            {
                "key": "tier-two-work", "label": "Tier 2 investigation work",
                "product_line": "SalINTEL Investigation",
                "service_scope": "Preferred-rate treatment subject to separate scope and price approval.",
                "treatment": "Preferred Rate", "capacity_type": "Commercial Treatment Only",
                "unit": "engagements", "rollover": False,
                "member_description": "Preferred-rate consideration; work remains separately authorized.",
            },
        ],
        "portfolio_pricing": [{
            "driver_key": "covered-facilities", "label": "Covered facilities", "unit": "facilities",
            "included_quantity": 3, "adjustment_method": "Negotiated",
            "planning_amount_cents": 0,
            "efficiency_basis": "Portfolio efficiency is reviewed as a whole rather than multiplying a single-site fee.",
        }],
        "member_summary": "Fictional hybrid membership with explicit services and capacity.",
        "internal_basis": "Demonstration plan for governed entitlement, portfolio, and economics acceptance.",
    }
    assert client.post(
        "/api/salcapa/commercial/membership/plans", headers=member, json=plan_payload
    ).status_code == 403
    created_plan = client.post(
        "/api/salcapa/commercial/membership/plans", headers=director, json=plan_payload
    )
    assert created_plan.status_code == 200, created_plan.text
    plan = created_plan.json()
    plan_id = plan["id"]
    assert plan["status"] == "Draft" and plan["arrangement"] == "Hybrid"
    assert len(plan["entitlements"]) == 4 and len(plan["content_sha256"]) == 64
    for status, headers, reason in (
        ("Submitted", director, "Submit the membership plan for independent review."),
        ("Approved", administrator, "Independent review confirms explicit, bounded entitlements."),
    ):
        response = client.post(
            f"/api/salcapa/commercial/membership/plans/{plan_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        )
        assert response.status_code == 200, response.text

    term_payload = {
        "plan_id": plan_id, "contract_reference": "fictional-sow-membership-001",
        "start_date": "2026-09-01", "end_date": "2027-08-31",
        "renewal_review_date": "2027-07-31", "billing_cadence": "Monthly",
        "recurring_fee_cents": 100000, "approved_term_value_cents": 1200000,
        "portfolio_coverage": [
            {
                "entity_type": "Facilities", "covered_quantity": 3,
                "scope_reference": "fictional-facility-register-v1",
                "member_description": "Three facilities listed in the released scope register.",
            },
            {
                "entity_type": "Personnel", "covered_quantity": 50,
                "scope_reference": "fictional-personnel-register-v1",
                "member_description": "Fifty personnel positions within the released scope.",
            },
        ],
        "negotiated_terms": "Fictional monthly arrangement; add-ons require separate written approval.",
        "internal_basis": "Approved term value is a commercial planning record, not recognized revenue.",
    }
    term_created = client.post(
        "/api/salcapa/commercial/membership/terms", headers=director, json=term_payload
    )
    assert term_created.status_code == 200, term_created.text
    term = term_created.json()
    term_id = term["id"]
    assert term["status"] == "Draft" and term["plan_snapshot"]["id"] == plan_id
    assert term["economics"]["monthly_recurring_value_cents"] == 100000
    assert term["economics"]["annualized_recurring_value_cents"] == 1200000
    assert term["economics"]["evidence_state"] == "Awaiting Validation"
    assert term["creates_charge"] is False and term["auto_renews"] is False
    for status, headers, reason in (
        ("Submitted", director, "Submit the exact term for independent commercial review."),
        ("Approved", administrator, "Independent review confirms the exact term and portfolio scope."),
        ("Released", administrator, "Release approved membership information to this Protected Member."),
    ):
        response = client.post(
            f"/api/salcapa/commercial/membership/terms/{term_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        )
        assert response.status_code == 200, response.text

    member_terms = client.get(
        "/api/salcapa/commercial/membership/terms", headers=member
    )
    assert member_terms.status_code == 200, member_terms.text
    member_term = member_terms.json()[0]
    assert member_term["plan_name"] == "Fictional Protected Membership"
    assert member_term["arrangement"] == "Hybrid"
    assert member_term["portfolio_coverage"][0]["covered_quantity"] == "3"
    assert member_term["creates_charge"] is False
    for forbidden in (
        "tenant_id", "plan_snapshot", "internal_basis", "negotiated_terms",
        "economics", "content_sha256", "approved_by",
    ):
        assert forbidden not in member_term
    assert client.get(
        "/api/salcapa/commercial/membership/consumption", headers=member
    ).status_code == 403

    monitoring_use = {
        "term_id": term_id, "entitlement_key": "monitoring-cycles", "quantity": 1,
        "occurred_on": "2026-09-08", "source_type": "Monitoring Cycle",
        "source_record_id": "fictional-monitoring-cycle-001",
        "source_reference": "Reviewed fictional cycle record.",
        "notes": "One monitoring cycle submitted as supported membership consumption.",
    }
    use_created = client.post(
        "/api/salcapa/commercial/membership/consumption", headers=director, json=monitoring_use
    )
    assert use_created.status_code == 200, use_created.text
    use_id = use_created.json()["id"]
    assert use_created.json()["capacity_analysis"]["approved_consumption"] == "1"
    assert use_created.json()["capacity_analysis"]["authorization_state"] == "Within Approved Entitlement"
    for status, headers, reason in (
        ("Submitted", director, "Submit supported use for independent review."),
        ("Approved", administrator, "Independent review confirms one monitoring cycle."),
    ):
        response = client.post(
            f"/api/salcapa/commercial/membership/consumption/{use_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        )
        assert response.status_code == 200, response.text
    overage_use = dict(
        monitoring_use, quantity=2, source_record_id="fictional-monitoring-cycle-002-003",
        source_reference="Two additional reviewed fictional cycle records.",
        notes="The quantity exceeds released capacity and requires a separate decision.",
    )
    overage = client.post(
        "/api/salcapa/commercial/membership/consumption", headers=director, json=overage_use
    )
    assert overage.status_code == 200, overage.text
    overage_id = overage.json()["id"]
    assert overage.json()["capacity_analysis"]["authorization_state"] == "Separate Authorization Required"
    assert overage.json()["creates_charge"] is False
    for status, headers, reason in (
        ("Submitted", director, "Submit the supported excess-use record for review."),
        ("Approved", administrator, "Confirm use evidence; separate commercial authorization remains required."),
    ):
        response = client.post(
            f"/api/salcapa/commercial/membership/consumption/{overage_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        )
        assert response.status_code == 200, response.text

    investigation_use = {
        "term_id": term_id, "entitlement_key": "tier-one-investigations", "quantity": 1,
        "occurred_on": "2026-09-08", "source_type": "Estimate",
        "source_record_id": estimate_id, "source_reference": "Released governed estimate.",
        "estimate_id": estimate_id,
        "notes": "Link one separately authorized Tier 1 investigation for cost-to-serve evidence.",
    }
    linked = client.post(
        "/api/salcapa/commercial/membership/consumption", headers=director, json=investigation_use
    )
    assert linked.status_code == 200, linked.text
    linked_id = linked.json()["id"]
    for status, headers, reason in (
        ("Submitted", director, "Submit linked investigation use for review."),
        ("Approved", administrator, "Confirm the linked estimate and membership use."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/membership/consumption/{linked_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        ).status_code == 200

    refreshed_member = client.get(
        "/api/salcapa/commercial/membership/terms", headers=member
    ).json()[0]
    monitoring_capacity = next(
        item for item in refreshed_member["capacity"] if item["entitlement_key"] == "monitoring-cycles"
    )
    assert monitoring_capacity["approved_consumption"] == "3"
    assert monitoring_capacity["remaining_quantity"] == "0"
    assert monitoring_capacity["quantity_requiring_separate_authorization"] == "1"
    assert monitoring_capacity["authorization_state"] == "Separate Authorization Required"
    internal_term = client.get(
        "/api/salcapa/commercial/membership/terms", headers=administrator
    ).json()[0]
    economics = internal_term["economics"]
    assert economics["monthly_recurring_value_cents"] == 100000
    assert economics["annualized_recurring_value_cents"] == 1200000
    assert economics["recognized_cost_to_serve_cents"] == 19025
    assert economics["forecast_cost_to_serve_cents"] == 25025
    assert economics["planning_contribution_cents"] == 1174975
    assert economics["evidence_state"] == "Evidence Needed"
    assert "not financial statements" in economics["interpretation"]
    assert client.post(
        "/api/salcapa/commercial/membership/consumption", headers=other, json=monitoring_use
    ).status_code == 422

    # A successor plan and term preserve the released historical snapshots.
    successor_plan_payload = copy.deepcopy(plan_payload)
    successor_plan_payload["supersedes_plan_id"] = plan_id
    successor_plan_payload["name"] = "Fictional Protected Membership — revised"
    successor_plan_payload["effective_from"] = "2027-09-01"
    successor_plan_payload["entitlements"][0]["included_quantity"] = 4
    successor_plan = client.post(
        "/api/salcapa/commercial/membership/plans", headers=director, json=successor_plan_payload
    )
    assert successor_plan.status_code == 200, successor_plan.text
    successor_plan_id = successor_plan.json()["id"]
    for status, headers, reason in (
        ("Submitted", director, "Submit revised plan for independent review."),
        ("Approved", administrator, "Approve the future plan without rewriting history."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/membership/plans/{successor_plan_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        ).status_code == 200
    successor_term_payload = dict(
        term_payload, plan_id=successor_plan_id, supersedes_term_id=term_id,
        contract_reference="fictional-sow-membership-002", start_date="2027-09-01",
        end_date="2028-08-31", renewal_review_date="2028-07-31",
    )
    successor_term = client.post(
        "/api/salcapa/commercial/membership/terms", headers=director, json=successor_term_payload
    )
    assert successor_term.status_code == 200, successor_term.text
    assert successor_term.json()["plan_snapshot"]["entitlements"][0]["included_quantity"] == "4"
    assert client.post(
        "/api/salcapa/commercial/membership/terms", headers=director, json=successor_term_payload
    ).status_code == 409
    member_history = client.get(
        "/api/salcapa/commercial/membership/terms", headers=member
    ).json()
    assert len(member_history) == 1
    assert member_history[0]["capacity"][0]["included_quantity"] == "2"

    # WIP is a dated, Salus-only commercial disposition—not accounting or billing automation.
    assert "Authorized for Billing" in body["wip_dispositions"]
    assert "does not create a charge or invoice" in body["guidance"]["wip_authority"]
    assert client.get(
        "/api/salcapa/commercial/wip-reviews", headers=member
    ).status_code == 403
    assert client.get(
        "/api/salcapa/commercial/wip-summary?as_of_date=2026-09-08", headers=member
    ).status_code == 403
    wip_payload = {
        "estimate_id": estimate_id,
        "as_of_date": "2026-09-08",
        "work_through_date": "2026-09-08",
        "commercial_disposition": "Evidence Needed",
        "work_value_cents": 40000,
        "billing_authorized_amount_cents": 0,
        "external_billing_reference": "",
        "review_basis": "Reviewed approved work, direct cost, and membership-use evidence.",
        "assumptions": "Work value is a dated management estimate pending the unavailable provider cost.",
        "known_gaps": "One provider cost remains unavailable.",
    }
    assert client.post(
        "/api/salcapa/commercial/wip-reviews", headers=member, json=wip_payload
    ).status_code == 403
    invalid_billing = dict(
        wip_payload, commercial_disposition="Authorized for Billing",
        billing_authorized_amount_cents=30000,
    )
    assert client.post(
        "/api/salcapa/commercial/wip-reviews", headers=director, json=invalid_billing
    ).status_code == 409
    wip = client.post(
        "/api/salcapa/commercial/wip-reviews", headers=director, json=wip_payload
    )
    assert wip.status_code == 200, wip.text
    wip_id = wip.json()["id"]
    assert wip.json()["evidence_state"] == "Evidence Needed"
    assert wip.json()["source_snapshot"]["recognized_actual_cost_cents"] == 19025
    assert wip.json()["source_snapshot"]["unavailable_cost_record_count"] == 1
    assert len(wip.json()["source_snapshot"]["active_membership_consumption"]) == 1
    for prohibited in (
        "creates_charge", "creates_invoice", "recognizes_revenue", "transmits_externally",
    ):
        assert wip.json()[prohibited] is False
    assert client.post(
        f"/api/salcapa/commercial/wip-reviews/{wip_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit the dated WIP evidence review."},
    ).status_code == 200
    assert client.post(
        f"/api/salcapa/commercial/wip-reviews/{wip_id}/transition", headers=director,
        json={"status": "Approved", "reason": "Attempt self-approval."},
    ).status_code == 409
    assert client.post(
        f"/api/salcapa/commercial/wip-reviews/{wip_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Independently confirm the evidence-needed disposition."},
    ).status_code == 200

    stale_payload = dict(
        wip_payload, supersedes_wip_review_id=wip_id,
        commercial_disposition="Ready for Billing Authorization",
        known_gaps="Source evidence will be rechecked before approval.",
    )
    stale = client.post(
        "/api/salcapa/commercial/wip-reviews", headers=director, json=stale_payload
    )
    assert stale.status_code == 200, stale.text
    stale_id = stale.json()["id"]
    assert client.post(
        f"/api/salcapa/commercial/wip-reviews/{stale_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit the proposed revision."},
    ).status_code == 200

    unavailable_correction = dict(
        actual_cost_payload,
        supersedes_entry_id=unavailable_id,
        amount_cents=200,
        source_reference="usage-record-demo-002",
        notes="Supported correction replaces the unavailable-cost classification.",
    )
    corrected_cost = client.post(
        "/api/salcapa/commercial/cost-entries", headers=director, json=unavailable_correction
    )
    assert corrected_cost.status_code == 200, corrected_cost.text
    corrected_cost_id = corrected_cost.json()["id"]
    for status, headers, reason in (
        ("Submitted", director, "Submit the supported cost correction."),
        ("Approved", administrator, "Confirm the corrected provider cost evidence."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/cost-entries/{corrected_cost_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        ).status_code == 200
    assert client.post(
        f"/api/salcapa/commercial/wip-reviews/{stale_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Attempt to approve a stale work snapshot."},
    ).status_code == 409
    assert client.post(
        f"/api/salcapa/commercial/wip-reviews/{stale_id}/transition", headers=administrator,
        json={"status": "Rejected", "reason": "Reject because source evidence changed."},
    ).status_code == 200

    authorized_payload = dict(
        invalid_billing, supersedes_wip_review_id=wip_id,
        known_gaps="No unresolved cost evidence within the reviewed period.",
        assumptions="Separate billing personnel must complete all later billing controls.",
    )
    authorized = client.post(
        "/api/salcapa/commercial/wip-reviews", headers=director, json=authorized_payload
    )
    assert authorized.status_code == 200, authorized.text
    authorized_id = authorized.json()["id"]
    assert authorized.json()["evidence_state"] == "Reasonably Supported"
    assert authorized.json()["source_snapshot"]["recognized_actual_cost_cents"] == 19225
    for status, headers, reason in (
        ("Submitted", director, "Submit the supported billing-authorization disposition."),
        ("Approved", administrator, "Authorize a separate billing process for the reviewed amount."),
    ):
        response = client.post(
            f"/api/salcapa/commercial/wip-reviews/{authorized_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        )
        assert response.status_code == 200, response.text
    assert client.post(
        "/api/salcapa/commercial/wip-reviews", headers=director,
        json=dict(wip_payload, commercial_disposition="Externally Billed"),
    ).status_code == 422
    assert client.get(
        f"/api/salcapa/commercial/wip-reviews?estimate_id={estimate_id}", headers=other
    ).status_code == 404
    wip_summary = client.get(
        "/api/salcapa/commercial/wip-summary?as_of_date=2026-09-08", headers=administrator
    )
    assert wip_summary.status_code == 200, wip_summary.text
    assert wip_summary.json()["totals"]["current_review_count"] == 1
    assert wip_summary.json()["totals"]["work_value_cents"] == 40000
    assert wip_summary.json()["totals"]["billing_authorized_amount_cents"] == 30000
    assert wip_summary.json()["totals"]["recognized_actual_cost_cents"] == 19225
    assert wip_summary.json()["groups"][0]["commercial_disposition"] == "Authorized for Billing"
    assert wip_summary.json()["creates_invoice"] is False

    # Current governed sources unlock recurring and comparative views without claiming accounting results.
    refreshed_forecast_payload = dict(
        forecast_payload,
        supersedes_forecast_id=revision_id,
        as_of_date="2026-09-09",
        remaining_labor_minutes=15,
        additional_remaining_direct_cost_cents=500,
        unavailable_cost_handling="Included in remaining estimate",
        assumptions="Fifteen minutes of final review and one supported bounded direct cost remain.",
        known_constraints="Current approved actual-cost evidence is reflected in this dated forecast.",
    )
    refreshed_forecast = client.post(
        "/api/salcapa/commercial/forecasts", headers=director,
        json=refreshed_forecast_payload,
    )
    assert refreshed_forecast.status_code == 200, refreshed_forecast.text
    refreshed_forecast_id = refreshed_forecast.json()["id"]
    for status, headers, reason in (
        ("Submitted", director, "Submit the refreshed source-grounded forecast."),
        ("Approved", administrator, "Independently confirm the current approved sources."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/forecasts/{refreshed_forecast_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        ).status_code == 200

    monitoring_estimate_payload = {
        "rate_card_id": card_id,
        "product_line": "SalINTEL Ongoing Monitoring",
        "domain_key": "protective-intelligence",
        "investigation_tier": "Not Applicable",
        "complexity": "Standard",
        "pricing_method": "Suggested Fixed Fee",
        "monitoring_service": "Monthly",
        "monitoring_cycles": 1,
        "customer_summary": "Fictional monthly ongoing-monitoring scope for reporting validation.",
        "internal_basis": "One bounded monitoring cycle; commercial records remain planning evidence.",
    }
    monitoring_estimate = client.post(
        "/api/salcapa/commercial/estimates", headers=director,
        json=monitoring_estimate_payload,
    )
    assert monitoring_estimate.status_code == 200, monitoring_estimate.text
    monitoring_estimate_id = monitoring_estimate.json()["id"]
    monitoring_price = monitoring_estimate.json()["recommended_customer_price_cents"]
    for status, headers, reason, price in (
        ("Submitted", director, "Submit the bounded monitoring estimate.", None),
        ("Approved", administrator, "Independently approve the monitoring price basis.", monitoring_price),
        ("Released", administrator, "Release the approved monitoring scope and price.", None),
    ):
        transition = {"status": status, "reason": reason}
        if price is not None:
            transition["approved_customer_price_cents"] = price
        assert client.post(
            f"/api/salcapa/commercial/estimates/{monitoring_estimate_id}/transition",
            headers=headers, json=transition,
        ).status_code == 200
    monitoring_forecast_payload = {
        "estimate_id": monitoring_estimate_id,
        "as_of_date": "2026-09-09",
        "forecast_through_date": "2026-09-30",
        "confidence_state": "Reasonably Supported",
        "unavailable_cost_handling": "Included in remaining estimate",
        "remaining_labor_minutes": 30,
        "additional_remaining_direct_cost_cents": 300,
        "assumptions": "One scheduled review cycle remains within the released scope.",
        "known_constraints": "No actual activity has yet been recorded for this future cycle.",
    }
    monitoring_forecast = client.post(
        "/api/salcapa/commercial/forecasts", headers=director,
        json=monitoring_forecast_payload,
    )
    assert monitoring_forecast.status_code == 200, monitoring_forecast.text
    monitoring_forecast_id = monitoring_forecast.json()["id"]
    for status, headers, reason in (
        ("Submitted", director, "Submit the dated monitoring forecast."),
        ("Approved", administrator, "Independently approve the monitoring planning judgment."),
    ):
        assert client.post(
            f"/api/salcapa/commercial/forecasts/{monitoring_forecast_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        ).status_code == 200

    completed_report = client.get(
        "/api/salcapa/commercial/management-report"
        "?start_date=2026-09-08&end_date=2026-09-10&group_by=Product%20Line",
        headers=administrator,
    )
    assert completed_report.status_code == 200, completed_report.text
    completed = completed_report.json()
    recurring = completed["recurring_commercial_position"]
    assert recurring["ongoing_monitoring"]["active_scope_count"] == 1
    assert recurring["ongoing_monitoring"]["approved_price_basis_cents"] == monitoring_price
    assert recurring["protected_membership"]["active_released_term_count"] == 1
    assert recurring["protected_membership"]["approved_monthly_recurring_value_cents"] == 100000
    assert recurring["protected_membership"]["approved_annualized_recurring_value_cents"] == 1200000
    assert recurring["recognizes_revenue"] is False and recurring["recognizes_margin"] is False
    product_comparison = next(
        item for item in completed["comparative_contribution_positions"]
        if item["dimension"] == "Product Line"
    )
    assert product_comparison["comparison_state"] == "Demonstrated"
    assert product_comparison["highest_supported_planning_contribution"] is not None
    assert product_comparison["lowest_supported_planning_contribution"] is not None
    assert "not recognized margin or profit" in product_comparison["interpretation"]

    # Cross-cutting Microsoft 365 provenance keeps exact document versions without a document silo.
    assert "Microsoft SharePoint" in body["source_providers"]
    assert "does not imply that a person reviewed" in body["guidance"]["source_truth"]
    assert client.get("/api/salcapa/sources", headers=member).status_code == 403
    invalid_source = {
        "provider": "Microsoft SharePoint", "external_tenant_id": "",
        "site_id": "salus-commercial-site", "drive_id": "documents-drive",
        "item_id": "estimate-workbook-item", "display_name": "Historical estimates.xlsx",
        "source_owner": "Salus Commercial", "record_type": "Estimate workbook",
        "sensitivity": "Salus Internal", "disclosure_boundary": "Salus Only",
        "business_purpose": "Preserve the exact source workbook identity for governed commercial work.",
        "retention_reference": "Salus commercial records schedule.",
    }
    assert client.post(
        "/api/salcapa/sources", headers=director, json=invalid_source
    ).status_code == 422
    source_payload = dict(invalid_source, external_tenant_id="m365-tenant-demo")
    source = client.post(
        "/api/salcapa/sources", headers=director, json=source_payload
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["id"]
    assert source.json()["stores_credentials"] is False
    assert client.post(
        "/api/salcapa/sources", headers=director, json=source_payload
    ).status_code == 409
    registered_version_payload = {
        "source_record_id": source_id, "external_version_id": "1.0",
        "etag": '"demo-etag-v1"',
        "web_url": "https://salus.example.sharepoint.com/sites/commercial/documents/estimate.xlsx",
        "source_last_modified_at": "2026-09-08T16:30:00Z",
        "access_status": "Registered Without Access", "content_bytes": 0,
        "file_sha256": "", "accessed_at": "", "unavailable_reason": "",
        "provenance_note": "Exact Microsoft 365 identity and version supplied by the authorized collection process.",
    }
    registered_version = client.post(
        "/api/salcapa/source-versions", headers=director, json=registered_version_payload
    )
    assert registered_version.status_code == 200, registered_version.text
    registered_version_id = registered_version.json()["id"]
    assert registered_version.json()["review_state"] == "Not Established"
    assert client.post(
        "/api/salcapa/source-versions", headers=director,
        json=dict(registered_version_payload, external_version_id="bad-access",
                  access_status="Accessed", content_bytes=100, accessed_at="2026-09-09T08:00:00Z",
                  file_sha256="not-a-digest"),
    ).status_code == 422
    supporting_link_payload = {
        "commercial_record_type": "WIP Review", "commercial_record_id": authorized_id,
        "source_record_id": source_id, "source_version_id": registered_version_id,
        "relationship_type": "Supporting Reference",
        "business_purpose": "Retain the registered workbook version while access evidence is pending.",
        "material_change_action": "Evidence Needed",
        "material_change_basis": "The exact version is known, but source bytes have not been accessed.",
    }
    supporting_link = client.post(
        "/api/salcapa/commercial/source-links", headers=director, json=supporting_link_payload
    )
    assert supporting_link.status_code == 200, supporting_link.text
    supporting_link_id = supporting_link.json()["id"]
    assert supporting_link.json()["source_snapshot"]["source_version"]["access_status"] == "Registered Without Access"
    for status, headers, reason in (
        ("Submitted", director, "Submit the exact registered-version relationship."),
        ("Approved", administrator, "Confirm the evidence-needed source relationship."),
    ):
        response = client.post(
            f"/api/salcapa/commercial/source-links/{supporting_link_id}/transition",
            headers=headers, json={"status": status, "reason": reason},
        )
        assert response.status_code == 200, response.text

    accessed_version_payload = dict(
        registered_version_payload, external_version_id="2.0", etag='"demo-etag-v2"',
        source_last_modified_at="2026-09-09T07:45:00Z", access_status="Accessed",
        content_bytes=48127, file_sha256="a" * 64,
        accessed_at="2026-09-09T08:00:00Z",
        provenance_note="Authorized collection process accessed the exact workbook bytes and recorded integrity evidence.",
    )
    accessed_version = client.post(
        "/api/salcapa/source-versions", headers=director, json=accessed_version_payload
    )
    assert accessed_version.status_code == 200, accessed_version.text
    accessed_version_id = accessed_version.json()["id"]
    assert accessed_version.json()["review_state"] == "Not Established"
    old_link = client.get(
        f"/api/salcapa/commercial/source-links?commercial_record_type=WIP%20Review&commercial_record_id={authorized_id}",
        headers=administrator,
    ).json()[0]
    assert old_link["newer_source_version_available"] is True
    revision_payload = dict(
        supporting_link_payload, supersedes_link_id=supporting_link_id,
        source_version_id=accessed_version_id, relationship_type="Approval Artifact",
        business_purpose="Retain the byte-verified workbook version supporting the approved WIP review.",
        material_change_action="Change Estimate Required",
        material_change_basis="The workbook changed after the original version; authorized staff must assess the commercial effect separately.",
    )
    revision = client.post(
        "/api/salcapa/commercial/source-links", headers=director, json=revision_payload
    )
    assert revision.status_code == 200, revision.text
    revision_id = revision.json()["id"]
    assert revision.json()["creates_charge"] is False
    assert revision.json()["changes_scope_or_price"] is False
    assert revision.json()["transmits_externally"] is False
    assert client.post(
        f"/api/salcapa/commercial/source-links/{revision_id}/transition", headers=director,
        json={"status": "Submitted", "reason": "Submit the exact version and material-change recommendation."},
    ).status_code == 200
    assert client.post(
        f"/api/salcapa/commercial/source-links/{revision_id}/transition", headers=director,
        json={"status": "Approved", "reason": "Attempt self-approval."},
    ).status_code == 409
    approved_revision = client.post(
        f"/api/salcapa/commercial/source-links/{revision_id}/transition", headers=administrator,
        json={"status": "Approved", "reason": "Approve the source relationship; a separate change estimate remains required."},
    )
    assert approved_revision.status_code == 200, approved_revision.text
    assert approved_revision.json()["current_approved_link"] is True
    history = client.get(
        f"/api/salcapa/commercial/source-links?commercial_record_type=WIP%20Review&commercial_record_id={authorized_id}",
        headers=administrator,
    ).json()
    assert len(history) == 2
    assert history[0]["current_approved_link"] is False
    assert history[1]["source_snapshot"]["source_version"]["file_sha256"] == "a" * 64
    assert client.get("/api/salcapa/sources", headers=other).json() == []
    assert client.get(
        f"/api/salcapa/source-versions?source_record_id={source_id}", headers=other
    ).status_code == 404
    assert client.post(
        "/api/salcapa/commercial/source-links", headers=other, json=revision_payload
    ).status_code == 404

    conn = salcapa_runtime.core.db()
    records = salcapa_runtime.core.collect_tenant_records(conn, 1)
    conn.close()
    assert len(records["salcapa_rate_cards"]) == 2
    assert len(records["salcapa_commercial_estimates"]) == 2
    assert len(records["salcapa_time_entries"]) == 2
    assert len(records["salcapa_cost_entries"]) == 5
    assert len(records["salcapa_commercial_forecasts"]) == 3
    assert len(records["salcapa_membership_plans"]) == 2
    assert len(records["salcapa_membership_terms"]) == 2
    assert len(records["salcapa_membership_consumption"]) == 3
    assert len(records["salcapa_wip_reviews"]) == 3
    assert len(records["salcapa_source_records"]) == 1
    assert len(records["salcapa_source_versions"]) == 2
    assert len(records["salcapa_commercial_source_links"]) == 2
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
    tampered_wip = copy.deepcopy(records)
    tampered_wip["salcapa_wip_reviews"][0]["commercial_disposition"] = "Write-Off"
    assert salcapa_runtime.core.validate_records(tampered_wip, 1) != []
    tampered_membership = copy.deepcopy(records)
    tampered_membership["salcapa_membership_terms"][0]["approved_term_value_cents"] = 1
    assert salcapa_runtime.core.validate_records(tampered_membership, 1) != []
    tampered_entitlement = copy.deepcopy(records)
    tampered_entitlement["salcapa_membership_consumption"][0]["entitlement_snapshot_json"] = "{}"
    assert salcapa_runtime.core.validate_records(tampered_entitlement, 1) != []
    tampered_source = copy.deepcopy(records)
    tampered_source["salcapa_source_versions"][1]["file_sha256"] = "b" * 64
    assert salcapa_runtime.core.validate_records(tampered_source, 1) != []
    tampered_source_link = copy.deepcopy(records)
    tampered_source_link["salcapa_commercial_source_links"][1]["source_snapshot_json"] = "{}"
    assert salcapa_runtime.core.validate_records(tampered_source_link, 1) != []

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
