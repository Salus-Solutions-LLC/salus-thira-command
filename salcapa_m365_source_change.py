"""Governed source-version change detection and reprocessing authorization for M365."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, M365IntakeError
from salcapa_m365_material_ingestion import M365MaterialIngestCommand


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

CREATE TABLE IF NOT EXISTS m365_intake_review_decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  decision_key TEXT NOT NULL UNIQUE,
  item_id TEXT NOT NULL,
  material_id INTEGER,
  version_etag TEXT NOT NULL,
  source_status TEXT NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT NOT NULL,
  decided_by TEXT NOT NULL,
  decided_by_role TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_m365_intake_review_queue
  ON m365_intake_review_decisions(tenant_id,item_id,version_etag,id);

CREATE TABLE IF NOT EXISTS m365_batch_capture_executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  execution_key TEXT NOT NULL UNIQUE,
  requested_count INTEGER NOT NULL,
  status TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  authority_basis TEXT NOT NULL,
  started_by TEXT NOT NULL,
  started_by_role TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS m365_batch_capture_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  execution_id INTEGER NOT NULL,
  decision_id INTEGER NOT NULL,
  item_id TEXT NOT NULL,
  source_status TEXT NOT NULL,
  status TEXT NOT NULL,
  material_id INTEGER,
  detail TEXT NOT NULL,
  completed_at TEXT NOT NULL,
  FOREIGN KEY (execution_id) REFERENCES m365_batch_capture_executions(id) ON DELETE RESTRICT,
  FOREIGN KEY (decision_id) REFERENCES m365_intake_review_decisions(id) ON DELETE RESTRICT,
  FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_m365_batch_capture_items
  ON m365_batch_capture_items(tenant_id,execution_id,id);
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



class M365BatchReviewDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_ids: list[str] = Field(min_length=1, max_length=50)
    decision: Literal["Approve", "Defer", "Dismiss"]
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("item_ids")
    @classmethod
    def normalize_item_ids(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            item_id = str(value).strip()
            if not item_id or len(item_id) > 240:
                raise ValueError("item identifiers must contain 1 to 240 characters")
            if item_id not in result:
                result.append(item_id)
        if not result:
            raise ValueError("at least one item identifier is required")
        return result

    @field_validator("reason")
    @classmethod
    def normalize_batch_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A documented review reason is required")
        return value



class M365ApprovedBatchCaptureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_ids: list[int] = Field(min_length=1, max_length=25)
    sensitivity: Literal["Standard", "Restricted", "Sensitive", "Highly Sensitive"] = "Restricted"
    purpose_tags: list[str] = Field(default_factory=lambda: ["SalINTEL research"], max_length=20)
    description: str = Field(default="", max_length=6000)
    recording_authority_basis: str = Field(min_length=1, max_length=2000)

    @field_validator("decision_ids")
    @classmethod
    def normalize_decision_ids(cls, values: list[int]) -> list[int]:
        result: list[int] = []
        for value in values:
            decision_id = int(value)
            if decision_id <= 0:
                raise ValueError("decision identifiers must be positive")
            if decision_id not in result:
                result.append(decision_id)
        if not result:
            raise ValueError("at least one decision identifier is required")
        return result

    @field_validator("recording_authority_basis")
    @classmethod
    def normalize_capture_authority(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A recording authority basis is required")
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
        "/api/integrations/m365/intake/reconcile-source-versions",
        include_in_schema=False,
    )
    def reconcile_source_versions(request: Request) -> dict[str, Any]:
        """Compare the authorized nested intake tree with latest active captured versions."""
        require_admin(request)
        tid = int(tenant_id(request))
        config = GovernedM365Config.from_environment()
        try:
            observed_items = GovernedM365Intake(config).list_files()
        except M365IntakeError as exc:
            raise HTTPException(
                503, "Governed Microsoft 365 reconciliation is unavailable",
            ) from exc

        observed_by_id = {
            str(item.get("id", "")): item
            for item in observed_items
            if str(item.get("id", ""))
        }
        conn = db()
        try:
            latest_by_id: dict[str, tuple[Any, dict[str, Any]]] = {}
            rows = conn.execute(
                "SELECT * FROM materials WHERE tenant_id=? "
                "AND source_origin='Microsoft 365 governed intake' "
                "AND disposition_status='Active' ORDER BY id DESC",
                (tid,),
            )
            for row in rows:
                try:
                    locator = _locator(row)
                except HTTPException:
                    continue
                if (
                    locator.get("drive_id") != config.drive_id
                    or locator.get("folder_item_id") != config.folder_item_id
                ):
                    continue
                item_id = str(locator.get("item_id", ""))
                if item_id and item_id not in latest_by_id:
                    latest_by_id[item_id] = (row, locator)

            items: list[dict[str, Any]] = []
            counts = {"New": 0, "Unchanged": 0, "Changed": 0, "Missing": 0}
            for item_id in sorted(set(observed_by_id) | set(latest_by_id)):
                observed = observed_by_id.get(item_id)
                captured = latest_by_id.get(item_id)
                if captured is None:
                    status = "New"
                    material_id = None
                    recorded_etag = ""
                    recorded_ctag = ""
                else:
                    material, locator = captured
                    material_id = int(material["id"])
                    recorded_etag = str(locator.get("etag", ""))
                    recorded_ctag = str(locator.get("ctag", ""))
                    if observed is None:
                        status = "Missing"
                    elif (
                        str(observed.get("etag", "")) == recorded_etag
                        and str(observed.get("ctag", "")) == recorded_ctag
                    ):
                        status = "Unchanged"
                    else:
                        status = "Changed"
                counts[status] += 1
                version_etag = (
                    str((observed or {}).get("etag", "")) or recorded_etag
                )
                decision_row = conn.execute(
                    "SELECT id,decision,reason,decided_by,decided_by_role,decided_at "
                    "FROM m365_intake_review_decisions WHERE tenant_id=? "
                    "AND item_id=? AND version_etag=? ORDER BY id DESC LIMIT 1",
                    (tid, item_id, version_etag),
                ).fetchone()
                items.append({
                    "item_id": item_id,
                    "material_id": material_id,
                    "status": status,
                    "name": str((observed or {}).get("name", "")),
                    "relative_path": str((observed or {}).get("relative_path", "")),
                    "size": int((observed or {}).get("size", 0)),
                    "recorded_etag": recorded_etag,
                    "observed_etag": str((observed or {}).get("etag", "")),
                    "recorded_ctag": recorded_ctag,
                    "observed_ctag": str((observed or {}).get("ctag", "")),
                    "last_modified": str((observed or {}).get("last_modified", "")),
                    "automatic_ingestion": False,
                    "automatic_reprocessing": False,
                    "human_review_required": status in {"New", "Changed", "Missing"},
                    "review_decision_id": int(decision_row["id"]) if decision_row else None,
                    "review_decision": decision_row["decision"] if decision_row else "Pending",
                    "review_reason": decision_row["reason"] if decision_row else "",
                    "reviewed_by": decision_row["decided_by"] if decision_row else "",
                    "reviewed_at": decision_row["decided_at"] if decision_row else "",
                    "version_etag": version_etag,
                })

            reconciled = now()
            conn.execute(
                "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,"
                "tenant_id) VALUES(?,?,?,?,?,?,?)",
                (
                    reconciled, actor(request), "M365_SOURCE_TREE_RECONCILED",
                    "m365_intake_reconciliation", 0,
                    "new={New}; unchanged={Unchanged}; changed={Changed}; missing={Missing}".format(
                        **counts
                    ),
                    tid,
                ),
            )
            conn.commit()
            return {
                "drive_id": config.drive_id,
                "folder_item_id": config.folder_item_id,
                "scope": "Authorized folder and all nested folders",
                "counts": counts,
                "items": items,
                "automatic_ingestion": False,
                "automatic_reprocessing": False,
                "human_authorization_required": True,
                "reconciled_at": reconciled,
            }
        except HTTPException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.post(
        "/api/integrations/m365/intake/review-queue/batch-decision",
        include_in_schema=False,
    )
    def record_batch_review_decision(
        payload: M365BatchReviewDecisionIn, request: Request,
    ) -> dict[str, Any]:
        """Record a bounded human decision only after revalidating current source state."""
        require_admin(request)
        reconciliation = reconcile_source_versions(request)
        current = {
            item["item_id"]: item
            for item in reconciliation["items"]
            if item["status"] in {"New", "Changed", "Missing"}
        }
        missing = [item_id for item_id in payload.item_ids if item_id not in current]
        if missing:
            raise HTTPException(
                409,
                "One or more selected sources are unchanged, unavailable, or stale; "
                "run reconciliation again",
            )

        tid = int(tenant_id(request))
        decided = now()
        conn = db()
        try:
            decisions = []
            for item_id in payload.item_ids:
                item = current[item_id]
                cur = conn.execute(
                    "INSERT INTO m365_intake_review_decisions(tenant_id,decision_key,"
                    "item_id,material_id,version_etag,source_status,decision,reason,"
                    "decided_by,decided_by_role,decided_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        tid, "MRD-" + uuid.uuid4().hex, item_id, item["material_id"],
                        item["version_etag"], item["status"], payload.decision,
                        payload.reason, actor(request), role(request), decided,
                    ),
                )
                decision_id = int(cur.lastrowid)
                decisions.append({
                    "decision_id": decision_id,
                    "item_id": item_id,
                    "material_id": item["material_id"],
                    "version_etag": item["version_etag"],
                    "source_status": item["status"],
                    "decision": payload.decision,
                })
            conn.execute(
                "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,"
                "tenant_id) VALUES(?,?,?,?,?,?,?)",
                (
                    decided, actor(request), "M365_BATCH_REVIEW_DECIDED",
                    "m365_intake_review_decision", decisions[0]["decision_id"],
                    f"decision={payload.decision}; count={len(decisions)}; "
                    f"ids={','.join(payload.item_ids)}",
                    tid,
                ),
            )
            conn.commit()
            return {
                "decision": payload.decision,
                "reason": payload.reason,
                "count": len(decisions),
                "items": decisions,
                "batch_limit": 50,
                "automatic_ingestion": False,
                "automatic_reprocessing": False,
                "next_step": (
                    "Approved items require an explicit governed capture or "
                    "reprocessing command."
                    if payload.decision == "Approve"
                    else "No capture or reprocessing action was authorized."
                ),
                "decided_at": decided,
            }
        except HTTPException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.post(
        "/api/integrations/m365/intake/review-queue/execute-approved",
        include_in_schema=False,
    )
    def execute_approved_batch(
        payload: M365ApprovedBatchCaptureIn, request: Request,
    ) -> dict[str, Any]:
        """Execute a bounded approved batch with isolated per-item results."""
        require_admin(request)
        capture = getattr(app.state, "m365_governed_capture", None)
        if capture is None:
            raise HTTPException(503, "Governed Microsoft 365 capture is unavailable")
        tid = int(tenant_id(request))
        reconciliation = reconcile_source_versions(request)
        current = {item["item_id"]: item for item in reconciliation["items"]}
        conn = db()
        try:
            decisions = []
            for decision_id in payload.decision_ids:
                row = conn.execute(
                    "SELECT * FROM m365_intake_review_decisions WHERE id=?",
                    (decision_id,),
                ).fetchone()
                if not row:
                    raise HTTPException(404, "Review decision not found")
                if int(row["tenant_id"]) != tid:
                    security_event(
                        request, "M365_BATCH_TENANT_BOUNDARY_VIOLATION", "High",
                        f"decision_id={decision_id}",
                    )
                    raise HTTPException(403, "Tenant boundary violation")
                latest = conn.execute(
                    "SELECT id FROM m365_intake_review_decisions WHERE tenant_id=? "
                    "AND item_id=? AND version_etag=? ORDER BY id DESC LIMIT 1",
                    (tid, row["item_id"], row["version_etag"]),
                ).fetchone()
                if (
                    row["decision"] != "Approve"
                    or not latest
                    or int(latest["id"]) != int(row["id"])
                ):
                    raise HTTPException(409, "A selected approval is not current")
                prior_success = conn.execute(
                    "SELECT id FROM m365_batch_capture_items WHERE tenant_id=? "
                    "AND decision_id=? AND status='Succeeded' LIMIT 1",
                    (tid, decision_id),
                ).fetchone()
                if prior_success:
                    raise HTTPException(409, "An approved source was already captured")
                item = current.get(row["item_id"])
                if (
                    not item
                    or item["status"] != row["source_status"]
                    or item["version_etag"] != row["version_etag"]
                ):
                    raise HTTPException(
                        409, "A selected source changed after approval; reconcile again",
                    )
                decisions.append(row)
            started = now()
            cur = conn.execute(
                "INSERT INTO m365_batch_capture_executions(tenant_id,execution_key,"
                "requested_count,status,sensitivity,authority_basis,started_by,"
                "started_by_role,started_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    tid, "MBE-" + uuid.uuid4().hex, len(decisions), "Running",
                    payload.sensitivity, payload.recording_authority_basis,
                    actor(request), role(request), started,
                ),
            )
            execution_id = int(cur.lastrowid)
            conn.commit()

            results = []
            for decision in decisions:
                material_id = None
                status = "Failed"
                detail = ""
                try:
                    if decision["source_status"] == "Missing":
                        raise HTTPException(
                            409, "A missing source cannot be captured",
                        )
                    supersedes = None
                    authorization_id = None
                    if decision["source_status"] == "Changed":
                        check = check_source_version(
                            int(decision["material_id"]), request,
                        )
                        if (
                            check["status"] != "Changed"
                            or check["observed_etag"] != decision["version_etag"]
                        ):
                            raise HTTPException(
                                409, "Changed source no longer matches its approval",
                            )
                        authorization = authorize_reprocessing(
                            int(check["check_id"]),
                            M365ReprocessingAuthorizationIn(
                                reason=payload.recording_authority_basis,
                            ),
                            request,
                        )
                        supersedes = int(decision["material_id"])
                        authorization_id = int(authorization["authorization_id"])
                    captured = capture(
                        str(decision["item_id"]),
                        M365MaterialIngestCommand(
                            sensitivity=payload.sensitivity,
                            purpose_tags=payload.purpose_tags,
                            description=payload.description,
                            recording_authority_basis=payload.recording_authority_basis,
                            supersedes_material_id=supersedes,
                            reprocessing_authorization_id=authorization_id,
                        ),
                        request,
                    )
                    material_id = int(captured["material_id"])
                    status = "Succeeded"
                    detail = "Governed immutable source captured for human review."
                except HTTPException as exc:
                    detail = str(exc.detail)[:1000]
                except Exception:
                    detail = "Governed source capture failed safely."
                completed = now()
                conn.execute(
                    "INSERT INTO m365_batch_capture_items(tenant_id,execution_id,"
                    "decision_id,item_id,source_status,status,material_id,detail,"
                    "completed_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        tid, execution_id, int(decision["id"]), decision["item_id"],
                        decision["source_status"], status, material_id, detail, completed,
                    ),
                )
                conn.commit()
                results.append({
                    "decision_id": int(decision["id"]),
                    "item_id": decision["item_id"],
                    "source_status": decision["source_status"],
                    "status": status,
                    "material_id": material_id,
                    "detail": detail,
                })

            succeeded = sum(item["status"] == "Succeeded" for item in results)
            final_status = (
                "Completed" if succeeded == len(results)
                else "Failed" if succeeded == 0
                else "Partial"
            )
            completed = now()
            conn.execute(
                "UPDATE m365_batch_capture_executions SET status=?,completed_at=? "
                "WHERE id=?",
                (final_status, completed, execution_id),
            )
            conn.execute(
                "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,"
                "tenant_id) VALUES(?,?,?,?,?,?,?)",
                (
                    completed, actor(request), "M365_APPROVED_BATCH_EXECUTED",
                    "m365_batch_capture_execution", execution_id,
                    f"status={final_status}; requested={len(results)}; "
                    f"succeeded={succeeded}; failed={len(results)-succeeded}",
                    tid,
                ),
            )
            conn.commit()
            return {
                "execution_id": execution_id,
                "status": final_status,
                "requested": len(results),
                "succeeded": succeeded,
                "failed": len(results) - succeeded,
                "items": results,
                "batch_limit": 25,
                "human_review_required": True,
                "automatic_indexing": False,
                "automatic_finding_creation": False,
                "completed_at": completed,
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
