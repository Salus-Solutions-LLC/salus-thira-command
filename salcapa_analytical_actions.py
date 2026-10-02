"""Assessment-scoped SAL-D055 recommendation and Member-decision register.

This register cannot authorize an operation, release a report, or validate proof.
Those transitions remain in their existing governed workflows.
"""
from __future__ import annotations

import json
import secrets
from typing import Any, Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


SCHEMA = """
CREATE TABLE IF NOT EXISTS salcapa_analytical_actions (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  assessment_id INTEGER NOT NULL,
  action_key TEXT NOT NULL,
  level INTEGER NOT NULL,
  product TEXT NOT NULL,
  state TEXT NOT NULL,
  revision_no INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(tenant_id, assessment_id, action_key)
);
CREATE INDEX IF NOT EXISTS idx_salcapa_analytical_actions_scope
  ON salcapa_analytical_actions(tenant_id, assessment_id, state);
CREATE TABLE IF NOT EXISTS salcapa_analytical_action_revisions (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  action_id TEXT NOT NULL,
  revision_no INTEGER NOT NULL,
  content_json TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(tenant_id, action_id, revision_no)
);
CREATE TABLE IF NOT EXISTS salcapa_analytical_action_events (
  id TEXT PRIMARY KEY,
  tenant_id INTEGER NOT NULL,
  action_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  detail_json TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_salcapa_analytical_action_events
  ON salcapa_analytical_action_events(tenant_id, action_id, created_at);
"""


class ActionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=5, max_length=1000)
    owner_role: str = Field(min_length=2, max_length=160)
    decision_window: str = Field(min_length=2, max_length=160)
    dependency_or_stop: str = Field(min_length=2, max_length=1000)
    completion_proof: str = Field(min_length=2, max_length=1000)


class ActionContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    report_reference: str = Field(min_length=3, max_length=200)
    source_references: list[str] = Field(min_length=1, max_length=30)
    working_assumption: str = Field(min_length=10, max_length=4000)
    alternative: str = Field(min_length=5, max_length=4000)
    recommendation_narrative: str = Field(min_length=20, max_length=8000)
    checklist: list[ActionStep] = Field(min_length=1, max_length=30)
    contradiction_note: str = Field(default="", max_length=4000)
    next_review: str = Field(min_length=3, max_length=160)


class ActionCreate(ActionContent):
    assessment_id: int = Field(gt=0)
    action_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,79}$")
    level: Literal[1, 2, 3]
    product: Literal["SalINTEL", "SalTHIRA", "SalOPS", "SalCAPA"]


class MemberDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["Member-selected", "Deferred", "Rejected"]
    decision_reference: str = Field(min_length=3, max_length=300)
    reason: str = Field(min_length=5, max_length=2000)


def _key(prefix: str) -> str:
    return prefix + "-" + secrets.token_hex(12).upper()


