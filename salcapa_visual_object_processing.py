"""Governed local object and visible-condition processing suggestions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Literal

import database as database_support
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


WORKER = Path(__file__).resolve().parent / "tools" / "salcapa_visual_object_worker.py"
PROFILE_MANIFEST = "SALUS_VISUAL_PROFILE_MANIFEST"
PROFILE_ROOT = "SALUS_VISUAL_PROFILE_ROOT"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_WORKER_OUTPUT_BYTES = 1024 * 1024


class ObjectJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(min_length=1, max_length=4000)
    region_x: int | None = Field(default=None, ge=0)
    region_y: int | None = Field(default=None, ge=0)
    region_width: int | None = Field(default=None, gt=0)
    region_height: int | None = Field(default=None, gt=0)

    @field_validator("purpose")
    @classmethod
    def clean_purpose(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def complete_region(self):
        values = (self.region_x, self.region_y, self.region_width, self.region_height)
        if any(value is not None for value in values) and not all(value is not None for value in values):
            raise ValueError("A source region requires x, y, width, and height.")
        return self


class SuggestionReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Confirm Representation", "Correct", "Reject", "Needs More Information"]
    reason: str = Field(min_length=1, max_length=4000)
    corrected_label: str = Field(default="", max_length=200)
    corrected_region_x: int | None = Field(default=None, ge=0)
    corrected_region_y: int | None = Field(default=None, ge=0)
    corrected_region_width: int | None = Field(default=None, gt=0)
    corrected_region_height: int | None = Field(default=None, gt=0)
    limitations: str = Field(default="", max_length=2000)

    @field_validator("reason", "corrected_label", "limitations")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def correction_contract(self):
        region = (self.corrected_region_x, self.corrected_region_y, self.corrected_region_width, self.corrected_region_height)
        if any(value is not None for value in region) and not all(value is not None for value in region):
            raise ValueError("A corrected region requires x, y, width, and height.")
        if self.status == "Correct" and not (self.corrected_label or all(value is not None for value in region)):
            raise ValueError("A correction requires a corrected label or source region.")
        if self.status != "Correct" and (self.corrected_label or any(value is not None for value in region)):
            raise ValueError("Corrected values are permitted only for Correct.")
        return self


SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_object_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, job_key TEXT NOT NULL UNIQUE,
 source_material_id INTEGER NOT NULL, source_sha256 TEXT NOT NULL, purpose TEXT NOT NULL,
 source_width INTEGER NOT NULL, source_height INTEGER NOT NULL, region_x INTEGER NOT NULL,
 region_y INTEGER NOT NULL, region_width INTEGER NOT NULL, region_height INTEGER NOT NULL,
 profile_key TEXT NOT NULL, profile_snapshot_json TEXT NOT NULL, profile_snapshot_sha256 TEXT NOT NULL,
 executable_sha256 TEXT NOT NULL, model_sha256 TEXT NOT NULL, vocabulary_sha256 TEXT NOT NULL,
 transform_json TEXT NOT NULL, external_processing INTEGER NOT NULL DEFAULT 0,
 outcome TEXT NOT NULL, error_code TEXT NOT NULL DEFAULT '', duration_ms INTEGER NOT NULL,
 suggestion_count INTEGER NOT NULL, truncated INTEGER NOT NULL DEFAULT 0, sensitivity TEXT NOT NULL,
 disclosure_status TEXT NOT NULL, requested_by TEXT NOT NULL, requested_by_role TEXT NOT NULL,
 requested_at TEXT NOT NULL, completed_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_visual_object_jobs_scope ON visual_object_jobs(tenant_id,outcome,id);

CREATE TABLE IF NOT EXISTS visual_object_suggestions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, suggestion_key TEXT NOT NULL UNIQUE,
 job_id INTEGER NOT NULL, source_material_id INTEGER NOT NULL, source_sha256 TEXT NOT NULL,
 category_id TEXT NOT NULL, display_label TEXT NOT NULL, processor_score TEXT NOT NULL,
 score_semantics TEXT NOT NULL, alternatives_json TEXT NOT NULL, limitations TEXT NOT NULL,
 region_x INTEGER NOT NULL, region_y INTEGER NOT NULL, region_width INTEGER NOT NULL, region_height INTEGER NOT NULL,
 record_type TEXT NOT NULL, record_origin TEXT NOT NULL, review_status TEXT NOT NULL,
 sensitivity TEXT NOT NULL, disclosure_status TEXT NOT NULL, reviewed_by TEXT NOT NULL DEFAULT '',
 reviewed_by_role TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '', review_basis TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (job_id) REFERENCES visual_object_jobs(id) ON DELETE RESTRICT,
 FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_visual_object_triage ON visual_object_suggestions(tenant_id,review_status,id);

CREATE TABLE IF NOT EXISTS visual_object_reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, suggestion_id INTEGER NOT NULL,
 review_type TEXT NOT NULL, reason TEXT NOT NULL, corrected_label TEXT NOT NULL DEFAULT '',
 corrected_region_json TEXT NOT NULL DEFAULT '{}', limitations TEXT NOT NULL DEFAULT '',
 reviewed_by TEXT NOT NULL, reviewed_by_role TEXT NOT NULL, reviewed_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (suggestion_id) REFERENCES visual_object_suggestions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_visual_object_reviews ON visual_object_reviews(suggestion_id,id);
"""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _profile() -> tuple[dict | None, str]:
    manifest_value = os.getenv(PROFILE_MANIFEST, "/opt/salcapa-visual/active-profile.json")
    root_value = os.getenv(PROFILE_ROOT, "/opt/salcapa-visual")
    manifest, root = Path(manifest_value), Path(root_value)
    if not manifest.is_absolute() or not root.is_absolute() or not manifest.is_file():
        return None, "No approved local visual processor is installed. Original-image and manual source-region review remain available."
    try:
        profile = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "The installed visual processor profile is unreadable. Processing is disabled; manual review remains available."
    required = {
        "profile_key", "name", "status", "executable_path", "executable_sha256", "model_path", "model_sha256",
        "model_version", "model_provenance", "model_license", "configuration_sha256", "vocabulary",
        "score_semantics", "preprocessing", "known_limitations", "approved_purposes", "timeout_seconds",
    }
    if not isinstance(profile, dict) or not required.issubset(profile) or profile.get("status") != "Active":
        return None, "The installed visual processor profile is not active. Processing is disabled; manual review remains available."
    executable, model = Path(str(profile["executable_path"])), Path(str(profile["model_path"]))
    try:
        executable.resolve(strict=True).relative_to(root.resolve(strict=True))
        model.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return None, "The installed visual processor is outside its approved boundary. Processing is disabled."
    if _sha(executable) != profile["executable_sha256"] or _sha(model) != profile["model_sha256"]:
        return None, "An installed visual processor artifact does not match its approved hash. Processing is disabled."
    vocabulary = profile.get("vocabulary")
    if not isinstance(vocabulary, list) or not vocabulary or any(not isinstance(item, dict) or not item.get("id") or not item.get("label") for item in vocabulary):
        return None, "The installed visual category vocabulary is invalid. Processing is disabled."
    profile["profile_root"] = str(root)
    profile["vocabulary_sha256"] = hashlib.sha256(_canonical(vocabulary).encode()).hexdigest()
    return profile, "The approved local processor is available for request-driven review. Results remain unverified until a different authorized person reviews the source region."


