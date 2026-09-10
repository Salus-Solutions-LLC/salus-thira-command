"""Governed exact-location review and source-region visual observations.

Exact coordinates remain restricted source metadata. Visual descriptions remain
review aids. Neither record type establishes source truth, identity, a finding,
an assessment, a decision, disclosure authority, or operational authority.
"""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from typing import Literal

import database as database_support
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PROCESSOR = "SalCAPA Isolated Location Metadata Extractor"
PROCESSOR_VERSION = "1.0.0"
WORKER = Path(__file__).resolve().parent / "tools" / "salcapa_visual_geospatial_worker.py"
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_WORKER_OUTPUT_BYTES = 1024 * 1024
WORKER_TIMEOUT_SECONDS = 20
DESTINATION_PRODUCTS = {
    "SalINTEL", "SalTHIRA", "SalCAPA", "SalOPS", "PROVE",
    "Personnel Assessment", "Facility Assessment", "Mission Map",
}


class PurposeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(min_length=1, max_length=4000)

    @field_validator("purpose")
    @classmethod
    def clean_purpose(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A legitimate review purpose is required.")
        return value


class LocationReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Human Reviewed", "Corrected", "Rejected"]
    reason: str = Field(min_length=1, max_length=4000)
    corrected_latitude_decimal: Decimal | None = Field(default=None, ge=Decimal("-90"), le=Decimal("90"))
    corrected_longitude_decimal: Decimal | None = Field(default=None, ge=Decimal("-180"), le=Decimal("180"))

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A review basis is required.")
        return value

    @model_validator(mode="after")
    def correction_pair(self):
        supplied = self.corrected_latitude_decimal is not None or self.corrected_longitude_decimal is not None
        if self.status == "Corrected" and not (
            self.corrected_latitude_decimal is not None and self.corrected_longitude_decimal is not None
        ):
            raise ValueError("A corrected location requires both latitude and longitude.")
        if self.status != "Corrected" and supplied:
            raise ValueError("Corrected coordinates are permitted only for a Corrected review.")
        return self


class VisualObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purpose: str = Field(min_length=1, max_length=4000)
    observation_text: str = Field(min_length=1, max_length=6000)
    uncertainty_note: str = Field(min_length=1, max_length=4000)
    region_x: int | None = Field(default=None, ge=0)
    region_y: int | None = Field(default=None, ge=0)
    region_width: int | None = Field(default=None, gt=0)
    region_height: int | None = Field(default=None, gt=0)

    @field_validator("purpose", "observation_text", "uncertainty_note")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A non-empty value is required.")
        return value

    @model_validator(mode="after")
    def complete_region(self):
        values = (self.region_x, self.region_y, self.region_width, self.region_height)
        if any(value is not None for value in values) and not all(value is not None for value in values):
            raise ValueError("A source region requires x, y, width, and height.")
        return self


class ObservationReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Human Reviewed", "Corrected", "Rejected", "Needs More Information"]
    reason: str = Field(min_length=1, max_length=4000)
    corrected_text: str = Field(default="", max_length=6000)

    @field_validator("reason", "corrected_text")
    @classmethod
    def clean_values(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def correction_required(self):
        if self.status == "Corrected" and not self.corrected_text:
            raise ValueError("A corrected observation requires corrected text.")
        if self.status != "Corrected" and self.corrected_text:
            raise ValueError("Corrected text is permitted only for a Corrected review.")
        return self


class VisualLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_product: Literal[
        "SalINTEL", "SalTHIRA", "SalCAPA", "SalOPS", "PROVE",
        "Personnel Assessment", "Facility Assessment", "Mission Map",
    ]
    destination_type: str = Field(min_length=1, max_length=120)
    destination_id: int = Field(default=0, ge=0)
    purpose: str = Field(min_length=1, max_length=4000)

    @field_validator("destination_type", "purpose")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A non-empty value is required.")
        return value


SCHEMA = """
CREATE TABLE IF NOT EXISTS visual_processor_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_key TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  execution_boundary TEXT NOT NULL,
  provider TEXT NOT NULL DEFAULT '',
  model_version TEXT NOT NULL DEFAULT '',
  configuration_hash TEXT NOT NULL,
  external_processing INTEGER NOT NULL DEFAULT 0,
  cost_posture TEXT NOT NULL,
  authority_note TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS visual_location_metadata (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  metadata_key TEXT NOT NULL UNIQUE,
  source_material_id INTEGER NOT NULL,
  source_sha256 TEXT NOT NULL,
  metadata_status TEXT NOT NULL,
  latitude_decimal TEXT NOT NULL DEFAULT '',
  longitude_decimal TEXT NOT NULL DEFAULT '',
  altitude_meters TEXT NOT NULL DEFAULT '',
  image_direction_degrees TEXT NOT NULL DEFAULT '',
  gps_date TEXT NOT NULL DEFAULT '',
  gps_time_utc TEXT NOT NULL DEFAULT '',
  map_datum TEXT NOT NULL DEFAULT '',
  source_components_json TEXT NOT NULL,
  parser TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  purpose TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  disclosure_status TEXT NOT NULL,
  review_status TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_by_role TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_by_role TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_basis TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,source_material_id,source_sha256,parser,parser_version)
);
CREATE INDEX IF NOT EXISTS idx_visual_location_triage
  ON visual_location_metadata(tenant_id,review_status,id);

CREATE TABLE IF NOT EXISTS visual_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  observation_key TEXT NOT NULL UNIQUE,
  source_material_id INTEGER NOT NULL,
  source_sha256 TEXT NOT NULL,
  record_type TEXT NOT NULL,
  record_origin TEXT NOT NULL,
  observation_text TEXT NOT NULL,
  uncertainty_note TEXT NOT NULL,
  purpose TEXT NOT NULL,
  source_width INTEGER NOT NULL,
  source_height INTEGER NOT NULL,
  region_x INTEGER NOT NULL,
  region_y INTEGER NOT NULL,
  region_width INTEGER NOT NULL,
  region_height INTEGER NOT NULL,
  orientation_applied INTEGER NOT NULL DEFAULT 0,
  processor_profile_id INTEGER,
  processor_profile_key TEXT NOT NULL,
  processor_profile_hash TEXT NOT NULL,
  processor_confidence TEXT NOT NULL DEFAULT '',
  sensitivity TEXT NOT NULL,
  disclosure_status TEXT NOT NULL,
  review_status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_by_role TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_by_role TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_basis TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
  FOREIGN KEY (processor_profile_id) REFERENCES visual_processor_profiles(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_visual_observations_triage
  ON visual_observations(tenant_id,review_status,id);

CREATE TABLE IF NOT EXISTS visual_observation_revisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  observation_id INTEGER NOT NULL,
  revision_type TEXT NOT NULL,
  corrected_text TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL,
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (observation_id) REFERENCES visual_observations(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_visual_observation_revisions
  ON visual_observation_revisions(observation_id,id);

CREATE TABLE IF NOT EXISTS visual_location_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  metadata_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  from_status TEXT NOT NULL DEFAULT '',
  to_status TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL,
  correction_json TEXT NOT NULL DEFAULT '{}',
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (metadata_id) REFERENCES visual_location_metadata(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_visual_location_events ON visual_location_events(metadata_id,id);

CREATE TABLE IF NOT EXISTS visual_governed_link_proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  proposal_key TEXT NOT NULL UNIQUE,
  observation_id INTEGER NOT NULL,
  destination_product TEXT NOT NULL,
  destination_type TEXT NOT NULL,
  destination_id INTEGER NOT NULL DEFAULT 0,
  purpose TEXT NOT NULL,
  status TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  proposed_by TEXT NOT NULL,
  proposed_by_role TEXT NOT NULL,
  proposed_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (observation_id) REFERENCES visual_observations(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_visual_links_scope
  ON visual_governed_link_proposals(tenant_id,status,destination_product,id);
"""


def _decimal_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.normalize(), "f")


def _run_worker(data: bytes, extension: str) -> dict:
    if os.name != "posix" or not WORKER.is_file():
        raise HTTPException(503, "Location-metadata review is unavailable. Manual image review remains available.")
    with tempfile.TemporaryDirectory(prefix="salcapa-location-") as directory:
        source = Path(directory) / f"source.{extension}"
        source.write_bytes(data)
        source.chmod(0o400)
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(WORKER), str(source)], cwd=directory,
                env={"PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0", "LC_ALL": "C.UTF-8"},
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=WORKER_TIMEOUT_SECONDS, check=False, start_new_session=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(422, "The image exceeded the bounded location-metadata review time.") from exc
        except OSError as exc:
            raise HTTPException(503, "Location-metadata review is unavailable. Manual image review remains available.") from exc
        if len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES:
            raise HTTPException(422, "The location-metadata result exceeded the bounded output limit.")
        try:
            payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(422, "The isolated location-metadata worker returned an invalid result.") from exc
        if completed.returncode != 0 or payload.get("ok") is not True:
            detail = str(payload.get("detail", ""))
            raise HTTPException(422, detail if 1 <= len(detail) <= 1000 else "Location metadata could not be read safely.")
        facts = payload.get("facts")
        if not isinstance(facts, dict) or facts.get("processor") != PROCESSOR or facts.get("processor_version") != PROCESSOR_VERSION:
            raise HTTPException(422, "The location-metadata worker identity could not be verified.")
        return facts


