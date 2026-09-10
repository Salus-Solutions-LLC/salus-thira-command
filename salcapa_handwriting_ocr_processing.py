"""Governed local handwriting and difficult-text recognition review."""

from __future__ import annotations

import hashlib
import io
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


WORKER = Path(__file__).resolve().parent / "tools" / "salcapa_handwriting_ocr_worker.py"
PROFILE_MANIFEST = "SALUS_HANDWRITING_OCR_PROFILE_MANIFEST"
PROFILE_ROOT = "SALUS_HANDWRITING_OCR_PROFILE_ROOT"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_WORKER_OUTPUT_BYTES = 2 * 1024 * 1024
PROHIBITED_CONCLUSIONS = (
    "Recognition prepares visible text only. It does not perform authorship attribution, signature verification, "
    "identity resolution, personality or health inference, credibility assessment, or intent analysis."
)


class RecognitionJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(min_length=1, max_length=4000)
    mode: Literal["Printed text", "Handwritten text", "Mixed text", "Targeted region review"]
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
        if self.mode == "Targeted region review" and not all(value is not None for value in values):
            raise ValueError("Targeted region review requires a source region.")
        return self


class SegmentReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Confirm Representation", "Correct", "Reject", "Needs More Information"]
    reason: str = Field(min_length=1, max_length=4000)
    corrected_text: str = Field(default="", max_length=12000)
    corrected_segment_type: str = Field(default="", max_length=80)
    limitations: str = Field(default="", max_length=2000)

    @field_validator("reason", "corrected_text", "corrected_segment_type", "limitations")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def correction_contract(self):
        corrected = bool(self.corrected_text or self.corrected_segment_type)
        allowed_types = {"printed", "handwritten", "mixed", "mark", "checkbox", "field", "table", "unknown", "illegible"}
        if self.corrected_segment_type and self.corrected_segment_type not in allowed_types:
            raise ValueError("The corrected segment type is outside the governed vocabulary.")
        if self.status == "Correct" and not corrected:
            raise ValueError("A correction requires corrected text or segment type.")
        if self.status != "Correct" and corrected:
            raise ValueError("Corrected values are permitted only for Correct.")
        return self


class ManualTranscriptionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(min_length=1, max_length=4000)
    transcription: str = Field(min_length=1, max_length=12000)
    segment_type: Literal["printed", "handwritten", "mixed", "mark", "checkbox", "field", "table", "unknown", "illegible"]
    limitations: str = Field(min_length=1, max_length=2000)
    region_x: int | None = Field(default=None, ge=0)
    region_y: int | None = Field(default=None, ge=0)
    region_width: int | None = Field(default=None, gt=0)
    region_height: int | None = Field(default=None, gt=0)

    @field_validator("purpose", "transcription", "limitations")
    @classmethod
    def clean_manual_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def complete_manual_region(self):
        values = (self.region_x, self.region_y, self.region_width, self.region_height)
        if any(value is not None for value in values) and not all(value is not None for value in values):
            raise ValueError("A source region requires x, y, width, and height.")
        return self