def register_salcapa_visual_object_processing(fastapi_app, core: dict) -> None:
    db, now, actor, role, tenant_id = (core[name] for name in ("db", "now", "actor", "role", "tenant_id"))
    require, require_sensitivity = core["require"], core["require_sensitivity"]
    protected_member_request = core["protected_member_request"]
    require_salus_component_authority = core["require_salus_component_authority"]
    security_event, storage = core["security_event"], core["storage"]
    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    tenant_tables = {"visual_object_jobs", "visual_object_suggestions", "visual_object_reviews"}
    database_support.ID_TABLES.update(tenant_tables)
    if not getattr(fastapi_app.state, "salcapa_visual_object_backup_registered", False):
        base_collect, base_validate, base_replace = (core[name] for name in ("collect_tenant_records", "validate_records", "replace_tenant_records"))

        def collect(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            for table in sorted(tenant_tables):
                records[table] = [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (selected_tenant,))]
            return records

        def validate(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            materials = {int(row["id"]) for row in records.get("materials", []) if row.get("id") is not None}
            jobs = {int(row["id"]) for row in records.get("visual_object_jobs", []) if row.get("id") is not None}
            suggestions = {int(row["id"]) for row in records.get("visual_object_suggestions", []) if row.get("id") is not None}
            for table in tenant_tables:
                for row in records.get(table, []):
                    if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("visual_object_jobs", []):
                if int(row.get("source_material_id", -1)) not in materials or len(str(row.get("source_sha256", ""))) != 64:
                    errors.append(f"visual object job {row.get('id')} has invalid source lineage")
                for field in ("profile_snapshot_sha256", "executable_sha256", "model_sha256", "vocabulary_sha256"):
                    if len(str(row.get(field, ""))) != 64:
                        errors.append(f"visual object job {row.get('id')} has invalid processor lineage")
                for field in ("profile_snapshot_json", "transform_json"):
                    try:
                        if not isinstance(json.loads(row.get(field, "{}")), dict): raise ValueError
                    except (TypeError, ValueError, json.JSONDecodeError):
                        errors.append(f"visual object job {row.get('id')} has invalid {field}")
            for row in records.get("visual_object_suggestions", []):
                if int(row.get("job_id", -1)) not in jobs or int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"visual object suggestion {row.get('id')} has invalid lineage")
                try:
                    if not isinstance(json.loads(row.get("alternatives_json", "[]")), list): raise ValueError
                except (TypeError, ValueError, json.JSONDecodeError):
                    errors.append(f"visual object suggestion {row.get('id')} has invalid alternatives")
            for row in records.get("visual_object_reviews", []):
                if int(row.get("suggestion_id", -1)) not in suggestions:
                    errors.append(f"visual object review {row.get('id')} has invalid suggestion lineage")
            return errors

        def insert(conn, table: str, row: dict):
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            conn.execute(f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})", tuple(data.values()))

        def replace(conn, selected_tenant: int, records: dict):
            errors = validate(records, selected_tenant)
            if errors: raise ValueError("; ".join(errors))
            for table in ("visual_object_reviews", "visual_object_suggestions", "visual_object_jobs"):
                conn.execute(f"DELETE FROM {table} WHERE tenant_id=?", (selected_tenant,))
            base_replace(conn, selected_tenant, records)
            for table in ("visual_object_jobs", "visual_object_suggestions", "visual_object_reviews"):
                for row in records.get(table, []): insert(conn, table, row)
            database_support.reset_identity_sequences(conn, tenant_tables)

        core["collect_tenant_records"], core["validate_records"], core["replace_tenant_records"] = collect, validate, replace
        fastapi_app.state.salcapa_visual_object_backup_registered = True

    def internal(request: Request, permission: str = "read"):
        require(request, permission)
        if protected_member_request(request):
            raise HTTPException(403, "Visual processing review is restricted to authorized Salus personnel.")

    def audit(conn, request: Request, action: str, entity_type: str, entity_id: int, detail: str):
        conn.execute("INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)", (now(), actor(request), action, entity_type, entity_id, detail[:2000], tenant_id(request)))

    def source(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row: raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "VISUAL_OBJECT_TENANT_BOUNDARY_VIOLATION", "High", f"material_id={material_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        extension = row["original_name"].rsplit(".", 1)[-1].lower() if "." in row["original_name"] else ""
        if row["disposition_status"] != "Active" or extension not in {"jpg", "jpeg", "png"}:
            raise HTTPException(422, "This bounded review accepts active JPEG and PNG source records only.")
        return row, extension

    @fastapi_app.get("/api/visual-object-analysis/status")
    def status(request: Request):
        internal(request)
        profile, guidance = _profile()
        return {"available": profile is not None, "profile": None if profile is None else {key: profile[key] for key in ("profile_key", "name", "model_version", "model_provenance", "model_license", "known_limitations", "score_semantics")}, "guidance": guidance, "external_processing": False, "manual_review_available": True}

    @fastapi_app.post("/api/materials/{material_id}/visual-object-analysis-jobs")
    def create_job(material_id: int, payload: ObjectJobIn, request: Request):
        internal(request, "write")
        require_salus_component_authority(request, "SalCAPA visible-condition processing review")
        profile, guidance = _profile()
        if profile is None: raise HTTPException(503, guidance)
        if not any(token.lower() in payload.purpose.lower() for token in profile["approved_purposes"]):
            raise HTTPException(403, "The stated purpose is outside the installed processor profile's approved purposes.")
        conn = db(); row, extension = source(conn, material_id, request); conn.close()
        if int(row["size_bytes"]) > MAX_SOURCE_BYTES: raise HTTPException(422, "The image exceeds the bounded processing limit.")
        try: data = storage.get_bytes(row["stored_name"])
        except FileNotFoundError as exc: raise HTTPException(404, "The governed source object is unavailable.") from exc
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            security_event(request, "VISUAL_OBJECT_SOURCE_HASH_MISMATCH", "Critical", f"material_id={material_id}")
            raise HTTPException(409, "Source integrity verification failed. No processing job was created.")
        from PIL import Image
        with tempfile.TemporaryDirectory(prefix="salcapa-visual-object-") as directory:
            source_path = Path(directory) / f"source.{extension}"; source_path.write_bytes(data); source_path.chmod(0o400)
            with Image.open(source_path) as image: width, height = image.size
            x, y, rw, rh = (0, 0, width, height) if payload.region_x is None else (payload.region_x, payload.region_y, payload.region_width, payload.region_height)
            if x + rw > width or y + rh > height: raise HTTPException(422, "The selected source region exceeds the original image dimensions.")
            snapshot = {key: value for key, value in profile.items() if key not in {"profile_root"}}
            snapshot_json = _canonical(snapshot); requested = now(); started = time.monotonic()
            request_manifest = {**profile, "source_path": str(source_path), "source_sha256": row["sha256"], "region": {"x": x, "y": y, "width": rw, "height": rh}}
            request_path = Path(directory) / "request.json"; request_path.write_text(_canonical(request_manifest), encoding="utf-8"); request_path.chmod(0o400)
            try:
                completed = subprocess.run([sys.executable, "-I", str(WORKER), str(request_path)], cwd=directory, env={"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0"}, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=int(profile["timeout_seconds"]) + 10, check=False, start_new_session=True)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise HTTPException(503, "The approved local visual processor is unavailable. Manual source-region review remains available.") from exc
            if len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES: raise HTTPException(422, "The bounded visual result exceeded its output limit.")
            try: result = json.loads(completed.stdout.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise HTTPException(422, "The isolated visual worker returned an invalid result.") from exc
            if completed.returncode != 0 or result.get("ok") is not True:
                raise HTTPException(422, str(result.get("detail", "Local visual processing did not complete safely."))[:1000])
            suggestions = result.get("suggestions", [])
        duration = max(0, int((time.monotonic() - started) * 1000)); completed_at = now(); job_key = "VOJ-" + uuid.uuid4().hex
        transform = {"source_dimensions": [width, height], "selected_region": [x, y, rw, rh], "preprocessing": profile["preprocessing"], "output_coordinates": "inverse-mapped original decoded pixels"}
        conn = db()
        conn.execute("INSERT INTO visual_object_jobs(tenant_id,job_key,source_material_id,source_sha256,purpose,source_width,source_height,region_x,region_y,region_width,region_height,profile_key,profile_snapshot_json,profile_snapshot_sha256,executable_sha256,model_sha256,vocabulary_sha256,transform_json,external_processing,outcome,duration_ms,suggestion_count,sensitivity,disclosure_status,requested_by,requested_by_role,requested_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id(request), job_key, material_id, row["sha256"], payload.purpose, width, height, x, y, rw, rh, profile["profile_key"], snapshot_json, hashlib.sha256(snapshot_json.encode()).hexdigest(), profile["executable_sha256"], profile["model_sha256"], profile["vocabulary_sha256"], _canonical(transform), 0, "Completed", duration, len(suggestions), row["sensitivity"], "Salus Internal — Not Released", actor(request), role(request), requested, completed_at))
        job = conn.execute("SELECT * FROM visual_object_jobs WHERE job_key=?", (job_key,)).fetchone()
        for item in suggestions:
            conn.execute("INSERT INTO visual_object_suggestions(tenant_id,suggestion_key,job_id,source_material_id,source_sha256,category_id,display_label,processor_score,score_semantics,alternatives_json,limitations,region_x,region_y,region_width,region_height,record_type,record_origin,review_status,sensitivity,disclosure_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id(request), "VOS-" + uuid.uuid4().hex, job["id"], material_id, row["sha256"], item["category_id"], item["display_label"], item["score"], profile["score_semantics"], _canonical(item["alternatives"]), item["limitations"], item["region_x"], item["region_y"], item["region_width"], item["region_height"], "Processing Suggestion — Derived and Unverified", "Approved local processor", "Awaiting Human Review", row["sensitivity"], "Salus Internal — Not Released", completed_at, completed_at))
        audit(conn, request, "VISUAL_OBJECT_JOB_COMPLETED", "visual_object_job", int(job["id"]), f"source_material_id={material_id}; suggestion_count={len(suggestions)}; external_processing=false; no_finding_or_disclosure=true")
        conn.commit(); output = {"job": dict(job), "suggestions": [dict(item) for item in conn.execute("SELECT * FROM visual_object_suggestions WHERE job_id=? ORDER BY id", (job["id"],))]}; conn.close()
        for item in output["suggestions"]: item["alternatives"] = json.loads(item.pop("alternatives_json")); item["authority_note"] = "This unverified processing suggestion directs attention to source pixels. It is not a finding, decision, threat judgment, or approved disclosure."
        return output

    @fastapi_app.get("/api/visual-object-analysis/triage")
    def triage(request: Request, limit: int = 200):
        internal(request); conn = db()
        rows = [dict(row) for row in conn.execute("SELECT s.*,m.title source_title,m.original_name,j.purpose,j.profile_key,j.requested_by FROM visual_object_suggestions s JOIN visual_object_jobs j ON j.id=s.job_id JOIN materials m ON m.id=s.source_material_id WHERE s.tenant_id=? ORDER BY CASE s.review_status WHEN 'Awaiting Human Review' THEN 0 ELSE 1 END,s.id DESC LIMIT ?", (tenant_id(request), max(1, min(limit, 500)))) if (require_sensitivity(request, row["sensitivity"]) is None)]
        conn.close()
        for item in rows: item["alternatives"] = json.loads(item.pop("alternatives_json")); item["authority_note"] = "Compare this unverified suggestion with the original source region before use."
        return {"items": rows, "guidance": "A missing suggestion does not prove absence. Each result remains unverified until a different authorized person compares it with the source."}

    @fastapi_app.post("/api/visual-object-analysis/suggestions/{suggestion_id}/review")
    def review(suggestion_id: int, payload: SuggestionReviewIn, request: Request):
        internal(request, "decide"); require_salus_component_authority(request, "SalCAPA visible-condition processing review")
        conn = db(); row = conn.execute("SELECT s.*,j.requested_by,j.source_width,j.source_height FROM visual_object_suggestions s JOIN visual_object_jobs j ON j.id=s.job_id WHERE s.id=?", (suggestion_id,)).fetchone()
        if not row: conn.close(); raise HTTPException(404, "Visual processing suggestion not found")
        if int(row["tenant_id"]) != tenant_id(request): conn.close(); raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["review_status"] != "Awaiting Human Review": conn.close(); raise HTTPException(409, "This suggestion already has a recorded review state")
        if row["requested_by"] == actor(request): conn.close(); raise HTTPException(409, "A different authorized person must review this processing suggestion")
        corrected_region = {}
        if payload.corrected_region_x is not None:
            corrected_region = {"x": payload.corrected_region_x, "y": payload.corrected_region_y, "width": payload.corrected_region_width, "height": payload.corrected_region_height}
            if corrected_region["x"] + corrected_region["width"] > row["source_width"] or corrected_region["y"] + corrected_region["height"] > row["source_height"]: conn.close(); raise HTTPException(422, "The corrected region exceeds the source dimensions.")
        reviewed = now(); conn.execute("UPDATE visual_object_suggestions SET review_status=?,reviewed_by=?,reviewed_by_role=?,reviewed_at=?,review_basis=?,updated_at=? WHERE id=?", (payload.status, actor(request), role(request), reviewed, payload.reason, reviewed, suggestion_id))
        conn.execute("INSERT INTO visual_object_reviews(tenant_id,suggestion_id,review_type,reason,corrected_label,corrected_region_json,limitations,reviewed_by,reviewed_by_role,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (tenant_id(request), suggestion_id, payload.status, payload.reason, payload.corrected_label, _canonical(corrected_region), payload.limitations, actor(request), role(request), reviewed))
        audit(conn, request, "VISUAL_OBJECT_SUGGESTION_REVIEWED", "visual_object_suggestion", suggestion_id, f"status={payload.status}; source_unchanged=true; no_finding_or_disclosure=true")
        conn.commit(); result = dict(conn.execute("SELECT * FROM visual_object_suggestions WHERE id=?", (suggestion_id,)).fetchone()); conn.close(); result["authority_note"] = "This review records whether the bounded representation matches visible pixels. It does not establish a finding, decision, or disclosure authority."; return result