def register_salcapa_visual_geospatial(fastapi_app, core: dict) -> None:
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
        timestamp = now()
        profile_hash = hashlib.sha256(b"manual-source-region-v1").hexdigest()
        if not conn.execute(
            "SELECT id FROM visual_processor_profiles WHERE profile_key=?",
            ("VPR-MANUAL-SOURCE-REGION-V1",),
        ).fetchone():
            conn.execute(
                "INSERT INTO visual_processor_profiles(profile_key,name,status,execution_boundary,provider,model_version,configuration_hash,external_processing,cost_posture,authority_note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "VPR-MANUAL-SOURCE-REGION-V1", "Manual Source-Region Review", "Active", "Human review",
                    "", "", profile_hash, 0, "No paid service or standing processing resource",
                    "This profile records person-entered observations. It does not represent model review or verification.",
                    timestamp, timestamp,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    tenant_tables = {
        "visual_location_metadata", "visual_observations", "visual_observation_revisions",
        "visual_location_events", "visual_governed_link_proposals",
    }
    all_tables = tenant_tables | {"visual_processor_profiles"}
    database_support.ID_TABLES.update(all_tables)
    if not getattr(fastapi_app.state, "salcapa_visual_geospatial_backup_registered", False):
        base_collect = core["collect_tenant_records"]
        base_validate = core["validate_records"]
        base_replace = core["replace_tenant_records"]

        def collect_with_visual(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            records["visual_processor_profiles"] = [dict(row) for row in conn.execute("SELECT * FROM visual_processor_profiles ORDER BY id")]
            for table in sorted(tenant_tables):
                records[table] = [dict(row) for row in conn.execute(
                    f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (selected_tenant,)
                )]
            return records

        def validate_with_visual(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            materials = {int(row["id"]) for row in records.get("materials", []) if row.get("id") is not None}
            profiles = {int(row["id"]) for row in records.get("visual_processor_profiles", []) if row.get("id") is not None}
            metadata = {int(row["id"]) for row in records.get("visual_location_metadata", []) if row.get("id") is not None}
            observations = {int(row["id"]) for row in records.get("visual_observations", []) if row.get("id") is not None}
            for table in tenant_tables:
                for row in records.get(table, []):
                    if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("visual_location_metadata", []):
                if int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"visual location metadata {row.get('id')} has an invalid source")
                if len(str(row.get("source_sha256", ""))) != 64:
                    errors.append(f"visual location metadata {row.get('id')} has an invalid source hash")
                try:
                    components = json.loads(row.get("source_components_json", "{}") or "{}")
                    if not isinstance(components, dict):
                        raise ValueError
                except (TypeError, ValueError, json.JSONDecodeError):
                    errors.append(f"visual location metadata {row.get('id')} has invalid source components")
            for row in records.get("visual_observations", []):
                if int(row.get("source_material_id", -1)) not in materials:
                    errors.append(f"visual observation {row.get('id')} has an invalid source")
                profile_id = row.get("processor_profile_id")
                if profile_id is not None and int(profile_id) not in profiles:
                    errors.append(f"visual observation {row.get('id')} has an invalid processor profile")
                if not str(row.get("processor_profile_key", "")).strip() or len(str(row.get("processor_profile_hash", ""))) != 64:
                    errors.append(f"visual observation {row.get('id')} has invalid processor lineage")
                values = [int(row.get(name, -1)) for name in ("source_width", "source_height", "region_x", "region_y", "region_width", "region_height")]
                width, height, x, y, region_width, region_height = values
                if min(width, height, region_width, region_height) < 1 or min(x, y) < 0 or x + region_width > width or y + region_height > height:
                    errors.append(f"visual observation {row.get('id')} has an invalid source region")
            for row in records.get("visual_observation_revisions", []):
                if int(row.get("observation_id", -1)) not in observations:
                    errors.append(f"visual observation revision {row.get('id')} has an invalid observation")
            for row in records.get("visual_location_events", []):
                if int(row.get("metadata_id", -1)) not in metadata:
                    errors.append(f"visual location event {row.get('id')} has invalid metadata lineage")
                try:
                    correction = json.loads(row.get("correction_json", "{}") or "{}")
                    if not isinstance(correction, dict):
                        raise ValueError
                except (TypeError, ValueError, json.JSONDecodeError):
                    errors.append(f"visual location event {row.get('id')} has invalid correction data")
            for row in records.get("visual_governed_link_proposals", []):
                if int(row.get("observation_id", -1)) not in observations:
                    errors.append(f"visual link proposal {row.get('id')} has an invalid observation")
                if row.get("status") not in {"Awaiting Destination Review", "Accepted", "Rejected", "Withdrawn", "Superseded"}:
                    errors.append(f"visual link proposal {row.get('id')} has an invalid state")
            return errors

        def insert_row(conn, table: str, row: dict) -> None:
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            if data:
                conn.execute(
                    f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})",
                    tuple(data.values()),
                )

        def replace_with_visual(conn, selected_tenant: int, records: dict):
            errors = validate_with_visual(records, selected_tenant)
            if errors:
                raise ValueError("; ".join(errors))
            for table in (
                "visual_governed_link_proposals", "visual_location_events", "visual_observation_revisions",
                "visual_observations", "visual_location_metadata",
            ):
                conn.execute(f"DELETE FROM {table} WHERE tenant_id=?", (selected_tenant,))
            base_replace(conn, selected_tenant, records)
            for row in records.get("visual_processor_profiles", []):
                existing = conn.execute("SELECT id FROM visual_processor_profiles WHERE profile_key=?", (row["profile_key"],)).fetchone()
                if not existing:
                    insert_row(conn, "visual_processor_profiles", row)
            for table in (
                "visual_location_metadata", "visual_observations", "visual_observation_revisions",
                "visual_location_events", "visual_governed_link_proposals",
            ):
                for row in records.get(table, []):
                    if table == "visual_observations":
                        row = dict(row)
                        profile = conn.execute(
                            "SELECT id FROM visual_processor_profiles WHERE profile_key=?",
                            (row.get("processor_profile_key", ""),),
                        ).fetchone()
                        if not profile:
                            raise ValueError("Visual observation processor lineage cannot be restored")
                        row["processor_profile_id"] = profile["id"]
                    insert_row(conn, table, row)
            database_support.reset_identity_sequences(conn, all_tables)

        core["collect_tenant_records"] = collect_with_visual
        core["validate_records"] = validate_with_visual
        core["replace_tenant_records"] = replace_with_visual
        fastapi_app.state.salcapa_visual_geospatial_backup_registered = True

    def internal(request: Request, permission: str = "read", *, exact: bool = False) -> None:
        require(request, permission)
        if protected_member_request(request):
            raise HTTPException(403, "Visual and exact-location review is restricted to authorized Salus personnel.")
        if exact:
            require_sensitivity(request, "Highly Sensitive")

    def audit(conn, request: Request, action: str, entity_type: str, entity_id: int, detail: str) -> None:
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, entity_type, entity_id, detail[:2000], tenant_id(request)),
        )

    def source_row(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "VISUAL_SOURCE_TENANT_BOUNDARY_VIOLATION", "High", f"material_id={material_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["disposition_status"] != "Active":
            raise HTTPException(409, "Disposed material cannot be reviewed")
        extension = row["original_name"].rsplit(".", 1)[-1].lower() if "." in row["original_name"] else ""
        if extension not in {"jpg", "jpeg", "png"}:
            raise HTTPException(422, "This bounded visual review accepts JPEG and PNG images only.")
        return row, extension

    def source_facts(row, extension: str, request: Request) -> dict:
        if int(row["size_bytes"]) > MAX_SOURCE_BYTES:
            raise HTTPException(422, "The image exceeds the bounded source-size limit.")
        try:
            data = storage.get_bytes(row["stored_name"])
        except FileNotFoundError as exc:
            raise HTTPException(404, "The governed source object is unavailable.") from exc
        except Exception as exc:
            security_event(request, "VISUAL_SOURCE_STORAGE_FAILURE", "High", type(exc).__name__)
            raise HTTPException(503, "The governed source store is unavailable.") from exc
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            security_event(request, "VISUAL_SOURCE_HASH_MISMATCH", "Critical", f"material_id={row['id']}")
            raise HTTPException(409, "Source integrity verification failed. No review aid was created.")
        return _run_worker(data, extension)

    def public_location(row) -> dict:
        result = dict(row)
        for field in (
            "latitude_decimal", "longitude_decimal", "altitude_meters", "image_direction_degrees",
            "gps_date", "gps_time_utc", "map_datum", "source_components_json",
        ):
            result.pop(field, None)
        result["exact_location_available"] = row["metadata_status"] == "Location Metadata Present"
        result["authority_note"] = (
            "Source-stored location metadata is unverified. It does not prove where a depicted subject, person, incident, or event was located."
        )
        return result

    def public_observation(conn, row) -> dict:
        result = dict(row)
        latest = conn.execute(
            "SELECT corrected_text FROM visual_observation_revisions WHERE observation_id=? AND revision_type='Correction' ORDER BY id DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        result["current_text"] = latest["corrected_text"] if latest else row["observation_text"]
        result["orientation_applied"] = bool(result["orientation_applied"])
        result["authority_note"] = (
            "This source-region review aid does not establish identity, cause, intent, authenticity, a finding, a decision, disclosure authority, or operational authority."
        )
        return result

    @fastapi_app.get("/api/visual-geospatial/processor-profiles")
    def processor_profiles(request: Request):
        internal(request)
        conn = db()
        rows = [dict(row) for row in conn.execute(
            "SELECT profile_key,name,status,execution_boundary,provider,model_version,external_processing,cost_posture,authority_note FROM visual_processor_profiles ORDER BY id"
        )]
        conn.close()
        return {"items": rows, "scope_note": "No visual model or external provider is enabled in this bounded implementation."}

    @fastapi_app.post("/api/materials/{material_id}/location-metadata-review-aids")
    def prepare_location_metadata(material_id: int, payload: PurposeIn, request: Request):
        internal(request, "write", exact=True)
        require_salus_component_authority(request, "SalCAPA exact location metadata review")
        conn = db()
        source, extension = source_row(conn, material_id, request)
        existing = conn.execute(
            "SELECT * FROM visual_location_metadata WHERE tenant_id=? AND source_material_id=? AND source_sha256=? AND parser=? AND parser_version=?",
            (tenant_id(request), material_id, source["sha256"], PROCESSOR, PROCESSOR_VERSION),
        ).fetchone()
        if existing:
            result = public_location(existing)
            conn.close()
            return {"metadata": result, "idempotent_reuse": True}
        conn.close()
        facts = source_facts(source, extension, request)
        metadata = facts["location_metadata"]
        created = now()
        conn = db()
        metadata_key = "VLM-" + uuid.uuid4().hex
        conn.execute(
            "INSERT INTO visual_location_metadata(tenant_id,metadata_key,source_material_id,source_sha256,metadata_status,latitude_decimal,longitude_decimal,altitude_meters,image_direction_degrees,gps_date,gps_time_utc,map_datum,source_components_json,parser,parser_version,purpose,sensitivity,disclosure_status,review_status,requested_by,requested_by_role,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id(request), metadata_key, material_id, source["sha256"],
                metadata["status"], metadata.get("latitude_decimal", ""), metadata.get("longitude_decimal", ""),
                metadata.get("altitude_meters", ""), metadata.get("image_direction_degrees", ""),
                metadata.get("gps_date", ""), metadata.get("gps_time_utc", ""), metadata.get("map_datum", ""),
                json.dumps(metadata.get("source_components", {}), sort_keys=True, separators=(",", ":")),
                PROCESSOR, PROCESSOR_VERSION, payload.purpose, "Highly Sensitive", "Salus Internal — Exact Location Restricted",
                "Awaiting Human Review", actor(request), role(request), created, created,
            ),
        )
        row = conn.execute("SELECT * FROM visual_location_metadata WHERE metadata_key=?", (metadata_key,)).fetchone()
        conn.execute(
            "INSERT INTO visual_location_events(tenant_id,metadata_id,event_type,to_status,reason,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (tenant_id(request), row["id"], "CREATED", "Awaiting Human Review", "Restricted source-metadata review aid created without changing the original.", actor(request), role(request), created),
        )
        audit(conn, request, "VISUAL_LOCATION_METADATA_PREPARED", "visual_location_metadata", int(row["id"]), f"source_material_id={material_id}; metadata_status={metadata['status']}; exact_values_not_logged=true")
        conn.commit()
        result = public_location(row)
        conn.close()
        return {"metadata": result, "idempotent_reuse": False}

    @fastapi_app.get("/api/visual-geospatial/triage")
    def triage(request: Request, limit: int = 200):
        internal(request)
        conn = db()
        locations = [public_location(row) for row in conn.execute(
            "SELECT l.*,m.title source_title,m.original_name FROM visual_location_metadata l JOIN materials m ON m.id=l.source_material_id WHERE l.tenant_id=? ORDER BY CASE l.review_status WHEN 'Awaiting Human Review' THEN 0 ELSE 1 END,l.id DESC LIMIT ?",
            (tenant_id(request), max(1, min(limit, 500))),
        ) if clearance_level(request) >= sensitivity_levels["Highly Sensitive"]]
        observations = [public_observation(conn, row) for row in conn.execute(
            "SELECT o.*,m.title source_title,m.original_name FROM visual_observations o JOIN materials m ON m.id=o.source_material_id WHERE o.tenant_id=? ORDER BY CASE o.review_status WHEN 'Awaiting Human Review' THEN 0 ELSE 1 END,o.id DESC LIMIT ?",
            (tenant_id(request), max(1, min(limit, 500))),
        ) if sensitivity_levels.get(row["sensitivity"], 4) <= clearance_level(request)]
        conn.close()
        return {
            "location_metadata": locations, "observations": observations,
            "guidance": "Review source metadata and visible conditions separately. Neither is a finding, decision, or approved disclosure.",
        }

    @fastapi_app.post("/api/visual-geospatial/location-metadata/{metadata_id}/view")
    def view_exact_location(metadata_id: int, payload: PurposeIn, request: Request):
        internal(request, exact=True)
        require_salus_component_authority(request, "SalCAPA exact location metadata review")
        conn = db()
        row = conn.execute("SELECT * FROM visual_location_metadata WHERE id=?", (metadata_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Location metadata not found")
        if int(row["tenant_id"]) != tenant_id(request):
            conn.close()
            security_event(request, "VISUAL_LOCATION_TENANT_BOUNDARY_VIOLATION", "High", f"metadata_id={metadata_id}")
            raise HTTPException(403, "Tenant boundary violation")
        audit(conn, request, "VISUAL_EXACT_LOCATION_VIEWED", "visual_location_metadata", metadata_id, "purpose_recorded=true; exact_values_not_logged=true")
        conn.commit()
        result = dict(row)
        result["source_components"] = json.loads(result.pop("source_components_json") or "{}")
        result["corrections"] = [
            {**dict(item), "correction": json.loads(item["correction_json"] or "{}")}
            for item in conn.execute("SELECT * FROM visual_location_events WHERE metadata_id=? AND event_type='HUMAN_REVIEW_RECORDED' ORDER BY id", (metadata_id,))
        ]
        for item in result["corrections"]:
            item.pop("correction_json", None)
        result["view_purpose"] = payload.purpose
        result["authority_note"] = "Exact source metadata remains unverified and restricted. It does not prove a depicted or reported real-world location."
        conn.close()
        return result

    @fastapi_app.post("/api/visual-geospatial/location-metadata/{metadata_id}/review")
    def review_location(metadata_id: int, payload: LocationReviewIn, request: Request):
        internal(request, "decide", exact=True)
        require_salus_component_authority(request, "SalCAPA exact location metadata review")
        conn = db()
        row = conn.execute("SELECT * FROM visual_location_metadata WHERE id=?", (metadata_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Location metadata not found")
        if int(row["tenant_id"]) != tenant_id(request):
            conn.close()
            raise HTTPException(403, "Tenant boundary violation")
        if row["review_status"] != "Awaiting Human Review":
            conn.close()
            raise HTTPException(409, "This location-metadata aid already has a recorded review state")
        if row["requested_by"] == actor(request):
            conn.close()
            raise HTTPException(409, "A different authorized person must review this location-metadata aid")
        correction = {}
        if payload.status == "Corrected":
            correction = {
                "latitude_decimal": _decimal_text(payload.corrected_latitude_decimal),
                "longitude_decimal": _decimal_text(payload.corrected_longitude_decimal),
                "classification": "Human interpretation — does not alter source-stored metadata",
            }
        reviewed = now()
        conn.execute(
            "UPDATE visual_location_metadata SET review_status=?,reviewed_by=?,reviewed_by_role=?,reviewed_at=?,review_basis=?,updated_at=? WHERE id=?",
            (payload.status, actor(request), role(request), reviewed, payload.reason, reviewed, metadata_id),
        )
        conn.execute(
            "INSERT INTO visual_location_events(tenant_id,metadata_id,event_type,from_status,to_status,reason,correction_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), metadata_id, "HUMAN_REVIEW_RECORDED", "Awaiting Human Review", payload.status, payload.reason, json.dumps(correction, sort_keys=True), actor(request), role(request), reviewed),
        )
        audit(conn, request, "VISUAL_LOCATION_METADATA_REVIEWED", "visual_location_metadata", metadata_id, f"status={payload.status}; exact_values_not_logged=true; source_unchanged=true")
        conn.commit()
        updated = conn.execute("SELECT * FROM visual_location_metadata WHERE id=?", (metadata_id,)).fetchone()
        result = public_location(updated)
        conn.close()
        return result

    @fastapi_app.post("/api/materials/{material_id}/visual-observations")
    def add_visual_observation(material_id: int, payload: VisualObservationIn, request: Request):
        internal(request, "write")
        require_salus_component_authority(request, "SalCAPA source-region visual review")
        conn = db()
        source, extension = source_row(conn, material_id, request)
        conn.close()
        facts = source_facts(source, extension, request)
        width, height = int(facts["width"]), int(facts["height"])
        if payload.region_x is None:
            x, y, region_width, region_height = 0, 0, width, height
        else:
            x, y = int(payload.region_x), int(payload.region_y)
            region_width, region_height = int(payload.region_width), int(payload.region_height)
        if x + region_width > width or y + region_height > height:
            raise HTTPException(422, "The source region exceeds the original image dimensions.")
        created = now()
        conn = db()
        profile = conn.execute(
            "SELECT id,profile_key,configuration_hash FROM visual_processor_profiles WHERE profile_key='VPR-MANUAL-SOURCE-REGION-V1'"
        ).fetchone()
        observation_key = "VOB-" + uuid.uuid4().hex
        conn.execute(
            "INSERT INTO visual_observations(tenant_id,observation_key,source_material_id,source_sha256,record_type,record_origin,observation_text,uncertainty_note,purpose,source_width,source_height,region_x,region_y,region_width,region_height,orientation_applied,processor_profile_id,processor_profile_key,processor_profile_hash,sensitivity,disclosure_status,review_status,created_by,created_by_role,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id(request), observation_key, material_id, source["sha256"],
                "Visible Observation — Unverified", "Person-entered", payload.observation_text,
                payload.uncertainty_note, payload.purpose, width, height, x, y, region_width, region_height,
                1 if facts.get("orientation_applied") else 0, profile["id"], profile["profile_key"],
                profile["configuration_hash"], source["sensitivity"],
                "Salus Internal — Not Released", "Awaiting Human Review", actor(request), role(request), created, created,
            ),
        )
        row = conn.execute("SELECT * FROM visual_observations WHERE observation_key=?", (observation_key,)).fetchone()
        conn.execute(
            "INSERT INTO visual_observation_revisions(tenant_id,observation_id,revision_type,reason,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?)",
            (tenant_id(request), row["id"], "Initial record", "Person-entered visible observation linked to the immutable source region.", actor(request), role(request), created),
        )
        audit(conn, request, "VISUAL_OBSERVATION_RECORDED", "visual_observation", int(row["id"]), f"source_material_id={material_id}; source_region={x},{y},{region_width},{region_height}; no_finding_or_disclosure=true")
        conn.commit()
        result = public_observation(conn, row)
        conn.close()
        return result

    @fastapi_app.post("/api/visual-geospatial/observations/{observation_id}/review")
    def review_observation(observation_id: int, payload: ObservationReviewIn, request: Request):
        internal(request, "decide")
        require_salus_component_authority(request, "SalCAPA source-region visual review")
        conn = db()
        row = conn.execute("SELECT * FROM visual_observations WHERE id=?", (observation_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Visual observation not found")
        if int(row["tenant_id"]) != tenant_id(request):
            conn.close()
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["review_status"] != "Awaiting Human Review":
            conn.close()
            raise HTTPException(409, "This visual observation already has a recorded review state")
        if row["created_by"] == actor(request):
            conn.close()
            raise HTTPException(409, "A different authorized person must review this visual observation")
        reviewed = now()
        conn.execute(
            "UPDATE visual_observations SET review_status=?,reviewed_by=?,reviewed_by_role=?,reviewed_at=?,review_basis=?,updated_at=? WHERE id=?",
            (payload.status, actor(request), role(request), reviewed, payload.reason, reviewed, observation_id),
        )
        conn.execute(
            "INSERT INTO visual_observation_revisions(tenant_id,observation_id,revision_type,corrected_text,reason,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (tenant_id(request), observation_id, "Correction" if payload.status == "Corrected" else "Human review", payload.corrected_text, payload.reason, actor(request), role(request), reviewed),
        )
        audit(conn, request, "VISUAL_OBSERVATION_REVIEWED", "visual_observation", observation_id, f"status={payload.status}; source_unchanged=true; no_finding_or_disclosure=true")
        conn.commit()
        updated = conn.execute("SELECT * FROM visual_observations WHERE id=?", (observation_id,)).fetchone()
        result = public_observation(conn, updated)
        conn.close()
        return result

    @fastapi_app.post("/api/visual-geospatial/observations/{observation_id}/governed-link-proposals")
    def propose_link(observation_id: int, payload: VisualLinkIn, request: Request):
        internal(request, "decide")
        require_salus_component_authority(request, "SalCAPA visual governed link proposal")
        if payload.destination_product not in DESTINATION_PRODUCTS:
            raise HTTPException(422, "Unsupported destination product")
        conn = db()
        row = conn.execute("SELECT * FROM visual_observations WHERE id=?", (observation_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "Visual observation not found")
        if int(row["tenant_id"]) != tenant_id(request):
            conn.close()
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["review_status"] not in {"Human Reviewed", "Corrected"}:
            conn.close()
            raise HTTPException(409, "A visual observation must receive human review before a governed link can be proposed")
        created = now()
        proposal_key = "VGL-" + uuid.uuid4().hex
        conn.execute(
            "INSERT INTO visual_governed_link_proposals(tenant_id,proposal_key,observation_id,destination_product,destination_type,destination_id,purpose,status,sensitivity,proposed_by,proposed_by_role,proposed_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), proposal_key, observation_id, payload.destination_product, payload.destination_type, payload.destination_id, payload.purpose, "Awaiting Destination Review", row["sensitivity"], actor(request), role(request), created, created),
        )
        proposal = conn.execute("SELECT * FROM visual_governed_link_proposals WHERE proposal_key=?", (proposal_key,)).fetchone()
        audit(conn, request, "VISUAL_GOVERNED_LINK_PROPOSED", "visual_governed_link_proposal", int(proposal["id"]), f"destination={payload.destination_product}; destination_type={payload.destination_type}; destination_id={payload.destination_id}; no_destination_acceptance=true")
        conn.commit()
        result = dict(proposal)
        result["authority_note"] = "This proposal awaits the destination authority and has not created or changed an authoritative relationship."
        conn.close()
        return result
