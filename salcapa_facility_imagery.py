"""Governed maps, plans, diagrams, and facility-imagery relationships.

This module records source representations and review proposals. It does not
interpret imagery, establish engineering facts, or grant destination authority.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Literal

import database as database_support
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


REPRESENTATION_CLASSES = {
    "Authoritative Plan or Survey",
    "Controlled Organizational Record",
    "Published Reference Map",
    "Field Photograph or Survey Image",
    "Annotated Working Copy",
    "Diagram or Schematic",
    "Reported or Unverified Representation",
}
COORDINATE_SPACES = {"Image Pixels", "PDF Page Points", "Rendered Page Pixels"}
ORIGINS = {
    "Source-stated", "Local Processing Suggestion", "Analyst Observation",
    "Reported Information", "Reconciled Reference",
}
RELATIONSHIP_TYPES = {
    "Facility", "Asset", "Room", "Area", "Route", "Control", "Dependency",
    "Visible Condition", "Damage", "Access or Egress", "Hazard", "Evidence",
}
REVIEW_STATES = {
    "Accept Representation", "Corrected", "Rejected", "Needs More Information", "Superseded",
}
DESTINATIONS = {
    "SalINTEL", "SalTHIRA", "SalCAPA", "SalOPS", "PROVE",
    "Personnel Assessment", "Facility Assessment", "Mission Map",
}


class SourceRepresentationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    representation_class: Literal[
        "Authoritative Plan or Survey", "Controlled Organizational Record",
        "Published Reference Map", "Field Photograph or Survey Image",
        "Annotated Working Copy", "Diagram or Schematic",
        "Reported or Unverified Representation",
    ]
    purpose: str = Field(min_length=1, max_length=4000)
    authority_basis: str = Field(default="", max_length=4000)
    source_revision: str = Field(default="", max_length=240)
    source_date: str = Field(default="Unknown", min_length=1, max_length=80)
    coordinate_space: Literal["Image Pixels", "PDF Page Points", "Rendered Page Pixels"]
    page_number: int = Field(default=0, ge=0, le=10000)
    source_width: float = Field(gt=0, le=1_000_000)
    source_height: float = Field(gt=0, le=1_000_000)
    region_x: float = Field(ge=0, le=1_000_000)
    region_y: float = Field(ge=0, le=1_000_000)
    region_width: float = Field(gt=0, le=1_000_000)
    region_height: float = Field(gt=0, le=1_000_000)
    scale_status: Literal["Reviewed Applicable", "Source Stated — Unverified", "Not to Scale", "Unknown"] = "Unknown"
    scale_basis: str = Field(default="", max_length=2000)
    north_reference: str = Field(default="Unknown", min_length=1, max_length=240)
    datum: str = Field(default="Unknown", min_length=1, max_length=240)
    projection: str = Field(default="Unknown", min_length=1, max_length=240)
    precision_status: Literal["Exact", "Approximate", "Generalized", "Unknown"] = "Unknown"
    limitations: str = Field(min_length=1, max_length=8000)
    rendered_page_id: int | None = Field(default=None, gt=0)

    @field_validator(
        "purpose", "authority_basis", "source_revision", "source_date", "scale_basis",
        "north_reference", "datum", "projection", "limitations",
    )
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def valid_region_and_authority(self):
        if self.region_x + self.region_width > self.source_width or self.region_y + self.region_height > self.source_height:
            raise ValueError("The selected source region exceeds the declared coordinate-space boundary.")
        if self.representation_class == "Authoritative Plan or Survey" and not self.authority_basis:
            raise ValueError("An authoritative representation requires a recorded authority basis.")
        if self.scale_status == "Reviewed Applicable" and not self.scale_basis:
            raise ValueError("A reviewed applicable scale requires its basis and conditions.")
        if self.coordinate_space in {"PDF Page Points", "Rendered Page Pixels"} and self.page_number < 1:
            raise ValueError("A PDF page coordinate space requires an exact one-based page number.")
        if self.rendered_page_id is not None and self.coordinate_space != "Rendered Page Pixels":
            raise ValueError("A rendered-page reference must use Rendered Page Pixels.")
        return self


class RelationshipProposalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relationship_type: Literal[
        "Facility", "Asset", "Room", "Area", "Route", "Control", "Dependency",
        "Visible Condition", "Damage", "Access or Egress", "Hazard", "Evidence",
    ]
    description: str = Field(min_length=1, max_length=8000)
    origin_type: Literal[
        "Source-stated", "Local Processing Suggestion", "Analyst Observation",
        "Reported Information", "Reconciled Reference",
    ]
    target_type: str = Field(default="", max_length=120)
    target_id: int = Field(default=0, ge=0)
    alternatives: list[str] = Field(default_factory=list, max_length=20)
    contradictions: str = Field(default="", max_length=8000)
    assumptions: str = Field(default="", max_length=8000)
    information_gaps: str = Field(default="", max_length=8000)
    uncertainty_note: str = Field(min_length=1, max_length=8000)

    @field_validator(
        "description", "target_type", "contradictions", "assumptions", "information_gaps", "uncertainty_note",
    )
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("alternatives")
    @classmethod
    def clean_alternatives(cls, values: list[str]) -> list[str]:
        cleaned = []
        for value in values:
            item = value.strip()
            if not item or len(item) > 1000:
                raise ValueError("Each alternative must contain 1 to 1000 characters.")
            if item not in cleaned:
                cleaned.append(item)
        return cleaned


class RelationshipReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Accept Representation", "Corrected", "Rejected", "Needs More Information", "Superseded"]
    reason: str = Field(min_length=1, max_length=4000)
    corrected_description: str = Field(default="", max_length=8000)
    corrected_target_type: str = Field(default="", max_length=120)
    corrected_target_id: int = Field(default=0, ge=0)
    corrected_geometry_json: str = Field(default="{}", max_length=16000)

    @field_validator("reason", "corrected_description", "corrected_target_type", "corrected_geometry_json")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def correction_requirements(self):
        try:
            geometry = json.loads(self.corrected_geometry_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Corrected geometry must be valid JSON.") from exc
        if not isinstance(geometry, dict):
            raise ValueError("Corrected geometry must be a JSON object.")
        if self.status == "Corrected" and not self.corrected_description:
            raise ValueError("A corrected review requires corrected wording.")
        return self


class DestinationProposalIn(BaseModel):
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
    def clean_text(cls, value: str) -> str:
        return value.strip()


SCHEMA = """
CREATE TABLE IF NOT EXISTS facility_image_sources (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 source_key TEXT NOT NULL UNIQUE, source_material_id INTEGER NOT NULL, source_sha256 TEXT NOT NULL,
 rendered_page_id INTEGER, representation_class TEXT NOT NULL, authority_basis TEXT NOT NULL,
 source_revision TEXT NOT NULL, source_date TEXT NOT NULL, coordinate_space TEXT NOT NULL,
 page_number INTEGER NOT NULL, source_width REAL NOT NULL, source_height REAL NOT NULL,
 region_x REAL NOT NULL, region_y REAL NOT NULL, region_width REAL NOT NULL, region_height REAL NOT NULL,
 geometry_sha256 TEXT NOT NULL, scale_status TEXT NOT NULL, scale_basis TEXT NOT NULL,
 north_reference TEXT NOT NULL, datum TEXT NOT NULL, projection TEXT NOT NULL, precision_status TEXT NOT NULL,
 limitations TEXT NOT NULL, purpose TEXT NOT NULL, sensitivity TEXT NOT NULL,
 disclosure_status TEXT NOT NULL, record_status TEXT NOT NULL,
 created_by TEXT NOT NULL, created_by_role TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_facility_image_sources_scope ON facility_image_sources(tenant_id,source_material_id,record_status,id);

CREATE TABLE IF NOT EXISTS facility_relationship_proposals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 proposal_key TEXT NOT NULL UNIQUE, source_id INTEGER NOT NULL, relationship_type TEXT NOT NULL,
 description TEXT NOT NULL, origin_type TEXT NOT NULL, target_type TEXT NOT NULL, target_id INTEGER NOT NULL,
 alternatives_json TEXT NOT NULL, contradictions TEXT NOT NULL, assumptions TEXT NOT NULL,
 information_gaps TEXT NOT NULL, uncertainty_note TEXT NOT NULL,
 epistemic_state TEXT NOT NULL, review_status TEXT NOT NULL,
 current_description TEXT NOT NULL, current_target_type TEXT NOT NULL, current_target_id INTEGER NOT NULL,
 sensitivity TEXT NOT NULL, disclosure_status TEXT NOT NULL,
 proposed_by TEXT NOT NULL, proposed_by_role TEXT NOT NULL, proposed_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (source_id) REFERENCES facility_image_sources(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_facility_relationship_proposals_scope ON facility_relationship_proposals(tenant_id,review_status,id);

CREATE TABLE IF NOT EXISTS facility_relationship_reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, proposal_id INTEGER NOT NULL,
 review_type TEXT NOT NULL, reason TEXT NOT NULL, corrected_description TEXT NOT NULL,
 corrected_target_type TEXT NOT NULL, corrected_target_id INTEGER NOT NULL,
 corrected_geometry_json TEXT NOT NULL, reviewed_by TEXT NOT NULL, reviewed_by_role TEXT NOT NULL,
 reviewed_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (proposal_id) REFERENCES facility_relationship_proposals(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_facility_relationship_reviews_scope ON facility_relationship_reviews(tenant_id,proposal_id,id);

CREATE TABLE IF NOT EXISTS facility_destination_proposals (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL,
 destination_key TEXT NOT NULL UNIQUE, proposal_id INTEGER NOT NULL, destination_product TEXT NOT NULL,
 destination_type TEXT NOT NULL, destination_id INTEGER NOT NULL, purpose TEXT NOT NULL,
 status TEXT NOT NULL, sensitivity TEXT NOT NULL, disclosure_status TEXT NOT NULL,
 proposed_by TEXT NOT NULL, proposed_by_role TEXT NOT NULL, proposed_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
 FOREIGN KEY (proposal_id) REFERENCES facility_relationship_proposals(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_facility_destination_proposals_scope ON facility_destination_proposals(tenant_id,status,id);
"""


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def register_salcapa_facility_imagery(fastapi_app, core: dict) -> None:
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

    tables = {
        "facility_image_sources", "facility_relationship_proposals",
        "facility_relationship_reviews", "facility_destination_proposals",
    }
    database_support.ID_TABLES.update(tables)
    if not getattr(fastapi_app.state, "salcapa_facility_imagery_backup_registered", False):
        base_collect = core["collect_tenant_records"]
        base_validate = core["validate_records"]
        base_replace = core["replace_tenant_records"]

        def collect(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            for table in sorted(tables):
                records[table] = [dict(row) for row in conn.execute(
                    f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (selected_tenant,)
                )]
            return records

        def validate(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            material_ids = {int(row["id"]) for row in records.get("materials", []) if row.get("id") is not None}
            source_ids = {int(row["id"]) for row in records.get("facility_image_sources", []) if row.get("id") is not None}
            proposal_ids = {int(row["id"]) for row in records.get("facility_relationship_proposals", []) if row.get("id") is not None}
            for table in tables:
                for row in records.get(table, []):
                    if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("facility_image_sources", []):
                if int(row.get("source_material_id", -1)) not in material_ids or len(str(row.get("source_sha256", ""))) != 64:
                    errors.append(f"facility image source {row.get('id')} has invalid source lineage")
                if len(str(row.get("geometry_sha256", ""))) != 64:
                    errors.append(f"facility image source {row.get('id')} has invalid geometry lineage")
                try:
                    width, height = float(row["source_width"]), float(row["source_height"])
                    x, y = float(row["region_x"]), float(row["region_y"])
                    rw, rh = float(row["region_width"]), float(row["region_height"])
                    if min(width, height, rw, rh) <= 0 or min(x, y) < 0 or x + rw > width or y + rh > height:
                        raise ValueError
                except (KeyError, TypeError, ValueError):
                    errors.append(f"facility image source {row.get('id')} has invalid bounded geometry")
            for row in records.get("facility_relationship_proposals", []):
                if int(row.get("source_id", -1)) not in source_ids:
                    errors.append(f"facility relationship proposal {row.get('id')} has invalid source lineage")
                try:
                    alternatives = json.loads(row.get("alternatives_json", "[]"))
                    if not isinstance(alternatives, list):
                        raise ValueError
                except (TypeError, ValueError, json.JSONDecodeError):
                    errors.append(f"facility relationship proposal {row.get('id')} has invalid alternatives")
                if row.get("review_status") not in {"Awaiting Human Review", *REVIEW_STATES}:
                    errors.append(f"facility relationship proposal {row.get('id')} has invalid review state")
            for row in records.get("facility_relationship_reviews", []):
                if int(row.get("proposal_id", -1)) not in proposal_ids:
                    errors.append(f"facility relationship review {row.get('id')} has invalid proposal lineage")
            for row in records.get("facility_destination_proposals", []):
                if int(row.get("proposal_id", -1)) not in proposal_ids:
                    errors.append(f"facility destination proposal {row.get('id')} has invalid proposal lineage")
                if row.get("status") not in {"Awaiting Destination Review", "Accepted", "Rejected", "Withdrawn", "Superseded"}:
                    errors.append(f"facility destination proposal {row.get('id')} has invalid status")
            return errors

        def insert(conn, table: str, row: dict):
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            if data:
                conn.execute(
                    f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})",
                    tuple(data.values()),
                )

        def replace(conn, selected_tenant: int, records: dict):
            errors = validate(records, selected_tenant)
            if errors:
                raise ValueError("; ".join(errors))
            for table in (
                "facility_destination_proposals", "facility_relationship_reviews",
                "facility_relationship_proposals", "facility_image_sources",
            ):
                conn.execute(f"DELETE FROM {table} WHERE tenant_id=?", (selected_tenant,))
            base_replace(conn, selected_tenant, records)
            for table in (
                "facility_image_sources", "facility_relationship_proposals",
                "facility_relationship_reviews", "facility_destination_proposals",
            ):
                for row in records.get(table, []):
                    insert(conn, table, row)
            database_support.reset_identity_sequences(conn, tables)

        core["collect_tenant_records"] = collect
        core["validate_records"] = validate
        core["replace_tenant_records"] = replace
        fastapi_app.state.salcapa_facility_imagery_backup_registered = True

    def internal(request: Request, permission: str = "read"):
        require(request, permission)
        if protected_member_request(request):
            raise HTTPException(403, "Plan and facility-image relationship review is restricted to authorized Salus personnel.")

    def audit(conn, request: Request, action: str, entity_type: str, entity_id: int, detail: str):
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, entity_type, entity_id, detail[:2000], tenant_id(request)),
        )

    def source(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "FACILITY_IMAGERY_TENANT_BOUNDARY_VIOLATION", "High", f"material_id={material_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["disposition_status"] != "Active" or len(str(row["sha256"])) != 64:
            raise HTTPException(422, "Only an active governed source with immutable SHA-256 lineage may be referenced.")
        return row

    def scoped(conn, table: str, item_id: int, request: Request):
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Facility-image review record not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "FACILITY_IMAGERY_TENANT_BOUNDARY_VIOLATION", "High", f"{table}_id={item_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        return row

    @fastapi_app.get("/api/facility-imagery/status")
    def status(request: Request):
        internal(request)
        return {
            "available": True, "external_processing": False, "standing_gpu": False,
            "cost_note": "No paid processing service or standing GPU is used by this bounded capability.",
            "supported_coordinate_spaces": sorted(COORDINATE_SPACES),
            "supported_representation_classes": sorted(REPRESENTATION_CLASSES),
            "guidance": "Review the exact source, its authority, revision, coordinate space, scale limits, uncertainty, and destination before use.",
            "authority_note": "A relationship proposal is not an engineering conclusion, finding, priority, decision, disclosure, identity claim, or approved destination record.",
        }

    @fastapi_app.post("/api/materials/{material_id}/facility-image-sources")
    def create_source(material_id: int, payload: SourceRepresentationIn, request: Request):
        internal(request, "write")
        require_salus_component_authority(request, "SalCAPA plan and facility-image review")
        conn = db()
        row = source(conn, material_id, request)
        if payload.rendered_page_id is not None:
            page = conn.execute(
                "SELECT * FROM pdf_rendered_pages WHERE id=?", (payload.rendered_page_id,)
            ).fetchone()
            if not page or int(page["tenant_id"]) != tenant_id(request) or int(page["source_material_id"]) != material_id:
                conn.close()
                raise HTTPException(409, "Rendered-page lineage does not match the governed source and tenant.")
            if int(page["page_number"]) != payload.page_number or float(page["rendered_width"]) != payload.source_width or float(page["rendered_height"]) != payload.source_height:
                conn.close()
                raise HTTPException(409, "Rendered-page coordinates do not match the recorded page fact.")
        geometry = {
            "coordinate_space": payload.coordinate_space, "page_number": payload.page_number,
            "source_width": payload.source_width, "source_height": payload.source_height,
            "region": [payload.region_x, payload.region_y, payload.region_width, payload.region_height],
        }
        ts = now()
        cur = conn.execute(
            "INSERT INTO facility_image_sources(tenant_id,source_key,source_material_id,source_sha256,rendered_page_id,representation_class,authority_basis,source_revision,source_date,coordinate_space,page_number,source_width,source_height,region_x,region_y,region_width,region_height,geometry_sha256,scale_status,scale_basis,north_reference,datum,projection,precision_status,limitations,purpose,sensitivity,disclosure_status,record_status,created_by,created_by_role,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), "FIS-" + uuid.uuid4().hex, material_id, row["sha256"], payload.rendered_page_id,
             payload.representation_class, payload.authority_basis, payload.source_revision, payload.source_date,
             payload.coordinate_space, payload.page_number, payload.source_width, payload.source_height,
             payload.region_x, payload.region_y, payload.region_width, payload.region_height,
             hashlib.sha256(_canonical(geometry).encode()).hexdigest(), payload.scale_status, payload.scale_basis,
             payload.north_reference, payload.datum, payload.projection, payload.precision_status,
             payload.limitations, payload.purpose, row["sensitivity"], "Salus Internal — Not Released", "Active",
             actor(request), role(request), ts, ts),
        )
        source_id = int(cur.lastrowid)
        audit(conn, request, "FACILITY_IMAGE_SOURCE_RECORDED", "facility_image_source", source_id,
              f"material_id={material_id}; coordinate_space={payload.coordinate_space}; external_processing=false; no_engineering_conclusion=true")
        conn.commit()
        result = dict(conn.execute("SELECT * FROM facility_image_sources WHERE id=?", (source_id,)).fetchone())
        conn.close()
        result["authority_note"] = "This record identifies a bounded source representation. It does not establish source truth or an engineering conclusion."
        return result

    @fastapi_app.post("/api/facility-imagery/sources/{source_id}/relationship-proposals")
    def create_proposal(source_id: int, payload: RelationshipProposalIn, request: Request):
        internal(request, "write")
        require_salus_component_authority(request, "SalCAPA plan and facility-image review")
        conn = db()
        source_row = scoped(conn, "facility_image_sources", source_id, request)
        if source_row["record_status"] != "Active":
            conn.close()
            raise HTTPException(409, "The source representation is not active.")
        ts = now()
        cur = conn.execute(
            "INSERT INTO facility_relationship_proposals(tenant_id,proposal_key,source_id,relationship_type,description,origin_type,target_type,target_id,alternatives_json,contradictions,assumptions,information_gaps,uncertainty_note,epistemic_state,review_status,current_description,current_target_type,current_target_id,sensitivity,disclosure_status,proposed_by,proposed_by_role,proposed_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), "FRP-" + uuid.uuid4().hex, source_id, payload.relationship_type,
             payload.description, payload.origin_type, payload.target_type, payload.target_id,
             _canonical(payload.alternatives), payload.contradictions, payload.assumptions,
             payload.information_gaps, payload.uncertainty_note, "Derived — Unverified",
             "Awaiting Human Review", payload.description, payload.target_type, payload.target_id,
             source_row["sensitivity"], "Salus Internal — Not Released", actor(request), role(request), ts, ts),
        )
        proposal_id = int(cur.lastrowid)
        audit(conn, request, "FACILITY_RELATIONSHIP_PROPOSED", "facility_relationship_proposal", proposal_id,
              f"source_id={source_id}; relationship_type={payload.relationship_type}; derived_unverified=true; no_destination_change=true")
        conn.commit()
        result = dict(conn.execute("SELECT * FROM facility_relationship_proposals WHERE id=?", (proposal_id,)).fetchone())
        conn.close()
        result["alternatives"] = json.loads(result.pop("alternatives_json"))
        result["authority_note"] = "Compare this unverified proposal with the exact source region and current governed records."
        return result

    @fastapi_app.post("/api/facility-imagery/relationship-proposals/{proposal_id}/review")
    def review_proposal(proposal_id: int, payload: RelationshipReviewIn, request: Request):
        internal(request, "decide")
        require_salus_component_authority(request, "SalCAPA plan and facility-image review")
        conn = db()
        row = scoped(conn, "facility_relationship_proposals", proposal_id, request)
        if row["review_status"] != "Awaiting Human Review":
            conn.close()
            raise HTTPException(409, "This proposal already has a recorded review state.")
        if row["proposed_by"] == actor(request):
            conn.close()
            raise HTTPException(409, "A different authorized person must review this relationship proposal.")
        description = payload.corrected_description if payload.status == "Corrected" else row["current_description"]
        target_type = payload.corrected_target_type if payload.status == "Corrected" else row["current_target_type"]
        target_id = payload.corrected_target_id if payload.status == "Corrected" else row["current_target_id"]
        ts = now()
        conn.execute(
            "UPDATE facility_relationship_proposals SET review_status=?,current_description=?,current_target_type=?,current_target_id=?,updated_at=? WHERE id=?",
            (payload.status, description, target_type, target_id, ts, proposal_id),
        )
        conn.execute(
            "INSERT INTO facility_relationship_reviews(tenant_id,proposal_id,review_type,reason,corrected_description,corrected_target_type,corrected_target_id,corrected_geometry_json,reviewed_by,reviewed_by_role,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), proposal_id, payload.status, payload.reason, payload.corrected_description,
             payload.corrected_target_type, payload.corrected_target_id,
             _canonical(json.loads(payload.corrected_geometry_json or "{}")), actor(request), role(request), ts),
        )
        audit(conn, request, "FACILITY_RELATIONSHIP_REVIEWED", "facility_relationship_proposal", proposal_id,
              f"status={payload.status}; source_unchanged=true; no_finding_or_disclosure=true")
        conn.commit()
        result = dict(conn.execute("SELECT * FROM facility_relationship_proposals WHERE id=?", (proposal_id,)).fetchone())
        conn.close()
        result["authority_note"] = "This review addresses the bounded representation only. Destination authority remains separate."
        return result

    @fastapi_app.post("/api/facility-imagery/relationship-proposals/{proposal_id}/destination-proposals")
    def create_destination(proposal_id: int, payload: DestinationProposalIn, request: Request):
        internal(request, "write")
        require_salus_component_authority(request, "SalCAPA plan and facility-image review")
        conn = db()
        row = scoped(conn, "facility_relationship_proposals", proposal_id, request)
        if row["review_status"] not in {"Accept Representation", "Corrected"}:
            conn.close()
            raise HTTPException(409, "Only an independently accepted or corrected representation may be proposed to a destination.")
        ts = now()
        cur = conn.execute(
            "INSERT INTO facility_destination_proposals(tenant_id,destination_key,proposal_id,destination_product,destination_type,destination_id,purpose,status,sensitivity,disclosure_status,proposed_by,proposed_by_role,proposed_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), "FDP-" + uuid.uuid4().hex, proposal_id, payload.destination_product,
             payload.destination_type, payload.destination_id, payload.purpose, "Awaiting Destination Review",
             row["sensitivity"], "Salus Internal — Not Released", actor(request), role(request), ts, ts),
        )
        destination_id = int(cur.lastrowid)
        audit(conn, request, "FACILITY_DESTINATION_REFERENCE_PROPOSED", "facility_destination_proposal", destination_id,
              f"proposal_id={proposal_id}; destination={payload.destination_product}; no_destination_change=true")
        conn.commit()
        result = dict(conn.execute("SELECT * FROM facility_destination_proposals WHERE id=?", (destination_id,)).fetchone())
        conn.close()
        result["authority_note"] = "The destination must apply its own authority, review, and disclosure rules before use."
        return result

    @fastapi_app.get("/api/facility-imagery/triage")
    def triage(request: Request, limit: int = 200):
        internal(request)
        conn = db()
        items = [dict(row) for row in conn.execute(
            "SELECT p.*,s.source_material_id,s.source_sha256,s.coordinate_space,s.page_number,s.region_x,s.region_y,s.region_width,s.region_height,s.representation_class,s.scale_status,s.authority_basis FROM facility_relationship_proposals p JOIN facility_image_sources s ON s.id=p.source_id WHERE p.tenant_id=? ORDER BY CASE p.review_status WHEN 'Awaiting Human Review' THEN 0 ELSE 1 END,p.id DESC LIMIT ?",
            (tenant_id(request), max(1, min(limit, 500))),
        )]
        for item in items:
            require_sensitivity(request, item["sensitivity"])
            item["alternatives"] = json.loads(item.pop("alternatives_json"))
        conn.close()
        return {
            "items": items,
            "guidance": "Review authority, revision, scale, coordinate space, uncertainty, contradictions, and the exact source region before accepting a representation.",
            "external_processing": False,
        }
