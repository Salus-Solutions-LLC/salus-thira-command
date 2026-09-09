"""Safe derived processing and analyst review for governed SalCAPA materials.

This first processing slice deliberately handles inert text only. Originals remain in
the governed material store, while every extracted representation is a separate,
source-hashed derivative that stays unverified until a different authorized person
records review. A reviewed derivative is a source aid, not a finding or decision.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from typing import Literal

import database as database_support

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator


PROCESSOR = "SalCAPA Safe Text Extractor"
PROCESSOR_VERSION = "1.0.0"
MAX_DERIVED_CHARACTERS = 2_000_000
SEARCH_CANDIDATE_LIMIT = 2_000
INERT_EXTENSIONS = {"txt", "md", "csv", "tsv", "json", "xml", "log", "eml"}
INERT_CONTENT_TYPES = {
    "application/json", "application/xml", "application/csv", "text/csv",
    "text/tab-separated-values", "message/rfc822",
}


class MaterialProcessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A processing purpose is required.")
        return value


class DerivativeReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Human Reviewed", "Rejected"]
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A review basis is required.")
        return value


SCHEMA = """
CREATE TABLE IF NOT EXISTS material_processing_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  job_key TEXT NOT NULL UNIQUE,
  source_material_id INTEGER NOT NULL,
  pipeline TEXT NOT NULL,
  status TEXT NOT NULL,
  purpose TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_by_role TEXT NOT NULL,
  processor TEXT NOT NULL,
  processor_version TEXT NOT NULL,
  started_at TEXT NOT NULL DEFAULT '',
  completed_at TEXT NOT NULL DEFAULT '',
  failure_code TEXT NOT NULL DEFAULT '',
  failure_detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_material_processing_jobs_queue
  ON material_processing_jobs(tenant_id,status,created_at,id);
CREATE INDEX IF NOT EXISTS idx_material_processing_jobs_source
  ON material_processing_jobs(source_material_id,id);