def register_analytical_actions(app: Any, core: dict[str, Any]) -> None:
    db, now = core["db"], core["now"]
    tenant_id, actor = core["tenant_id"], core["actor"]
    require = core["require"]
    salus = core["require_salus_component_authority"]
    member = core["require_protected_member_authority"]
    assessment = core["assessment_row_for_request"]
    audit = core["audit"]

    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    def scoped(conn: Any, request: Request, action_id: str) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM salcapa_analytical_actions WHERE id=? AND tenant_id=?",
            (action_id, tenant_id(request)),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Recommendation not found")
        item = dict(row)
        assessment(request, int(item["assessment_id"]))
        return item

    def view(conn: Any, item: dict[str, Any]) -> dict[str, Any]:
        revision = conn.execute(
            "SELECT content_json FROM salcapa_analytical_action_revisions "
            "WHERE tenant_id=? AND action_id=? AND revision_no=?",
            (item["tenant_id"], item["id"], item["revision_no"]),
        ).fetchone()
        return {**item, "content": json.loads(revision["content_json"]),
                "operational_authorization": "Not recorded by this register",
                "proof_status": "Unverified here"}

    @app.get("/api/salcapa/analytical-actions")
    def list_actions(request: Request, assessment_id: int):
        require(request, "read")
        assessment(request, assessment_id)
        conn = db()
        try:
            rows = conn.execute(
                "SELECT * FROM salcapa_analytical_actions WHERE tenant_id=? "
                "AND assessment_id=? ORDER BY action_key",
                (tenant_id(request), assessment_id),
            ).fetchall()
            return [view(conn, dict(row)) for row in rows]
        finally:
            conn.close()

    @app.get("/api/salcapa/analytical-actions/{action_id}")
    def get_action(action_id: str, request: Request):
        require(request, "read")
        conn = db()
        try:
            item = scoped(conn, request, action_id)
            events = conn.execute(
                "SELECT event_type,detail_json,actor,created_at FROM "
                "salcapa_analytical_action_events WHERE tenant_id=? AND action_id=? "
                "ORDER BY created_at,id",
                (tenant_id(request), action_id),
            ).fetchall()
            return {**view(conn, item), "events": [
                {**dict(event), "detail": json.loads(event["detail_json"])}
                for event in events]}
        finally:
            conn.close()

    @app.post("/api/salcapa/analytical-actions")
    def create_action(payload: ActionCreate, request: Request):
        require(request, "write")
        salus(request, "SalCAPA analytical recommendations")
        assessment(request, payload.assessment_id)
        action_id, created = _key("SAA"), now()
        content = payload.model_dump(exclude={"assessment_id", "action_key", "level", "product"})
        conn = db()
        try:
            exists = conn.execute(
                "SELECT id FROM salcapa_analytical_actions WHERE tenant_id=? "
                "AND assessment_id=? AND action_key=?",
                (tenant_id(request), payload.assessment_id, payload.action_key),
            ).fetchone()
            if exists:
                raise HTTPException(409, "Use the existing recommendation lineage")
            conn.execute(
                "INSERT INTO salcapa_analytical_actions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (action_id, tenant_id(request), payload.assessment_id,
                 payload.action_key, payload.level, payload.product, "Suggested", 1,
                 created, created),
            )
            conn.execute(
                "INSERT INTO salcapa_analytical_action_revisions VALUES(?,?,?,?,?,?,?)",
                (_key("SAAR"), tenant_id(request), action_id, 1,
                 json.dumps(content, ensure_ascii=False), actor(request), created),
            )
            conn.execute(
                "INSERT INTO salcapa_analytical_action_events VALUES(?,?,?,?,?,?,?)",
                (_key("SAAE"), tenant_id(request), action_id, "Suggested",
                 json.dumps({"revision": 1}), actor(request), created),
            )
            audit(conn, "ANALYTICAL_ACTION_SUGGESTED", "salcapa_analytical_action", None,
                  action_id, actor(request))
            conn.commit()
            return view(conn, scoped(conn, request, action_id))
        finally:
            conn.close()

    @app.post("/api/salcapa/analytical-actions/{action_id}/revisions")
    def revise_action(action_id: str, payload: ActionContent, request: Request):
        require(request, "write")
        salus(request, "SalCAPA analytical recommendations")
        conn = db()
        try:
            item = scoped(conn, request, action_id)
            if item["state"] != "Suggested":
                raise HTTPException(409, "A Member decision requires a new governed review before revision")
            number, created = int(item["revision_no"]) + 1, now()
            conn.execute(
                "INSERT INTO salcapa_analytical_action_revisions VALUES(?,?,?,?,?,?,?)",
                (_key("SAAR"), tenant_id(request), action_id, number,
                 payload.model_dump_json(), actor(request), created),
            )
            conn.execute(
                "UPDATE salcapa_analytical_actions SET revision_no=?,updated_at=? "
                "WHERE id=? AND tenant_id=?",
                (number, created, action_id, tenant_id(request)),
            )
            conn.execute(
                "INSERT INTO salcapa_analytical_action_events VALUES(?,?,?,?,?,?,?)",
                (_key("SAAE"), tenant_id(request), action_id, "Revised",
                 json.dumps({"revision": number}), actor(request), created),
            )
            audit(conn, "ANALYTICAL_ACTION_REVISED", "salcapa_analytical_action", None,
                  action_id, actor(request))
            conn.commit()
            return view(conn, scoped(conn, request, action_id))
        finally:
            conn.close()

    @app.post("/api/salcapa/analytical-actions/{action_id}/member-decision")
    def member_decision(action_id: str, payload: MemberDecision, request: Request):
        member(request, "analytical recommendation selection")
        conn = db()
        try:
            item = scoped(conn, request, action_id)
            if item["state"] != "Suggested":
                raise HTTPException(409, "A Member decision is already recorded")
            created = now()
            conn.execute(
                "UPDATE salcapa_analytical_actions SET state=?,updated_at=? "
                "WHERE id=? AND tenant_id=?",
                (payload.decision, created, action_id, tenant_id(request)),
            )
            conn.execute(
                "INSERT INTO salcapa_analytical_action_events VALUES(?,?,?,?,?,?,?)",
                (_key("SAAE"), tenant_id(request), action_id, payload.decision,
                 payload.model_dump_json(), actor(request), created),
            )
            audit(conn, "ANALYTICAL_ACTION_MEMBER_DECISION", "salcapa_analytical_action",
                  None, action_id + ": " + payload.decision, actor(request))
            conn.commit()
            return view(conn, scoped(conn, request, action_id))
        finally:
            conn.close()
