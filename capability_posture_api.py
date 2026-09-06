"""FastAPI attachment for SalCAPA Protected Member capability posture.

Routes are registered only when the host application supplies its assessment
authorization callback. This prevents a parallel authorization model from
bypassing Salus THIRA Command tenant and assessment access controls.
"""
from __future__ import annotations

import inspect
from typing import Callable

from fastapi import APIRouter, HTTPException, Request

from capability_posture_source import build_capability_measures
from capability_posture_store import (
    dashboard_payload,
    posture_trend,
    save_posture_snapshot,
)
from database import connect_database


def build_router(authorize_assessment: Callable, connection_factory=connect_database) -> APIRouter:
    """Create routes using the host application's authorization callback.

    authorize_assessment(request, assessment_id, write=False) must return a
    mapping containing tenant_id and, for writes, user_name/actor. It may be
    synchronous or asynchronous.
    """
    router = APIRouter(prefix="/api/capability-posture", tags=["capability-posture"])

    async def context(request: Request, assessment_id: int, write: bool = False) -> dict:
        result = authorize_assessment(request, assessment_id, write=write)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, dict) or not result.get("tenant_id"):
            raise HTTPException(status_code=403, detail="Assessment access denied")
        return result

    @router.get("/{assessment_id}")
    async def get_posture(assessment_id: int, request: Request):
        ctx = await context(request, assessment_id, write=False)
        conn = connection_factory()
        try:
            return dashboard_payload(conn, tenant_id=int(ctx["tenant_id"]), assessment_id=assessment_id)
        finally:
            conn.close()

    @router.get("/{assessment_id}/trend")
    async def get_posture_trend(assessment_id: int, request: Request, limit: int = 24):
        ctx = await context(request, assessment_id, write=False)
        conn = connection_factory()
        try:
            return {
                "assessment_id": assessment_id,
                "trend": posture_trend(
                    conn,
                    tenant_id=int(ctx["tenant_id"]),
                    assessment_id=assessment_id,
                    limit=limit,
                ),
            }
        finally:
            conn.close()

    @router.post("/{assessment_id}/refresh")
    async def refresh_posture(assessment_id: int, request: Request):
        ctx = await context(request, assessment_id, write=True)
        conn = connection_factory()
        try:
            row = conn.execute(
                "SELECT organization,name FROM assessments WHERE id=? AND tenant_id=?",
                (assessment_id, int(ctx["tenant_id"])),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Assessment not found")
            protected_member_name = str(row["organization"] or row["name"] or "Protected Member")
            capabilities = build_capability_measures(conn, assessment_id)
            snapshot_id = save_posture_snapshot(
                conn,
                tenant_id=int(ctx["tenant_id"]),
                assessment_id=assessment_id,
                protected_member_name=protected_member_name,
                capabilities=capabilities,
                created_by=str(ctx.get("user_name") or ctx.get("actor") or "authorized-user"),
            )
            payload = dashboard_payload(conn, tenant_id=int(ctx["tenant_id"]), assessment_id=assessment_id)
            payload["refreshed"] = True
            payload["snapshot_id"] = snapshot_id
            return payload
        finally:
            conn.close()

    return router


def register_routes(app, authorize_assessment: Callable, connection_factory=connect_database) -> None:
    app.include_router(build_router(authorize_assessment, connection_factory))