CREATE TABLE IF NOT EXISTS material_derivatives (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  derivative_key TEXT NOT NULL UNIQUE,
  source_material_id INTEGER NOT NULL,
  processing_job_id INTEGER NOT NULL,
  derivative_type TEXT NOT NULL,
  content_text TEXT NOT NULL,
  content_sha256 TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  processor TEXT NOT NULL,
  processor_version TEXT NOT NULL,
  extraction_method TEXT NOT NULL,
  confidence_status TEXT NOT NULL,
  uncertainty_note TEXT NOT NULL,
  truncated INTEGER NOT NULL DEFAULT 0,
  review_status TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_by_role TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_basis TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
  FOREIGN KEY (processing_job_id) REFERENCES material_processing_jobs(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_material_derivatives_triage
  ON material_derivatives(tenant_id,review_status,created_at,id);
CREATE INDEX IF NOT EXISTS idx_material_derivatives_source
  ON material_derivatives(source_material_id,id);

CREATE TABLE IF NOT EXISTS material_derivative_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  derivative_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  from_status TEXT NOT NULL DEFAULT '',
  to_status TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (derivative_id) REFERENCES material_derivatives(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_material_derivative_events_record
  ON material_derivative_events(derivative_id,id);
"""


class ProcessingFailure(Exception):
    def __init__(self, code: str, public_detail: str):
        super().__init__(public_detail)
        self.code = code
        self.public_detail = public_detail


def _decode_inert_text(data: bytes, original_name: str, content_type: str) -> tuple[str, str, bool]:
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if not (
        normalized_type.startswith("text/")
        or normalized_type in INERT_CONTENT_TYPES
        or extension in INERT_EXTENSIONS
    ):
        raise ProcessingFailure(
            "FORMAT_NOT_SUPPORTED",
            "This first processing stage supports inert text, CSV, TSV, JSON, XML, log, and EML material. The original remains ready for a later compatible processor.",
        )
    encoding = "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    try:
        text = data.decode(encoding, errors="strict")
    except UnicodeDecodeError as exc:
        raise ProcessingFailure(
            "TEXT_ENCODING_UNSUPPORTED",
            "The text encoding could not be read safely. The original remains unchanged for human review or a compatible processor.",
        ) from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    method = "Strict text decoding"
    if extension == "json" or normalized_type == "application/json":
        try:
            json.loads(text)
        except (TypeError, ValueError) as exc:
            raise ProcessingFailure(
                "STRUCTURED_DATA_INVALID",
                "The material is labeled JSON but is not valid JSON. The original remains unchanged for review.",
            ) from exc
        method = "Strict text decoding with JSON structure validation"
    elif extension in {"csv", "tsv"} or normalized_type in {
        "application/csv", "text/csv", "text/tab-separated-values",
    }:
        dialect = "excel-tab" if extension == "tsv" or normalized_type == "text/tab-separated-values" else "excel"
        reader = csv.reader(io.StringIO(text), dialect=dialect)
        try:
            for index, row in enumerate(reader):
                if index > 100_000 or len(row) > 2_000:
                    raise ProcessingFailure(
                        "STRUCTURED_DATA_LIMIT",
                        "The structured material exceeds the safe validation limit. The original remains unchanged.",
                    )
        except csv.Error as exc:
            raise ProcessingFailure(
                "STRUCTURED_DATA_INVALID",
                "The delimited material could not be parsed safely. The original remains unchanged for review.",
            ) from exc
        method = "Strict text decoding with delimited-structure validation"
    truncated = len(text) > MAX_DERIVED_CHARACTERS
    if truncated:
        text = text[:MAX_DERIVED_CHARACTERS]
    return text, method, truncated


def register_salcapa_material_processing(fastapi_app, core: dict) -> None:
    db = core["db"]
    now = core["now"]
    actor = core["actor"]
    role = core["role"]
    tenant_id = core["tenant_id"]
    require = core["require"]
    require_sensitivity = core["require_sensitivity"]
    protected_member_request = core["protected_member_request"]
    require_salus_component_authority = core["require_salus_component_authority"]
    security_event = core["security_event"]
    clearance_level = core["clearance_level"]
    sensitivity_levels = core["SENSITIVITY_LEVELS"]
    storage = core["storage"]

    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    # Extend the active portable-record contract without rewriting the frozen base
    # source. The imported ID table set is shared with portable_backup, so updating
    # it in place also preserves PostgreSQL identity handling for restored records.
    processing_tables = {
        "material_processing_jobs", "material_derivatives", "material_derivative_events",
    }
    database_support.ID_TABLES.update(processing_tables)
    if not getattr(fastapi_app.state, "salcapa_material_processing_backup_registered", False):
        base_collect = core["collect_tenant_records"]
        base_validate = core["validate_records"]
        base_replace = core["replace_tenant_records"]

        def collect_with_derivatives(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            for table in (
                "material_processing_jobs", "material_derivatives", "material_derivative_events",
            ):
                records[table] = [
                    dict(row) for row in conn.execute(
                        f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (selected_tenant,)
                    )
                ]
            return records

        def validate_with_derivatives(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            materials = {int(row["id"]) for row in records.get("materials", []) if row.get("id") is not None}
            jobs = {int(row["id"]) for row in records.get("material_processing_jobs", []) if row.get("id") is not None}
            derivatives = {int(row["id"]) for row in records.get("material_derivatives", []) if row.get("id") is not None}
            for table in processing_tables:
                for row in records.get(table, []):
                    if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("material_processing_jobs", []):
                if int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"material processing job {row.get('id')} has an invalid source")
            for row in records.get("material_derivatives", []):
                if int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"material derivative {row.get('id')} has an invalid source")
                if int(row.get("processing_job_id", -1)) not in jobs:
                    errors.append(f"material derivative {row.get('id')} has an invalid processing job")
                for field in ("content_sha256", "source_sha256"):
                    if len(str(row.get(field, ""))) != 64:
                        errors.append(f"material derivative {row.get('id')} has an invalid {field}")
            for row in records.get("material_derivative_events", []):
                if int(row.get("derivative_id", -1)) not in derivatives:
                    errors.append(f"material derivative event {row.get('id')} has an invalid derivative")
            return errors

        def insert_restored_row(conn, table: str, row: dict) -> None:
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            if not data:
                return
            conn.execute(
                f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})",
                tuple(data.values()),
            )

        def replace_with_derivatives(conn, selected_tenant: int, records: dict):
            errors = validate_with_derivatives(records, selected_tenant)
            if errors:
                raise ValueError("; ".join(errors))
            conn.execute("DELETE FROM material_derivative_events WHERE tenant_id=?", (selected_tenant,))
            conn.execute("DELETE FROM material_derivatives WHERE tenant_id=?", (selected_tenant,))
            conn.execute("DELETE FROM material_processing_jobs WHERE tenant_id=?", (selected_tenant,))
            base_replace(conn, selected_tenant, records)
            for table in (
                "material_processing_jobs", "material_derivatives", "material_derivative_events",
            ):
                for row in records.get(table, []):
                    insert_restored_row(conn, table, row)
            database_support.reset_identity_sequences(conn, processing_tables)

        core["collect_tenant_records"] = collect_with_derivatives
        core["validate_records"] = validate_with_derivatives
        core["replace_tenant_records"] = replace_with_derivatives
        fastapi_app.state.salcapa_material_processing_backup_registered = True

    def audit(conn, request: Request, action: str, entity_type: str, entity_id: int, detail: str) -> None:
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, entity_type, entity_id, detail[:2000], tenant_id(request)),
        )

    def material_event(conn, request: Request, material, event_type: str, reason: str, before: str, after: str) -> None:
        conn.execute(
            "INSERT INTO material_events(tenant_id,material_id,event_type,from_status,to_status,reason,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                material["tenant_id"], material["id"], event_type, before, after, reason,
                json.dumps(dict(material), sort_keys=True, default=str), actor(request), role(request), now(),
            ),
        )

    def internal_request(request: Request) -> None:
        require(request, "read")
        if protected_member_request(request):
            raise HTTPException(403, "Derived processing and analyst review are restricted to authorized Salus personnel.")

    def source_for_request(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "MATERIAL_PROCESSING_TENANT_BOUNDARY_VIOLATION", "High", f"material_id={material_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        return row

    def public_derivative(row, include_content: bool = False) -> dict:
        result = dict(row)
        content = result.pop("content_text", "")
        result["truncated"] = bool(result.get("truncated"))
        result["content_preview"] = content[:1000]
        if include_content:
            result["content_text"] = content
        result["authority_note"] = (
            "This is a derived source aid. Human review confirms the recorded representation only; it does not establish the truth of the source, a finding, a decision, disclosure authority, or operational authority."
        )
        return result

    @fastapi_app.post("/api/materials/{material_id}/safe-text-processing")
    def process_safe_text(material_id: int, payload: MaterialProcessIn, request: Request):
        require(request, "write")
        require_salus_component_authority(request, "SalCAPA derived material processing")
        conn = db()
        source = source_for_request(conn, material_id, request)
        if source["disposition_status"] != "Active":
            conn.close()
            raise HTTPException(409, "Disposed material cannot be processed")
        if source["processing_status"] != "Ready for Processing":
            conn.close()
            raise HTTPException(409, "Material must be Ready for Processing")
        job_key = "MPJ-" + uuid.uuid4().hex
        created = now()
        conn.execute(
            "INSERT INTO material_processing_jobs(tenant_id,job_key,source_material_id,pipeline,status,purpose,requested_by,requested_by_role,processor,processor_version,started_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id(request), job_key, material_id, "safe-text-v1", "Processing",
                payload.reason, actor(request), role(request), PROCESSOR, PROCESSOR_VERSION,
                created, created, created,
            ),
        )
        job = conn.execute("SELECT * FROM material_processing_jobs WHERE job_key=?", (job_key,)).fetchone()
        conn.execute("UPDATE materials SET processing_status='Processing',updated_at=? WHERE id=?", (created, material_id))
        material_event(conn, request, source, "DERIVED_PROCESSING_STARTED", payload.reason, "Ready for Processing", "Processing")
        audit(conn, request, "MATERIAL_PROCESSING_STARTED", "material_processing_job", int(job["id"]), f"material_id={material_id}; pipeline=safe-text-v1")
        conn.commit()
        conn.close()

        failure_status = 422
        try:
            try:
                data = storage.get_bytes(source["stored_name"])
            except FileNotFoundError as exc:
                failure_status = 404
                raise ProcessingFailure("SOURCE_OBJECT_MISSING", "The governed source object is unavailable. No derived content was created.") from exc
            except Exception as exc:
                failure_status = 503
                raise ProcessingFailure("SOURCE_STORAGE_UNAVAILABLE", "The governed source store is unavailable. No derived content was created.") from exc
            if hashlib.sha256(data).hexdigest() != source["sha256"]:
                failure_status = 409
                security_event(request, "MATERIAL_PROCESSING_HASH_MISMATCH", "Critical", f"material_id={material_id}")
                raise ProcessingFailure("SOURCE_HASH_MISMATCH", "Source integrity verification failed. Processing stopped without creating derived content.")
            text, method, truncated = _decode_inert_text(data, source["original_name"], source["content_type"])
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            completed = now()
            derivative_key = "MDR-" + uuid.uuid4().hex
            conn = db()
            conn.execute(
                "INSERT INTO material_derivatives(tenant_id,derivative_key,source_material_id,processing_job_id,derivative_type,content_text,content_sha256,source_sha256,processor,processor_version,extraction_method,confidence_status,uncertainty_note,truncated,review_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id(request), derivative_key, material_id, int(job["id"]),
                    "Extracted Text", text, digest, source["sha256"], PROCESSOR,
                    PROCESSOR_VERSION, method, "Derived — Unverified",
                    "Text extraction does not establish source truth, relevance, or a qualified conclusion.",
                    1 if truncated else 0, "Awaiting Human Review", completed, completed,
                ),
            )
            derivative = conn.execute("SELECT * FROM material_derivatives WHERE derivative_key=?", (derivative_key,)).fetchone()
            conn.execute(
                "UPDATE material_processing_jobs SET status='Completed',completed_at=?,updated_at=? WHERE id=?",
                (completed, completed, int(job["id"])),
            )
            current = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
            conn.execute("UPDATE materials SET processing_status='Ready for Human Review',updated_at=? WHERE id=?", (completed, material_id))
            material_event(
                conn, request, current, "DERIVED_PROCESSING_COMPLETED",
                f"Separate unverified derivative {derivative_key} created by {PROCESSOR} {PROCESSOR_VERSION}.",
                "Processing", "Ready for Human Review",
            )
            conn.execute(
                "INSERT INTO material_derivative_events(tenant_id,derivative_id,event_type,from_status,to_status,reason,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    tenant_id(request), int(derivative["id"]), "CREATED", "", "Awaiting Human Review",
                    "Derived representation created separately from immutable source bytes.",
                    actor(request), role(request), completed,
                ),
            )
            audit(conn, request, "MATERIAL_DERIVATIVE_CREATED", "material_derivative", int(derivative["id"]), f"source_material_id={material_id}; source_sha256={source['sha256']}; content_sha256={digest}")
            conn.commit()
            result = public_derivative(derivative)
            conn.close()
            return {"job": dict(job) | {"status": "Completed", "completed_at": completed}, "derivative": result}
        except ProcessingFailure as exc:
            failed = now()
            conn = db()
            current = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
            conn.execute(
                "UPDATE material_processing_jobs SET status='Failed',failure_code=?,failure_detail=?,completed_at=?,updated_at=? WHERE id=?",
                (exc.code, exc.public_detail, failed, failed, int(job["id"])),
            )
            if current and current["processing_status"] == "Processing":
                conn.execute("UPDATE materials SET processing_status='Ready for Processing',updated_at=? WHERE id=?", (failed, material_id))
                material_event(conn, request, current, "DERIVED_PROCESSING_FAILED", exc.public_detail, "Processing", "Ready for Processing")
            audit(conn, request, "MATERIAL_PROCESSING_FAILED", "material_processing_job", int(job["id"]), f"material_id={material_id}; failure_code={exc.code}")
            conn.commit()
            conn.close()
            raise HTTPException(failure_status, exc.public_detail)

    @fastapi_app.get("/api/material-processing/triage")
    def processing_triage(request: Request, limit: int = 200):
        internal_request(request)
        conn = db()
        rows = conn.execute(
            "SELECT d.*,m.title source_title,m.original_name,m.material_kind,m.sensitivity,m.processing_status source_processing_status FROM material_derivatives d JOIN materials m ON m.id=d.source_material_id WHERE d.tenant_id=? ORDER BY CASE d.review_status WHEN 'Awaiting Human Review' THEN 0 ELSE 1 END,d.id DESC LIMIT ?",
            (tenant_id(request), max(1, min(limit, 500))),
        )
        results = []
        for row in rows:
            if sensitivity_levels.get(row["sensitivity"] or "Standard", 1) <= clearance_level(request):
                results.append(public_derivative(row))
        conn.close()
        return {
            "items": results,
            "guidance": "Review confirms whether the derived representation is usable as a source aid. It does not qualify intelligence, establish a finding, authorize disclosure, or make a decision.",
        }

    @fastapi_app.get("/api/material-processing/derivatives/{derivative_id}")
    def get_derivative(derivative_id: int, request: Request):
        internal_request(request)
        conn = db()
        row = conn.execute(
            "SELECT d.*,m.title source_title,m.original_name,m.material_kind,m.sensitivity FROM material_derivatives d JOIN materials m ON m.id=d.source_material_id WHERE d.id=?",
            (derivative_id,),
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Derived material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            conn.close()
            security_event(request, "MATERIAL_DERIVATIVE_TENANT_BOUNDARY_VIOLATION", "High", f"derivative_id={derivative_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        result = public_derivative(row, include_content=True)
        result["events"] = [dict(item) for item in conn.execute("SELECT id,event_type,from_status,to_status,reason,changed_by,changed_by_role,created_at FROM material_derivative_events WHERE derivative_id=? ORDER BY id", (derivative_id,))]
        conn.close()
        return result

    @fastapi_app.get("/api/material-processing/search")
    def search_derivatives(request: Request, q: str, limit: int = 50):
        internal_request(request)
        query = q.strip().casefold()
        if len(query) < 2 or len(query) > 200:
            raise HTTPException(422, "Search terms must contain 2 to 200 characters")
        conn = db()
        rows = conn.execute(
            "SELECT d.*,m.title source_title,m.original_name,m.material_kind,m.sensitivity FROM material_derivatives d JOIN materials m ON m.id=d.source_material_id WHERE d.tenant_id=? AND d.review_status<>'Rejected' ORDER BY d.id DESC LIMIT ?",
            (tenant_id(request), SEARCH_CANDIDATE_LIMIT),
        )
        results = []
        maximum = max(1, min(limit, 200))
        for row in rows:
            if sensitivity_levels.get(row["sensitivity"] or "Standard", 1) > clearance_level(request):
                continue
            content = row["content_text"] or ""
            index = content.casefold().find(query)
            if index < 0:
                continue
            start = max(0, index - 180)
            end = min(len(content), index + len(query) + 320)
            item = public_derivative(row)
            item["match_excerpt"] = ("…" if start else "") + content[start:end] + ("…" if end < len(content) else "")
            results.append(item)
            if len(results) >= maximum:
                break
        conn.close()
        return {
            "query": q.strip(), "items": results,
            "scope_note": "Results are limited to this tenant, the requester's sensitivity clearance, and non-rejected derived source aids.",
        }

    @fastapi_app.post("/api/material-processing/derivatives/{derivative_id}/review")
    def review_derivative(derivative_id: int, payload: DerivativeReviewIn, request: Request):
        require(request, "decide")
        require_salus_component_authority(request, "SalCAPA derived material review")
        conn = db()
        row = conn.execute(
            "SELECT d.*,m.sensitivity FROM material_derivatives d JOIN materials m ON m.id=d.source_material_id WHERE d.id=?",
            (derivative_id,),
        ).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Derived material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            conn.close()
            security_event(request, "MATERIAL_DERIVATIVE_REVIEW_BOUNDARY_VIOLATION", "High", f"derivative_id={derivative_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["review_status"] != "Awaiting Human Review":
            conn.close()
            raise HTTPException(409, "This derived representation already has a recorded review state")
        job = conn.execute("SELECT requested_by FROM material_processing_jobs WHERE id=?", (row["processing_job_id"],)).fetchone()
        if job and job["requested_by"] == actor(request):
            conn.close()
            raise HTTPException(409, "A different authorized person must review this derived representation")
        reviewed = now()
        conn.execute(
            "UPDATE material_derivatives SET review_status=?,reviewed_by=?,reviewed_by_role=?,reviewed_at=?,review_basis=?,updated_at=? WHERE id=?",
            (payload.status, actor(request), role(request), reviewed, payload.reason, reviewed, derivative_id),
        )
        conn.execute(
            "INSERT INTO material_derivative_events(tenant_id,derivative_id,event_type,from_status,to_status,reason,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), derivative_id, "HUMAN_REVIEW_RECORDED", "Awaiting Human Review", payload.status, payload.reason, actor(request), role(request), reviewed),
        )
        audit(conn, request, "MATERIAL_DERIVATIVE_REVIEWED", "material_derivative", derivative_id, f"status={payload.status}; does_not_promote_source=true")
        conn.commit()
        result = conn.execute("SELECT * FROM material_derivatives WHERE id=?", (derivative_id,)).fetchone()
        conn.close()
        return public_derivative(result)
