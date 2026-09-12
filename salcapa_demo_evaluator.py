"""Read-only Salus evaluator view of governed fictional demonstrations.

This view never changes the authenticated tenant, impersonates a fictional
persona, or grants lifecycle authority. It exposes only the exact Issue #124
fixture set to explicitly authorized Salus roles.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from salcapa_demo_fixtures import (
    DEMONSTRATION_ACKNOWLEDGEMENT,
    ENVIRONMENTS,
    FIXTURE_AUTHORITY,
    FIXTURE_VERSION,
)


EVALUATOR_ROLES = frozenset({
    "System Administrator",
    "Assessment Director",
    "Lead Assessor",
    "SME Assessor",
    "Program Owner",
})
EXPECTED_KEYS = tuple(environment.key for environment in ENVIRONMENTS)
ENVIRONMENT_BY_KEY = {environment.key: environment for environment in ENVIRONMENTS}


def _require_evaluator(core: Any, request: Request) -> dict[str, Any]:
    core.require(request, "read")
    context = core.auth_context(request)
    if context["role"] not in EVALUATOR_ROLES:
        core.security_event(
            request,
            "DEMONSTRATION_EVALUATOR_ACCESS_DENIED",
            "Medium",
            f"role={context['role']}",
        )
        raise HTTPException(
            403,
            "Demonstration Environments are limited to authorized Salus evaluators.",
        )
    return context


def _rows(conn: Any, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params)]


def _count(conn: Any, query: str, params: tuple[Any, ...]) -> int:
    return int(conn.execute(query, params).fetchone()["c"])


def _environment_view(conn: Any, tenant: dict[str, Any]) -> dict[str, Any]:
    tenant_id = int(tenant["id"])
    key = str(tenant["fixture_key"])
    definition = ENVIRONMENT_BY_KEY[key]
    assessments = _rows(
        conn,
        """SELECT id,name,organization,status,purpose,mission
           FROM assessments
           WHERE tenant_id=? AND fixture_key<>''
           ORDER BY id""",
        (tenant_id,),
    )
    intelligence = _rows(
        conn,
        """SELECT title,status,credibility,validation_status,operational_significance
           FROM intel_findings WHERE tenant_id=? ORDER BY id""",
        (tenant_id,),
    )
    coordination = _rows(
        conn,
        """SELECT subject,status,assigned_contact_summary
           FROM cop_coordination_threads WHERE tenant_id=? ORDER BY id""",
        (tenant_id,),
    )
    decisions = _rows(
        conn,
        """SELECT title,status,decision,due_at
           FROM cop_decision_requests WHERE tenant_id=? ORDER BY id""",
        (tenant_id,),
    )
    operations = _rows(
        conn,
        """SELECT title,priority,status
           FROM ops_requests WHERE tenant_id=? ORDER BY id""",
        (tenant_id,),
    )
    reports = _rows(
        conn,
        """SELECT report_type,status,created_at,released_at
           FROM report_versions WHERE tenant_id=? ORDER BY id DESC""",
        (tenant_id,),
    )
    assessment_params = (tenant_id,)
    return {
        "key": key,
        "name": tenant["name"],
        "sector": definition.sector,
        "purpose": definition.purpose,
        "label": tenant["display_label"],
        "fixture_version": tenant["fixture_version"],
        "status": tenant["status"],
        "assessments": assessments,
        "intelligence": intelligence,
        "coordination": coordination,
        "decisions": decisions,
        "operations": operations,
        "reports": reports,
        "counts": {
            "qualified_intelligence": _count(
                conn,
                "SELECT COUNT(*) c FROM intel_findings WHERE tenant_id=? AND status='Qualified'",
                assessment_params,
            ),
            "threats_and_hazards": _count(
                conn,
                """SELECT COUNT(*) c FROM threats h
                   JOIN assessments a ON a.id=h.assessment_id WHERE a.tenant_id=?""",
                assessment_params,
            ),
            "capabilities": _count(
                conn,
                """SELECT COUNT(*) c FROM capabilities c
                   JOIN assessments a ON a.id=c.assessment_id WHERE a.tenant_id=?""",
                assessment_params,
            ),
            "evidence_records": _count(
                conn,
                """SELECT COUNT(*) c FROM evidence e
                   JOIN assessments a ON a.id=e.assessment_id WHERE a.tenant_id=?""",
                assessment_params,
            ),
            "improvement_actions": _count(
                conn,
                """SELECT COUNT(*) c FROM improvements i
                   JOIN assessments a ON a.id=i.assessment_id WHERE a.tenant_id=?""",
                assessment_params,
            ),
            "coordination_threads": len(coordination),
            "decision_requests": len(decisions),
            "operations_requests": len(operations),
            "report_versions": len(reports),
        },
    }


def register_demo_evaluator(core: Any) -> None:
    """Register one read-only, exact-fixture evaluator endpoint."""

    async def list_demo_environments(request: Request):
        context = _require_evaluator(core, request)
        conn = core.db()
        try:
            marks = ",".join("?" for _ in EXPECTED_KEYS)
            tenants = _rows(
                conn,
                f"""SELECT id,name,status,display_label,fixture_key,fixture_version
                    FROM tenants
                    WHERE environment_kind='Fictional Demonstration'
                      AND fixture_key IN ({marks})
                    ORDER BY id""",
                EXPECTED_KEYS,
            )
            environments = [_environment_view(conn, tenant) for tenant in tenants]
        finally:
            conn.close()
        core.security_event(
            request,
            "DEMONSTRATION_EVALUATOR_VIEWED",
            "Info",
            "fixture_keys=" + ",".join(item["key"] for item in environments),
        )
        return {
            "label": DEMONSTRATION_ACKNOWLEDGEMENT,
            "authority": FIXTURE_AUTHORITY,
            "fixture_version": FIXTURE_VERSION,
            "access_mode": "Read-only Salus evaluation",
            "authenticated_tenant_id": int(context["tenant_id"]),
            "environment_count": len(environments),
            "environments": environments,
            "boundaries": [
                "The authenticated tenant and role remain server controlled.",
                "This view does not impersonate a fictional Protected Member persona.",
                "No approval, release, validation, decision, or operational authority is represented.",
                "Actions remain unavailable in this read-only evaluation view.",
            ],
        }

    core.app.add_api_route(
        "/api/demonstration-environments",
        list_demo_environments,
        methods=["GET"],
        include_in_schema=False,
    )

