"""Server-controlled local review profiles for governed facility imagery.

Profiles guide bounded source-region review. They do not process source bytes,
establish findings, or grant destination or disclosure authority.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import database as database_support
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _profile(
    key: str,
    name: str,
    capability_class: str,
    source_classes: list[str],
    relationship_types: list[str],
    vocabulary: list[str],
    purpose_terms: list[str],
    limitations: str,
    negative_inference: str,
) -> dict:
    profile = {
        "profile_key": key,
        "profile_version": "1.0.0",
        "name": name,
        "capability_class": capability_class,
        "status": "Active for Bounded Review",
        "effective_date": "12 September 2026",
        "expiry_rule": "No automatic expiry; suspension and supersession remain governed.",
        "review_method": "Manual source-region review; an approved hash-verified local processor may support a later separately validated request.",
        "processor_required": False,
        "external_processing": False,
        "standing_gpu": False,
        "no_network": True,
        "allowed_representation_classes": source_classes,
        "allowed_coordinate_spaces": ["Image Pixels", "PDF Page Points", "Rendered Page Pixels"],
        "allowed_relationship_types": relationship_types,
        "vocabulary": vocabulary,
        "approved_purpose_terms": purpose_terms,
        "max_regions_per_request": 20,
        "known_limitations": limitations,
        "negative_inference_rule": negative_inference,
        "required_human_step": "An authorized Salus person must compare any prepared relationship with the exact source region; a different authorized person must perform consequential representation review.",
        "validation_evidence": "Repository acceptance validates profile governance and boundaries, not real-world detection accuracy.",
        "cost_posture": "Request-driven local or manual review; no paid external call and no standing GPU.",
        "rollback_state": "Disable or supersede the profile without changing historical snapshots or source records.",
    }
    profile["profile_snapshot_sha256"] = hashlib.sha256(_canonical(profile).encode()).hexdigest()
    return profile


_ALL_SOURCES = [
    "Authoritative Plan or Survey", "Controlled Organizational Record",
    "Published Reference Map", "Field Photograph or Survey Image",
    "Annotated Working Copy", "Diagram or Schematic",
    "Reported or Unverified Representation",
]

PROFILES = {
    profile["profile_key"]: profile
    for profile in (
        _profile(
            "FRP-LAYOUT-V1", "Plan and Layout Review", "Layout",
            ["Authoritative Plan or Survey", "Controlled Organizational Record", "Published Reference Map", "Annotated Working Copy", "Diagram or Schematic", "Reported or Unverified Representation"],
            ["Facility", "Room", "Area", "Route", "Access or Egress", "Dependency"],
            ["boundary", "level", "room", "area", "route", "opening", "assembly area", "adjacency", "dimension statement", "north reference"],
            ["layout", "plan", "room", "area", "route", "egress"],
            "A depicted relationship may be proposed for review; physical adjacency, scale, currency, accessibility, and operational feasibility are not established by appearance alone.",
            "Absence from a plan or selected region does not prove absence from the facility.",
        ),
        _profile(
            "FRP-SYMBOL-V1", "Symbol and Legend Review", "Symbol and Legend",
            ["Authoritative Plan or Survey", "Controlled Organizational Record", "Published Reference Map", "Annotated Working Copy", "Diagram or Schematic", "Reported or Unverified Representation"],
            ["Asset", "Control", "Dependency", "Evidence"],
            ["legend entry", "symbol", "line style", "color key", "annotation", "label", "revision mark", "north arrow", "scale bar"],
            ["symbol", "legend", "annotation", "label", "marking"],
            "A symbol is interpreted only under the exact source legend, sheet, discipline, edition, and revision. Similar appearance does not establish identical meaning.",
            "An unrecognized or missing symbol does not prove that an asset, control, or condition is absent.",
        ),
        _profile(
            "FRP-CONDITION-V1", "Visible Facility Condition Review", "Visible Condition",
            ["Field Photograph or Survey Image", "Controlled Organizational Record", "Annotated Working Copy", "Reported or Unverified Representation"],
            ["Visible Condition", "Access or Egress", "Hazard", "Evidence"],
            ["obstruction", "surface condition", "standing water", "corrosion-like appearance", "temporary condition", "lighting condition", "housekeeping condition", "signage condition"],
            ["condition", "visible", "facility", "access", "egress"],
            "Only what is visible within the recorded frame, time, viewpoint, quality, and source limitations may be described. Cause, duration, severity, and hidden condition remain unknown unless separately supported.",
            "Not visible in the selected frame does not mean absent at the facility.",
        ),
        _profile(
            "FRP-DAMAGE-V1", "Damage Indicator Review", "Damage Indicator",
            ["Field Photograph or Survey Image", "Controlled Organizational Record", "Annotated Working Copy", "Reported or Unverified Representation"],
            ["Damage", "Visible Condition", "Hazard", "Evidence"],
            ["displacement-like appearance", "crack-like appearance", "deformation-like appearance", "burn-like appearance", "water mark", "missing component", "debris", "temporary repair"],
            ["damage", "debris", "repair", "condition"],
            "This profile supports neutral visible indicators only. It does not determine cause, structural integrity, habitability, code compliance, repair scope, or safety.",
            "No visible indicator does not establish that damage is absent or that an area is safe.",
        ),
        _profile(
            "FRP-EQUIPMENT-V1", "Equipment Presence Review", "Equipment Presence",
            _ALL_SOURCES,
            ["Asset", "Control", "Dependency", "Evidence"],
            ["generator", "panel", "valve", "pump", "camera", "sensor", "extinguisher", "cabinet", "antenna", "vehicle", "container", "protective equipment"],
            ["equipment", "asset", "utility", "generator", "sensor", "camera"],
            "Appearance may support an equipment-category proposal only. Identity, ownership, capacity, configuration, operability, maintenance, certification, and availability require authoritative records or qualified review.",
            "No equipment suggestion does not prove absence, inoperability, or lack of capability.",
        ),
        _profile(
            "FRP-PROTECTIVE-CONTROL-V1", "Protective Control Review", "Protective Control",
            _ALL_SOURCES,
            ["Control", "Access or Egress", "Dependency", "Visible Condition", "Evidence"],
            ["barrier", "gate", "door", "lock-like hardware", "camera-like device", "sensor-like device", "alarm device", "fire protection equipment", "warning sign", "access-control reader-like device"],
            ["protective control", "security", "barrier", "access control", "life safety", "fire protection"],
            "Visible form does not establish installation quality, coverage, configuration, monitoring, effectiveness, compliance, operability, authority, or current status.",
            "No visible protective-control suggestion does not prove that a control is absent or ineffective.",
        ),
    )
}


class ProfileApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_key: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1, max_length=4000)
    review_question: str = Field(min_length=1, max_length=4000)
    destination_under_consideration: str = Field(default="None", min_length=1, max_length=240)
    expected_region_count: int = Field(default=1, ge=1, le=20)

    @field_validator("profile_key", "purpose", "review_question", "destination_under_consideration")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


SCHEMA = """
CREATE TABLE IF NOT EXISTS facility_review_profile_applications (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 application_key TEXT NOT NULL UNIQUE, source_id INTEGER NOT NULL,
 source_material_id INTEGER NOT NULL, source_sha256 TEXT NOT NULL, geometry_sha256 TEXT NOT NULL,
 profile_key TEXT NOT NULL, profile_snapshot_json TEXT NOT NULL, profile_snapshot_sha256 TEXT NOT NULL,
 capability_class TEXT NOT NULL, purpose TEXT NOT NULL, review_question TEXT NOT NULL,
 destination_under_consideration TEXT NOT NULL, expected_region_count INTEGER NOT NULL,
 application_status TEXT NOT NULL, external_processing INTEGER NOT NULL DEFAULT 0,
 standing_gpu INTEGER NOT NULL DEFAULT 0, no_network INTEGER NOT NULL DEFAULT 1,
 sensitivity TEXT NOT NULL, disclosure_status TEXT NOT NULL,
 prepared_by TEXT NOT NULL, prepared_by_role TEXT NOT NULL, prepared_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (source_id) REFERENCES facility_image_sources(id) ON DELETE RESTRICT,
 FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_facility_review_profiles_scope
 ON facility_review_profile_applications(tenant_id,application_status,id);
"""


def register_salcapa_facility_review_profiles(fastapi_app, core: dict) -> None:
    db, now, actor, role, tenant_id = (core[name] for name in ("db", "now", "actor", "role", "tenant_id"))
    require, require_sensitivity = core["require"], core["require_sensitivity"]
    protected_member_request = core["protected_member_request"]
    require_salus_component_authority = core["require_salus_component_authority"]
    security_event = core["security_event"]

    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    table = "facility_review_profile_applications"
    database_support.ID_TABLES.add(table)
    if not getattr(fastapi_app.state, "salcapa_facility_review_profiles_backup_registered", False):
        base_collect, base_validate, base_replace = (
            core[name] for name in ("collect_tenant_records", "validate_records", "replace_tenant_records")
        )

        def collect(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            records[table] = [dict(row) for row in conn.execute(
                f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (selected_tenant,)
            )]
            return records

        def validate(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            source_ids = {int(row["id"]) for row in records.get("facility_image_sources", []) if row.get("id") is not None}
            material_ids = {int(row["id"]) for row in records.get("materials", []) if row.get("id") is not None}
            for row in records.get(table, []):
                if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                    errors.append(f"facility review profile application {row.get('id')} crosses the tenant boundary")
                if int(row.get("source_id", -1)) not in source_ids or int(row.get("source_material_id", -1)) not in material_ids:
                    errors.append(f"facility review profile application {row.get('id')} has invalid source lineage")
                if len(str(row.get("source_sha256", ""))) != 64 or len(str(row.get("geometry_sha256", ""))) != 64:
                    errors.append(f"facility review profile application {row.get('id')} has invalid hash lineage")
                snapshot_json = str(row.get("profile_snapshot_json", ""))
                try:
                    snapshot = json.loads(snapshot_json)
                    if not isinstance(snapshot, dict) or snapshot.get("profile_key") != row.get("profile_key"):
                        raise ValueError
                except (TypeError, ValueError, json.JSONDecodeError):
                    errors.append(f"facility review profile application {row.get('id')} has invalid profile snapshot")
                if hashlib.sha256(snapshot_json.encode()).hexdigest() != row.get("profile_snapshot_sha256"):
                    errors.append(f"facility review profile application {row.get('id')} has invalid profile snapshot hash")
                if int(row.get("external_processing", -1)) != 0 or int(row.get("standing_gpu", -1)) != 0 or int(row.get("no_network", -1)) != 1:
                    errors.append(f"facility review profile application {row.get('id')} violates the local cost boundary")
                if row.get("application_status") != "Prepared — Human Review Required":
                    errors.append(f"facility review profile application {row.get('id')} has invalid authority state")
            return errors

        def replace(conn, selected_tenant: int, records: dict):
            errors = validate(records, selected_tenant)
            if errors:
                raise ValueError("; ".join(errors))
            conn.execute(f"DELETE FROM {table} WHERE tenant_id=?", (selected_tenant,))
            base_replace(conn, selected_tenant, records)
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            for row in records.get(table, []):
                data = {key: value for key, value in row.items() if key in allowed}
                conn.execute(
                    f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})",
                    tuple(data.values()),
                )
            database_support.reset_identity_sequences(conn, {table})

        core["collect_tenant_records"], core["validate_records"], core["replace_tenant_records"] = collect, validate, replace
        fastapi_app.state.salcapa_facility_review_profiles_backup_registered = True

    def internal(request: Request, permission: str = "read"):
        require(request, permission)
        if protected_member_request(request):
            raise HTTPException(403, "Facility image review profiles are restricted to authorized Salus personnel.")

    def audit(conn, request: Request, action: str, entity_id: int, detail: str):
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, "facility_review_profile_application", entity_id, detail[:2000], tenant_id(request)),
        )

    def scoped_source(conn, source_id: int, request: Request):
        row = conn.execute("SELECT * FROM facility_image_sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Facility image source representation not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "FACILITY_PROFILE_TENANT_BOUNDARY_VIOLATION", "High", f"source_id={source_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["record_status"] != "Active":
            raise HTTPException(409, "Only an active governed source representation may use a review profile.")
        return row

    @fastapi_app.get("/api/facility-imagery/review-profiles")
    def list_profiles(request: Request):
        internal(request)
        return {
            "items": list(PROFILES.values()),
            "guidance": "Choose a profile that matches the authorized purpose and exact source representation. Profiles guide review; they do not establish findings, decisions, engineering conclusions, safe routes, or disclosure authority.",
            "external_processing": False,
            "standing_gpu": False,
            "manual_review_available": True,
        }

    @fastapi_app.post("/api/facility-imagery/sources/{source_id}/profile-applications")
    def prepare_profile_application(source_id: int, payload: ProfileApplicationIn, request: Request):
        internal(request, "write")
        require_salus_component_authority(request, "SalCAPA plan and facility-image review")
        profile = PROFILES.get(payload.profile_key)
        if profile is None:
            raise HTTPException(422, "The requested facility review profile is not server-approved.")
        conn = db()
        source = scoped_source(conn, source_id, request)
        if source["representation_class"] not in profile["allowed_representation_classes"]:
            conn.close()
            raise HTTPException(409, "The selected review profile does not permit this source representation class.")
        if source["coordinate_space"] not in profile["allowed_coordinate_spaces"]:
            conn.close()
            raise HTTPException(409, "The selected review profile does not permit this coordinate space.")
        purpose_text = f"{payload.purpose} {payload.review_question}".casefold()
        if not any(term.casefold() in purpose_text for term in profile["approved_purpose_terms"]):
            conn.close()
            raise HTTPException(403, "The stated purpose is outside this review profile's approved purpose terms.")
        snapshot_json = _canonical(profile)
        snapshot_sha = hashlib.sha256(snapshot_json.encode()).hexdigest()
        ts = now()
        cur = conn.execute(
            "INSERT INTO facility_review_profile_applications(tenant_id,application_key,source_id,source_material_id,source_sha256,geometry_sha256,profile_key,profile_snapshot_json,profile_snapshot_sha256,capability_class,purpose,review_question,destination_under_consideration,expected_region_count,application_status,external_processing,standing_gpu,no_network,sensitivity,disclosure_status,prepared_by,prepared_by_role,prepared_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tenant_id(request), "FRPA-" + uuid.uuid4().hex, source_id, source["source_material_id"],
                source["source_sha256"], source["geometry_sha256"], profile["profile_key"], snapshot_json,
                snapshot_sha, profile["capability_class"], payload.purpose, payload.review_question,
                payload.destination_under_consideration, payload.expected_region_count,
                "Prepared — Human Review Required", 0, 0, 1, source["sensitivity"],
                "Salus Internal — Not Released", actor(request), role(request), ts,
            ),
        )
        application_id = int(cur.lastrowid)
        audit(
            conn, request, "FACILITY_REVIEW_PROFILE_PREPARED", application_id,
            f"source_id={source_id}; profile_key={profile['profile_key']}; external_processing=false; no_finding_or_decision=true",
        )
        conn.commit()
        result = dict(conn.execute(f"SELECT * FROM {table} WHERE id=?", (application_id,)).fetchone())
        conn.close()
        result["profile_snapshot"] = json.loads(result.pop("profile_snapshot_json"))
        result["authority_note"] = "This profile application prepares bounded human review. It does not process source bytes or create a finding, priority, decision, safe-route determination, engineering conclusion, disclosure, or authorization."
        return result

    @fastapi_app.get("/api/facility-imagery/profile-applications")
    def triage_profile_applications(request: Request, limit: int = 200):
        internal(request)
        conn = db()
        rows = [dict(row) for row in conn.execute(
            f"SELECT a.*,s.representation_class,s.coordinate_space,s.page_number,s.region_x,s.region_y,s.region_width,s.region_height FROM {table} a JOIN facility_image_sources s ON s.id=a.source_id WHERE a.tenant_id=? ORDER BY a.id DESC LIMIT ?",
            (tenant_id(request), max(1, min(limit, 500))),
        )]
        for row in rows:
            require_sensitivity(request, row["sensitivity"])
            row["profile_snapshot"] = json.loads(row.pop("profile_snapshot_json"))
        conn.close()
        return {
            "items": rows,
            "guidance": "Review the exact source region under the selected profile. Record any relationship as Derived — Unverified and route it through independent representation review.",
        }