SCHEMA = """
CREATE TABLE IF NOT EXISTS handwriting_ocr_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, job_key TEXT NOT NULL UNIQUE,
 source_material_id INTEGER NOT NULL, source_sha256 TEXT NOT NULL, source_media_type TEXT NOT NULL,
 purpose TEXT NOT NULL, recognition_mode TEXT NOT NULL, route TEXT NOT NULL,
 source_width INTEGER NOT NULL, source_height INTEGER NOT NULL,
 region_x INTEGER NOT NULL, region_y INTEGER NOT NULL, region_width INTEGER NOT NULL, region_height INTEGER NOT NULL,
 profile_key TEXT NOT NULL, profile_snapshot_json TEXT NOT NULL, profile_snapshot_sha256 TEXT NOT NULL,
 executable_sha256 TEXT NOT NULL, model_sha256 TEXT NOT NULL, language_data_sha256 TEXT NOT NULL,
 configuration_sha256 TEXT NOT NULL, transform_json TEXT NOT NULL, external_processing INTEGER NOT NULL DEFAULT 0,
 outcome TEXT NOT NULL, error_code TEXT NOT NULL DEFAULT '', duration_ms INTEGER NOT NULL,
 segment_count INTEGER NOT NULL, character_count INTEGER NOT NULL, truncated INTEGER NOT NULL DEFAULT 0,
 sensitivity TEXT NOT NULL, disclosure_status TEXT NOT NULL, requested_by TEXT NOT NULL,
 requested_by_role TEXT NOT NULL, requested_at TEXT NOT NULL, completed_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_handwriting_ocr_jobs_scope ON handwriting_ocr_jobs(tenant_id,outcome,id);

CREATE TABLE IF NOT EXISTS handwriting_ocr_segments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, segment_key TEXT NOT NULL UNIQUE,
 job_id INTEGER NOT NULL, source_material_id INTEGER NOT NULL, source_sha256 TEXT NOT NULL,
 reading_order INTEGER NOT NULL, original_text TEXT NOT NULL, segment_type TEXT NOT NULL,
 processor_score TEXT NOT NULL, score_semantics TEXT NOT NULL, alternatives_json TEXT NOT NULL,
 uncertain_spans_json TEXT NOT NULL, limitations TEXT NOT NULL,
 region_x INTEGER NOT NULL, region_y INTEGER NOT NULL, region_width INTEGER NOT NULL, region_height INTEGER NOT NULL,
 language TEXT NOT NULL, script TEXT NOT NULL, record_type TEXT NOT NULL, record_origin TEXT NOT NULL,
 review_status TEXT NOT NULL, sensitivity TEXT NOT NULL, disclosure_status TEXT NOT NULL,
 reviewed_by TEXT NOT NULL DEFAULT '', reviewed_by_role TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '',
 review_basis TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (job_id) REFERENCES handwriting_ocr_jobs(id) ON DELETE RESTRICT,
 FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_handwriting_ocr_triage ON handwriting_ocr_segments(tenant_id,review_status,id);

CREATE TABLE IF NOT EXISTS handwriting_ocr_reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, segment_id INTEGER NOT NULL,
 review_type TEXT NOT NULL, reason TEXT NOT NULL, corrected_text TEXT NOT NULL DEFAULT '',
 corrected_segment_type TEXT NOT NULL DEFAULT '', limitations TEXT NOT NULL DEFAULT '',
 reviewed_by TEXT NOT NULL, reviewed_by_role TEXT NOT NULL, reviewed_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (segment_id) REFERENCES handwriting_ocr_segments(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_handwriting_ocr_reviews ON handwriting_ocr_reviews(segment_id,id);
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
    manifest = Path(os.getenv(PROFILE_MANIFEST, "/opt/salcapa-handwriting-ocr/active-profile.json"))
    root = Path(os.getenv(PROFILE_ROOT, "/opt/salcapa-handwriting-ocr"))
    if not manifest.is_absolute() or not root.is_absolute() or not manifest.is_file():
        return None, "No approved local text-recognition profile is installed. The original and manual transcription remain available."
    try:
        profile = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "The installed text-recognition profile is unreadable. Processing is disabled; manual transcription remains available."
    required = {
        "profile_key", "name", "status", "executable_path", "executable_sha256", "model_path", "model_sha256",
        "language_data_path", "language_data_sha256", "configuration_sha256", "model_version", "model_provenance",
        "model_license", "modes", "languages", "scripts", "score_semantics", "preprocessing", "known_limitations",
        "approved_purposes", "timeout_seconds", "max_segments", "max_characters",
    }
    if not isinstance(profile, dict) or not required.issubset(profile) or profile.get("status") != "Active":
        return None, "The installed text-recognition profile is not active. Processing is disabled; manual transcription remains available."
    artifacts = [Path(str(profile[name])) for name in ("executable_path", "model_path", "language_data_path")]
    try:
        for artifact in artifacts:
            artifact.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return None, "The installed text-recognition artifacts are outside their approved boundary. Processing is disabled."
    expected = [profile["executable_sha256"], profile["model_sha256"], profile["language_data_sha256"]]
    if any(_sha(path) != digest for path, digest in zip(artifacts, expected)):
        return None, "An installed text-recognition artifact does not match its approved hash. Processing is disabled."
    if not all(isinstance(profile[name], list) and profile[name] for name in ("modes", "languages", "scripts")):
        return None, "The installed text-recognition capability declaration is invalid. Processing is disabled."
    if not 1 <= int(profile["max_segments"]) <= 500 or not 1 <= int(profile["max_characters"]) <= 100000:
        return None, "The installed text-recognition output limits are invalid. Processing is disabled."
    profile["profile_root"] = str(root)
    return profile, "The approved local profile is available on request. Prepared text remains unverified until a different authorized person compares it with the original."


def register_salcapa_handwriting_ocr_processing(fastapi_app, core: dict) -> None:
    db, now, actor, role, tenant_id = (core[name] for name in ("db", "now", "actor", "role", "tenant_id"))
    require, require_sensitivity = core["require"], core["require_sensitivity"]
    protected_member_request = core["protected_member_request"]
    require_salus_component_authority = core["require_salus_component_authority"]
    security_event, storage = core["security_event"], core["storage"]
    conn = db()
    try:
        conn.executescript(SCHEMA); conn.commit()
    finally:
        conn.close()

    tenant_tables = {"handwriting_ocr_jobs", "handwriting_ocr_segments", "handwriting_ocr_reviews"}
    database_support.ID_TABLES.update(tenant_tables)
    if not getattr(fastapi_app.state, "salcapa_handwriting_ocr_backup_registered", False):
        base_collect, base_validate, base_replace = (core[name] for name in ("collect_tenant_records", "validate_records", "replace_tenant_records"))

        def collect(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            for table in sorted(tenant_tables):
                records[table] = [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (selected_tenant,))]
            return records

        def validate(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            materials = {int(row["id"]) for row in records.get("materials", []) if row.get("id") is not None}
            jobs = {int(row["id"]) for row in records.get("handwriting_ocr_jobs", []) if row.get("id") is not None}
            segments = {int(row["id"]) for row in records.get("handwriting_ocr_segments", []) if row.get("id") is not None}
            for table in tenant_tables:
                for row in records.get(table, []):
                    if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("handwriting_ocr_jobs", []):
                if int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"handwriting OCR job {row.get('id')} has invalid source lineage")
                for field in ("source_sha256", "profile_snapshot_sha256", "executable_sha256", "model_sha256", "language_data_sha256", "configuration_sha256"):
                    if len(str(row.get(field, ""))) != 64:
                        errors.append(f"handwriting OCR job {row.get('id')} has invalid {field}")
                for field in ("profile_snapshot_json", "transform_json"):
                    try:
                        if not isinstance(json.loads(row.get(field, "{}")), dict): raise ValueError
                    except (TypeError, ValueError, json.JSONDecodeError):
                        errors.append(f"handwriting OCR job {row.get('id')} has invalid {field}")
            for row in records.get("handwriting_ocr_segments", []):
                if int(row.get("job_id", -1)) not in jobs or int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"handwriting OCR segment {row.get('id')} has invalid lineage")
                for field in ("alternatives_json", "uncertain_spans_json"):
                    try:
                        if not isinstance(json.loads(row.get(field, "[]")), list): raise ValueError
                    except (TypeError, ValueError, json.JSONDecodeError):
                        errors.append(f"handwriting OCR segment {row.get('id')} has invalid {field}")
            for row in records.get("handwriting_ocr_reviews", []):
                if int(row.get("segment_id", -1)) not in segments:
                    errors.append(f"handwriting OCR review {row.get('id')} has invalid segment lineage")
            return errors

        def insert(conn, table: str, row: dict):
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            conn.execute(f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})", tuple(data.values()))

        def replace(conn, selected_tenant: int, records: dict):
            errors = validate(records, selected_tenant)
            if errors: raise ValueError("; ".join(errors))
            for table in ("handwriting_ocr_reviews", "handwriting_ocr_segments", "handwriting_ocr_jobs"):
                conn.execute(f"DELETE FROM {table} WHERE tenant_id=?", (selected_tenant,))
            base_replace(conn, selected_tenant, records)
            for table in ("handwriting_ocr_jobs", "handwriting_ocr_segments", "handwriting_ocr_reviews"):
                for row in records.get(table, []): insert(conn, table, row)
            database_support.reset_identity_sequences(conn, tenant_tables)

        core["collect_tenant_records"], core["validate_records"], core["replace_tenant_records"] = collect, validate, replace
        fastapi_app.state.salcapa_handwriting_ocr_backup_registered = True

    def internal(request: Request, permission: str = "read"):
        require(request, permission)
        if protected_member_request(request):
            raise HTTPException(403, "Text-recognition review is restricted to authorized Salus personnel.")

    def audit(conn, request: Request, action: str, entity_type: str, entity_id: int, detail: str):
        conn.execute("INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)", (now(), actor(request), action, entity_type, entity_id, detail[:2000], tenant_id(request)))

    def source(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row: raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "HANDWRITING_OCR_TENANT_BOUNDARY_VIOLATION", "High", f"material_id={material_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        extension = row["original_name"].rsplit(".", 1)[-1].lower() if "." in row["original_name"] else ""
        if row["disposition_status"] != "Active" or extension not in {"jpg", "jpeg", "png"}:
            raise HTTPException(422, "This bounded recognition release accepts active JPEG and PNG source records only.")
        return row, extension

    @fastapi_app.get("/api/handwriting-ocr/status")
    def status(request: Request):
        internal(request); profile, guidance = _profile()
        public_profile = None if profile is None else {key: profile[key] for key in ("profile_key", "name", "model_version", "model_provenance", "model_license", "modes", "languages", "scripts", "known_limitations", "score_semantics")}
        return {"available": profile is not None, "profile": public_profile, "guidance": guidance, "prohibited_conclusions": PROHIBITED_CONCLUSIONS, "external_processing": False, "manual_transcription_available": True}

    @fastapi_app.post("/api/materials/{material_id}/handwriting-ocr-jobs")
    def create_job(material_id: int, payload: RecognitionJobIn, request: Request):
        internal(request, "write"); require_salus_component_authority(request, "SalCAPA text-recognition review")
        profile, guidance = _profile()
        if profile is None: raise HTTPException(503, guidance)
        if payload.mode not in profile["modes"]: raise HTTPException(422, "The selected recognition mode is not supported by the installed profile.")
        if not any(token.lower() in payload.purpose.lower() for token in profile["approved_purposes"]):
            raise HTTPException(403, "The stated purpose is outside the installed profile's approved purposes.")
        conn = db(); row, extension = source(conn, material_id, request); conn.close()
        if int(row["size_bytes"]) > MAX_SOURCE_BYTES: raise HTTPException(422, "The source exceeds the bounded recognition limit.")
        try: data = storage.get_bytes(row["stored_name"])
        except FileNotFoundError as exc: raise HTTPException(404, "The governed source object is unavailable.") from exc
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            security_event(request, "HANDWRITING_OCR_SOURCE_HASH_MISMATCH", "Critical", f"material_id={material_id}")
            raise HTTPException(409, "Source integrity verification failed. No recognition job was created.")
        from PIL import Image
        with tempfile.TemporaryDirectory(prefix="salcapa-handwriting-ocr-") as directory:
            source_path = Path(directory) / f"source.{extension}"; source_path.write_bytes(data); source_path.chmod(0o400)
            with Image.open(source_path) as image: width, height = image.size
            x, y, rw, rh = (0, 0, width, height) if payload.region_x is None else (payload.region_x, payload.region_y, payload.region_width, payload.region_height)
            if x + rw > width or y + rh > height: raise HTTPException(422, "The selected source region exceeds the original image dimensions.")
            snapshot = {key: value for key, value in profile.items() if key != "profile_root"}; snapshot_json = _canonical(snapshot)
            manifest = {**profile, "source_path": str(source_path), "source_sha256": row["sha256"], "mode": payload.mode, "region": {"x": x, "y": y, "width": rw, "height": rh}}
            request_path = Path(directory) / "request.json"; request_path.write_text(_canonical(manifest), encoding="utf-8"); request_path.chmod(0o400)
            requested, started = now(), time.monotonic()
            try:
                completed = subprocess.run([sys.executable, "-I", str(WORKER), str(request_path)], cwd=directory, env={"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0"}, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=int(profile["timeout_seconds"]) + 10, check=False, start_new_session=True)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise HTTPException(503, "The approved local text-recognition process is unavailable. Original-source review and manual transcription remain available.") from exc
            if len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES: raise HTTPException(422, "The bounded recognition result exceeded its output limit.")
            try: result = json.loads(completed.stdout.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise HTTPException(422, "The isolated recognition worker returned an invalid result.") from exc
            if completed.returncode != 0 or result.get("ok") is not True:
                raise HTTPException(422, str(result.get("detail", "Local recognition did not complete safely."))[:1000])
            segments = result["segments"]
        completed_at = now(); duration = max(0, int((time.monotonic() - started) * 1000)); job_key = "HROJ-" + uuid.uuid4().hex
        transform = {"source_dimensions": [width, height], "selected_region": [x, y, rw, rh], "preprocessing": profile["preprocessing"], "output_coordinates": "inverse-mapped original decoded pixels"}
        conn = db()
        conn.execute("INSERT INTO handwriting_ocr_jobs(tenant_id,job_key,source_material_id,source_sha256,source_media_type,purpose,recognition_mode,route,source_width,source_height,region_x,region_y,region_width,region_height,profile_key,profile_snapshot_json,profile_snapshot_sha256,executable_sha256,model_sha256,language_data_sha256,configuration_sha256,transform_json,external_processing,outcome,duration_ms,segment_count,character_count,sensitivity,disclosure_status,requested_by,requested_by_role,requested_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id(request), job_key, material_id, row["sha256"], row["content_type"], payload.purpose, payload.mode, "Approved local profile", width, height, x, y, rw, rh, profile["profile_key"], snapshot_json, hashlib.sha256(snapshot_json.encode()).hexdigest(), profile["executable_sha256"], profile["model_sha256"], profile["language_data_sha256"], profile["configuration_sha256"], _canonical(transform), 0, "Completed", duration, len(segments), sum(len(item["text"]) for item in segments), row["sensitivity"], "Salus Internal — Not Released", actor(request), role(request), requested, completed_at))
        job = conn.execute("SELECT * FROM handwriting_ocr_jobs WHERE job_key=?", (job_key,)).fetchone()
        for item in segments:
            conn.execute("INSERT INTO handwriting_ocr_segments(tenant_id,segment_key,job_id,source_material_id,source_sha256,reading_order,original_text,segment_type,processor_score,score_semantics,alternatives_json,uncertain_spans_json,limitations,region_x,region_y,region_width,region_height,language,script,record_type,record_origin,review_status,sensitivity,disclosure_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id(request), "HROS-" + uuid.uuid4().hex, job["id"], material_id, row["sha256"], item["reading_order"], item["text"], item["segment_type"], item["score"], profile["score_semantics"], _canonical(item["alternatives"]), _canonical(item["uncertain_spans"]), item["limitations"], item["region_x"], item["region_y"], item["region_width"], item["region_height"], item["language"], item["script"], "Prepared Text — Derived and Unverified", "Approved local recognition profile", "Awaiting Human Review", row["sensitivity"], "Salus Internal — Not Released", completed_at, completed_at))
        audit(conn, request, "HANDWRITING_OCR_JOB_COMPLETED", "handwriting_ocr_job", int(job["id"]), f"source_material_id={material_id}; segments={len(segments)}; external_processing=false; no_authorship_identity_finding_or_disclosure=true")
        conn.commit(); output = {"job": dict(job), "segments": [dict(item) for item in conn.execute("SELECT * FROM handwriting_ocr_segments WHERE job_id=? ORDER BY reading_order,id", (job["id"],))]}; conn.close()
        for item in output["segments"]:
            item["alternatives"] = json.loads(item.pop("alternatives_json")); item["uncertain_spans"] = json.loads(item.pop("uncertain_spans_json")); item["authority_note"] = "Prepared text is an unverified representation of visible marks. It does not establish authorship, authenticity, source truth, identity, a finding, or disclosure authority."
        return output

    @fastapi_app.post("/api/materials/{material_id}/manual-transcriptions")
    def create_manual_transcription(material_id: int, payload: ManualTranscriptionIn, request: Request):
        internal(request, "write"); require_salus_component_authority(request, "SalCAPA manual transcription review")
        conn = db(); row, extension = source(conn, material_id, request); conn.close()
        try: data = storage.get_bytes(row["stored_name"])
        except FileNotFoundError as exc: raise HTTPException(404, "The governed source object is unavailable.") from exc
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            security_event(request, "MANUAL_TRANSCRIPTION_SOURCE_HASH_MISMATCH", "Critical", f"material_id={material_id}")
            raise HTTPException(409, "Source integrity verification failed. No transcription was recorded.")
        from PIL import Image
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
        x, y, rw, rh = (0, 0, width, height) if payload.region_x is None else (payload.region_x, payload.region_y, payload.region_width, payload.region_height)
        if x + rw > width or y + rh > height: raise HTTPException(422, "The selected source region exceeds the original image dimensions.")
        recorded = now(); job_key = "HROJ-" + uuid.uuid4().hex; zero = "0" * 64
        snapshot = _canonical({"route": "Human-entered manual transcription", "processor": None, "external_processing": False})
        transform = _canonical({"source_dimensions": [width, height], "selected_region": [x, y, rw, rh], "output_coordinates": "original decoded pixels"})
        conn = db(); conn.execute("INSERT INTO handwriting_ocr_jobs(tenant_id,job_key,source_material_id,source_sha256,source_media_type,purpose,recognition_mode,route,source_width,source_height,region_x,region_y,region_width,region_height,profile_key,profile_snapshot_json,profile_snapshot_sha256,executable_sha256,model_sha256,language_data_sha256,configuration_sha256,transform_json,external_processing,outcome,duration_ms,segment_count,character_count,sensitivity,disclosure_status,requested_by,requested_by_role,requested_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id(request), job_key, material_id, row["sha256"], row["content_type"], payload.purpose, "Manual transcription", "Human-entered manual transcription", width, height, x, y, rw, rh, "MANUAL", snapshot, hashlib.sha256(snapshot.encode()).hexdigest(), zero, zero, zero, zero, transform, 0, "Completed", 0, 1, len(payload.transcription), row["sensitivity"], "Salus Internal — Not Released", actor(request), role(request), recorded, recorded))
        job = conn.execute("SELECT * FROM handwriting_ocr_jobs WHERE job_key=?", (job_key,)).fetchone()
        conn.execute("INSERT INTO handwriting_ocr_segments(tenant_id,segment_key,job_id,source_material_id,source_sha256,reading_order,original_text,segment_type,processor_score,score_semantics,alternatives_json,uncertain_spans_json,limitations,region_x,region_y,region_width,region_height,language,script,record_type,record_origin,review_status,sensitivity,disclosure_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tenant_id(request), "HROS-" + uuid.uuid4().hex, job["id"], material_id, row["sha256"], 1, payload.transcription, payload.segment_type, "", "No processor score; human-entered text awaiting independent source comparison.", "[]", "[]", payload.limitations, x, y, rw, rh, "Not asserted", "Not asserted", "Human-Entered Transcription — Awaiting Independent Review", "Authorized person-entered transcription", "Awaiting Human Review", row["sensitivity"], "Salus Internal — Not Released", recorded, recorded))
        segment = conn.execute("SELECT * FROM handwriting_ocr_segments WHERE job_id=?", (job["id"],)).fetchone(); audit(conn, request, "MANUAL_TRANSCRIPTION_RECORDED", "handwriting_ocr_segment", int(segment["id"]), f"source_material_id={material_id}; independent_review_required=true; no_source_truth_or_disclosure=true"); conn.commit(); result = {"job": dict(job), "segment": dict(segment)}; conn.close(); result["segment"]["authority_note"] = "This person-entered transcription still requires an independent source comparison. It does not establish source truth, authorship, identity, a finding, or disclosure authority."; return result

    @fastapi_app.get("/api/handwriting-ocr/triage")
    def triage(request: Request, limit: int = 200):
        internal(request); conn = db()
        rows = [dict(row) for row in conn.execute("SELECT s.*,m.title source_title,m.original_name,j.purpose,j.recognition_mode,j.route,j.requested_by FROM handwriting_ocr_segments s JOIN handwriting_ocr_jobs j ON j.id=s.job_id JOIN materials m ON m.id=s.source_material_id WHERE s.tenant_id=? ORDER BY CASE s.review_status WHEN 'Awaiting Human Review' THEN 0 ELSE 1 END,s.id DESC LIMIT ?", (tenant_id(request), max(1, min(limit, 500)))) if (require_sensitivity(request, row["sensitivity"]) is None)]
        conn.close()
        for item in rows:
            item["alternatives"] = json.loads(item.pop("alternatives_json")); item["uncertain_spans"] = json.loads(item.pop("uncertain_spans_json")); item["authority_note"] = "Compare this prepared text with the exact original source region. Uncertain or missing text must not be guessed."
        return {"items": rows, "guidance": "Prepared text remains derived and unverified. Absence of recognized text does not prove that no text is present."}

    @fastapi_app.post("/api/handwriting-ocr/segments/{segment_id}/review")
    def review(segment_id: int, payload: SegmentReviewIn, request: Request):
        internal(request, "decide"); require_salus_component_authority(request, "SalCAPA text-recognition review")
        conn = db(); row = conn.execute("SELECT s.*,j.requested_by FROM handwriting_ocr_segments s JOIN handwriting_ocr_jobs j ON j.id=s.job_id WHERE s.id=?", (segment_id,)).fetchone()
        if not row: conn.close(); raise HTTPException(404, "Prepared text segment not found")
        if int(row["tenant_id"]) != tenant_id(request): conn.close(); raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["review_status"] != "Awaiting Human Review": conn.close(); raise HTTPException(409, "This segment already has a recorded review state")
        if row["requested_by"] == actor(request): conn.close(); raise HTTPException(409, "A different authorized person must compare this prepared text with the original")
        reviewed = now(); conn.execute("UPDATE handwriting_ocr_segments SET review_status=?,reviewed_by=?,reviewed_by_role=?,reviewed_at=?,review_basis=?,updated_at=? WHERE id=?", (payload.status, actor(request), role(request), reviewed, payload.reason, reviewed, segment_id))
        conn.execute("INSERT INTO handwriting_ocr_reviews(tenant_id,segment_id,review_type,reason,corrected_text,corrected_segment_type,limitations,reviewed_by,reviewed_by_role,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (tenant_id(request), segment_id, payload.status, payload.reason, payload.corrected_text, payload.corrected_segment_type, payload.limitations, actor(request), role(request), reviewed))
        audit(conn, request, "HANDWRITING_OCR_SEGMENT_REVIEWED", "handwriting_ocr_segment", segment_id, f"status={payload.status}; source_and_original_output_unchanged=true; no_source_truth_or_disclosure=true")
        conn.commit(); result = dict(conn.execute("SELECT * FROM handwriting_ocr_segments WHERE id=?", (segment_id,)).fetchone()); conn.close(); result["authority_note"] = "This review addresses representation of visible marks only. It does not establish source truth, authorship, identity, a finding, or disclosure authority."; return result
