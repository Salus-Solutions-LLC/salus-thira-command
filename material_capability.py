"""Governed universal material records and cross-SalCAPA source links.

This module is registered by app.py after the core authorization and audit helpers exist.
It deliberately keeps original material, processing state, disclosure, and promotion
server-controlled. Derived extraction and analysis are separate governed capabilities.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator


MaterialKind = Literal[
    "Document", "Image", "Map / Geospatial", "Audio", "Video",
    "Recorded Call", "Text", "Structured Data", "Email / Message",
    "Web Capture", "Other",
]
Sensitivity = Literal["Standard", "Restricted", "Sensitive", "Highly Sensitive"]
ProcessingStatus = Literal[
    "Received", "Security Review", "Quarantined", "Ready for Processing",
    "Processing", "Ready for Human Review", "Linked / Promoted", "Rejected",
]
DispositionStatus = Literal["Active", "Disposed"]


class MaterialTransitionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ProcessingStatus
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A documented transition reason is required.")
        return value


class MaterialLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: Literal[
        "assessment", "governed_intake", "evidence", "intel_finding",
        "observation", "threat", "scenario", "capability", "gap",
        "improvement", "decision", "ops_request", "ops_engagement",
        "ops_task", "ops_field_report", "report",
    ]
    target_id: int = Field(gt=0)
    purpose: str = Field(min_length=1, max_length=1000)

    @field_validator("purpose")
    @classmethod
    def normalize_purpose(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A link purpose is required.")
        return value


class MaterialDisclosureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved_for_protected_member: bool
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A disclosure decision reason is required.")
        return value


class MaterialGovernanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retention_until: str | None = Field(default=None, max_length=40)
    legal_hold: bool | None = None
    disposition_status: DispositionStatus | None = None
    sensitivity: Sensitivity | None = None
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A governance reason is required.")
        return value


SCHEMA = """
CREATE TABLE IF NOT EXISTS materials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  record_key TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  material_kind TEXT NOT NULL,
  original_name TEXT NOT NULL,
  stored_name TEXT NOT NULL DEFAULT '',
  content_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  sha256 TEXT NOT NULL,
  source_origin TEXT NOT NULL,
  source_locator TEXT NOT NULL DEFAULT '',
  acquired_at TEXT NOT NULL DEFAULT '',
  ingested_at TEXT NOT NULL,
  uploaded_by TEXT NOT NULL,
  uploaded_by_user_id INTEGER,
  sensitivity TEXT NOT NULL DEFAULT 'Standard',
  purpose_tags_json TEXT NOT NULL DEFAULT '[]',
  description TEXT NOT NULL DEFAULT '',
  recording_authority_basis TEXT NOT NULL DEFAULT '',
  provenance_status TEXT NOT NULL DEFAULT 'Submitted',
  processing_status TEXT NOT NULL DEFAULT 'Received',
  scan_status TEXT NOT NULL DEFAULT '',
  scan_detail TEXT NOT NULL DEFAULT '',
  scanned_at TEXT NOT NULL DEFAULT '',
  retention_until TEXT NOT NULL DEFAULT '',
  legal_hold INTEGER NOT NULL DEFAULT 0,
  disposition_status TEXT NOT NULL DEFAULT 'Active',
  disclosure_status TEXT NOT NULL DEFAULT 'Salus Internal',
  immutable_original INTEGER NOT NULL DEFAULT 1,
  parent_material_id INTEGER,
  derivation_type TEXT NOT NULL DEFAULT '',
  processor TEXT NOT NULL DEFAULT '',
  processor_version TEXT NOT NULL DEFAULT '',
  derived_at TEXT NOT NULL DEFAULT '',
  duplicate_of_material_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
  FOREIGN KEY (duplicate_of_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_materials_tenant_created ON materials(tenant_id,created_at,id);
CREATE INDEX IF NOT EXISTS idx_materials_tenant_hash ON materials(tenant_id,sha256,id);
CREATE INDEX IF NOT EXISTS idx_materials_tenant_processing ON materials(tenant_id,processing_status,disposition_status);
CREATE INDEX IF NOT EXISTS idx_materials_parent ON materials(parent_material_id,id);

CREATE TABLE IF NOT EXISTS material_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  link_key TEXT NOT NULL UNIQUE,
  material_id INTEGER NOT NULL,
  target_type TEXT NOT NULL,
  target_id INTEGER NOT NULL,
  assessment_id INTEGER,
  purpose TEXT NOT NULL,
  linked_by TEXT NOT NULL,
  linked_by_role TEXT NOT NULL,
  linked_at TEXT NOT NULL,
  member_visible INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE,
  FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
  UNIQUE(material_id,target_type,target_id)
);
CREATE INDEX IF NOT EXISTS idx_material_links_material ON material_links(material_id,id);
CREATE INDEX IF NOT EXISTS idx_material_links_target ON material_links(tenant_id,target_type,target_id);

