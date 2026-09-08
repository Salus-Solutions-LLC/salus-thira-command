#!/usr/bin/env python3
"""Acceptance checks for Issue #154 governed rate cards and estimate snapshots."""
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

    assert client.get("/api/system/mode").json()["version"] == "3.81"
    assert client.get("/api/salcapa/commercial/catalog", headers=member).status_code == 403
    catalog = client.get("/api/salcapa/commercial/catalog", headers=director)
    assert catalog.status_code == 200, catalog.text
    body = catalog.json()
    assert body["initial_planning_defaults"]["loaded_labor_cost_cents_per_hour"] == 9000
    assert body["initial_planning_defaults"]["technology_planning_allowance_cents"]["Tier 1"] == 400
    assert body["guidance"]["consequence"].startswith("A recommendation is not a charge")
    assert body["guidance"]["actual_cost_truth"].startswith("When actual provider")

    forged = client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "Forged card", "status": "Approved", "rules": DEFAULT_RULES,
    })
    assert forged.status_code == 422
    created = client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "SYNTHETIC Salus planning defaults", "effective_from": "2026-09-08",
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

    estimate_payload = {
        "rate_card_id": card_id,
        "product_line": "SalINTEL Investigation",
        "domain_key": "personnel-assessment",
        "investigation_tier": "Tier 1",
        "complexity": "Standard",
        "pricing_method": "Suggested Fixed Fee",
        "customer_summary": "SYNTHETIC bounded Tier 1 personnel investigation.",
        "internal_basis": "SYNTHETIC planning basis; actual labor and provider costs remain unrecorded.",
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

    # A later card cannot rewrite the immutable estimate snapshot.
    changed_rules = copy.deepcopy(DEFAULT_RULES)
    changed_rules["standard_bill_rate_cents_per_hour"] = 30000
    successor = client.post("/api/salcapa/commercial/rate-cards", headers=director, json={
        "name": "SYNTHETIC future planning defaults", "effective_from": "2027-01-01",
        "supersedes_id": card_id, "rules": changed_rules,
    })
    assert successor.status_code == 200, successor.text
    internal_rows = client.get("/api/salcapa/commercial/estimates", headers=administrator).json()
    assert internal_rows[0]["rate_snapshot"]["version_no"] == 1
    assert internal_rows[0]["calculation"]["recommended_customer_price_cents"] == 60000

    conn = salcapa_runtime.core.db()
    records = salcapa_runtime.core.collect_tenant_records(conn, 1)
    conn.close()
    assert len(records["salcapa_rate_cards"]) == 2
    assert len(records["salcapa_commercial_estimates"]) == 1
    assert salcapa_runtime.core.validate_records(records, 1) == []
    tampered = copy.deepcopy(records)
    tampered["salcapa_commercial_estimates"][0]["recommended_customer_price_cents"] = 1
    # The summary column is governed too: this must fail because it disagrees with the signed snapshot.
    assert salcapa_runtime.core.validate_records(tampered, 1) != []

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
