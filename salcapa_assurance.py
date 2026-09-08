"""Server-derived SalCAPA PROVE assurance register and trace-gap model.

PROVE is a cross-cutting assurance view over persisted authoritative records.  It
does not create facts, infer causality, release records, or replace component and
human lifecycle authority.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


STAGE_DEFINITIONS = (
    ("qualified_intelligence", "Qualified intelligence", "SalINTEL™", "See"),
    ("risk_priority", "Risk and priority", "SalTHIRA™", "Decide"),
    ("decision", "Authorized decision", "Authorized people", "Decide"),
    ("authorized_action", "Authorized action", "SalCAPA™ / SalOPS™", "Coordinate / Act"),
    ("execution", "Execution", "SalOPS™", "Act"),
    ("evidence", "Evidence and provenance", "SalCAPA™ assurance", "Prove"),
    ("result_validation", "Result and validation", "SalCAPA™ assurance", "Prove"),
    ("reassessment", "Reassessment and learning", "SalCAPA-wide", "See / Decide"),
)

AssurancePackageType = Literal[
    "Executive Assurance",
    "Capability Validation",
    "Decision-to-Action Traceability",
    "Evidence & Provenance",
    "After-Action & Improvement",
    "Protected Member Results",
]
ASSURANCE_PACKAGE_TYPES = (
    "Executive Assurance",
    "Capability Validation",
    "Decision-to-Action Traceability",
    "Evidence & Provenance",
    "After-Action & Improvement",
    "Protected Member Results",
)
ASSURANCE_REPORT_PREFIX = "PROVE — "


class AssurancePackageCreate(BaseModel):
    """The client selects only a governed package type; all state is server-derived."""

    model_config = ConfigDict(extra="forbid")
    package_type: AssurancePackageType


def register_salcapa_assurance(app, core: dict) -> None:
    db = core["db"]
    require = core["require"]
    tenant_id = core["tenant_id"]
    accessible_assessment_ids = core["accessible_assessment_ids"]
    protected_member = core["protected_member_request"]
    require_sensitivity = core["require_sensitivity"]
    require_salus_authority = core["require_salus_component_authority"]
    assessment_for_request = core["assessment_row_for_request"]
    actor = core["actor"]
    audit = core["audit"]
    now = core["now"]
    sensitivity_levels = core["SENSITIVITY_LEVELS"]

    def rows(conn, sql: str, params=()):
        return [dict(item) for item in conn.execute(sql, params)]

    def selected_assessments(conn, request: Request, assessment_id: int | None):
        allowed = set(accessible_assessment_ids(request))
        if assessment_id is not None:
            candidate = conn.execute(
                "SELECT * FROM assessments WHERE id=?", (assessment_id,)
            ).fetchone()
            if not candidate:
                raise HTTPException(404, "Assessment not found")
            if int(candidate["tenant_id"]) != tenant_id(request) or assessment_id not in allowed:
                raise HTTPException(403, "Assessment access denied")
            require_sensitivity(request, candidate["classification"])
            return [dict(candidate)]
        result = []
        for item in conn.execute(
            "SELECT * FROM assessments WHERE tenant_id=? ORDER BY id", (tenant_id(request),)
        ):
            if int(item["id"]) in allowed:
                try:
                    require_sensitivity(request, item["classification"])
                except HTTPException:
                    continue
                result.append(dict(item))
        return result

    def node(kind: str, item: dict, label_field: str, status_field: str = "status"):
        return {
            "key": f"{kind}:{item['id']}", "record_type": kind,
            "record_id": item["id"], "label": item.get(label_field) or f"{kind} #{item['id']}",
            "status": item.get(status_field, ""),
        }

    def reference_values(value) -> list[str]:
        """Return only explicit scalar identifiers from a persisted JSON reference list."""
        try:
            decoded = json.loads(value or "[]")
        except (TypeError, ValueError):
            return []
        if not isinstance(decoded, list):
            return []
        return [str(item) for item in decoded if isinstance(item, (str, int))]

    def build_assurance(conn, request: Request, assessment: dict):
        aid, tid = int(assessment["id"]), tenant_id(request)
        is_member = protected_member(request)
        intelligence = rows(conn,
            "SELECT id,title,status,credibility,validation_status,qualified_at FROM intel_findings "
            "WHERE tenant_id=? AND assessment_id=? AND status IN ('Qualified','Sent to SalTHIRA') ORDER BY id",
            (tid, aid))
        threats = rows(conn,
            "SELECT id,name,status,inclusion_status FROM threats WHERE assessment_id=? ORDER BY id", (aid,))
        scenarios = rows(conn,
            "SELECT id,threat_id,title,evidence_confidence FROM scenarios WHERE assessment_id=? ORDER BY id", (aid,))
        capabilities = rows(conn,
            "SELECT id,scenario_id,name,confidence,current_performance,required_standard,last_validated "
            "FROM capabilities WHERE assessment_id=? ORDER BY id", (aid,))
        gaps = rows(conn,
            "SELECT id,capability_id,description,severity,status FROM gaps WHERE assessment_id=? ORDER BY id", (aid,))
        improvements = rows(conn,
            "SELECT id,gap_id,title,status,validation_status,validation_evidence_id,validation_outcome,"
            "validated_at FROM improvements WHERE assessment_id=? ORDER BY id", (aid,))
        decisions = rows(conn,
            "SELECT id,improvement_id,decision_type,authority,review_lifecycle_status,created_at "
            "FROM decisions WHERE assessment_id=? ORDER BY id", (aid,))
        requests = rows(conn,
            "SELECT id,source_type,source_id,title,status,result_summary,completed_at FROM ops_requests "
            "WHERE tenant_id=? AND assessment_id=? ORDER BY id", (tid, aid))
        engagements = rows(conn,
            "SELECT id,ops_request_id,title,status FROM ops_engagements WHERE tenant_id=? AND assessment_id=? ORDER BY id",
            (tid, aid))
        tasks = rows(conn,
            "SELECT id,engagement_id,title,status,result_summary,completed_at FROM ops_tasks "
            "WHERE tenant_id=? AND assessment_id=? ORDER BY id", (tid, aid))
        evidence = []
        for item in conn.execute(
            "SELECT id,capability_id,scenario_id,title,verification_status,lifecycle_status,sensitivity,"
            "evidence_date,updated_at FROM evidence WHERE assessment_id=? ORDER BY id", (aid,)
        ):
            try:
                require_sensitivity(request, item["sensitivity"])
            except HTTPException:
                continue
            value = dict(item)
            if not is_member or (
                value["verification_status"] == "Verified" and value["lifecycle_status"] == "Current"
            ):
                evidence.append(value)
        triggers = rows(conn,
            "SELECT id,affected_record_type,affected_record_id,trigger_type,severity,status,created_at "
            "FROM reassessment_triggers WHERE assessment_id=? ORDER BY id", (aid,))
        reports = []
        for report in conn.execute(
            "SELECT id,report_type,status,released_at,snapshot_json FROM report_versions "
            "WHERE tenant_id=? AND assessment_id=? AND status='Released' ORDER BY id", (tid, aid)
        ):
            value = dict(report)
            if str(value["report_type"]).startswith(ASSURANCE_REPORT_PREFIX):
                try:
                    package_payload = json.loads(value["snapshot_json"])
                    require_sensitivity(
                        request, package_payload.get("classification", "Highly Sensitive")
                    )
                except (ValueError, TypeError, HTTPException):
                    continue
            value.pop("snapshot_json", None)
            reports.append(value)
        field_reports = rows(conn,
            "SELECT id,engagement_id,task_id,report_type,status,released_at FROM ops_field_reports "
            "WHERE tenant_id=? AND assessment_id=? AND status='Released' ORDER BY id", (tid, aid))

        # Preparedness records retain their own lifecycle and disclosure authority. PROVE reads
        # qualifying records and explicit persisted links; it does not transition or release them.
        plans = []
        for item in conn.execute(
            "SELECT id,title,status,member_adoption_status,sensitivity,training_requirements,"
            "exercise_validation_requirements,evidence_refs_json FROM salops_preparedness_plans "
            "WHERE tenant_id=? AND assessment_id=? ORDER BY created_at,id", (tid, aid)
        ):
            value = dict(item)
            try:
                require_sensitivity(request, value["sensitivity"])
            except HTTPException:
                continue
            if not is_member or value["status"] == "Approved":
                plans.append(value)
        plan_ids = {str(item["id"]) for item in plans}

        training = []
        for item in conn.execute(
            "SELECT id,plan_id,title,status,member_release_status,evidence_refs_json "
            "FROM salops_preparedness_training WHERE tenant_id=? AND assessment_id=? "
            "ORDER BY created_at,id", (tid, aid)
        ):
            value = dict(item)
            if value["plan_id"] and str(value["plan_id"]) not in plan_ids:
                continue
            if not is_member or value["member_release_status"] == "Released":
                training.append(value)

        exercises = []
        for item in conn.execute(
            "SELECT id,plan_id,title,status,sensitivity FROM salops_preparedness_exercises "
            "WHERE tenant_id=? AND assessment_id=? ORDER BY created_at,id", (tid, aid)
        ):
            value = dict(item)
            if value["plan_id"] and str(value["plan_id"]) not in plan_ids:
                continue
            try:
                require_sensitivity(request, value["sensitivity"])
            except HTTPException:
                continue
            if not is_member or value["status"] in (
                "Approved", "In Progress", "Completed", "Evaluated", "Closed"
            ):
                exercises.append(value)
        exercise_ids = {str(item["id"]) for item in exercises}

        observations = []
        for item in conn.execute(
            "SELECT observation.id,observation.exercise_id,observation.title,"
            "observation.status,observation.epistemic_state,observation.member_release_status "
            "FROM salops_preparedness_observations observation "
            "JOIN salops_preparedness_exercises exercise ON exercise.id=observation.exercise_id "
            "WHERE observation.tenant_id=? AND exercise.assessment_id=? "
            "ORDER BY observation.created_at,observation.id", (tid, aid)
        ):
            value = dict(item)
            if str(value["exercise_id"]) not in exercise_ids:
                continue
            if not is_member or value["member_release_status"] == "Released":
                observations.append(value)

        correctives = []
        for item in conn.execute(
            "SELECT DISTINCT action.id,action.observation_id,action.exercise_id,action.plan_id,"
            "action.title,action.status,action.member_release_status,action.completion_evidence_json,"
            "action.validation_result,action.reexercise_required "
            "FROM salops_preparedness_corrective_actions action "
            "LEFT JOIN salops_preparedness_plans plan ON plan.id=action.plan_id "
            "LEFT JOIN salops_preparedness_exercises exercise ON exercise.id=action.exercise_id "
            "WHERE action.tenant_id=? AND (action.assessment_id=? OR plan.assessment_id=? "
            "OR exercise.assessment_id=?) ORDER BY action.created_at,action.id", (tid, aid, aid, aid)
        ):
            value = dict(item)
            if value["plan_id"] and str(value["plan_id"]) not in plan_ids:
                continue
            if value["exercise_id"] and str(value["exercise_id"]) not in exercise_ids:
                continue
            if not is_member or value["member_release_status"] == "Released":
                correctives.append(value)

        aars = []
        for item in conn.execute(
            "SELECT aar.id,aar.exercise_id,aar.title,aar.status,aar.corrective_action_ids_json "
            "FROM salops_preparedness_aars aar "
            "JOIN salops_preparedness_exercises exercise ON exercise.id=aar.exercise_id "
            "WHERE aar.tenant_id=? AND exercise.assessment_id=? ORDER BY aar.created_at,aar.id",
            (tid, aid),
        ):
            value = dict(item)
            if str(value["exercise_id"]) not in exercise_ids:
                continue
            if not is_member or value["status"] == "Released":
                aars.append(value)

        nodes = []
        nodes.extend(node("intel_finding", item, "title") for item in intelligence)
        nodes.extend(node("threat", item, "name") for item in threats)
        nodes.extend(node("scenario", item, "title", "evidence_confidence") for item in scenarios)
        nodes.extend(node("capability", item, "name", "confidence") for item in capabilities)
        nodes.extend(node("gap", item, "description") for item in gaps)
        nodes.extend(node("improvement", item, "title") for item in improvements)
        nodes.extend(node("decision", item, "decision_type", "review_lifecycle_status") for item in decisions)
        nodes.extend(node("ops_request", item, "title") for item in requests)
        nodes.extend(node("ops_engagement", item, "title") for item in engagements)
        nodes.extend(node("ops_task", item, "title") for item in tasks)
        nodes.extend(node("evidence", item, "title", "verification_status") for item in evidence)
        nodes.extend(node("reassessment_trigger", item, "trigger_type") for item in triggers)
        nodes.extend(node("preparedness_plan", item, "title") for item in plans)
        nodes.extend(node("preparedness_training", item, "title") for item in training)
        nodes.extend(node("preparedness_exercise", item, "title") for item in exercises)
        nodes.extend(node("preparedness_observation", item, "title", "epistemic_state") for item in observations)
        nodes.extend(node("preparedness_corrective_action", item, "title") for item in correctives)
        nodes.extend(node("preparedness_aar", item, "title") for item in aars)

        keys = {item["key"] for item in nodes}
        edges = []
        def edge(source: str, target: str, relationship: str):
            if source in keys and target in keys:
                edges.append({"source": source, "target": target,
                              "relationship": relationship, "basis": "Persisted explicit link"})
        for item in scenarios:
            edge(f"threat:{item['threat_id']}", f"scenario:{item['id']}", "has scenario")
        for item in capabilities:
            if item["scenario_id"]:
                edge(f"scenario:{item['scenario_id']}", f"capability:{item['id']}", "requires capability")
        for item in gaps:
            edge(f"capability:{item['capability_id']}", f"gap:{item['id']}", "has capability gap")
        for item in improvements:
            edge(f"gap:{item['gap_id']}", f"improvement:{item['id']}", "addressed by")
            if item["validation_evidence_id"]:
                edge(f"evidence:{item['validation_evidence_id']}", f"improvement:{item['id']}", "validates")
        for item in decisions:
            if item["improvement_id"]:
                edge(f"improvement:{item['improvement_id']}", f"decision:{item['id']}", "governed by decision")
        for item in requests:
            if item["source_type"] and item["source_id"]:
                edge(f"{item['source_type']}:{item['source_id']}", f"ops_request:{item['id']}", "authorizes request")
        for item in engagements:
            edge(f"ops_request:{item['ops_request_id']}", f"ops_engagement:{item['id']}", "implemented through")
        for item in tasks:
            edge(f"ops_engagement:{item['engagement_id']}", f"ops_task:{item['id']}", "contains task")
        for item in evidence:
            if item["capability_id"]:
                edge(f"evidence:{item['id']}", f"capability:{item['capability_id']}", "supports capability")
            if item["scenario_id"]:
                edge(f"evidence:{item['id']}", f"scenario:{item['scenario_id']}", "supports scenario")
        for item in triggers:
            if item["affected_record_type"] and item["affected_record_id"]:
                edge(f"{item['affected_record_type']}:{item['affected_record_id']}",
                     f"reassessment_trigger:{item['id']}", "triggers reassessment")
        for item in plans:
            for evidence_id in reference_values(item["evidence_refs_json"]):
                edge(f"evidence:{evidence_id}", f"preparedness_plan:{item['id']}", "supports plan")
        for item in training:
            if item["plan_id"]:
                edge(f"preparedness_plan:{item['plan_id']}",
                     f"preparedness_training:{item['id']}", "requires training")
            for evidence_id in reference_values(item["evidence_refs_json"]):
                edge(f"evidence:{evidence_id}", f"preparedness_training:{item['id']}",
                     "supports completion")
        for item in exercises:
            if item["plan_id"]:
                edge(f"preparedness_plan:{item['plan_id']}",
                     f"preparedness_exercise:{item['id']}", "validated through")
        for item in observations:
            edge(f"preparedness_exercise:{item['exercise_id']}",
                 f"preparedness_observation:{item['id']}", "produces observation")
        for item in correctives:
            if item["observation_id"]:
                edge(f"preparedness_observation:{item['observation_id']}",
                     f"preparedness_corrective_action:{item['id']}", "drives corrective action")
            if item["exercise_id"]:
                edge(f"preparedness_exercise:{item['exercise_id']}",
                     f"preparedness_corrective_action:{item['id']}", "drives corrective action")
            if item["plan_id"]:
                edge(f"preparedness_plan:{item['plan_id']}",
                     f"preparedness_corrective_action:{item['id']}", "improved through")
        for item in aars:
            edge(f"preparedness_exercise:{item['exercise_id']}",
                 f"preparedness_aar:{item['id']}", "evaluated in")
            for action_id in reference_values(item["corrective_action_ids_json"]):
                edge(f"preparedness_corrective_action:{action_id}",
                     f"preparedness_aar:{item['id']}", "included in improvement plan")

        authorized_requests = [item for item in requests
                               if item["status"] in ("Authorized", "In Progress", "Completed")]
        completed_work = [item for item in requests + tasks if item["status"] == "Completed"]
        verified_evidence = [item for item in evidence if item["verification_status"] == "Verified"
                             and item["lifecycle_status"] == "Current"]
        validated = [item for item in improvements
                     if item["validation_status"] in ("Validated", "Partially Validated")]
        approved_plans = [item for item in plans if item["status"] == "Approved"]
        authorized_plans = [item for item in approved_plans
                            if item["member_adoption_status"] == "Adopted"]
        completed_training = [item for item in training if item["status"] == "Completed"]
        completed_exercises = [item for item in exercises
                               if item["status"] in ("Completed", "Evaluated", "Closed")]
        validated_exercises = [item for item in exercises
                               if item["status"] in ("Evaluated", "Closed")]
        implemented_correctives = [item for item in correctives if item["status"] in (
            "Implemented", "Awaiting Validation", "Validated", "Closed"
        )]
        validated_correctives = [item for item in correctives
                                 if item["status"] in ("Validated", "Closed")]
        released_aars = [item for item in aars if item["status"] == "Released"]
        preparedness_evidence = (
            len([item for item in completed_training if reference_values(item["evidence_refs_json"])])
            + len(observations)
            + len([item for item in implemented_correctives
                   if reference_values(item["completion_evidence_json"])])
            + len(released_aars)
        )
        stage_counts = {
            "qualified_intelligence": len(intelligence),
            "risk_priority": len([item for item in threats if item["status"] == "Active"])
                             + len(improvements),
            "decision": len(decisions),
            "authorized_action": len(authorized_requests) + len(authorized_plans),
            "execution": len(completed_work) + len(completed_training) + len(completed_exercises),
            "evidence": len(verified_evidence) + len(reports) + len(field_reports)
                        + preparedness_evidence,
            "result_validation": len(validated) + len([item for item in completed_work
                                                       if item.get("result_summary")])
                                 + len(validated_exercises) + len(validated_correctives),
            "reassessment": len(triggers),
        }
        stages = [{"key": key, "label": label, "owner": owner, "function": function,
                   "record_count": stage_counts[key],
                   "state": "Evidence present" if stage_counts[key] else "Assurance gap"}
                  for key, label, owner, function in STAGE_DEFINITIONS]
        assurance_gaps = [{"gap_key": f"stage:{item['key']}", "stage": item["label"],
                           "reason": "No qualifying persisted record is available.",
                           "inferred": False}
                          for item in stages if not item["record_count"]]
        request_by_improvement = {int(item["source_id"]) for item in authorized_requests
                                  if item["source_type"] == "improvement" and item["source_id"]}
        for item in decisions:
            if item["decision_type"] in ("Approve", "Approve with Conditions") and item["improvement_id"] \
                    and int(item["improvement_id"]) not in request_by_improvement:
                assurance_gaps.append({"gap_key": f"decision:{item['id']}:action",
                    "stage": "Decision to authorized action",
                    "reason": "Approved decision has no explicitly linked authorized SalOPS request.",
                    "record_key": f"decision:{item['id']}", "inferred": False})
        for item in improvements:
            if item["status"] == "Complete" and item["validation_status"] not in (
                "Validated", "Partially Validated"
            ):
                assurance_gaps.append({"gap_key": f"improvement:{item['id']}:validation",
                    "stage": "Completion to validation",
                    "reason": "Completed improvement lacks governed validation.",
                    "record_key": f"improvement:{item['id']}", "inferred": False})
        training_by_plan = {str(item["plan_id"]) for item in training
                            if item["plan_id"] and item["status"] != "Cancelled"}
        exercises_by_plan = {str(item["plan_id"]) for item in exercises
                             if item["plan_id"] and item["status"] != "Cancelled"}
        for item in approved_plans:
            if str(item.get("training_requirements") or "").strip() and str(item["id"]) not in training_by_plan:
                assurance_gaps.append({"gap_key": f"preparedness_plan:{item['id']}:training",
                    "stage": "Authorized plan to training",
                    "reason": "Approved plan has training requirements but no qualifying governed training record is available.",
                    "record_key": f"preparedness_plan:{item['id']}", "inferred": False})
            if str(item.get("exercise_validation_requirements") or "").strip() and str(item["id"]) not in exercises_by_plan:
                assurance_gaps.append({"gap_key": f"preparedness_plan:{item['id']}:exercise",
                    "stage": "Authorized plan to exercise",
                    "reason": "Approved plan has validation requirements but no qualifying governed exercise record is available.",
                    "record_key": f"preparedness_plan:{item['id']}", "inferred": False})
        aars_by_exercise = {str(item["exercise_id"]) for item in aars}
        for item in completed_exercises:
            if str(item["id"]) not in aars_by_exercise:
                assurance_gaps.append({"gap_key": f"preparedness_exercise:{item['id']}:aar",
                    "stage": "Exercise to after-action improvement",
                    "reason": "Completed exercise has no qualifying governed AAR/IP record available.",
                    "record_key": f"preparedness_exercise:{item['id']}", "inferred": False})
        for item in completed_training:
            if not reference_values(item["evidence_refs_json"]):
                assurance_gaps.append({"gap_key": f"preparedness_training:{item['id']}:evidence",
                    "stage": "Training completion to evidence",
                    "reason": "Completed training has no explicit persisted evidence reference.",
                    "record_key": f"preparedness_training:{item['id']}", "inferred": False})
        for item in implemented_correctives:
            if not reference_values(item["completion_evidence_json"]):
                assurance_gaps.append({"gap_key": f"preparedness_corrective_action:{item['id']}:evidence",
                    "stage": "Corrective implementation to evidence",
                    "reason": "Implemented corrective action has no explicit completion evidence reference.",
                    "record_key": f"preparedness_corrective_action:{item['id']}", "inferred": False})
        for item in validated_correctives:
            if not str(item.get("validation_result") or "").strip():
                assurance_gaps.append({"gap_key": f"preparedness_corrective_action:{item['id']}:validation",
                    "stage": "Corrective action to validation",
                    "reason": "Validated corrective action has no persisted validation result.",
                    "record_key": f"preparedness_corrective_action:{item['id']}", "inferred": False})
        if intelligence and not any(edge_item["source"].startswith("intel_finding:")
                                    for edge_item in edges):
            assurance_gaps.append({"gap_key": "intelligence:explicit-risk-link",
                "stage": "Qualified intelligence to risk/priority",
                "reason": "Qualified intelligence exists, but no explicit persisted downstream link is available.",
                "inferred": False})

        return {
            "assessment": {"id": aid, "name": assessment["name"],
                           "organization": assessment["organization"],
                           "status": assessment["status"], "version": assessment["version"]},
            "stages": stages, "nodes": nodes, "explicit_edges": edges,
            "assurance_gaps": assurance_gaps,
            "released_outputs": {"reports": reports, "field_reports": field_reports},
            "preparedness_trace": {
                "plans": len(plans), "training": len(training), "exercises": len(exercises),
                "observations": len(observations), "corrective_actions": len(correctives),
                "after_action_reports": len(aars),
            },
            "trace_policy": {"server_derived": True, "explicit_links_only": True,
                             "missing_links_are_gaps": True, "automatic_completion": False,
                             "automatic_disclosure": False, "automatic_authority": False,
                             "preparedness_lifecycles_remain_authoritative": True,
                             "training_completion_is_readiness_proof": False},
        }

    def package_classification(conn, assessment: dict, assurance: dict) -> str:
        """Classify the immutable snapshot at the highest included evidence level."""
        candidates = [assessment.get("classification") or "Standard"]
        evidence_ids = [item["record_id"] for item in assurance["nodes"]
                        if item["record_type"] == "evidence"]
        if evidence_ids:
            marks = ",".join("?" for _ in evidence_ids)
            candidates.extend(item["sensitivity"] or "Standard" for item in conn.execute(
                f"SELECT sensitivity FROM evidence WHERE id IN ({marks})", tuple(evidence_ids)
            ))
        for record_type, table in (
            ("preparedness_plan", "salops_preparedness_plans"),
            ("preparedness_exercise", "salops_preparedness_exercises"),
        ):
            record_ids = [item["record_id"] for item in assurance["nodes"]
                          if item["record_type"] == record_type]
            if record_ids:
                marks = ",".join("?" for _ in record_ids)
                candidates.extend(item["sensitivity"] or "Standard" for item in conn.execute(
                    f"SELECT sensitivity FROM {table} WHERE id IN ({marks})", tuple(record_ids)
                ))
        return max(candidates, key=lambda value: sensitivity_levels.get(value, 1))

    def package_rows(conn, request: Request, aid: int):
        result = []
        for item in conn.execute(
            "SELECT id,assessment_id,assessment_version,report_type,status,snapshot_json,"
            "snapshot_sha256,created_by,created_at,reviewed_by,reviewed_at,approved_by,"
            "approved_at,released_by,released_at,transition_reason FROM report_versions "
            "WHERE tenant_id=? AND assessment_id=? AND report_type LIKE ? ORDER BY id DESC",
            (tenant_id(request), aid, f"{ASSURANCE_REPORT_PREFIX}%"),
        ):
            value = dict(item)
            try:
                payload = json.loads(value.pop("snapshot_json"))
                require_sensitivity(request, payload.get("classification", "Highly Sensitive"))
            except (ValueError, TypeError, HTTPException):
                continue
            if protected_member(request) and value["status"] != "Released":
                continue
            value["package_type"] = value["report_type"][len(ASSURANCE_REPORT_PREFIX):]
            value["package_version"] = int(payload.get("package_version", 1))
            value["classification"] = payload.get("classification", "Highly Sensitive")
            if protected_member(request):
                value = {key: value[key] for key in (
                    "id", "assessment_id", "assessment_version", "package_type",
                    "package_version", "status", "snapshot_sha256", "classification",
                    "released_at",
                )}
            result.append(value)
        return result

    @app.middleware("http")
    async def protect_assurance_package_snapshots(request: Request, call_next):
        """Close the generic report route around PROVE classification and release policy."""
        path = request.url.path
        prefix, suffix = "/api/reports/versions/", "/snapshot"
        if request.method == "GET" and path.startswith(prefix) and path.endswith(suffix):
            raw_id = path[len(prefix):-len(suffix)]
            if raw_id.isdigit():
                conn = db()
                try:
                    item = conn.execute(
                        "SELECT tenant_id,report_type,status,snapshot_json FROM report_versions WHERE id=?",
                        (int(raw_id),),
                    ).fetchone()
                    if item and str(item["report_type"]).startswith(ASSURANCE_REPORT_PREFIX):
                        try:
                            if int(item["tenant_id"]) != tenant_id(request):
                                raise HTTPException(403, "Assurance package access denied")
                            payload = json.loads(item["snapshot_json"])
                            require_sensitivity(
                                request, payload.get("classification", "Highly Sensitive")
                            )
                            if protected_member(request) and item["status"] != "Released":
                                raise HTTPException(
                                    403, "Only released assurance packages are member-visible"
                                )
                        except HTTPException as exc:
                            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
                finally:
                    conn.close()
        return await call_next(request)

    @app.get("/api/salcapa/assurance")
    def salcapa_assurance(request: Request, assessment_id: int | None = None):
        require(request, "read")
        conn = db()
        try:
            assessments = selected_assessments(conn, request, assessment_id)
            result = []
            for item in assessments:
                assurance = build_assurance(conn, request, item)
                assurance["assurance_packages"] = package_rows(
                    conn, request, int(item["id"])
                )
                result.append(assurance)
            return {
                "workspace": "PROVE — Assurance & Results",
                "purpose": "Evidence, accountability, results, validation, learning, and improvement across SalCAPA.",
                "cross_cutting": True, "not_a_separate_product": True,
                "package_types": list(ASSURANCE_PACKAGE_TYPES),
                "assessments": result,
                "links": [
                    {"label": "Evidence & provenance", "view": "evidence"},
                    {"label": "Decision record", "view": "decisions"},
                    {"label": "Action verification", "view": "implementation"},
                    {"label": "Capability validation", "view": "capabilities"},
                    {"label": "Reassessment history", "view": "reassessment"},
                    {"label": "Reports", "view": "reports"},
                    {"label": "Audit & version history", "view": "audit"},
                ],
            }
        finally:
            conn.close()

    @app.post("/api/salcapa/assurance/assessments/{assessment_id}/packages")
    def create_assurance_package(
        assessment_id: int, payload: AssurancePackageCreate, request: Request
    ):
        require(request, "write")
        require_salus_authority(request, "SalCAPA PROVE assurance")
        assessment = assessment_for_request(request, assessment_id)
        require_sensitivity(request, assessment["classification"])
        conn = db()
        try:
            assurance = build_assurance(conn, request, assessment)
            report_type = f"{ASSURANCE_REPORT_PREFIX}{payload.package_type}"
            prior = conn.execute(
                "SELECT COUNT(*) c FROM report_versions WHERE tenant_id=? AND assessment_id=? "
                "AND report_type=?",
                (tenant_id(request), assessment_id, report_type),
            ).fetchone()
            version = int(prior["c"]) + 1
            stamp = now()
            snapshot_payload = {
                "schema": "salcapa.prove.assurance-package.v1",
                "package_type": payload.package_type,
                "package_version": version,
                "classification": package_classification(conn, assessment, assurance),
                "created_at": stamp,
                "assessment": assurance["assessment"],
                "stages": assurance["stages"],
                "records": assurance["nodes"],
                "explicit_traceability": assurance["explicit_edges"],
                "assurance_gaps": assurance["assurance_gaps"],
                "released_source_outputs": assurance["released_outputs"],
                "preparedness_trace": assurance["preparedness_trace"],
                "trace_policy": assurance["trace_policy"],
                "release_policy": {
                    "draft_is_member_visible": False,
                    "salus_release_required": True,
                    "sensitivity_clearance_required": True,
                    "automatic_disclosure": False,
                    "automatic_completion": False,
                },
            }
            snapshot = json.dumps(
                snapshot_payload, sort_keys=True, separators=(",", ":"), default=str
            )
            digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
            who = actor(request)
            cursor = conn.execute(
                "INSERT INTO report_versions(tenant_id,assessment_id,assessment_version,"
                "report_type,status,snapshot_json,snapshot_sha256,created_by,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (tenant_id(request), assessment_id, assessment["version"], report_type,
                 "Draft", snapshot, digest, who, stamp),
            )
            package_id = cursor.lastrowid
            audit(
                conn, "CREATE", "report_version", package_id,
                f"Immutable {report_type} v{version} snapshot sha256={digest}; "
                f"classification={snapshot_payload['classification']}; release=false",
                who,
            )
            conn.commit()
            return {
                "id": package_id,
                "assessment_id": assessment_id,
                "assessment_version": assessment["version"],
                "package_type": payload.package_type,
                "package_version": version,
                "status": "Draft",
                "classification": snapshot_payload["classification"],
                "snapshot_sha256": digest,
                "created_by": who,
                "created_at": stamp,
                "server_derived": True,
                "member_visible": False,
            }
        finally:
            conn.close()