CREATE TABLE IF NOT EXISTS material_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  material_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  from_status TEXT NOT NULL DEFAULT '',
  to_status TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_material_events_material ON material_events(material_id,id);
CREATE INDEX IF NOT EXISTS idx_material_events_tenant_time ON material_events(tenant_id,created_at,id);
"""


TRANSITIONS = {
    "Received": {"Security Review", "Quarantined", "Ready for Processing", "Rejected"},
    "Security Review": {"Quarantined", "Ready for Processing", "Rejected"},
    "Quarantined": {"Security Review", "Rejected"},
    "Ready for Processing": {"Processing", "Rejected"},
    "Processing": {"Ready for Human Review", "Ready for Processing", "Rejected"},
    "Ready for Human Review": {"Ready for Processing", "Linked / Promoted", "Rejected"},
    "Linked / Promoted": {"Ready for Human Review"},
    "Rejected": set(),
}

TARGETS = {
    "assessment": ("assessments", "tenant"),
    "governed_intake": ("governed_intake", "tenant"),
    "evidence": ("evidence", "assessment"),
    "intel_finding": ("intel_findings", "tenant_assessment"),
    "observation": ("observations", "tenant"),
    "threat": ("threats", "assessment"),
    "scenario": ("scenarios", "assessment"),
    "capability": ("capabilities", "assessment"),
    "gap": ("gaps", "assessment"),
    "improvement": ("improvements", "assessment"),
    "decision": ("decisions", "assessment"),
    "ops_request": ("ops_requests", "tenant_assessment"),
    "ops_engagement": ("ops_engagements", "tenant_assessment"),
    "ops_task": ("ops_tasks", "tenant_assessment"),
    "ops_field_report": ("ops_field_reports", "tenant_assessment"),
    "report": ("report_versions", "tenant_assessment"),
}


def register_material_capability(fastapi_app, core: dict) -> None:
    db = core["db"]
    now = core["now"]
    actor = core["actor"]
    role = core["role"]
    tenant_id = core["tenant_id"]
    require = core["require"]
    require_sensitivity = core["require_sensitivity"]
    protected_member_request = core["protected_member_request"]
    require_salus_component_authority = core["require_salus_component_authority"]
    assessment_row_for_request = core["assessment_row_for_request"]
    security_event = core["security_event"]
    safe_filename = core["safe_filename"]
    scan_bytes = core["scan_bytes"]
    storage = core["storage"]
    max_bytes = core["MAX_ATTACHMENT_BYTES"]
    retention_days = core["RETENTION_DEFAULT_DAYS"]
    iso_now_dt = core["_iso_now_dt"]

    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    def _audit(conn, request: Request, action: str, material_id: int, detail: str) -> None:
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) "
            "VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, "material", material_id, detail[:2000], tenant_id(request)),
        )

    def _event(
        conn, request: Request, material_id: int, event_type: str,
        reason: str, from_status: str = "", to_status: str = "",
    ) -> None:
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Material not found")
        conn.execute(
            "INSERT INTO material_events(tenant_id,material_id,event_type,from_status,to_status,"
            "reason,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                row["tenant_id"], material_id, event_type, from_status, to_status, reason,
                json.dumps(dict(row), sort_keys=True, default=str),
                actor(request), role(request), now(),
            ),
        )

    def _can_member_view(row, request: Request) -> bool:
        if row["disclosure_status"] == "Approved for Tenant":
            return True
        if row["disclosure_status"] != "Protected Member Submitted":
            return False
        if role(request) == "Client Executive":
            return True
        return row["uploaded_by"] == actor(request)

    def _material_for_request(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(
                request, "MATERIAL_TENANT_BOUNDARY_VIOLATION", "High",
                f"material_id={material_id}",
            )
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if protected_member_request(request) and not _can_member_view(row, request):
            raise HTTPException(403, "Material is not approved for Protected Member access")
        return row

    def _public_row(row) -> dict:
        value = dict(row)
        value.pop("stored_name", None)
        value.pop("scan_detail", None)
        try:
            value["purpose_tags"] = json.loads(value.pop("purpose_tags_json", "[]"))
        except (TypeError, ValueError):
            value["purpose_tags"] = []
        value["legal_hold"] = bool(value.get("legal_hold"))
        value["immutable_original"] = bool(value.get("immutable_original"))
        return value

    def _parse_tags(raw: str) -> list[str]:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            parsed = [part.strip() for part in str(raw).split(",") if part.strip()]
        if not isinstance(parsed, list):
            raise HTTPException(422, "Purpose tags must be a JSON array or comma-separated list")
        tags = []
        for item in parsed:
            tag = str(item).strip()
            if not tag:
                continue
            if len(tag) > 80:
                raise HTTPException(422, "Purpose tags may not exceed 80 characters")
            if tag not in tags:
                tags.append(tag)
        if len(tags) > 20:
            raise HTTPException(422, "No more than 20 purpose tags are permitted")
        return tags

    def _target_scope(conn, target_type: str, target_id: int, request: Request):
        table, mode = TARGETS[target_type]
        if mode == "assessment":
            row = conn.execute(
                f"SELECT t.id target_id,a.tenant_id,a.id assessment_id FROM {table} t "
                "JOIN assessments a ON a.id=t.assessment_id WHERE t.id=?",
                (target_id,),
            ).fetchone()
        elif mode == "tenant_assessment":
            row = conn.execute(
                f"SELECT id target_id,tenant_id,assessment_id FROM {table} WHERE id=?",
                (target_id,),
            ).fetchone()
        elif table == "assessments":
            row = conn.execute(
                "SELECT id target_id,tenant_id,id assessment_id FROM assessments WHERE id=?",
                (target_id,),
            ).fetchone()
        else:
            row = conn.execute(
                f"SELECT id target_id,tenant_id,NULL assessment_id FROM {table} WHERE id=?",
                (target_id,),
            ).fetchone()
        if not row:
            raise HTTPException(404, "Link target not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(
                request, "MATERIAL_LINK_TENANT_BOUNDARY_VIOLATION", "High",
                f"target_type={target_type}; target_id={target_id}",
            )
            raise HTTPException(403, "Tenant boundary violation")
        assessment_id = row["assessment_id"]
        if assessment_id not in (None, ""):
            assessment_row_for_request(request, int(assessment_id))
        return int(assessment_id) if assessment_id not in (None, "") else None

    @fastapi_app.post("/api/materials/upload")
    async def upload_material(
        request: Request,
        file: UploadFile = File(...),
        title: str = Form(default="", max_length=240),
        material_kind: MaterialKind = Form(default="Other"),
        source_origin: str = Form(default="User submission", max_length=500),
        source_locator: str = Form(default="", max_length=1000),
        acquired_at: str = Form(default="", max_length=40),
        sensitivity: Sensitivity = Form(default="Standard"),
        purpose_tags: str = Form(default="[]", max_length=2000),
        description: str = Form(default="", max_length=6000),
        recording_authority_basis: str = Form(default="", max_length=2000),
    ):
        require(request, "write")
        content = await file.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise HTTPException(413, "Material exceeds 25 MB limit")
        original = safe_filename(file.filename or "material")
        normalized_title = title.strip() or original
        normalized_source = source_origin.strip()
        if not normalized_source:
            raise HTTPException(422, "Source or origin context is required")
        tags = _parse_tags(purpose_tags)
        scan = scan_bytes(content, original)
        if not scan["ok"]:
            security_event(
                request, "MATERIAL_UPLOAD_REJECTED",
                "High" if scan["status"] == "Infected" else "Medium",
                f"{original}: {scan['status']}",
            )
            raise HTTPException(
                422 if scan["status"] == "Infected" else 503,
                f"Upload rejected: {scan['status']}",
            )
        digest = hashlib.sha256(content).hexdigest()
        tid = tenant_id(request)
        conn = db()
        existing = conn.execute(
            "SELECT id,stored_name FROM materials WHERE tenant_id=? AND sha256=? "
            "AND stored_name<>'' AND disposition_status='Active' ORDER BY id LIMIT 1",
            (tid, digest),
        ).fetchone()
        duplicate_id = int(existing["id"]) if existing else None
        stored = (
            existing["stored_name"] if existing else
            f"tenant-{tid}/materials/{digest[:2]}/{digest}_{original}"
        )
        wrote_object = False
        if not existing:
            try:
                storage.put_bytes(stored, content)
                wrote_object = True
            except Exception as exc:
                conn.close()
                security_event(request, "MATERIAL_STORAGE_WRITE_FAILURE", "High", type(exc).__name__)
                raise HTTPException(503, "Material storage unavailable")
        created = now()
        retention_until = (
            (iso_now_dt() + timedelta(days=retention_days))
            .replace(microsecond=0).isoformat().replace("+00:00", "Z")
            if retention_days > 0 else ""
        )
        disclosure = (
            "Protected Member Submitted"
            if protected_member_request(request) else "Salus Internal"
        )
        ctx = core["auth_context"](request)
        try:
            cur = conn.execute(
                "INSERT INTO materials(tenant_id,record_key,title,material_kind,original_name,"
                "stored_name,content_type,size_bytes,sha256,source_origin,source_locator,acquired_at,"
                "ingested_at,uploaded_by,uploaded_by_user_id,sensitivity,purpose_tags_json,description,"
                "recording_authority_basis,provenance_status,processing_status,scan_status,scan_detail,"
                "scanned_at,retention_until,legal_hold,disposition_status,disclosure_status,"
                "immutable_original,parent_material_id,derivation_type,processor,processor_version,"
                "derived_at,duplicate_of_material_id,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tid, "MAT-" + uuid.uuid4().hex, normalized_title, material_kind, original,
                    stored, (file.content_type or "application/octet-stream")[:200],
                    len(content), digest, normalized_source, source_locator.strip(),
                    acquired_at.strip(), created, actor(request), ctx.get("user_id"),
                    sensitivity, json.dumps(tags, separators=(",", ":")), description.strip(),
                    recording_authority_basis.strip(), "Submitted", "Ready for Processing",
                    scan["status"], scan["detail"][:1000], created, retention_until, 0,
                    "Active", disclosure, 1, None, "", "", "", "", duplicate_id,
                    created, created,
                ),
            )
            material_id = int(cur.lastrowid)
            reason = "Original material preserved after successful security scanning."
            if duplicate_id:
                reason += f" Storage deduplicated against material {duplicate_id}."
            _event(conn, request, material_id, "CAPTURED", reason, "Received", "Ready for Processing")
            _audit(conn, request, "MATERIAL_CAPTURED", material_id, f"sha256={digest}; scan={scan['status']}")
            conn.commit()
            row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        except Exception:
            conn.rollback()
            conn.close()
            if wrote_object:
                try:
                    storage.delete(stored)
                except Exception:
                    pass
            raise
        conn.close()
        return _public_row(row)

    @fastapi_app.get("/api/materials/catalog")
    def list_materials(request: Request, limit: int = 200):
        require(request, "read")
        conn = db()
        rows = []
        for row in conn.execute(
            "SELECT m.*,(SELECT COUNT(*) FROM material_links l WHERE l.material_id=m.id) link_count "
            "FROM materials m WHERE m.tenant_id=? ORDER BY m.id DESC LIMIT ?",
            (tenant_id(request), max(1, min(limit, 1000))),
        ):
            if core["SENSITIVITY_LEVELS"].get(row["sensitivity"] or "Standard", 1) > core["clearance_level"](request):
                continue
            if protected_member_request(request) and not _can_member_view(row, request):
                continue
            rows.append(_public_row(row))
        conn.close()
        return rows

    @fastapi_app.get("/api/materials/{material_id}")
    def get_material(material_id: int, request: Request):
        require(request, "read")
        conn = db()
        row = _material_for_request(conn, material_id, request)
        result = _public_row(row)
        if protected_member_request(request):
            result["links"] = []
            result["events"] = []
        else:
            result["links"] = [
                dict(item) for item in conn.execute(
                    "SELECT id,link_key,target_type,target_id,assessment_id,purpose,linked_by,"
                    "linked_by_role,linked_at FROM material_links WHERE material_id=? ORDER BY id",
                    (material_id,),
                )
            ]
            result["events"] = [
                dict(item) for item in conn.execute(
                    "SELECT id,event_type,from_status,to_status,reason,changed_by,changed_by_role,"
                    "created_at FROM material_events WHERE material_id=? ORDER BY id",
                    (material_id,),
                )
            ]
        conn.close()
        return result

    @fastapi_app.get("/api/materials/{material_id}/download")
    def download_material(material_id: int, request: Request):
        require(request, "read")
        conn = db()
        row = _material_for_request(conn, material_id, request)
        if row["disposition_status"] == "Disposed":
            conn.close()
            raise HTTPException(410, "Material has been disposed")
        stored_name = row["stored_name"]
        original_name = row["original_name"]
        expected_hash = row["sha256"]
        content_type = row["content_type"]
        conn.close()
        try:
            data = storage.get_bytes(stored_name)
        except FileNotFoundError:
            raise HTTPException(404, "Stored material missing")
        except Exception as exc:
            security_event(request, "MATERIAL_STORAGE_READ_FAILURE", "High", type(exc).__name__)
            raise HTTPException(503, "Material storage unavailable")
        if hashlib.sha256(data).hexdigest() != expected_hash:
            security_event(
                request, "MATERIAL_HASH_MISMATCH", "Critical",
                f"material_id={material_id}",
            )
            raise HTTPException(409, "Material integrity verification failed")
        conn = db()
        _audit(conn, request, "MATERIAL_DOWNLOADED", material_id, "Content hash verified")
        conn.commit()
        conn.close()
        return Response(
            content=data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename(original_name)}"',
                "X-Content-SHA256": expected_hash,
                "X-Content-Type-Options": "nosniff",
            },
        )

    @fastapi_app.post("/api/materials/{material_id}/transition")
    def transition_material(material_id: int, payload: MaterialTransitionIn, request: Request):
        require(request, "decide")
        require_salus_component_authority(request, "SalCAPA material processing")
        conn = db()
        row = _material_for_request(conn, material_id, request)
        current = row["processing_status"]
        if payload.status not in TRANSITIONS.get(current, set()):
            conn.close()
            raise HTTPException(409, f"Invalid material transition {current} -> {payload.status}")
        changed = now()
        conn.execute(
            "UPDATE materials SET processing_status=?,updated_at=? WHERE id=?",
            (payload.status, changed, material_id),
        )
        _event(conn, request, material_id, "PROCESSING_TRANSITION", payload.reason, current, payload.status)
        _audit(conn, request, "MATERIAL_TRANSITION", material_id, f"{current} -> {payload.status}")
        conn.commit()
        result = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        conn.close()
        return _public_row(result)

    @fastapi_app.post("/api/materials/{material_id}/links")
    def link_material(material_id: int, payload: MaterialLinkIn, request: Request):
        require(request, "decide")
        require_salus_component_authority(request, "SalCAPA material promotion")
        conn = db()
        row = _material_for_request(conn, material_id, request)
        if row["disposition_status"] != "Active":
            conn.close()
            raise HTTPException(409, "Disposed material cannot be linked")
        if row["processing_status"] not in {"Ready for Human Review", "Linked / Promoted"}:
            conn.close()
            raise HTTPException(409, "Material must complete processing and reach human review before linking")
        assessment_id = _target_scope(conn, payload.target_type, payload.target_id, request)
        existing = conn.execute(
            "SELECT * FROM material_links WHERE material_id=? AND target_type=? AND target_id=?",
            (material_id, payload.target_type, payload.target_id),
        ).fetchone()
        if existing:
            conn.close()
            return dict(existing)
        linked_at = now()
        cur = conn.execute(
            "INSERT INTO material_links(tenant_id,link_key,material_id,target_type,target_id,"
            "assessment_id,purpose,linked_by,linked_by_role,linked_at,member_visible) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id(request), "MLK-" + uuid.uuid4().hex, material_id,
                payload.target_type, payload.target_id, assessment_id, payload.purpose,
                actor(request), role(request), linked_at, 0,
            ),
        )
        if row["processing_status"] != "Linked / Promoted":
            conn.execute(
                "UPDATE materials SET processing_status='Linked / Promoted',updated_at=? WHERE id=?",
                (linked_at, material_id),
            )
            _event(
                conn, request, material_id, "LINKED",
                f"Human-approved link to {payload.target_type} {payload.target_id}: {payload.purpose}",
                row["processing_status"], "Linked / Promoted",
            )
        _audit(
            conn, request, "MATERIAL_LINKED", material_id,
            f"target_type={payload.target_type}; target_id={payload.target_id}",
        )
        conn.commit()
        result = conn.execute("SELECT * FROM material_links WHERE id=?", (cur.lastrowid,)).fetchone()
        conn.close()
        return dict(result)

    @fastapi_app.post("/api/materials/{material_id}/disclosure")
    def decide_material_disclosure(
        material_id: int, payload: MaterialDisclosureIn, request: Request,
    ):
        require(request, "decide")
        require_salus_component_authority(request, "SalCAPA material disclosure")
        conn = db()
        row = _material_for_request(conn, material_id, request)
        target = "Approved for Tenant" if payload.approved_for_protected_member else "Salus Internal"
        conn.execute(
            "UPDATE materials SET disclosure_status=?,updated_at=? WHERE id=?",
            (target, now(), material_id),
        )
        _event(
            conn, request, material_id, "DISCLOSURE_DECISION", payload.reason,
            row["disclosure_status"], target,
        )
        _audit(conn, request, "MATERIAL_DISCLOSURE_DECIDED", material_id, target)
        conn.commit()
        result = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        conn.close()
        return _public_row(result)

    @fastapi_app.patch("/api/materials/{material_id}/governance")
    def govern_material(material_id: int, payload: MaterialGovernanceIn, request: Request):
        require(request, "decide")
        require_salus_component_authority(request, "SalCAPA material governance")
        conn = db()
        row = _material_for_request(conn, material_id, request)
        changes = {}
        if payload.retention_until is not None:
            changes["retention_until"] = payload.retention_until.strip()
        if payload.legal_hold is not None:
            changes["legal_hold"] = 1 if payload.legal_hold else 0
        if payload.sensitivity is not None:
            changes["sensitivity"] = payload.sensitivity
        if payload.disposition_status is not None:
            if payload.disposition_status == "Active" and row["disposition_status"] == "Disposed":
                conn.close()
                raise HTTPException(409, "Disposed material cannot be reactivated")
            effective_hold = changes.get("legal_hold", row["legal_hold"])
            if payload.disposition_status == "Disposed" and effective_hold:
                conn.close()
                raise HTTPException(409, "Material under legal hold cannot be disposed")
            changes["disposition_status"] = payload.disposition_status
            if payload.disposition_status == "Disposed":
                changes["processing_status"] = "Rejected"
        if not changes:
            conn.close()
            raise HTTPException(422, "At least one governance field is required")
        changes["updated_at"] = now()
        conn.execute(
            "UPDATE materials SET " + ",".join(f"{key}=?" for key in changes) + " WHERE id=?",
            tuple(changes.values()) + (material_id,),
        )
        _event(conn, request, material_id, "GOVERNANCE_CHANGED", payload.reason)
        _audit(conn, request, "MATERIAL_GOVERNANCE_CHANGED", material_id, json.dumps(changes, sort_keys=True))
        conn.commit()
        result = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        conn.close()
        return _public_row(result)
