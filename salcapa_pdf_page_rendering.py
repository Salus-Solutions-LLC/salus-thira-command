"""Governed, bounded local rendering of explicitly selected PDF pages."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Literal

import database as database_support
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import salcapa_pdf_processing as pdf_processing


WORKER = Path(__file__).resolve().parent / "tools" / "salcapa_pdf_render_worker.py"
PROFILE_MANIFEST = "SALUS_PDF_RENDER_PROFILE_MANIFEST"
PROFILE_ROOT = "SALUS_PDF_RENDER_PROFILE_ROOT"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_WORKER_OUTPUT_BYTES = 2 * 1024 * 1024
PAGE_REASONS = {
    "No Embedded Text",
    "Visible Text Missing",
    "Embedded Text Mismatch",
    "Handwriting or Mark Review",
    "Layout Review Needed",
}
AUTHORITY_NOTE = (
    "A rendered page is a source-linked representation for review. It does not establish source truth, "
    "authenticity, authorship, identity, evidence, intelligence, a finding, a priority, a decision, or disclosure authority."
)


class PageSelectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int = Field(ge=1)
    reason: Literal[
        "No Embedded Text",
        "Visible Text Missing",
        "Embedded Text Mismatch",
        "Handwriting or Mark Review",
        "Layout Review Needed",
    ]


class PdfRenderJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(min_length=1, max_length=4000)
    pages: list[PageSelectionIn] = Field(min_length=1, max_length=12)

    @field_validator("purpose")
    @classmethod
    def clean_purpose(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def unique_pages(self):
        page_numbers = [item.page_number for item in self.pages]
        if len(page_numbers) != len(set(page_numbers)):
            raise ValueError("Each selected PDF page may appear only once.")
        return self


SCHEMA = """
CREATE TABLE IF NOT EXISTS pdf_render_jobs (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, job_key TEXT NOT NULL UNIQUE,
 source_material_id INTEGER NOT NULL, source_sha256 TEXT NOT NULL, source_media_type TEXT NOT NULL,
 purpose TEXT NOT NULL, requested_pages_json TEXT NOT NULL,
 inspection_processor TEXT NOT NULL, inspection_processor_version TEXT NOT NULL,
 inspection_facts_sha256 TEXT NOT NULL,
 profile_key TEXT NOT NULL, profile_snapshot_json TEXT NOT NULL, profile_snapshot_sha256 TEXT NOT NULL,
 executable_sha256 TEXT NOT NULL, configuration_sha256 TEXT NOT NULL,
 dpi INTEGER NOT NULL, color_mode TEXT NOT NULL, output_format TEXT NOT NULL,
 external_processing INTEGER NOT NULL DEFAULT 0, network_allowed INTEGER NOT NULL DEFAULT 0,
 outcome TEXT NOT NULL, error_code TEXT NOT NULL DEFAULT '', duration_ms INTEGER NOT NULL,
 page_count INTEGER NOT NULL, total_pixels INTEGER NOT NULL, total_output_bytes INTEGER NOT NULL,
 rendered_bytes_posture TEXT NOT NULL, sensitivity TEXT NOT NULL, disclosure_status TEXT NOT NULL,
 requested_by TEXT NOT NULL, requested_by_role TEXT NOT NULL, requested_at TEXT NOT NULL, completed_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_pdf_render_jobs_scope ON pdf_render_jobs(tenant_id,outcome,id);

CREATE TABLE IF NOT EXISTS pdf_rendered_pages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, page_key TEXT NOT NULL UNIQUE,
 job_id INTEGER NOT NULL, source_material_id INTEGER NOT NULL, source_sha256 TEXT NOT NULL,
 page_number INTEGER NOT NULL, source_page_label TEXT NOT NULL, rendering_reason TEXT NOT NULL,
 embedded_text_available INTEGER NOT NULL, media_box_json TEXT NOT NULL, crop_box_json TEXT NOT NULL,
 rotation INTEGER NOT NULL, user_unit TEXT NOT NULL, rendered_width INTEGER NOT NULL, rendered_height INTEGER NOT NULL,
 dpi INTEGER NOT NULL, color_mode TEXT NOT NULL, output_format TEXT NOT NULL, rendered_sha256 TEXT NOT NULL,
 forward_transform_json TEXT NOT NULL, inverse_transform_json TEXT NOT NULL,
 limitations TEXT NOT NULL, rendered_bytes_posture TEXT NOT NULL, retained_material_id INTEGER,
 record_type TEXT NOT NULL, review_status TEXT NOT NULL, sensitivity TEXT NOT NULL, purpose TEXT NOT NULL,
 disclosure_status TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (job_id) REFERENCES pdf_render_jobs(id) ON DELETE RESTRICT,
 FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
 FOREIGN KEY (retained_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_pdf_rendered_pages_scope ON pdf_rendered_pages(tenant_id,source_material_id,page_number,id);
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
    manifest = Path(os.getenv(PROFILE_MANIFEST, "/opt/salcapa-pdf-render/active-profile.json"))
    root = Path(os.getenv(PROFILE_ROOT, "/opt/salcapa-pdf-render"))
    if not manifest.is_absolute() or not root.is_absolute() or not manifest.is_file():
        return None, "No approved local PDF page-rendering profile is installed. The original PDF and embedded text remain available."
    try:
        manifest.resolve(strict=True).relative_to(root.resolve(strict=True))
        manifest_mode = manifest.stat().st_mode
    except (OSError, ValueError):
        return None, "The installed PDF page-rendering profile is outside its approved boundary. Rendering is disabled."
    if manifest_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return None, "The installed PDF page-rendering profile permissions are not acceptable. Rendering is disabled."
    try:
        profile = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, "The installed PDF page-rendering profile is unreadable. Rendering is disabled."
    required = {
        "profile_key", "name", "status", "executable_path", "executable_sha256", "renderer_version",
        "renderer_provenance", "renderer_license", "configuration_sha256", "approved_purposes",
        "dpi", "color_mode", "output_format", "max_pages", "max_pixels_per_page", "max_total_pixels",
        "max_output_bytes_per_page", "max_total_output_bytes", "timeout_seconds", "known_limitations",
        "external_processing", "no_network",
    }
    if not isinstance(profile, dict) or not required.issubset(profile) or profile.get("status") != "Active":
        return None, "The installed PDF page-rendering profile is not active. Rendering is disabled."
    executable = Path(str(profile["executable_path"]))
    try:
        executable.resolve(strict=True).relative_to(root.resolve(strict=True))
        mode = executable.stat().st_mode
    except (OSError, ValueError):
        return None, "The installed PDF renderer is outside its approved boundary. Rendering is disabled."
    if not executable.is_file() or not os.access(executable, os.X_OK) or mode & (stat.S_IWGRP | stat.S_IWOTH):
        return None, "The installed PDF renderer permissions are not acceptable. Rendering is disabled."
    if _sha(executable) != profile["executable_sha256"]:
        return None, "The installed PDF renderer does not match its approved hash. Rendering is disabled."
    for field in ("executable_sha256", "configuration_sha256"):
        value = str(profile[field])
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value.lower()):
            return None, "The installed PDF page-rendering profile contains an invalid integrity value. Rendering is disabled."
    try:
        limits = {
            "dpi": int(profile["dpi"]), "max_pages": int(profile["max_pages"]),
            "max_pixels_per_page": int(profile["max_pixels_per_page"]),
            "max_total_pixels": int(profile["max_total_pixels"]),
            "max_output_bytes_per_page": int(profile["max_output_bytes_per_page"]),
            "max_total_output_bytes": int(profile["max_total_output_bytes"]),
            "timeout_seconds": int(profile["timeout_seconds"]),
        }
    except (TypeError, ValueError):
        return None, "The installed PDF page-rendering limits are invalid. Rendering is disabled."
    if not (72 <= limits["dpi"] <= 300 and 1 <= limits["max_pages"] <= 12):
        return None, "The installed PDF page-rendering resolution or page limit is outside the governed boundary."
    if not (1 <= limits["max_pixels_per_page"] <= 40_000_000 and 1 <= limits["max_total_pixels"] <= 120_000_000):
        return None, "The installed PDF page-rendering pixel limits are outside the governed boundary."
    if limits["max_total_pixels"] < limits["max_pixels_per_page"]:
        return None, "The installed PDF page-rendering aggregate limit is invalid."
    if not (1 <= limits["timeout_seconds"] <= 90 and 1 <= limits["max_output_bytes_per_page"] <= 128 * 1024 * 1024):
        return None, "The installed PDF page-rendering resource limits are outside the governed boundary."
    if not (1 <= limits["max_total_output_bytes"] <= 512 * 1024 * 1024):
        return None, "The installed PDF page-rendering output limit is outside the governed boundary."
    if profile["external_processing"] is not False or profile["no_network"] is not True:
        return None, "The installed profile does not enforce local no-network rendering. Rendering is disabled."
    if profile["color_mode"] != "RGB" or profile["output_format"] != "PNG":
        return None, "The installed PDF page-rendering output format is outside the approved profile."
    if not isinstance(profile["approved_purposes"], list) or not profile["approved_purposes"]:
        return None, "The installed PDF page-rendering purpose controls are invalid."
    profile["profile_root"] = str(root)
    return profile, "The approved local renderer is available for explicitly selected pages. Rendered bytes are ephemeral by default."


def _affine(box: list[float], rotation: int, width: int, height: int) -> tuple[list[float], list[float]]:
    llx, lly, urx, ury = box
    page_width, page_height = urx - llx, ury - lly
    if page_width <= 0 or page_height <= 0:
        raise ValueError("Invalid PDF crop box")
    rotation %= 360
    if rotation == 0:
        forward = [width / page_width, 0.0, -llx * width / page_width, 0.0, -height / page_height, ury * height / page_height]
    elif rotation == 90:
        forward = [0.0, width / page_height, -lly * width / page_height, height / page_width, 0.0, -llx * height / page_width]
    elif rotation == 180:
        forward = [-width / page_width, 0.0, urx * width / page_width, 0.0, height / page_height, -lly * height / page_height]
    elif rotation == 270:
        forward = [0.0, -width / page_height, ury * width / page_height, -height / page_width, 0.0, urx * height / page_width]
    else:
        raise ValueError("Unsupported PDF page rotation")
    a, b, c, d, e, f = forward
    determinant = a * e - b * d
    if not math.isfinite(determinant) or abs(determinant) < 1e-12:
        raise ValueError("Invalid PDF page transform")
    inverse = [e / determinant, -b / determinant, (b * f - e * c) / determinant,
               -d / determinant, a / determinant, (d * c - a * f) / determinant]
    if not all(math.isfinite(item) for item in forward + inverse):
        raise ValueError("Non-finite PDF page transform")
    return [round(item, 12) for item in forward], [round(item, 12) for item in inverse]


def register_salcapa_pdf_page_rendering(fastapi_app, core: dict) -> None:
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

    tenant_tables = {"pdf_render_jobs", "pdf_rendered_pages"}
    database_support.ID_TABLES.update(tenant_tables)
    if not getattr(fastapi_app.state, "salcapa_pdf_render_backup_registered", False):
        base_collect, base_validate, base_replace = (core[name] for name in ("collect_tenant_records", "validate_records", "replace_tenant_records"))

        def collect(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            for table in sorted(tenant_tables):
                records[table] = [dict(row) for row in conn.execute(f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (selected_tenant,))]
            return records

        def validate(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            materials = {int(row["id"]) for row in records.get("materials", []) if row.get("id") is not None}
            jobs = {int(row["id"]) for row in records.get("pdf_render_jobs", []) if row.get("id") is not None}
            for table in tenant_tables:
                for row in records.get(table, []):
                    if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("pdf_render_jobs", []):
                if int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"PDF render job {row.get('id')} has invalid source lineage")
                for field in ("source_sha256", "inspection_facts_sha256", "profile_snapshot_sha256", "executable_sha256", "configuration_sha256"):
                    if len(str(row.get(field, ""))) != 64:
                        errors.append(f"PDF render job {row.get('id')} has invalid {field}")
                for field in ("requested_pages_json", "profile_snapshot_json"):
                    try:
                        if not isinstance(json.loads(row.get(field, "[]")), (list, dict)): raise ValueError
                    except (TypeError, ValueError, json.JSONDecodeError):
                        errors.append(f"PDF render job {row.get('id')} has invalid {field}")
            for row in records.get("pdf_rendered_pages", []):
                if int(row.get("job_id", -1)) not in jobs or int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"rendered PDF page {row.get('id')} has invalid lineage")
                if row.get("rendering_reason") not in PAGE_REASONS:
                    errors.append(f"rendered PDF page {row.get('id')} has invalid rendering reason")
                if len(str(row.get("rendered_sha256", ""))) != 64:
                    errors.append(f"rendered PDF page {row.get('id')} has invalid rendered hash")
                for field in ("media_box_json", "crop_box_json", "forward_transform_json", "inverse_transform_json"):
                    try:
                        value = json.loads(row.get(field, "[]"))
                        if not isinstance(value, list) or not all(isinstance(item, (int, float)) and math.isfinite(item) for item in value): raise ValueError
                    except (TypeError, ValueError, json.JSONDecodeError):
                        errors.append(f"rendered PDF page {row.get('id')} has invalid {field}")
            return errors

        def insert(conn, table: str, row: dict):
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            conn.execute(f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})", tuple(data.values()))

        def replace(conn, selected_tenant: int, records: dict):
            errors = validate(records, selected_tenant)
            if errors: raise ValueError("; ".join(errors))
            for table in ("pdf_rendered_pages", "pdf_render_jobs"):
                conn.execute(f"DELETE FROM {table} WHERE tenant_id=?", (selected_tenant,))
            base_replace(conn, selected_tenant, records)
            for table in ("pdf_render_jobs", "pdf_rendered_pages"):
                for row in records.get(table, []): insert(conn, table, row)
            database_support.reset_identity_sequences(conn, tenant_tables)

        core["collect_tenant_records"], core["validate_records"], core["replace_tenant_records"] = collect, validate, replace
        fastapi_app.state.salcapa_pdf_render_backup_registered = True

    def internal(request: Request, permission: str = "read"):
        require(request, permission)
        if protected_member_request(request):
            raise HTTPException(403, "Scanned-page review is restricted to authorized Salus personnel.")

    def audit(conn, request: Request, action: str, entity_type: str, entity_id: int, detail: str):
        conn.execute("INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)", (now(), actor(request), action, entity_type, entity_id, detail[:2000], tenant_id(request)))

    def source(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row: raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "PDF_RENDER_TENANT_BOUNDARY_VIOLATION", "High", f"material_id={material_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        extension = row["original_name"].rsplit(".", 1)[-1].lower() if "." in row["original_name"] else ""
        if row["disposition_status"] != "Active" or extension != "pdf" or row["content_type"].split(";", 1)[0].strip().lower() != "application/pdf":
            raise HTTPException(422, "This bounded page-review path accepts active governed PDF source records only.")
        return row

    @fastapi_app.get("/api/pdf-page-rendering/status")
    def status(request: Request):
        internal(request); profile, guidance = _profile()
        public_profile = None if profile is None else {key: profile[key] for key in (
            "profile_key", "name", "renderer_version", "renderer_provenance", "renderer_license", "dpi",
            "color_mode", "output_format", "max_pages", "known_limitations")}
        return {"available": profile is not None, "profile": public_profile, "guidance": guidance,
                "page_reasons": sorted(PAGE_REASONS), "external_processing": False,
                "rendered_bytes_posture": "Ephemeral — Deleted After Validation", "authority_note": AUTHORITY_NOTE}

    @fastapi_app.post("/api/materials/{material_id}/pdf-render-jobs")
    def create_job(material_id: int, payload: PdfRenderJobIn, request: Request):
        internal(request, "write"); require_salus_component_authority(request, "SalCAPA scanned-page review")
        profile, guidance = _profile()
        if profile is None: raise HTTPException(503, guidance)
        if len(payload.pages) > int(profile["max_pages"]):
            raise HTTPException(422, "The selected page count exceeds the installed profile limit.")
        if not any(token.lower() in payload.purpose.lower() for token in profile["approved_purposes"]):
            raise HTTPException(403, "The stated purpose is outside the installed profile's approved purposes.")
        conn = db(); row = source(conn, material_id, request); conn.close()
        if int(row["size_bytes"]) > MAX_SOURCE_BYTES: raise HTTPException(422, "The PDF exceeds the bounded source-size limit.")
        try: data = storage.get_bytes(row["stored_name"])
        except FileNotFoundError as exc: raise HTTPException(404, "The governed source object is unavailable.") from exc
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            security_event(request, "PDF_RENDER_SOURCE_HASH_MISMATCH", "Critical", f"material_id={material_id}")
            raise HTTPException(409, "Source integrity verification failed. No page-rendering job was created.")
        try:
            inspection = pdf_processing._run_worker(data)
        except pdf_processing.base.ProcessingFailure as exc:
            raise HTTPException(422, exc.detail) from exc
        facts = inspection.get("facts", {})
        page_count = int(facts.get("source_page_count", 0))
        page_facts = {int(item["page"]): item for item in facts.get("page_facts", []) if isinstance(item, dict) and "page" in item}
        for selected in payload.pages:
            if selected.page_number > page_count or selected.page_number not in page_facts:
                raise HTTPException(422, "A selected page is outside the strictly inspected PDF page set.")
            if selected.reason == "No Embedded Text" and page_facts[selected.page_number].get("embedded_text_available") is not False:
                raise HTTPException(422, "No Embedded Text may be used only when inspection found no usable embedded text on that page.")
        snapshot = {key: value for key, value in profile.items() if key != "profile_root"}; snapshot_json = _canonical(snapshot)
        requested_pages = [{"page_number": item.page_number, "reason": item.reason} for item in payload.pages]
        inspection_json = _canonical(facts)
        requested_at, started = now(), time.monotonic()
        with tempfile.TemporaryDirectory(prefix="salcapa-pdf-render-") as directory:
            root = Path(directory); source_path = root / "source.pdf"; output_dir = root / "output"; output_dir.mkdir(mode=0o700)
            source_path.write_bytes(data); source_path.chmod(0o400)
            manifest = {**snapshot, "source_path": str(source_path), "source_sha256": row["sha256"],
                        "output_dir": str(output_dir), "pages": requested_pages}
            request_path = root / "request.json"; request_path.write_text(_canonical(manifest), encoding="utf-8"); request_path.chmod(0o400)
            try:
                completed = subprocess.run([sys.executable, "-I", str(WORKER), str(request_path)], cwd=directory,
                    env={"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "HOME": directory, "PATH": "/usr/bin:/bin"},
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=int(profile["timeout_seconds"]) + 10, check=False, start_new_session=True)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise HTTPException(503, "The approved local page renderer is unavailable. Original-PDF and manual review remain available.") from exc
            if len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES:
                raise HTTPException(422, "The bounded page-rendering result exceeded its response limit.")
            try: result = json.loads(completed.stdout.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc: raise HTTPException(422, "The isolated page renderer returned an invalid result.") from exc
            if completed.returncode != 0 or result.get("ok") is not True:
                raise HTTPException(422, str(result.get("detail", "Local page rendering did not complete safely."))[:1000])
            rendered = result.get("pages")
            if not isinstance(rendered, list) or len(rendered) != len(payload.pages):
                raise HTTPException(422, "The isolated page renderer returned an incomplete result.")
            expected_files = {str(item.get("output_name", "")) for item in rendered}
            if not expected_files or set(path.name for path in output_dir.iterdir()) != expected_files:
                raise HTTPException(422, "The isolated page renderer returned unexpected output files.")
            validated_pages = []
            total_pixels = total_bytes = 0
            from PIL import Image
            selected_by_page = {item.page_number: item for item in payload.pages}
            for item in rendered:
                number = int(item.get("page_number", 0)); selected = selected_by_page.get(number)
                if selected is None: raise HTTPException(422, "The isolated page renderer returned an unexpected page.")
                output_path = output_dir / str(item.get("output_name", ""))
                rendered_bytes = output_path.read_bytes(); digest = hashlib.sha256(rendered_bytes).hexdigest()
                if digest != item.get("rendered_sha256"): raise HTTPException(422, "Rendered-page integrity validation failed.")
                with Image.open(output_path) as image:
                    width, height = image.size
                    if image.format != "PNG" or image.mode not in {"RGB", "RGBA"}: raise HTTPException(422, "Rendered-page format validation failed.")
                if width != int(item.get("width", 0)) or height != int(item.get("height", 0)):
                    raise HTTPException(422, "Rendered-page dimensions do not match the worker result.")
                pixels, output_bytes = width * height, len(rendered_bytes); total_pixels += pixels; total_bytes += output_bytes
                if pixels > int(profile["max_pixels_per_page"]) or output_bytes > int(profile["max_output_bytes_per_page"]):
                    raise HTTPException(422, "A rendered page exceeded the governed resource boundary.")
                media_box, crop_box = item.get("media_box"), item.get("crop_box")
                if not (isinstance(media_box, list) and isinstance(crop_box, list) and len(media_box) == len(crop_box) == 4):
                    raise HTTPException(422, "The isolated page renderer returned invalid page geometry.")
                try:
                    numeric_media = [float(value) for value in media_box]; numeric_crop = [float(value) for value in crop_box]
                    if not all(math.isfinite(value) for value in numeric_media + numeric_crop): raise ValueError
                    rotation = int(item.get("rotation", 0)) % 360
                    forward, inverse = _affine(numeric_crop, rotation, width, height)
                except (TypeError, ValueError) as exc: raise HTTPException(422, "The isolated page renderer returned invalid page geometry.") from exc
                validated_pages.append({**item, "page_number": number, "reason": selected.reason,
                    "embedded_text_available": bool(page_facts[number].get("embedded_text_available")),
                    "media_box": numeric_media, "crop_box": numeric_crop, "forward": forward, "inverse": inverse,
                    "width": width, "height": height, "rendered_sha256": digest, "output_bytes": output_bytes})
            if total_pixels > int(profile["max_total_pixels"]) or total_bytes > int(profile["max_total_output_bytes"]):
                raise HTTPException(422, "The rendered page set exceeded the aggregate governed resource boundary.")
        completed_at = now(); duration_ms = max(0, int((time.monotonic() - started) * 1000)); job_key = "PDRJ-" + uuid.uuid4().hex
        conn = db()
        conn.execute("INSERT INTO pdf_render_jobs(tenant_id,job_key,source_material_id,source_sha256,source_media_type,purpose,requested_pages_json,inspection_processor,inspection_processor_version,inspection_facts_sha256,profile_key,profile_snapshot_json,profile_snapshot_sha256,executable_sha256,configuration_sha256,dpi,color_mode,output_format,external_processing,network_allowed,outcome,duration_ms,page_count,total_pixels,total_output_bytes,rendered_bytes_posture,sensitivity,disclosure_status,requested_by,requested_by_role,requested_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), job_key, material_id, row["sha256"], row["content_type"], payload.purpose, _canonical(requested_pages),
             str(facts.get("processor", "")), str(facts.get("processor_version", "")), hashlib.sha256(inspection_json.encode()).hexdigest(),
             profile["profile_key"], snapshot_json, hashlib.sha256(snapshot_json.encode()).hexdigest(), profile["executable_sha256"],
             profile["configuration_sha256"], int(profile["dpi"]), profile["color_mode"], profile["output_format"], 0, 0,
             "Completed", duration_ms, len(validated_pages), total_pixels, total_bytes, "Ephemeral — Deleted After Validation",
             row["sensitivity"], "Salus Internal — Not Released", actor(request), role(request), requested_at, completed_at))
        job = conn.execute("SELECT * FROM pdf_render_jobs WHERE job_key=?", (job_key,)).fetchone()
        for item in validated_pages:
            conn.execute("INSERT INTO pdf_rendered_pages(tenant_id,page_key,job_id,source_material_id,source_sha256,page_number,source_page_label,rendering_reason,embedded_text_available,media_box_json,crop_box_json,rotation,user_unit,rendered_width,rendered_height,dpi,color_mode,output_format,rendered_sha256,forward_transform_json,inverse_transform_json,limitations,rendered_bytes_posture,record_type,review_status,sensitivity,purpose,disclosure_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tenant_id(request), "PDRP-" + uuid.uuid4().hex, job["id"], material_id, row["sha256"], item["page_number"],
                 str(item.get("source_page_label", ""))[:200], item["reason"], int(item["embedded_text_available"]),
                 _canonical(item["media_box"]), _canonical(item["crop_box"]), int(item["rotation"]), str(item.get("user_unit", 1)),
                 item["width"], item["height"], int(profile["dpi"]), profile["color_mode"], profile["output_format"],
                 item["rendered_sha256"], _canonical(item["forward"]), _canonical(item["inverse"]),
                 str(item.get("limitations", profile["known_limitations"]))[:2000], "Ephemeral — Deleted After Validation",
                 "Rendered Representation — Not Source Truth", "Awaiting Human Review", row["sensitivity"], payload.purpose,
                 "Salus Internal — Not Released", completed_at))
        audit(conn, request, "PDF_SELECTED_PAGES_RENDERED", "pdf_render_job", int(job["id"]),
              f"source_material_id={material_id}; selected_pages={len(validated_pages)}; external_processing=false; rendered_bytes_deleted=true; no_finding_decision_or_disclosure=true")
        conn.commit(); output = {"job": dict(job), "pages": [dict(item) for item in conn.execute("SELECT * FROM pdf_rendered_pages WHERE job_id=? ORDER BY page_number,id", (job["id"],))]}; conn.close()
        for item in output["pages"]:
            for field in ("media_box_json", "crop_box_json", "forward_transform_json", "inverse_transform_json"):
                item[field.removesuffix("_json")] = json.loads(item.pop(field))
            item["authority_note"] = AUTHORITY_NOTE
        output["authority_note"] = AUTHORITY_NOTE
        return output
