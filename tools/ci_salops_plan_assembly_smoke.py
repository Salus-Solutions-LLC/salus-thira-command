#!/usr/bin/env python3
"""Acceptance checks for governed autonomous emergency-plan assembly."""
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "plan-assembly.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
os.environ.setdefault("SALUS_PLAN_RESEARCH_ALLOWED_DOMAINS", "example.com")
os.environ.setdefault("SALUS_PLAN_RESEARCH_SEARCH_ENDPOINT", "https://example.com/search")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime
import salops_plan_assembly


def main() -> None:
    client = TestClient(salcapa_runtime.app)
    director = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Preparedness Director", "X-Salus-Clearance": "Highly Sensitive",
    }
    member = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
        "X-Salus-User": "Protected Member", "X-Salus-Clearance": "Standard",
    }
    owner = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Program Owner",
        "X-Salus-User": "Preparedness Program Owner", "X-Salus-Clearance": "Highly Sensitive",
    }
    administrator = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "System Administrator",
        "X-Salus-User": "Release Administrator", "X-Salus-Clearance": "Highly Sensitive",
    }
    other = {
        "X-Salus-Tenant": "2", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Other Tenant", "X-Salus-Clearance": "Highly Sensitive",
    }

    assert client.get("/api/system/mode").json()["version"] == "3.77"
    catalog_path = "/api/salops/preparedness/plan-assembly/catalog"
    assert client.get(catalog_path, headers=member).status_code == 403
    catalog = client.get(catalog_path, headers=director)
    assert catalog.status_code == 200, catalog.text
    authority = catalog.json()["authority"]
    assert authority["chat_may"] == ["Inspect", "Research", "Reconcile", "Draft", "Compare", "Recommend"]
    assert authority["automatic_release"] is False
    assert authority["automatic_plan_replacement"] is False
    assert authority["automatic_charge"] is False
    adapter = catalog.json()["external_research_adapter"]
    assert adapter["enabled"] is True and adapter["configured_domains"] == ["example.com"]
    assert adapter["https_only"] is True and adapter["redirects_followed"] is False
    assert adapter["credentials_sent"] is False and adapter["automatic_verified_fact"] is False
    assert adapter["maximum_discovered_links"] == 50
    assert "application/rss+xml" in adapter["allowed_content_types"]
    assert "application/atom+xml" in adapter["allowed_content_types"]
    assert "application/json" in adapter["allowed_content_types"]
    search_adapter = catalog.json()["external_search_adapter"]
    assert search_adapter["enabled"] is True
    assert search_adapter["type"] == "Public JSON Search"
    assert search_adapter["endpoint_hostname"] == "example.com"
    assert search_adapter["query_transmitted_only_after_authorization"] is True
    assert search_adapter["automatic_candidate_access"] is False
    try:
        salops_plan_assembly._research_document(b"{", "application/json", "https://example.com/api")
        raise AssertionError("Malformed JSON must fail closed")
    except ValueError as exc:
        assert "not valid JSON" in str(exc)

    plan = client.post("/api/salops/preparedness/plans", headers=director, json={
        "assessment_id": 1,
        "title": "SYNTHETIC Emergency Operations Plan",
        "plan_type": "Emergency Operations",
        "purpose": "Provide a governed synthetic baseline for plan-revision testing.",
        "scope_statement": "SYNTHETIC facility and its documented essential functions.",
        "mission_lenses": ["Prevention", "Protection", "Mitigation", "Response", "Recovery"],
        "sensitivity": "Standard",
    })
    assert plan.status_code == 200, plan.text
    plan_id = plan.json()["id"]
    for status in ("Reviewed", "Approved"):
        response = client.post(
            f"/api/salops/preparedness/plans/{plan_id}/transition", headers=director,
            json={"status": status, "reason": f"SYNTHETIC {status} governance basis."},
        )
        assert response.status_code == 200, response.text
    approved = client.get(f"/api/salops/preparedness/plans/{plan_id}", headers=director).json()["plan"]
    assert approved["status"] == "Approved" and approved["version"] == 1

    create_path = "/api/salops/preparedness/plan-assembly"
    forged = client.post(create_path, headers=director, json={
        "base_plan_id": plan_id, "plan_title": "Forged", "plan_type": "EOP",
        "purpose": "Attempt to forge lifecycle state.", "scope_statement": "Bounded scope.",
        "research_questions": ["What changed?"], "status": "Qualified",
        "qualified_by": "Client", "approved_plan_preserved": False,
    })
    assert forged.status_code == 422
    incomplete = client.post(create_path, headers=director, json={
        "plan_title": "No research plan", "plan_type": "EOP",
        "purpose": "Missing source plan.", "scope_statement": "Bounded scope.",
    })
    assert incomplete.status_code == 422

    created = client.post(create_path, headers=director, json={
        "base_plan_id": plan_id,
        "plan_title": "SYNTHETIC Emergency Operations Plan — proposed revision",
        "plan_type": "Emergency Operations",
        "purpose": "Research whether current capability and authority changes affect the approved plan.",
        "scope_statement": "The exact approved synthetic facility scope; no newly added entity enters automatically.",
        "portfolio_scope": {"facility_refs": ["SYNTHETIC-FACILITY-001"]},
        "internal_record_refs": ["SalINTEL:SYNTHETIC-CHANGE-001", "SalTHIRA:1"],
        "library_refs": ["SALUS-LIB:EOP-STRUCTURE-V1"],
        "authorized_external_sources": ["example.com"],
        "source_exclusions": ["Unapproved personal information", "Unapproved partner databases"],
        "research_questions": ["Did the communications dependency materially change?"],
        "known_unknowns": ["Current alternate communications endurance"],
        "assumptions_to_validate": ["Primary notification path remains available during an outage"],
        "sensitivity": "Standard",
    })
    assert created.status_code == 200, created.text
    run = created.json()
    run_id = run["id"]
    assert run["assembly_mode"] == "Revision"
    assert run["status"] == "Research Planning"
    assert run["base_plan_version"] == 1 and len(run["base_plan_sha256"]) == 64
    assert not {"commercial_treatment", "release_status", "approved_by"} & set(run)
    assert client.get(f"{create_path}/{run_id}", headers=member).status_code == 403
    assert client.get(f"{create_path}/{run_id}", headers=other).status_code == 404

    live_path = f"{create_path}/{run_id}/external-research"
    assert client.post(live_path, headers=director, json={
        "url": "http://example.com/guidance", "purpose": "Reject plaintext retrieval.",
    }).status_code == 422
    assert client.post(live_path, headers=director, json={
        "url": "https://127.0.0.1/private", "purpose": "Reject IP-literal retrieval.",
    }).status_code == 422
    assert client.post(live_path, headers=director, json={
        "url": "https://unapproved.example.org/guidance", "purpose": "Reject unapproved host.",
    }).status_code == 409
    requested = client.post(live_path, headers=director, json={
        "url": "https://example.com/emergency-guidance?edition=current",
        "purpose": "Retrieve the exact synthetic public guidance for analyst review.",
    })
    assert requested.status_code == 200, requested.text
    live = requested.json()
    live_id = live["id"]
    assert live["status"] == "Pending Human Authorization" and live["access_status"] == "Not Attempted"
    assert live["creates_verified_fact"] is False and live["creates_disclosure"] is False
    assert live["creates_charge"] is False and len(live["request_sha256"]) == 64
    execute_live = f"{create_path}/external-research/{live_id}/execute"
    authorize_live = f"{create_path}/external-research/{live_id}/authorize"
    assert client.post(execute_live, headers=director, json={"reason": "Premature execution."}).status_code == 409
    assert client.post(authorize_live, headers=member, json={
        "reason": "Member must not authorize.", "scope_confirmed": True,
        "external_transmission_authorized": True, "sensitive_data_absent": True,
    }).status_code == 403
    assert client.post(authorize_live, headers=director, json={
        "reason": "Missing confirmation must fail.", "scope_confirmed": True,
        "external_transmission_authorized": True, "sensitive_data_absent": False,
    }).status_code == 422
    authorized_live = client.post(authorize_live, headers=director, json={
        "reason": "SYNTHETIC exact public source and external transmission authorization.",
        "scope_confirmed": True, "external_transmission_authorized": True,
        "sensitive_data_absent": True,
    })
    assert authorized_live.status_code == 200, authorized_live.text
    assert authorized_live.json()["status"] == "Authorized"
    salops_plan_assembly._resolve_public_host = lambda hostname: ["93.184.216.34"]
    salops_plan_assembly.LIVE_RESEARCH_FETCHER = lambda url, maximum_bytes: {
        "status": 200, "content_type": "text/html",
        "headers": {"content-type": "text/html; charset=utf-8", "etag": '"synthetic"'},
        "content": (b"<html><body>SYNTHETIC public emergency guidance for analyst review."
                    b"<a href='/annex/current'>Current annex</a>"
                    b"<a href='https://outside.example.org/not-authorized'>Outside scope</a>"
                    b"<a href='http://example.com/plaintext'>Plaintext</a></body></html>"),
    }
    executed_live = client.post(execute_live, headers=owner, json={
        "reason": "Execute the separately authorized exact public retrieval.",
    })
    assert executed_live.status_code == 200, executed_live.text
    live_result = executed_live.json()
    live_source_id = live_result["source_id"]
    assert live_result["status"] == "Accessed" and live_result["access_status"] == "Accessed"
    assert live_result["content_type"] == "text/html" and live_result["content_bytes"] > 0
    assert len(live_result["content_sha256"]) == 64
    assert "SYNTHETIC public emergency guidance" in live_result["content_text"]
    assert live_result["discovered_links"] == ["https://example.com/annex/current"]
    assert client.post(execute_live, headers=owner, json={"reason": "Duplicate must fail."}).status_code == 409
    live_bundle = client.get(f"{create_path}/{run_id}", headers=director).json()
    live_source = next(item for item in live_bundle["sources"] if item["id"] == live_source_id)
    assert live_source["access_status"] == "Accessed"
    assert live_source["linked_record_type"] == "External Research Request"
    assert live_source["source_derived_statements"] == []
    assert live_source["reliability"] == "Not Assessed" and live_source["confidence"] == "Not Assessed"
    assert client.get(f"{create_path}/{run_id}", headers=other).status_code == 404

    unavailable_request = client.post(live_path, headers=director, json={
        "url": "https://example.com/unavailable-guidance",
        "purpose": "Truthfully capture an unavailable synthetic source.",
    }).json()
    unavailable_id = unavailable_request["id"]
    unavailable_authorize = f"{create_path}/external-research/{unavailable_id}/authorize"
    unavailable_execute = f"{create_path}/external-research/{unavailable_id}/execute"
    assert client.post(unavailable_authorize, headers=administrator, json={
        "reason": "SYNTHETIC bounded unavailable-source test.", "scope_confirmed": True,
        "external_transmission_authorized": True, "sensitive_data_absent": True,
    }).status_code == 200
    def unavailable_fetch(url, maximum_bytes):
        raise ValueError("SYNTHETIC upstream source unavailable")
    salops_plan_assembly.LIVE_RESEARCH_FETCHER = unavailable_fetch
    unavailable_live = client.post(unavailable_execute, headers=administrator, json={
        "reason": "Record actual unavailable outcome without inventing facts.",
    })
    assert unavailable_live.status_code == 200, unavailable_live.text
    assert unavailable_live.json()["status"] == "Unavailable"
    assert "upstream source unavailable" in unavailable_live.json()["unavailable_reason"]
    unavailable_source_id = unavailable_live.json()["source_id"]
    refreshed_live_bundle = client.get(f"{create_path}/{run_id}", headers=director).json()
    unavailable_source = next(item for item in refreshed_live_bundle["sources"] if item["id"] == unavailable_source_id)
    assert unavailable_source["access_status"] == "Unavailable"
    assert unavailable_source["source_derived_statements"] == []

    feed_request = client.post(live_path, headers=director, json={
        "url": "https://example.com/feed/current.xml",
        "purpose": "Discover current synthetic public-feed entries for separate review.",
    }).json()
    feed_id = feed_request["id"]
    assert client.post(
        f"{create_path}/external-research/{feed_id}/authorize", headers=administrator,
        json={
            "reason": "SYNTHETIC exact public RSS source authorization.",
            "scope_confirmed": True, "external_transmission_authorized": True,
            "sensitive_data_absent": True,
        },
    ).status_code == 200
    salops_plan_assembly.LIVE_RESEARCH_FETCHER = lambda url, maximum_bytes: {
        "status": 200, "content_type": "application/rss+xml",
        "headers": {"content-type": "application/rss+xml; charset=utf-8"},
        "content": b'''<?xml version="1.0"?><rss><channel><title>SYNTHETIC Alerts</title>
        <item><title>Entry One</title><link>https://example.com/bulletins/one</link></item>
        <item><title>Entry Two</title><guid>https://example.com/bulletins/two</guid></item>
        <item><link>https://outside.example.org/blocked</link></item></channel></rss>''',
    }
    feed_live = client.post(
        f"{create_path}/external-research/{feed_id}/execute", headers=owner,
        json={"reason": "Parse the separately authorized feed without visiting entries."},
    )
    assert feed_live.status_code == 200, feed_live.text
    feed_result = feed_live.json()
    assert feed_result["status"] == "Accessed" and feed_result["content_type"] == "application/rss+xml"
    assert "SYNTHETIC Alerts" in feed_result["content_text"] and "Entry One" in feed_result["content_text"]
    assert feed_result["discovered_links"] == [
        "https://example.com/bulletins/one", "https://example.com/bulletins/two",
    ]
    feed_source = next(
        item for item in client.get(f"{create_path}/{run_id}", headers=director).json()["sources"]
        if item["id"] == feed_result["source_id"]
    )
    assert feed_source["source_derived_statements"] == []
    assert feed_source["reliability"] == "Not Assessed" and feed_source["confidence"] == "Not Assessed"

    api_request = client.post(live_path, headers=director, json={
        "url": "https://example.com/api/current.json",
        "purpose": "Discover source links returned by an exact authorized public API endpoint.",
    }).json()
    api_id = api_request["id"]
    assert client.post(
        f"{create_path}/external-research/{api_id}/authorize", headers=administrator,
        json={
            "reason": "SYNTHETIC exact public JSON API authorization.",
            "scope_confirmed": True, "external_transmission_authorized": True,
            "sensitive_data_absent": True,
        },
    ).status_code == 200
    salops_plan_assembly.LIVE_RESEARCH_FETCHER = lambda url, maximum_bytes: {
        "status": 200, "content_type": "application/json",
        "headers": {"content-type": "application/json; charset=utf-8"},
        "content": json.dumps({
            "title": "SYNTHETIC Public API",
            "records": [
                {"url": "/api/bulletins/one"},
                {"links": [{"href": "https://example.com/api/bulletins/two"}]},
                {"url": "https://outside.example.org/blocked"},
                {"description": "https://example.com/not-a-link-field"},
            ],
        }).encode("utf-8"),
    }
    api_live = client.post(
        f"{create_path}/external-research/{api_id}/execute", headers=owner,
        json={"reason": "Parse the authorized API response without following returned links."},
    )
    assert api_live.status_code == 200, api_live.text
    api_result = api_live.json()
    assert api_result["status"] == "Accessed" and api_result["content_type"] == "application/json"
    assert "SYNTHETIC Public API" in api_result["content_text"]
    assert api_result["discovered_links"] == [
        "https://example.com/api/bulletins/one", "https://example.com/api/bulletins/two",
    ]
    api_source = next(
        item for item in client.get(f"{create_path}/{run_id}", headers=director).json()["sources"]
        if item["id"] == api_result["source_id"]
    )
    assert api_source["source_derived_statements"] == []
    assert api_source["reliability"] == "Not Assessed" and api_source["confidence"] == "Not Assessed"

    search_path = f"{create_path}/{run_id}/external-search"
    assert client.post(search_path, headers=member, json={
        "query": "synthetic continuity guidance", "purpose": "Member cannot initiate search.",
    }).status_code == 403
    assert client.post(search_path, headers=director, json={
        "query": "x", "purpose": "Reject an underspecified query.",
    }).status_code == 422
    searched = client.post(search_path, headers=director, json={
        "query": "synthetic severe weather continuity 2026",
        "purpose": "Discover current public sources for separate analyst collection.",
    })
    assert searched.status_code == 200, searched.text
    search_request = searched.json()
    search_id = search_request["id"]
    assert search_request["adapter_type"] == "Public JSON Search"
    assert search_request["status"] == "Pending Human Authorization"
    assert search_request["access_status"] == "Not Attempted"
    assert search_request["normalized_url"].startswith("https://example.com/search?q=")
    assert "synthetic+severe+weather+continuity+2026" in search_request["normalized_url"]
    assert client.post(
        f"{create_path}/external-research/{search_id}/authorize", headers=administrator,
        json={
            "reason": "Exact public query and destination approved for transmission.",
            "scope_confirmed": True, "external_transmission_authorized": True,
            "sensitive_data_absent": True,
        },
    ).status_code == 200
    salops_plan_assembly.LIVE_RESEARCH_FETCHER = lambda url, maximum_bytes: {
        "status": 200, "content_type": "application/json",
        "headers": {"content-type": "application/json"},
        "content": json.dumps({
            "query": "synthetic severe weather continuity 2026",
            "results": [
                {"title": "SYNTHETIC Result One", "url": "https://example.com/search/result-one"},
                {"title": "Outside Scope", "url": "https://outside.example.org/result-two"},
            ],
        }).encode("utf-8"),
    }
    search_live = client.post(
        f"{create_path}/external-research/{search_id}/execute", headers=owner,
        json={"reason": "Execute the separately authorized exact public search."},
    )
    assert search_live.status_code == 200, search_live.text
    search_result = search_live.json()
    assert search_result["status"] == "Accessed"
    assert search_result["adapter_type"] == "Public JSON Search"
    assert search_result["discovered_links"] == ["https://example.com/search/result-one"]
    search_source = next(
        item for item in client.get(f"{create_path}/{run_id}", headers=director).json()["sources"]
        if item["id"] == search_result["source_id"]
    )
    assert search_source["source_derived_statements"] == []

    hostile_request = client.post(live_path, headers=director, json={
        "url": "https://example.com/feed/hostile.xml",
        "purpose": "Verify prohibited XML declarations fail closed.",
    }).json()
    hostile_id = hostile_request["id"]
    assert client.post(
        f"{create_path}/external-research/{hostile_id}/authorize", headers=administrator,
        json={
            "reason": "SYNTHETIC parser-hardening validation.", "scope_confirmed": True,
            "external_transmission_authorized": True, "sensitive_data_absent": True,
        },
    ).status_code == 200
    salops_plan_assembly.LIVE_RESEARCH_FETCHER = lambda url, maximum_bytes: {
        "status": 200, "content_type": "application/xml",
        "headers": {"content-type": "application/xml"},
        "content": b'<!DOCTYPE rss [<!ENTITY probe "blocked">]><rss><title>&probe;</title></rss>',
    }
    hostile_live = client.post(
        f"{create_path}/external-research/{hostile_id}/execute", headers=owner,
        json={"reason": "Confirm the authorized hostile XML sample fails closed."},
    )
    assert hostile_live.status_code == 200, hostile_live.text
    assert hostile_live.json()["status"] == "Unavailable"
    assert "prohibited" in hostile_live.json()["unavailable_reason"].lower()
    assert hostile_live.json()["discovered_links"] == []

    cost_path = f"{create_path}/{run_id}/research-cost-envelopes"
    forged_cost = client.post(cost_path, headers=director, json={
        "estimated_chat_ai_cost_cents": 400, "estimated_human_cost_cents": 9000,
        "maximum_authorized_cost_cents": 9400, "scope_basis": "SYNTHETIC bounded planning research.",
        "status": "Authorized", "creates_charge": True,
    })
    assert forged_cost.status_code == 422
    underfunded = client.post(cost_path, headers=director, json={
        "estimated_chat_ai_cost_cents": 400, "estimated_human_cost_cents": 9000,
        "maximum_authorized_cost_cents": 9000, "scope_basis": "SYNTHETIC bounded planning research.",
    })
    assert underfunded.status_code == 422
    cost = client.post(cost_path, headers=director, json={
        "currency": "USD", "estimated_chat_ai_cost_cents": 400,
        "estimated_human_cost_cents": 9000, "external_data_allowance_cents": 500,
        "partner_allowance_cents": 0, "other_direct_allowance_cents": 100,
        "maximum_authorized_cost_cents": 10000,
        "scope_basis": "SYNTHETIC bounded plan research, source capture, analysis, and human review.",
        "commercial_reference": "SYNTHETIC-ESTIMATE-001",
    })
    assert cost.status_code == 200, cost.text
    envelope = cost.json()["envelope"]
    envelope_id = envelope["id"]
    assert envelope["status"] == "Draft" and len(envelope["content_sha256"]) == 64
    assert cost.json()["creates_charge"] is False and cost.json()["creates_invoice"] is False
    usage_path = f"/api/salops/preparedness/plan-assembly/research-cost-envelopes/{envelope_id}/usage"
    usage_payload = {
        "category": "Chat / AI", "provider_tool": "SYNTHETIC model",
        "task_reference": "SYNTHETIC-RESEARCH-TASK-001", "metered_units": {"input": 100},
        "measurement_status": "Actual Metered", "amount_cents": 125,
        "occurred_at": "2026-09-07T20:00:00Z",
        "recording_basis": "SYNTHETIC provider receipt.",
    }
    assert client.post(usage_path, headers=director, json=usage_payload).status_code == 409
    assert client.post(usage_path, headers=member, json=usage_payload).status_code == 403
    authorized = client.post(
        f"/api/salops/preparedness/plan-assembly/research-cost-envelopes/{envelope_id}/authorize",
        headers=director, json={"reason": "SYNTHETIC exact internal delivery-cost authorization."},
    )
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["envelope"]["status"] == "Authorized"
    assert authorized.json()["envelope"]["creates_customer_price"] is False
    used = client.post(usage_path, headers=director, json=usage_payload)
    assert used.status_code == 200, used.text
    assert used.json()["recognized_cost_cents"] == 125
    assert used.json()["actual_metered_cost_cents"] == 125
    assert used.json()["remaining_authorized_cost_cents"] == 9875
    exceeds = dict(usage_payload, amount_cents=276, task_reference="SYNTHETIC-OVER-COMPONENT")
    over = client.post(usage_path, headers=director, json=exceeds)
    assert over.status_code == 409 and "new governed envelope" in over.text
    no_partner = dict(usage_payload, category="Approved Partner", amount_cents=1,
                      task_reference="SYNTHETIC-UNAUTHORIZED-PARTNER")
    assert client.post(usage_path, headers=director, json=no_partner).status_code == 409
    revised_cost = client.post(cost_path, headers=director, json={
        "estimated_chat_ai_cost_cents": 500, "estimated_human_cost_cents": 9000,
        "external_data_allowance_cents": 500, "partner_allowance_cents": 500,
        "other_direct_allowance_cents": 100, "maximum_authorized_cost_cents": 10600,
        "scope_basis": "SYNTHETIC governed change envelope adding bounded partner eligibility.",
        "commercial_reference": "SYNTHETIC-ESTIMATE-CHANGE-001",
    })
    assert revised_cost.status_code == 200, revised_cost.text
    revised_id = revised_cost.json()["envelope"]["id"]
    revised_authorized = client.post(
        f"/api/salops/preparedness/plan-assembly/research-cost-envelopes/{revised_id}/authorize",
        headers=director, json={"reason": "SYNTHETIC separately approved change envelope."},
    )
    assert revised_authorized.status_code == 200, revised_authorized.text
    cost_history = client.get(f"{create_path}/{run_id}", headers=director).json()["research_cost_envelopes"]
    assert [item["envelope"]["status"] for item in cost_history] == ["Superseded", "Authorized"]
    assert cost_history[0]["envelope"]["content_sha256"] == envelope["content_sha256"]
    assert cost_history[0]["recognized_cost_cents"] == 125
    assert client.post(usage_path, headers=director, json=usage_payload).status_code == 409

    upload = client.post(
        "/api/materials/upload", headers=director,
        files={"file": ("synthetic-guidance.txt", b"SYNTHETIC current authority guidance and communications dependency evidence", "text/plain")},
        data={
            "title": "SYNTHETIC authoritative research capture",
            "material_kind": "Web Capture", "source_origin": "Authorized external research",
            "source_locator": "https://example.invalid/synthetic-authority-guidance",
            "sensitivity": "Standard", "purpose_tags": '["planning","synthetic"]',
            "description": "Synthetic governed source for plan-assembly acceptance.",
            "recording_authority_basis": "Synthetic test authorization.",
        },
    )
    assert upload.status_code == 200, upload.text
    material_id = upload.json()["id"]

    accessed_path = f"{create_path}/{run_id}/sources"
    missing_material = client.post(accessed_path, headers=director, json={
        "source_kind": "External Research", "access_status": "Accessed",
        "locator": "https://example.invalid/source", "citation": "Synthetic source",
        "source_summary": "Synthetic summary without governed material.",
    })
    assert missing_material.status_code == 422
    unavailable_facts = client.post(accessed_path, headers=director, json={
        "source_kind": "External Research", "access_status": "Unavailable",
        "unavailable_reason": "Source was unavailable in this synthetic run.",
        "source_derived_statements": [{"state": "Reported Information", "statement": "Forged fact"}],
    })
    assert unavailable_facts.status_code == 422
    automated_verified = client.post(accessed_path, headers=director, json={
        "source_kind": "External Research", "access_status": "Accessed",
        "locator": "https://example.invalid/source", "citation": "Synthetic source",
        "governed_material_id": material_id, "source_summary": "Synthetic source summary.",
        "source_derived_statements": [{"state": "Verified Fact", "statement": "Client-forged verification"}],
    })
    assert automated_verified.status_code == 422

    accessed = client.post(accessed_path, headers=director, json={
        "source_kind": "External Research", "access_status": "Accessed",
        "locator": "https://example.invalid/synthetic-authority-guidance",
        "citation": "SYNTHETIC authority guidance, accessed for governed acceptance",
        "governed_material_id": material_id,
        "search_or_collection_method": "Authorized source retrieval and governed capture",
        "source_summary": "The synthetic source reports a changed external communications dependency.",
        "source_derived_statements": [{
            "state": "Reported Information",
            "statement": "The external communications dependency changed after plan approval.",
        }],
        "reliability": "Authoritative synthetic source", "confidence": "High",
    })
    assert accessed.status_code == 200, accessed.text
    source_id = accessed.json()["id"]
    assert accessed.json()["accessed_at"]
    unavailable = client.post(accessed_path, headers=director, json={
        "source_kind": "Approved Partner Return", "access_status": "Partner Needed",
        "unavailable_reason": "No external transmission or partner cost was authorized.",
        "search_or_collection_method": "Partner need identified; no contact initiated.",
    })
    assert unavailable.status_code == 200, unavailable.text
    assert unavailable.json()["accessed_at"] == ""
    assert unavailable.json()["source_derived_statements"] == []

    question = client.post(f"{create_path}/{run_id}/questions", headers=director, json={
        "target_type": "Protected Member",
        "question": "What alternate communications capability is currently approved and available?",
        "purpose": "Resolve the unsupported continuity assumption without inventing client policy.",
        "requested_method": "Document request and authorized interview",
        "related_section_keys": ["communications", "continuity"], "priority": "High",
    })
    assert question.status_code == 200, question.text
    question_id = question.json()["id"]
    assert question.json()["status"] == "Open"
    answer = client.post(f"{create_path}/{run_id}/questions/{question_id}/answer", headers=director, json={
        "response_summary": "Protected Member reports an alternate system; operational validation remains required.",
        "response_source_ref": f"material:{material_id}",
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["status"] == "Answered"

    for status in ("Collecting", "Drafting"):
        advanced = client.post(f"{create_path}/{run_id}/advance", headers=director, json={
            "status": status, "reason": f"SYNTHETIC gate to {status}; source distinctions preserved.",
        })
        assert advanced.status_code == 200, advanced.text

    unknown_source = client.post(f"{create_path}/{run_id}/sections", headers=director, json={
        "section_key": "communications", "title": "Emergency Communications",
        "content": "Unsupported reference must fail.", "source_refs": ["pas_missing"],
    })
    assert unknown_source.status_code == 422
    forged_section_fact = client.post(f"{create_path}/{run_id}/sections", headers=director, json={
        "section_key": "communications", "title": "Emergency Communications",
        "content": "Automated draft cannot create a verified fact.", "source_refs": [source_id],
        "epistemic_items": [{"state": "Verified Fact", "statement": "Forged", "source_refs": [source_id]}],
    })
    assert forged_section_fact.status_code == 422
    section = client.post(f"{create_path}/{run_id}/sections", headers=director, json={
        "section_key": "communications", "title": "Emergency Communications",
        "content": "Use the approved primary notification path. The alternate path requires human authority and validation before adoption.",
        "source_refs": [source_id],
        "epistemic_items": [
            {"state": "Reported Information", "statement": "The external dependency changed.", "source_refs": [source_id]},
            {"state": "Assumption", "statement": "The proposed alternate may support essential notification.", "source_refs": [source_id]},
        ],
        "unsupported_assumptions": ["Alternate-system endurance has not been validated."],
        "known_unknowns": ["Member authority for activation remains unresolved."],
        "dependencies": ["Primary and alternate communications providers"],
        "alternate_capabilities": ["Proposed alternate system; pending human approval"],
        "capability_gaps": ["No validated communications-loss exercise"],
        "change_rationale": "Current source conflicts with the approved plan dependency assumption.",
        "human_authority_required": True,
    })
    assert section.status_code == 200, section.text
    assert section.json()["support_status"] == "Needs Human Authority"
    assert section.json()["section_version"] == 1

    submit = client.post(f"{create_path}/{run_id}/submit", headers=director, json={
        "completion_statement": "Bounded synthetic first-draft revision completed for human review; unresolved authority and validation needs remain explicit.",
        "contradictions": ["Approved plan assumes an unchanged external communications dependency."],
        "missing_authorities": ["Protected Member activation authority for alternate communications."],
        "unresolved_dependencies": ["Alternate provider endurance and restoration priority."],
        "affected_sections": ["communications", "continuity"],
        "proposed_training_actions": ["Train designated communications alternates after approval."],
        "proposed_exercise_actions": ["Conduct a communications-loss drill."],
        "proposed_validation_actions": ["Validate endurance and restoration assumptions."],
        "proposed_reassessment_actions": [
            "Reassess the communications capability and related priority after current evidence is reviewed."
        ],
        "change_rationale": "Actually accessed governed source indicates a material dependency change.",
    })
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "Submitted for Human Review"
    assert len(submit.json()["content_sha256"]) == 64
    premature = client.post(f"{create_path}/{run_id}/revision-recommendations", headers=director, json={
        "material_change_summary": "Premature", "recommendation": "Must fail before qualification.",
    })
    assert premature.status_code == 409

    review = client.post(f"{create_path}/{run_id}/review", headers=director, json={
        "decision": "Human Reviewed",
        "reason": "Salus reviewer challenged sources, assumptions, authority gaps, and proposed validation actions.",
    })
    assert review.status_code == 200, review.text
    qualify = client.post(f"{create_path}/{run_id}/qualify", headers=director, json={
        "reason": "Human-qualified as a bounded planning product and revision recommendation basis; not approved or released.",
    })
    assert qualify.status_code == 200, qualify.text
    assert qualify.json()["status"] == "Qualified"

    recommendation = client.post(f"{create_path}/{run_id}/revision-recommendations", headers=director, json={
        "material_change_summary": "The communications dependency changed after approval and may invalidate the continuity assumption.",
        "recommendation": "Prepare a separate proposed plan version for governed review; retain the approved version until replacement is authorized.",
    })
    assert recommendation.status_code == 200, recommendation.text
    rec = recommendation.json()
    assert rec["status"] == "Pending Salus Review"
    assert rec["approved_plan_preserved"] is True
    assert rec["creates_plan_version"] is False and rec["creates_release"] is False
    assert rec["creates_authority"] is False and rec["creates_charge"] is False
    rec_review = client.post(
        f"{create_path}/revision-recommendations/{rec['id']}/review", headers=director,
        json={
            "decision": "Accepted for Drafting",
            "reason": "Authorize preparation of a separate draft only; no approved plan replacement or release.",
        },
    )
    assert rec_review.status_code == 200, rec_review.text
    assert rec_review.json()["status"] == "Accepted for Drafting"
    assert rec_review.json()["creates_plan_version"] is False

    candidate_path = f"{create_path}/{run_id}/version-candidates"
    forged_candidate = client.post(candidate_path, headers=director, json={
        "rationale": "Attempt to forge plan authority.",
        "revision_recommendation_id": rec["id"], "status": "Accepted",
        "creates_plan_version": True, "creates_release": True,
    })
    assert forged_candidate.status_code == 422
    candidate = client.post(candidate_path, headers=director, json={
        "rationale": "Freeze the exact qualified, source-grounded proposal for separate review.",
        "revision_recommendation_id": rec["id"],
    })
    assert candidate.status_code == 200, candidate.text
    frozen = candidate.json()
    candidate_id = frozen["id"]
    assert frozen["status"] == "Draft Candidate"
    assert frozen["suggested_plan_version"] == 2
    assert frozen["immutable_content"] is True and frozen["approved_plan_preserved"] is True
    assert frozen["creates_plan_version"] is False and frozen["creates_release"] is False
    assert frozen["creates_authority"] is False and frozen["creates_charge"] is False
    assert len(frozen["candidate_sha256"]) == 64
    assert frozen["candidate_snapshot"]["baseline"]["version"] == 1
    assert frozen["candidate_snapshot"]["authority_effect"]["creates_release"] is False
    assert frozen["diff_manifest"][0]["section_key"] == "communications"
    assert frozen["diff_manifest"][0]["change"] == "Added"
    assert source_id in frozen["diff_manifest"][0]["source_refs"]
    assert any("endurance" in item.lower() for item in frozen["unresolved_items"])
    assert client.post(candidate_path, headers=director, json={
        "rationale": "Duplicate must fail.", "revision_recommendation_id": rec["id"],
    }).status_code == 409
    assert client.post(candidate_path, headers=member, json={
        "rationale": "Member must not create candidates.", "revision_recommendation_id": rec["id"],
    }).status_code == 403

    premature_accept = client.post(
        f"{create_path}/version-candidates/{candidate_id}/accept", headers=director,
        json={"reason": "Acceptance before review must fail."},
    )
    assert premature_accept.status_code == 409
    candidate_review = client.post(
        f"{create_path}/version-candidates/{candidate_id}/review", headers=director,
        json={"decision": "Candidate Reviewed", "reason": "Reviewed the exact frozen content, provenance, diff, unknowns, and authority flags."},
    )
    assert candidate_review.status_code == 200, candidate_review.text
    assert candidate_review.json()["status"] == "Candidate Reviewed"
    assert candidate_review.json()["candidate_sha256"] == frozen["candidate_sha256"]
    accepted_candidate = client.post(
        f"{create_path}/version-candidates/{candidate_id}/accept", headers=director,
        json={"reason": "Accept only as input to a future governed plan revision; no replacement or release."},
    )
    assert accepted_candidate.status_code == 200, accepted_candidate.text
    assert accepted_candidate.json()["status"] == "Accepted for Plan Revision"
    assert accepted_candidate.json()["creates_plan_version"] is False
    assert accepted_candidate.json()["creates_release"] is False

    materialize_path = f"{create_path}/version-candidates/{candidate_id}/materialize-draft"
    forged_materialization = client.post(materialize_path, headers=director, json={
        "reason": "Attempt to forge plan release.", "status": "Approved", "creates_release": True,
    })
    assert forged_materialization.status_code == 422
    assert client.post(materialize_path, headers=member, json={
        "reason": "Protected Member must not materialize an internal plan candidate.",
    }).status_code == 403
    assert client.post(materialize_path, headers=other, json={
        "reason": "Other tenant must not access the candidate.",
    }).status_code == 404
    materialized = client.post(materialize_path, headers=director, json={
        "reason": "Create a separate Draft from the accepted immutable candidate for normal Salus review; preserve the Approved baseline.",
    })
    assert materialized.status_code == 200, materialized.text
    materialization = materialized.json()
    draft_plan_id = materialization["draft_plan_id"]
    assert materialization["status"] == "Draft Materialized"
    assert materialization["draft_plan_version"] == 2
    assert materialization["candidate_sha256"] == frozen["candidate_sha256"]
    assert materialization["approved_plan_preserved"] is True
    assert materialization["creates_plan_version"] is True
    assert materialization["creates_release"] is False
    assert materialization["creates_authority"] is False
    assert materialization["creates_charge"] is False
    assert len(materialization["draft_plan_sha256"]) == 64
    assert materialization["draft_plan_snapshot"]["id"] == draft_plan_id
    assert materialization["draft_plan_snapshot"]["status"] == "Draft"
    assert materialization["draft_plan_snapshot"]["version"] == 2
    assert materialization["draft_plan_snapshot"]["communications"] == section.json()["content"]
    assert materialization["draft_plan_snapshot"]["commercial_treatment"] == "Not Determined"
    draft_bundle = client.get(f"/api/salops/preparedness/plans/{draft_plan_id}", headers=director)
    assert draft_bundle.status_code == 200
    assert draft_bundle.json()["events"][0]["event_type"] == "Materialize Separate Draft"
    assert client.get(f"/api/salops/preparedness/plans/{draft_plan_id}", headers=member).status_code == 403
    assert client.post(materialize_path, headers=director, json={
        "reason": "Duplicate materialization must fail.",
    }).status_code == 409
    listed_materializations = client.get("/api/salops/preparedness/plan-materializations", headers=director)
    assert listed_materializations.status_code == 200
    assert listed_materializations.json()[0]["draft_plan_id"] == draft_plan_id
    assert client.get("/api/salops/preparedness/plan-materializations", headers=member).status_code == 403
    assert client.get("/api/salops/preparedness/plan-materializations", headers=other).json() == []
    preserved_after_materialization = client.get(
        f"/api/salops/preparedness/plans/{plan_id}", headers=director,
    ).json()["plan"]
    assert preserved_after_materialization == approved
    materialized_bundle = client.get(f"{create_path}/{run_id}", headers=director).json()
    assert materialized_bundle["plan_materializations"][0]["draft_plan_id"] == draft_plan_id
    successor = materialized_bundle["plan_successor_governance"][0]
    materialization_id = materialization["id"]
    assert successor["materialization_id"] == materialization_id
    assert successor["status"] == "Pending Review"
    assert successor["creates_release"] is False
    assert successor["creates_authority"] is False and successor["creates_charge"] is False

    bypass_transition = client.post(
        f"/api/salops/preparedness/plans/{draft_plan_id}/transition", headers=director,
        json={"status": "Reviewed", "reason": "Attempt to bypass controlled successor governance."},
    )
    assert bypass_transition.status_code == 409 and "controlled review" in bypass_transition.text
    bypass_revision = client.post(
        f"/api/salops/preparedness/plans/{draft_plan_id}/revise", headers=director,
        json={"reason": "Attempt to escape controlled successor governance."},
    )
    assert bypass_revision.status_code == 409 and "controlled review" in bypass_revision.text

    successor_path = f"/api/salops/preparedness/plan-materializations/{materialization_id}"
    assert client.post(f"{successor_path}/approve", headers=owner, json={
        "reason": "Premature approval must fail.",
    }).status_code == 409
    assert client.post(f"{successor_path}/release", headers=administrator, json={
        "reason": "Premature release must fail.", "authority_confirmed": True,
        "disclosure_authorized": True, "unresolved_items_accepted": True,
    }).status_code == 409
    assert client.post(f"{successor_path}/review", headers=member, json={
        "reason": "Protected Member cannot perform an internal Salus review.",
    }).status_code == 403
    reviewed_successor = client.post(f"{successor_path}/review", headers=director, json={
        "reason": "Reviewed the exact candidate lineage, source manifest, unresolved items, and proposed plan text.",
    })
    assert reviewed_successor.status_code == 200, reviewed_successor.text
    assert reviewed_successor.json()["status"] == "Human Reviewed"
    assert len(reviewed_successor.json()["review_snapshot_sha256"]) == 64
    assert client.get(f"/api/salops/preparedness/plans/{draft_plan_id}", headers=member).status_code == 403

    approved_successor = client.post(f"{successor_path}/approve", headers=owner, json={
        "reason": "Approve this exact successor proposal for a separate release decision; no disclosure yet.",
    })
    assert approved_successor.status_code == 200, approved_successor.text
    assert approved_successor.json()["status"] == "Approved for Release"
    assert approved_successor.json()["creates_release"] is False
    assert len(approved_successor.json()["approval_snapshot_sha256"]) == 64
    assert client.get(f"/api/salops/preparedness/plans/{draft_plan_id}", headers=member).status_code == 403
    missing_release_authority = client.post(f"{successor_path}/release", headers=administrator, json={
        "reason": "Missing explicit authority acknowledgements must fail.",
    })
    assert missing_release_authority.status_code == 422

    released_successor = client.post(f"{successor_path}/release", headers=administrator, json={
        "reason": "Release the separately reviewed and approved successor for authorized Protected Member use.",
        "authority_confirmed": True, "disclosure_authorized": True,
        "unresolved_items_accepted": True,
    })
    assert released_successor.status_code == 200, released_successor.text
    release_record = released_successor.json()
    released_plan_id = release_record["released_plan_id"]
    assert release_record["status"] == "Released" and released_plan_id != draft_plan_id
    assert release_record["creates_release"] is True
    assert release_record["creates_authority"] is False and release_record["creates_charge"] is False
    assert release_record["approved_baseline_preserved"] is True
    assert release_record["authority_confirmed"] is True
    assert release_record["disclosure_authorized"] is True
    assert release_record["unresolved_items_accepted"] is True
    assert len(release_record["released_plan_sha256"]) == 64
    released_bundle = client.get(f"/api/salops/preparedness/plans/{released_plan_id}", headers=member)
    assert released_bundle.status_code == 200, released_bundle.text
    assert released_bundle.json()["plan"]["status"] == "Approved"
    assert released_bundle.json()["plan"]["version"] == 2
    assert released_bundle.json()["plan"]["communications"] == section.json()["content"]
    assert client.post(f"{successor_path}/release", headers=administrator, json={
        "reason": "Duplicate release must fail.", "authority_confirmed": True,
        "disclosure_authorized": True, "unresolved_items_accepted": True,
    }).status_code == 409
    preserved_after_release = client.get(
        f"/api/salops/preparedness/plans/{plan_id}", headers=director,
    ).json()["plan"]
    assert preserved_after_release == approved
    released_run_bundle = client.get(f"{create_path}/{run_id}", headers=director).json()
    assert released_run_bundle["plan_successor_governance"][0]["status"] == "Released"
    handoffs = released_run_bundle["preparedness_handoffs"]
    assert len(handoffs) == 4
    assert {item["handoff_type"] for item in handoffs} == {
        "Training", "Exercise", "Validation", "SalTHIRA Reassessment",
    }
    assert all(item["status"] == "Pending Human Review" for item in handoffs)
    assert all(len(item["proposal_sha256"]) == 64 for item in handoffs)
    assert all(item["released_plan_id"] == released_plan_id for item in handoffs)
    assert all(not item["creates_schedule"] and not item["creates_release"]
               and not item["creates_authority"] and not item["creates_charge"] for item in handoffs)
    handoff_list_path = "/api/salops/preparedness/plan-handoffs"
    assert client.get(handoff_list_path, headers=member).status_code == 403
    assert client.get(handoff_list_path, headers=other).json() == []
    assert client.post(
        f"{handoff_list_path}/{handoffs[0]['id']}/materialize", headers=owner,
        json={"reason": "Premature materialization must fail."},
    ).status_code == 409
    forged_handoff_review = client.post(
        f"{handoff_list_path}/{handoffs[0]['id']}/review", headers=director,
        json={"decision": "Accepted", "reason": "Attempt to forge effects.", "creates_charge": True},
    )
    assert forged_handoff_review.status_code == 422
    assessment_conn = salcapa_runtime.core.db()
    try:
        assessment_before_handoffs = dict(
            assessment_conn.execute("SELECT * FROM assessments WHERE id=1").fetchone()
        )
    finally:
        assessment_conn.close()
    materialized_handoffs = []
    for handoff in handoffs:
        review_path = f"{handoff_list_path}/{handoff['id']}/review"
        assert client.post(review_path, headers=member, json={
            "decision": "Accepted", "reason": "Member cannot accept an internal work proposal.",
        }).status_code == 403
        accepted = client.post(review_path, headers=director, json={
            "decision": "Accepted",
            "reason": "Accept the exact released-plan recommendation as input to a separate internal preparedness record.",
        })
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["status"] == "Accepted"
        materialized = client.post(
            f"{handoff_list_path}/{handoff['id']}/materialize", headers=owner,
            json={"reason": "Create the bounded internal record; downstream lifecycle decisions remain separate."},
        )
        assert materialized.status_code == 200, materialized.text
        item = materialized.json()
        assert item["status"] == "Materialized" and item["target_record_id"]
        assert item["target_record_type"] in {
            "Training", "Exercise", "Corrective Action", "Reassessment Trigger",
        }
        assert item["creates_schedule"] is False and item["creates_charge"] is False
        materialized_handoffs.append(item)
        assert client.post(
            f"{handoff_list_path}/{handoff['id']}/materialize", headers=owner,
            json={"reason": "Duplicate materialization must fail."},
        ).status_code == 409
    training_handoff = next(item for item in materialized_handoffs if item["target_record_type"] == "Training")
    exercise_handoff = next(item for item in materialized_handoffs if item["target_record_type"] == "Exercise")
    validation_handoff = next(item for item in materialized_handoffs if item["target_record_type"] == "Corrective Action")
    reassessment_handoff = next(
        item for item in materialized_handoffs if item["target_record_type"] == "Reassessment Trigger"
    )
    training_rows = client.get("/api/salops/preparedness/training", headers=director).json()
    assert next(item for item in training_rows if item["id"] == training_handoff["target_record_id"])["status"] == "Draft"
    exercise_rows = client.get("/api/salops/preparedness/exercises", headers=director).json()
    assert next(item for item in exercise_rows if item["id"] == exercise_handoff["target_record_id"])["status"] == "Planned"
    corrective_rows = client.get("/api/salops/preparedness/corrective-actions", headers=director).json()
    validation_record = next(item for item in corrective_rows if item["id"] == validation_handoff["target_record_id"])
    assert validation_record["status"] == "Open" and validation_record["reexercise_required"] is True
    reassessment_conn = salcapa_runtime.core.db()
    try:
        trigger = dict(reassessment_conn.execute(
            "SELECT * FROM reassessment_triggers WHERE id=?",
            (int(reassessment_handoff["target_record_id"]),),
        ).fetchone())
        assessment_after_handoffs = dict(
            reassessment_conn.execute("SELECT * FROM assessments WHERE id=1").fetchone()
        )
    finally:
        reassessment_conn.close()
    assert trigger["source"] == "SalOPS Preparedness"
    assert trigger["trigger_type"] == "Preparedness Plan Reassessment Recommendation"
    assert trigger["affected_record_type"] == "assessment" and trigger["affected_record_id"] == 1
    assert trigger["status"] == "Open" and released_plan_id in trigger["description"]
    assert assessment_after_handoffs == assessment_before_handoffs
    assert training_handoff["target_record_id"] not in {
        item["id"] for item in client.get("/api/salops/preparedness/training", headers=member).json()
    }
    assert exercise_handoff["target_record_id"] not in {
        item["id"] for item in client.get("/api/salops/preparedness/exercises", headers=member).json()
    }
    assert validation_handoff["target_record_id"] not in {
        item["id"] for item in client.get("/api/salops/preparedness/corrective-actions", headers=member).json()
    }

    impact_path = f"/api/salops/preparedness/plans/{plan_id}/impact-detections"
    forged_impact = client.post(impact_path, headers=director, json={
        "source_record_type": "Governed Material", "source_record_id": str(material_id),
        "change_summary": "Attempt to forge materiality and lifecycle.",
        "status": "Material Change", "materiality_decision": "Material Change",
        "revision_recommended": True, "creates_plan_version": True,
    })
    assert forged_impact.status_code == 422
    detected = client.post(impact_path, headers=director, json={
        "source_record_type": "Governed Material", "source_record_id": str(material_id),
        "change_summary": "The governed communications source may invalidate the approved plan dependency assumption.",
        "suggested_affected_sections": ["communications", "dependencies"],
        "detection_reasons": ["The source describes a changed external communications dependency."],
        "research_questions": ["What exact communications and continuity provisions require revision?"],
        "known_unknowns": ["Alternate communications endurance remains unvalidated."],
    })
    assert detected.status_code == 200, detected.text
    impact = detected.json()
    impact_id = impact["id"]
    assert impact["status"] == "Potential Impact"
    assert impact["materiality_decision"] == "Not Reviewed"
    assert impact["server_detected"] is True and impact["revision_recommended"] is False
    assert impact["approved_plan_preserved"] is True
    assert impact["creates_plan_version"] is False and impact["creates_release"] is False
    assert impact["creates_authority"] is False and impact["creates_charge"] is False
    assert impact["source_snapshot"]["id"] == material_id
    assert len(impact["source_sha256"]) == 64
    assert impact["suggested_affected_sections"] == ["communications", "dependencies"]
    assert client.post(impact_path, headers=director, json={
        "source_record_type": "Governed Material", "source_record_id": str(material_id),
        "change_summary": "Exact duplicate must fail.",
    }).status_code == 409
    assert client.post(impact_path, headers=member, json={
        "source_record_type": "Governed Material", "source_record_id": str(material_id),
        "change_summary": "Protected Member must not create an internal detection.",
    }).status_code == 403
    assert client.get("/api/salops/preparedness/plan-impact-detections", headers=member).status_code == 403
    assert client.get("/api/salops/preparedness/plan-impact-detections", headers=other).json() == []

    missing_recommendation = client.post(
        f"/api/salops/preparedness/plan-impact-detections/{impact_id}/review", headers=director,
        json={"decision": "Material Change", "reason": "Materiality confirmed by human review."},
    )
    assert missing_recommendation.status_code == 422
    impact_review = client.post(
        f"/api/salops/preparedness/plan-impact-detections/{impact_id}/review", headers=director,
        json={
            "decision": "Material Change",
            "reason": "Salus reviewed the governed source against the exact Approved plan and confirmed material impact.",
            "confirmed_affected_sections": ["communications", "dependencies"],
            "revision_recommendation": "Research and prepare a separate proposed plan revision; preserve the Approved version until authorized replacement.",
        },
    )
    assert impact_review.status_code == 200, impact_review.text
    reviewed_impact = impact_review.json()
    assert reviewed_impact["status"] == "Revision Recommended"
    assert reviewed_impact["materiality_decision"] == "Material Change"
    assert reviewed_impact["revision_recommended"] is True
    assert reviewed_impact["assembly_run_id"]
    assert reviewed_impact["creates_plan_version"] is False
    impact_run = client.get(
        f"{create_path}/{reviewed_impact['assembly_run_id']}", headers=director,
    )
    assert impact_run.status_code == 200, impact_run.text
    impact_run_data = impact_run.json()["run"]
    assert impact_run_data["status"] == "Research Planning"
    assert impact_run_data["base_plan_id"] == plan_id and impact_run_data["base_plan_version"] == 1
    assert impact_run_data["affected_sections"] == ["communications", "dependencies"]
    assert f"plan-impact:{impact_id}" in impact_run_data["internal_record_refs"]
    assert impact_run.json()["plan_impact_detections"][0]["id"] == impact_id
    assert client.post(
        f"/api/salops/preparedness/plan-impact-detections/{impact_id}/review", headers=director,
        json={"decision": "No Material Change", "reason": "Second decision must fail."},
    ).status_code == 409

    still_approved = client.get(f"/api/salops/preparedness/plans/{plan_id}", headers=director).json()["plan"]
    assert still_approved["status"] == "Approved" and still_approved["version"] == 1
    bundle = client.get(f"{create_path}/{run_id}", headers=director)
    assert bundle.status_code == 200, bundle.text
    assert len(bundle.json()["sources"]) == 8
    assert len(bundle.json()["external_research_requests"]) == 6
    assert len(bundle.json()["sections"]) == 1
    assert len(bundle.json()["revision_recommendations"]) == 1
    assert len(bundle.json()["version_candidates"]) == 1
    assert len(bundle.json()["research_cost_envelopes"]) == 2
    assert bundle.json()["research_cost_envelopes"][0]["recognized_cost_cents"] == 125
    assert len(bundle.json()["events"]) >= 13

    backup_conn = salcapa_runtime.core.db()
    try:
        records = salcapa_runtime.core.collect_tenant_records(backup_conn, 1)
    finally:
        backup_conn.close()
    for table in (
        "salops_plan_assembly_runs", "salops_plan_assembly_sources",
        "salops_plan_external_research_requests", "salops_plan_external_research_events",
        "salops_plan_assembly_questions", "salops_plan_assembly_sections",
        "salops_plan_revision_recommendations", "salops_plan_version_candidates",
        "salops_plan_materializations",
        "salops_plan_successor_governance", "salops_plan_successor_events",
        "salops_plan_preparedness_handoffs", "salops_plan_preparedness_handoff_events",
        "salops_plan_research_cost_envelopes", "salops_plan_research_cost_usage",
        "salops_plan_impact_detections", "salops_plan_impact_events",
        "salops_plan_assembly_events",
    ):
        assert table in records and records[table], table
    tampered = {key: list(value) for key, value in records.items()}
    tampered["salops_plan_assembly_runs"] = [dict(records["salops_plan_assembly_runs"][0], tenant_id=2)]
    errors = salcapa_runtime.core.validate_records(tampered, 1)
    assert any("crosses the tenant boundary" in error for error in errors)
    tampered_research = {key: [dict(row) for row in value] for key, value in records.items()}
    tampered_research["salops_plan_external_research_requests"][0]["policy_snapshot_json"] = '{}'
    errors = salcapa_runtime.core.validate_records(tampered_research, 1)
    assert any("external research request" in error and "integrity" in error for error in errors)
    tampered_research_lineage = {key: [dict(row) for row in value] for key, value in records.items()}
    tampered_research_lineage["salops_plan_external_research_requests"][0]["source_id"] = "pas_missing"
    errors = salcapa_runtime.core.validate_records(tampered_research_lineage, 1)
    assert any("external research request" in error and "source lineage" in error for error in errors)
    tampered_discovery = {key: [dict(row) for row in value] for key, value in records.items()}
    accessed_research = next(
        row for row in tampered_discovery["salops_plan_external_research_requests"]
        if row["status"] == "Accessed"
    )
    accessed_research["discovered_links_json"] = '["http://127.0.0.1/private"]'
    errors = salcapa_runtime.core.validate_records(tampered_discovery, 1)
    assert any("external research request" in error and "unsafe discovered link" in error for error in errors)
    tampered_candidate = {key: [dict(row) for row in value] for key, value in records.items()}
    tampered_candidate["salops_plan_version_candidates"][0]["candidate_snapshot_json"] = '{}'
    errors = salcapa_runtime.core.validate_records(tampered_candidate, 1)
    assert any("failed integrity verification" in error for error in errors)
    tampered_impact = {key: [dict(row) for row in value] for key, value in records.items()}
    tampered_impact["salops_plan_impact_detections"][0]["source_snapshot_json"] = '{}'
    errors = salcapa_runtime.core.validate_records(tampered_impact, 1)
    assert any("plan-impact detection" in error and "integrity" in error for error in errors)
    tampered_materialization = {key: [dict(row) for row in value] for key, value in records.items()}
    tampered_materialization["salops_plan_materializations"][0]["draft_plan_snapshot_json"] = '{}'
    errors = salcapa_runtime.core.validate_records(tampered_materialization, 1)
    assert any("plan materialization" in error and "integrity" in error for error in errors)
    tampered_cost = {key: [dict(row) for row in value] for key, value in records.items()}
    tampered_cost["salops_plan_research_cost_envelopes"][0]["maximum_authorized_cost_cents"] = 1
    errors = salcapa_runtime.core.validate_records(tampered_cost, 1)
    assert any("research-cost envelope" in error and ("integrity" in error or "maximum" in error) for error in errors)
    tampered_usage = {key: [dict(row) for row in value] for key, value in records.items()}
    tampered_usage["salops_plan_research_cost_usage"][0]["creates_charge"] = 1
    errors = salcapa_runtime.core.validate_records(tampered_usage, 1)
    assert any("research-cost usage" in error and "commercial effect" in error for error in errors)
    tampered_handoff = {key: [dict(row) for row in value] for key, value in records.items()}
    tampered_handoff["salops_plan_preparedness_handoffs"][0]["proposal_snapshot_json"] = '{}'
    errors = salcapa_runtime.core.validate_records(tampered_handoff, 1)
    assert any("preparedness handoff" in error and "integrity" in error for error in errors)
    tampered_handoff_target = {key: [dict(row) for row in value] for key, value in records.items()}
    reassessment_backup = next(
        row for row in tampered_handoff_target["salops_plan_preparedness_handoffs"]
        if row["target_record_type"] == "Reassessment Trigger"
    )
    reassessment_backup["target_record_id"] = "999999999"
    errors = salcapa_runtime.core.validate_records(tampered_handoff_target, 1)
    assert any("preparedness handoff" in error and "target lineage" in error for error in errors)

    print("SALOPS_AUTONOMOUS_PLAN_ASSEMBLY_PASS")


if __name__ == "__main__":
    main()
