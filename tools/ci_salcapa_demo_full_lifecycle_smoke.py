#!/usr/bin/env python3
"""Exercise the complete Issue #124 journey without representing real human approval."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ["SALUS_DB_BACKEND"] = "sqlite"
os.environ["SALUS_DB_PATH"] = str(pathlib.Path(WORKSPACE.name) / "issue-124-full-lifecycle.db")
os.environ["SALUS_BACKUP_DIR"] = str(pathlib.Path(WORKSPACE.name) / "backups")
os.environ["SALUS_LOCAL_STORAGE_DIR"] = str(pathlib.Path(WORKSPACE.name) / "attachments")
os.environ["SALUS_AUTH_MODE"] = "prototype"
os.environ["SALUS_SEED_DEMO"] = "0"
os.environ["SALUS_ENV"] = "development"
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

import app  # noqa: E402
from salcapa_demo_fixtures import (  # noqa: E402
    DEMONSTRATION_ACKNOWLEDGEMENT,
    ENVIRONMENTS,
    FIXTURE_AUTHORITY,
    register_demo_fixture_contract,
    seed_demo_environments,
)


SIMULATION_NOTICE = (
    "Fictional demonstration acceptance simulation only; no real human review, "
    "approval, authority, policy, or operational decision is represented."
)


def post(client: TestClient, path: str, headers: dict[str, str], payload: dict | None = None, status: int = 200):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == status, (path, response.status_code, response.text)
    return response.json() if response.content else None


def headers(tenant_id: int, role: str, responsibility: str) -> dict[str, str]:
    return {
        "X-Salus-Tenant": str(tenant_id),
        "X-Salus-Role": role,
        "X-Salus-User": f"Fictional demonstration {responsibility} - simulated acceptance test",
        "X-Salus-Clearance": "Highly Sensitive",
    }


def main() -> None:
    register_demo_fixture_contract(app)
    conn = app.db()
    try:
        result = seed_demo_environments(
            conn,
            environment="development",
            authority=FIXTURE_AUTHORITY,
            acknowledgement=DEMONSTRATION_ACKNOWLEDGEMENT,
            now=app.now,
        )
    finally:
        conn.close()
    assert result["environment_count"] == 3
    assert result["persona_count"] == 24

    client = TestClient(app.app)
    released_reports: list[tuple[int, int]] = []

    for environment in ENVIRONMENTS:
        conn = app.db()
        tenant = conn.execute(
            "SELECT * FROM tenants WHERE fixture_key=?", (environment.key,)
        ).fetchone()
        assert tenant is not None
        tenant_id = int(tenant["id"])
        assessment = conn.execute(
            "SELECT * FROM assessments WHERE tenant_id=? AND fixture_key=?",
            (tenant_id, f"{environment.key}:baseline-assessment"),
        ).fetchone()
        if assessment is None:
            assessment = conn.execute(
                "SELECT * FROM assessments WHERE tenant_id=? AND fixture_key<>''",
                (tenant_id,),
            ).fetchone()
        assert assessment is not None
        assessment_id = int(assessment["id"])
        finding = conn.execute(
            "SELECT * FROM intel_findings WHERE tenant_id=? AND assessment_id=?",
            (tenant_id, assessment_id),
        ).fetchone()
        improvement = conn.execute(
            "SELECT * FROM improvements WHERE assessment_id=?", (assessment_id,)
        ).fetchone()
        decision_request = conn.execute(
            "SELECT * FROM cop_decision_requests WHERE tenant_id=? AND assessment_id=?",
            (tenant_id, assessment_id),
        ).fetchone()
        operation = conn.execute(
            "SELECT * FROM ops_requests WHERE tenant_id=? AND assessment_id=?",
            (tenant_id, assessment_id),
        ).fetchone()
        thread = conn.execute(
            "SELECT * FROM cop_coordination_threads WHERE tenant_id=? AND assessment_id=?",
            (tenant_id, assessment_id),
        ).fetchone()
        assert all((finding, improvement, decision_request, operation, thread))
        finding_id = int(finding["id"])
        improvement_id = int(improvement["id"])
        decision_request_id = int(decision_request["id"])
        operation_id = int(operation["id"])
        thread_id = int(thread["id"])
        conn.close()

        analyst = headers(tenant_id, "SME Assessor", "Salus Intelligence Analyst")
        reviewer = headers(tenant_id, "Lead Assessor", "Salus Lead Assessor")
        director = headers(tenant_id, "Assessment Director", "Salus Assessment Director")
        operations = headers(tenant_id, "Program Owner", "Salus Operations Coordinator")
        member = headers(tenant_id, "Client Executive", "Protected Member Executive Sponsor")
        viewer = headers(tenant_id, "Protected Member Viewer", "Protected Member Read-only User")

        assert client.get("/api/salintel/findings", headers=member).json() == []
        qualified = post(
            client,
            f"/api/salintel/findings/{finding_id}/qualify",
            analyst,
            {
                "relevance": "Relevant",
                "credibility": "Medium",
                "validation_status": "Qualified",
                "operational_significance": (
                    "The fictional condition warrants review of the associated "
                    "assessment, coordination need, and validation plan."
                ),
            },
        )
        assert qualified["status"] == "Qualified"
        handoff = post(client, f"/api/salintel/findings/{finding_id}/send-to-salthira", analyst)
        assert handoff["status"] == "Sent to SalTHIRA"

        recorded = post(
            client,
            f"/api/salcapa/decision-requests/{decision_request_id}/decide",
            member,
            {
                "decision": "Approve with Conditions",
                "rationale": SIMULATION_NOTICE,
                "conditions": (
                    "Limit work to the fictional demonstration and preserve all "
                    "human authority gates."
                ),
                "authorized_amount": 0,
            },
        )
        assert recorded["status"] == "Decision Recorded"
        assert "simulated acceptance test" in recorded["decided_by"]

        authorized = post(
            client,
            f"/api/salops/requests/{operation_id}/decision",
            member,
            {
                "decision": "Authorized",
                "reason": SIMULATION_NOTICE,
                "assigned_to": "Fictional demonstration Salus Operations Coordinator",
            },
        )
        assert authorized["status"] == "Authorized"
        completed = post(
            client,
            f"/api/salops/requests/{operation_id}/complete",
            operations,
            {
                "result_summary": (
                    "Demonstration action completed. Lesson observed: alternate "
                    "coordination methods must be confirmed before a disruption. "
                    + SIMULATION_NOTICE
                )
            },
        )
        assert completed["operation"]["status"] == "Completed"
        assert completed["reassessment_trigger_id"]

        lesson = post(
            client,
            "/api/reassessment_triggers",
            director,
            {
                "assessment_id": assessment_id,
                "source": "Fictional Demonstration Walkthrough",
                "trigger_type": "Lesson Learned",
                "description": (
                    "Review alternate coordination dependencies and incorporate "
                    "the demonstrated information gap into the next validation cycle."
                ),
                "severity": "Moderate",
                "affected_record_type": "improvement",
                "affected_record_id": improvement_id,
                "status": "Open",
                "assigned_to": "Salus Assessment Director",
                "due_date": "",
                "resolution": "",
            },
        )
        assert lesson["status"] == "Open"

        reviewed = post(
            client,
            f"/api/assessments/{assessment_id}/reassessment-review",
            member,
            {
                "next_reassessment_date": "2027-03-31",
                "review_outcome": (
                    "The fictional walkthrough identified a validation need and "
                    "established the next review date. " + SIMULATION_NOTICE
                ),
            },
        )
        assert reviewed["reassessment_lifecycle_status"] == "Current"
        assert reviewed["reassessment_date"] == "2027-03-31"
        assert "simulated acceptance test" in reviewed["last_reassessment_review_by"]

        post(
            client,
            f"/api/salcapa/coordination/threads/{thread_id}/messages",
            operations,
            {
                "body": (
                    "Walkthrough result recorded: completed action, lesson learned, "
                    "open validation need, and scheduled reassessment. " + SIMULATION_NOTICE
                ),
                "audience": "Shared",
            },
        )
        closed = post(
            client,
            f"/api/salcapa/coordination/threads/{thread_id}/close",
            director,
            {"reason": "The fictional walkthrough coordination objective is complete. " + SIMULATION_NOTICE},
        )
        assert closed["status"] == "Closed"

        assert post(client, f"/api/reports/{assessment_id}", viewer, {}, 403) is not None
        report = post(client, f"/api/reports/{assessment_id}", director, {})
        assert report["status"] == "Draft"
        report_id = int(report["id"])
        assert client.get(
            f"/api/reports/versions/{report_id}/snapshot", headers=member
        ).status_code == 404
        for status, actor_headers in (
            ("Reviewed", reviewer),
            ("Approved", member),
            ("Released", director),
        ):
            transitioned = post(
                client,
                f"/api/reports/versions/{report_id}/transition",
                actor_headers,
                {
                    "status": status,
                    "reason": f"{status} in a fictional acceptance simulation. {SIMULATION_NOTICE}",
                },
            )
            assert transitioned["status"] == status

        member_reports = client.get(f"/api/reports/{assessment_id}", headers=member)
        assert member_reports.status_code == 200
        assert [item["id"] for item in member_reports.json()] == [report_id]
        snapshot = client.get(f"/api/reports/versions/{report_id}/snapshot", headers=member)
        assert snapshot.status_code == 200
        assert snapshot.headers["X-Salus-Report-Status"] == "Released"
        assert client.get(f"/api/report/{assessment_id}/executive.csv", headers=member).status_code == 200
        assert client.get(f"/api/report/{assessment_id}/executive.html", headers=member).status_code == 200

        cop = client.get("/api/salcapa/common-operating-picture", headers=member)
        assert cop.status_code == 200
        payload = cop.json()
        assert any(item["id"] == report_id for item in payload["see"]["deliverables"])
        assert any(item["id"] == operation_id and item["status"] == "Completed" for item in payload["see"]["operations"])
        assert all(item["status"] != "Open" for item in payload["coordinate"]["threads"] if item["id"] == thread_id)
        released_reports.append((tenant_id, report_id))

    assert len(released_reports) == 3
    first_tenant, _ = released_reports[0]
    _, second_report = released_reports[1]
    cross_tenant_member = headers(
        first_tenant, "Client Executive", "Protected Member Executive Sponsor"
    )
    assert client.get(
        f"/api/reports/versions/{second_report}/snapshot", headers=cross_tenant_member
    ).status_code == 404

    conn = app.db()
    assert conn.execute(
        "SELECT COUNT(*) c FROM intel_findings f JOIN tenants t ON t.id=f.tenant_id "
        "WHERE t.fixture_key<>'' AND f.status='Sent to SalTHIRA'"
    ).fetchone()["c"] == 3
    assert conn.execute(
        "SELECT COUNT(*) c FROM ops_requests o JOIN tenants t ON t.id=o.tenant_id "
        "WHERE t.fixture_key<>'' AND o.status='Completed'"
    ).fetchone()["c"] == 3
    assert conn.execute(
        "SELECT COUNT(*) c FROM reassessment_triggers r JOIN assessments a ON a.id=r.assessment_id "
        "JOIN tenants t ON t.id=a.tenant_id WHERE t.fixture_key<>'' "
        "AND r.source='Fictional Demonstration Walkthrough' AND r.trigger_type='Lesson Learned'"
    ).fetchone()["c"] == 3
    assert conn.execute(
        "SELECT COUNT(*) c FROM report_versions r JOIN tenants t ON t.id=r.tenant_id "
        "WHERE t.fixture_key<>'' AND r.status='Released'"
    ).fetchone()["c"] == 3
    assert conn.execute(
        "SELECT COUNT(*) c FROM cop_coordination_threads c JOIN tenants t ON t.id=c.tenant_id "
        "WHERE t.fixture_key<>'' AND c.status='Closed'"
    ).fetchone()["c"] == 3
    conn.close()
    print("SALCAPA_ISSUE_124_FULL_LIFECYCLE_WALKTHROUGH_PASS")


if __name__ == "__main__":
    main()
