"""Governed source-version change detection and reprocessing authorization for M365."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, M365IntakeError


SCHEMA = """
CREATE TABLE IF NOT EXISTS m365_material_source_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  check_key TEXT NOT NULL UNIQUE,
  material_id INTEGER NOT NULL,
  item_id TEXT NOT NULL,
  recorded_etag TEXT NOT NULL,
  observed_etag TEXT NOT NULL DEFAULT '',
  recorded_ctag TEXT NOT NULL DEFAULT '',
  observed_ctag TEXT NOT NULL DEFAULT '',
  observed_last_modified TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  observed_metadata_json TEXT NOT NULL,
  checked_by TEXT NOT NULL,
  checked_by_role TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_m365_source_checks_material
  ON m365_material_source_checks(tenant_id,material_id,id);

CREATE TABLE IF NOT EXISTS m365_material_reprocessing_authorizations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  authorization_key TEXT NOT NULL UNIQUE,
  source_check_id INTEGER NOT NULL UNIQUE,
  prior_material_id INTEGER NOT NULL,
  item_id TEXT NOT NULL,
  recorded_etag TEXT NOT NULL,
  authorized_etag TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL,
  authorized_by TEXT NOT NULL,
  authorized_by_role TEXT NOT NULL,
  authorized_at TEXT NOT NULL,
  consumed_at TEXT NOT NULL DEFAULT '',
  new_material_id INTEGER,
  FOREIGN KEY (source_check_id) REFERENCES m365_material_source_checks(id) ON DELETE RESTRICT,
  FOREIGN KEY (prior_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
  FOREIGN KEY (new_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_m365_reprocessing_material
  ON m365_material_reprocessing_authorizations(tenant_id,prior_material_id,status,id);
"""


class M365ReprocessingAuthorizationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A documented reprocessing reason is required")
        return value


def _locator(row: Any) -> dict[str, Any]:
    try:
        value = json.loads(row["source_locator"])
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(409, "Material source attribution is invalid") from exc
    if not isinstance(value, dict):
        raise HTTPException(409, "Material source attribution is invalid")
    return value


def register_m365_source_change_control(app: Any, core: dict[str, Any]) -> None:
    required = (
        "db", "now", "actor", "role", "tenant_id", "auth_context",
        "require_sensitivity", "security_event",
    )
    if any(name not in core for name in required):
        return
    db = core["db"]
    now = core["now"]
    actor = core["actor"]
    role = core["role"]
    tenant_id = core["tenant_id"]
    auth_context = core["auth_context"]
    require_sensitivity = core["require_sensitivity"]
    security_event = core["security_event"]

    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    def require_admin(request: Request) -> None:
        if auth_context(request).get("role") != "System Administrator":
            raise HTTPException(403, "System Administrator authority is required")

    def material_for_request(conn, material_id: int, request: Request):
        row = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Material not found")
        if int(row["tenant_id"]) != int(tenant_id(request)):
            security_event(
                request, "M365_CHANGE_TENANT_BOUNDARY_VIOLATION", "High",
                f"material_id={material_id}",
            )
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["source_origin"] != "Microsoft 365 governed intake":
            raise HTTPException(409, "Material is not a governed Microsoft 365 source")
        if row["disposition_status"] != "Active":
            raise HTTPException(409, "Disposed material cannot be checked")
        return row

    @app.post(
        "/api/integrations/m365/intake/materials/{material_id}/check-source-version",
        include_in_schema=False,
    )
    def check_source_version(material_id: int, request: Request) -> dict[str, Any]:
        require_admin(request)
        tid = int(tenant_id(request))
        conn = db()
        try:
            material = material_for_request(conn, material_id, request)
            locator = _locator(material)
            config = GovernedM365Config.from_environment()
            if (
                locator.get("drive_id") != config.drive_id
                or locator.get("folder_item_id") != config.folder_item_id
            ):
                raise HTTPException(
                    409, "Material is outside the currently authorized intake folder",
                )
            item_id = str(locator.get("item_id", ""))
            try:
                items = GovernedM365Intake(config).list_files()
            except M365IntakeError as exc:
                raise HTTPException(
                    503, "Governed Microsoft 365 source check is unavailable",
                ) from exc
            observed = next((item for item in items if item["id"] == item_id), None)
            recorded_etag = str(locator.get("etag", ""))
            recorded_ctag = str(locator.get("ctag", ""))
            if observed is None:
                status = "Missing"
                observed_etag = ""
                observed_ctag = ""
                observed_last_modified = ""
                metadata = {"item_id": item_id, "present": False}
            else:
                observed_etag = observed["etag"]
                observed_ctag = observed["ctag"]
                observed_last_modified = observed["last_modified"]
                status = (
                    "Unchanged"
                    if observed_etag == recorded_etag
                    and observed_ctag == recorded_ctag
                    else "Changed"
                )
                metadata = dict(observed) | {"present": True}
            checked = now()
            cur = conn.execute(
                "INSERT INTO m365_material_source_checks(tenant_id,check_key,material_id,"
                "item_id,recorded_etag,observed_etag,recorded_ctag,observed_ctag,"
                "observed_last_modified,status,observed_metadata_json,checked_by,"
                "checked_by_role,checked_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tid, "MSC-" + uuid.uuid4().hex, material_id, item_id,
                    recorded_etag, observed_etag, recorded_ctag, observed_ctag,
                    observed_last_modified, status,
                    json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                    actor(request), role(request), checked,
                ),
            )
            check_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,"
                "tenant_id) VALUES(?,?,?,?,?,?,?)",
                (
                    checked, actor(request), "M365_SOURCE_VERSION_CHECKED",
                    "m365_material_source_check", check_id,
                    f"material_id={material_id}; status={status}; "
                    f"recorded_etag={recorded_etag}; observed_etag={observed_etag}",
                    tid,
                ),
            )
            conn.commit()
            return {
                "check_id": check_id,
                "material_id": material_id,
                "item_id": item_id,
                "status": status,
                "recorded_etag": recorded_etag,
                "observed_etag": observed_etag,
                "recorded_ctag": recorded_ctag,
                "observed_ctag": observed_ctag,
                "observed_last_modified": observed_last_modified,
                "reprocessing_required": status == "Changed",
                "reprocessing_authorized": False,
                "missing_source_requires_review": status == "Missing",
            }
        except HTTPException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.post(
        "/api/integrations/m365/intake/source-checks/{check_id}/authorize-reprocessing",
        include_in_schema=False,
    )
    def authorize_reprocessing(
        check_id: int, payload: M365ReprocessingAuthorizationIn, request: Request,
    ) -> dict[str, Any]:
        require_admin(request)
        tid = int(tenant_id(request))
        conn = db()
        try:
            check = conn.execute(
                "SELECT * FROM m365_material_source_checks WHERE id=?", (check_id,),
            ).fetchone()
            if not check:
                raise HTTPException(404, "Source-version check not found")
            if int(check["tenant_id"]) != tid:
                security_event(
                    request, "M365_REPROCESS_TENANT_BOUNDARY_VIOLATION", "High",
                    f"check_id={check_id}",
                )
                raise HTTPException(403, "Tenant boundary violation")
            if check["status"] != "Changed":
                raise HTTPException(
                    409, "Reprocessing may be authorized only for a changed source",
                )
            existing = conn.execute(
                "SELECT * FROM m365_material_reprocessing_authorizations "
                "WHERE source_check_id=?", (check_id,),
            ).fetchone()
            if existing:
                raise HTTPException(409, "This source change already has an authorization")
            authorized = now()
            cur = conn.execute(
                "INSERT INTO m365_material_reprocessing_authorizations(tenant_id,"
                "authorization_key,source_check_id,prior_material_id,item_id,"
                "recorded_etag,authorized_etag,reason,status,authorized_by,"
                "authorized_by_role,authorized_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tid, "MRA-" + uuid.uuid4().hex, check_id, check["material_id"],
                    check["item_id"], check["recorded_etag"], check["observed_etag"],
                    payload.reason, "Authorized", actor(request), role(request), authorized,
                ),
            )
            authorization_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,"
                "tenant_id) VALUES(?,?,?,?,?,?,?)",
                (
                    authorized, actor(request), "M365_REPROCESSING_AUTHORIZED",
                    "m365_material_reprocessing_authorization", authorization_id,
                    f"prior_material_id={check['material_id']}; "
                    f"authorized_etag={check['observed_etag']}", tid,
                ),
            )
            conn.commit()
            return {
                "authorization_id": authorization_id,
                "authorization_key": conn.execute(
                    "SELECT authorization_key FROM m365_material_reprocessing_authorizations "
                    "WHERE id=?", (authorization_id,),
                ).fetchone()["authorization_key"],
                "prior_material_id": check["material_id"],
                "item_id": check["item_id"],
                "authorized_etag": check["observed_etag"],
                "status": "Authorized",
                "capture_command": {
                    "supersedes_material_id": check["material_id"],
                    "reprocessing_authorization_id": authorization_id,
                },
                "automatic_processing": False,
                "human_review_required": True,
            }
        except HTTPException:
            conn.rollback()
            raise
        finally:
            conn.close()
