"""Persist approved Microsoft 365 intake files as governed SalCAPA materials."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, M365IntakeError


class M365MaterialIngestCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="", max_length=240)
    sensitivity: str = "Restricted"
    purpose_tags: list[str] = Field(default_factory=lambda: ["SalINTEL research"], max_length=20)
    description: str = Field(default="", max_length=6000)
    recording_authority_basis: str = Field(min_length=1, max_length=2000)
    supersedes_material_id: int | None = Field(default=None, gt=0)
    reprocessing_authorization_id: int | None = Field(default=None, gt=0)

    @field_validator("sensitivity")
    @classmethod
    def validate_sensitivity(cls, value: str) -> str:
        if value not in {"Standard", "Restricted", "Sensitive", "Highly Sensitive"}:
            raise ValueError("unsupported material sensitivity")
        return value

    @field_validator("purpose_tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            tag = str(value).strip()
            if not tag or len(tag) > 80:
                raise ValueError("purpose tags must contain 1 to 80 characters")
            if tag not in result:
                result.append(tag)
        return result

    @field_validator("recording_authority_basis")
    @classmethod
    def validate_authority(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("a recording authority basis is required")
        return value


def _material_kind(name: str) -> str:
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension in {"jpg", "jpeg", "png"}:
        return "Image"
    if extension in {"csv", "tsv", "json", "xml", "xlsx"}:
        return "Structured Data"
    if extension in {"txt", "log"}:
        return "Text"
    return "Document"


def register_m365_material_ingestion(app: Any, namespace: dict[str, Any]) -> None:
    """Register an administrator-only governed-subtree material capture route."""
    required_names = (
        "db", "storage", "scan_bytes", "safe_filename", "now", "actor",
        "tenant_id", "auth_context", "RETENTION_DEFAULT_DAYS", "_iso_now_dt",
    )
    if any(name not in namespace for name in required_names):
        return
    db = namespace["db"]
    storage = namespace["storage"]
    scan_bytes = namespace["scan_bytes"]
    safe_filename = namespace["safe_filename"]
    now = namespace["now"]
    actor = namespace["actor"]
    tenant_id = namespace["tenant_id"]
    auth_context = namespace["auth_context"]
    retention_days = int(namespace["RETENTION_DEFAULT_DAYS"])
    iso_now_dt = namespace["_iso_now_dt"]
    security_event = namespace.get("security_event")

    def require_admin(request: Request) -> dict[str, Any]:
        context = auth_context(request)
        if context.get("role") != "System Administrator":
            raise HTTPException(403, "System Administrator authority is required")
        return context

    @app.post(
        "/api/integrations/m365/intake/files/{item_id}/ingest",
        include_in_schema=False,
    )
    def ingest_m365_material(
        item_id: str, command: M365MaterialIngestCommand, request: Request,
    ) -> dict[str, Any]:
        context = require_admin(request)
        config = GovernedM365Config.from_environment()
        try:
            source = GovernedM365Intake(config).read_document(
                item_id, access_classification=command.sensitivity,
            )
        except M365IntakeError as exc:
            raise HTTPException(503, "Governed Microsoft 365 intake is unavailable") from exc
        original = safe_filename(source.name)
        scan = scan_bytes(source.content, original)
        if not scan.get("ok"):
            if security_event:
                security_event(
                    request, "M365_MATERIAL_REJECTED",
                    "High" if scan.get("status") == "Infected" else "Medium",
                    f"{original}: {scan.get('status', 'Scan unavailable')}",
                )
            raise HTTPException(
                422 if scan.get("status") == "Infected" else 503,
                f"Microsoft 365 material rejected: {scan.get('status', 'Scan unavailable')}",
            )
        tid = int(tenant_id(request))
        source_locator = json.dumps({
            "provider": "Microsoft 365",
            "drive_id": config.drive_id,
            "folder_item_id": config.folder_item_id,
            "relative_path": source.relative_path or source.name,
            "item_id": source.item_id,
            "etag": source.etag,
            "ctag": source.ctag,
            "web_url": source.web_url,
        }, sort_keys=True, separators=(",", ":"))
        provenance = json.dumps({
            "authority_basis": command.recording_authority_basis,
            "source_owner": source.source_owner,
            "source_owner_id": source.source_owner_id,
            "last_modified_by": source.last_modified_by,
            "relative_path": source.relative_path or source.name,
        }, sort_keys=True, separators=(",", ":"))
        conn = db()
        wrote_object = False
        stored = ""
        try:
            existing_version = conn.execute(
                "SELECT id FROM materials WHERE tenant_id=? AND source_locator=? "
                "AND disposition_status='Active' ORDER BY id LIMIT 1",
                (tid, source_locator),
            ).fetchone()
            if existing_version:
                raise HTTPException(409, "This Microsoft 365 source version is already ingested")
            prior = None
            for candidate in conn.execute(
                "SELECT id,source_locator,processing_status FROM materials "
                "WHERE tenant_id=? AND source_origin='Microsoft 365 governed intake' "
                "AND disposition_status='Active' ORDER BY id DESC",
                (tid,),
            ):
                try:
                    candidate_locator = json.loads(candidate["source_locator"])
                except (TypeError, ValueError):
                    continue
                if (
                    isinstance(candidate_locator, dict)
                    and candidate_locator.get("drive_id") == config.drive_id
                    and candidate_locator.get("folder_item_id") == config.folder_item_id
                    and candidate_locator.get("item_id") == source.item_id
                ):
                    prior = candidate
                    break
            authorization = None
            if prior is not None:
                if (
                    command.supersedes_material_id != int(prior["id"])
                    or command.reprocessing_authorization_id is None
                ):
                    raise HTTPException(
                        409,
                        "A changed Microsoft 365 source requires explicit reprocessing authorization",
                    )
                try:
                    authorization = conn.execute(
                        "SELECT * FROM m365_material_reprocessing_authorizations "
                        "WHERE id=? AND tenant_id=? AND prior_material_id=? AND item_id=? "
                        "AND authorized_etag=? AND status='Authorized'",
                        (
                            command.reprocessing_authorization_id, tid, int(prior["id"]),
                            source.item_id, source.etag,
                        ),
                    ).fetchone()
                except Exception as exc:
                    raise HTTPException(
                        409, "Microsoft 365 reprocessing authorization is unavailable",
                    ) from exc
                if not authorization:
                    raise HTTPException(
                        409, "Microsoft 365 reprocessing authorization is invalid or stale",
                    )
            elif (
                command.supersedes_material_id is not None
                or command.reprocessing_authorization_id is not None
            ):
                raise HTTPException(
                    409, "Reprocessing authorization does not match an earlier source version",
                )
            duplicate = conn.execute(
                "SELECT id,stored_name FROM materials WHERE tenant_id=? AND sha256=? "
                "AND stored_name<>'' AND disposition_status='Active' ORDER BY id LIMIT 1",
                (tid, source.sha256),
            ).fetchone()
            duplicate_id = int(duplicate["id"]) if duplicate else None
            stored = (
                duplicate["stored_name"] if duplicate else
                f"tenant-{tid}/materials/{source.sha256[:2]}/{source.sha256}_{original}"
            )
            if not duplicate:
                storage.put_bytes(stored, source.content)
                wrote_object = True
            created = now()
            retention_until = (
                (iso_now_dt() + timedelta(days=retention_days))
                .replace(microsecond=0).isoformat().replace("+00:00", "Z")
                if retention_days > 0 else ""
            )
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
                    tid, "MAT-" + uuid.uuid4().hex, command.title.strip() or original,
                    _material_kind(original), original, stored, source.mime_type, source.size,
                    source.sha256, "Microsoft 365 governed intake", source_locator,
                    source.last_modified, created, actor(request), context.get("user_id"),
                    command.sensitivity, json.dumps(command.purpose_tags, separators=(",", ":")),
                    command.description.strip(), provenance, "Submitted", "Ready for Processing",
                    str(scan.get("status", "")), str(scan.get("detail", ""))[:1000], created,
                    retention_until, 0, "Active", "Salus Internal", 1,
                    int(prior["id"]) if prior is not None else None,
                    "M365 Source Version" if prior is not None else "", "", "", "",
                    duplicate_id, created, created,
                ),
            )
            material_id = int(cur.lastrowid)
            row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
            if authorization is not None:
                conn.execute(
                    "UPDATE m365_material_reprocessing_authorizations "
                    "SET status='Consumed',consumed_at=?,new_material_id=? WHERE id=?",
                    (created, material_id, int(authorization["id"])),
                )
                prior_row = conn.execute(
                    "SELECT * FROM materials WHERE id=?", (int(prior["id"]),)
                ).fetchone()
                conn.execute(
                    "INSERT INTO material_events(tenant_id,material_id,event_type,"
                    "from_status,to_status,reason,snapshot_json,changed_by,changed_by_role,"
                    "created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        tid, int(prior["id"]), "M365_SOURCE_VERSION_SUPERSEDED",
                        prior["processing_status"], prior["processing_status"],
                        f"Authorized successor material {material_id} captured for eTag {source.etag}.",
                        json.dumps(dict(prior_row), sort_keys=True, default=str),
                        actor(request), context.get("role", "System Administrator"), created,
                    ),
                )
            conn.execute(
                "INSERT INTO material_events(tenant_id,material_id,event_type,from_status,to_status,"
                "reason,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    tid, material_id, "M365_SOURCE_CAPTURED", "Received", "Ready for Processing",
                    "Approved exact-folder Microsoft 365 source captured as an immutable original.",
                    json.dumps(dict(row), sort_keys=True, default=str), actor(request),
                    context.get("role", "System Administrator"), created,
                ),
            )
            conn.execute(
                "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    created, actor(request), "M365_MATERIAL_CAPTURED", "material", material_id,
                    f"item={source.item_id}; etag={source.etag}; sha256={source.sha256}", tid,
                ),
            )
            conn.commit()
            return {
                "material_id": material_id,
                "record_key": row["record_key"],
                "title": row["title"],
                "original_name": original,
                "material_kind": row["material_kind"],
                "content_type": source.mime_type,
                "size_bytes": source.size,
                "sha256": source.sha256,
                "source_item_id": source.item_id,
                "source_etag": source.etag,
                "source_ctag": source.ctag,
                "source_last_modified": source.last_modified,
                "source_owner": source.source_owner,
                "sensitivity": command.sensitivity,
                "processing_status": "Ready for Processing",
                "disclosure_status": "Salus Internal",
                "immutable_original": True,
                "duplicate_of_material_id": duplicate_id,
                "supersedes_material_id": int(prior["id"]) if prior is not None else None,
                "source_version_status": "Authorized New Version" if prior is not None else "Initial Version",
                "processing_endpoint": f"/api/materials/{material_id}/safe-text-processing",
                "human_review_required": True,
                "indexing_status": "Not Indexed",
                "finding_status": "None Created",
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            if wrote_object:
                try:
                    storage.delete(stored)
                except Exception:
                    pass
            raise HTTPException(503, "Governed material intake could not be recorded") from exc
        finally:
            conn.close()
