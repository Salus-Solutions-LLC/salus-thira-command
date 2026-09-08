"""Development runtime composition for SalCAPA.

The governed v3.43 source archive remains byte-for-byte verifiable. Development
capabilities that have not yet been frozen into the next release are composed here
without modifying a frozen source snapshot. Once the candidate is all-green, the
combined source can be snapshotted and this composition point advanced normally.
"""
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

import app as core
from salops_preparedness import register_salops_preparedness
from personnel_assessment import register_personnel_assessment
from salintel_relationships import register_salintel_relationships
from salintel_research import register_salintel_research
from salintel_handoffs import register_salintel_handoffs
from facility_assessment import register_facility_assessment
try:
    from salops_plan_assembly import register_salops_plan_assembly
except ModuleNotFoundError:  # Other capability workflows may not reconstruct this archive.
    register_salops_plan_assembly = None
try:
    from salcapa_assurance import register_salcapa_assurance
except ModuleNotFoundError:  # Other capability workflows may not reconstruct this archive.
    register_salcapa_assurance = None
try:
    from salintel_monitoring import register_salintel_monitoring
except ModuleNotFoundError:  # Other capability workflows may not reconstruct this archive.
    register_salintel_monitoring = None

register_salops_preparedness(core.app, core.__dict__)
register_salintel_relationships(core.app, core.__dict__)
register_salintel_research(core.app, core.__dict__)
register_personnel_assessment(core.app, core.__dict__)
register_salintel_handoffs(core.app, core.__dict__)
register_facility_assessment(core.app, core.__dict__)
if register_salintel_monitoring is not None:
    register_salintel_monitoring(core.app, core.__dict__)
if register_salcapa_assurance is not None:
    register_salcapa_assurance(core.app, core.__dict__)
if register_salops_plan_assembly is not None:
    register_salops_plan_assembly(core.app, core.__dict__)

SALCAPA_RELEASE_VERSION = "3.75"


_base_protective_readiness_summary = core._protective_readiness_summary


def _salcapa_operating_model_summary(conn, assessment_ids: list[int], tenant: int):
    """Present the approved functional architecture without assigning human authority to software."""
    result = _base_protective_readiness_summary(conn, assessment_ids, tenant)
    trace = result["trace"]
    coordination_count = int(conn.execute(
        "SELECT COUNT(*) c FROM cop_coordination_threads WHERE tenant_id=?", (tenant,)
    ).fetchone()["c"])
    result["promise"] = (
        "See with qualified intelligence. Decide with an assessed risk picture. "
        "Coordinate people, information, decisions, and action. Act through protective capability."
    )
    result["stages"] = [
        {"key": "see", "label": "See — SalINTEL™",
         "count": trace["qualified_signals"],
         "description": "SalINTEL develops qualified intelligence."},
        {"key": "decide", "label": "Decide — SalTHIRA™ and authorized people",
         "count": trace["prioritized_improvements"] + trace["executive_decisions"],
         "description": "SalTHIRA identifies risk and establishes priorities; authorized people decide."},
        {"key": "coordinate", "label": "Coordinate — SalCAPA™",
         "count": coordination_count,
         "description": "SalCAPA coordinates Protected Members, information, decisions, and action."},
        {"key": "act", "label": "Act — SalOPS™",
         "count": trace["authorized_actions"],
         "description": "SalOPS implements, sustains, and improves protective capability."},
        {"key": "prove", "label": "Prove — cross-cutting assurance",
         "count": trace["completed_actions"] + trace["verified_actions"]
                  + trace["released_proof_records"],
         "description": "Evidence, accountability, results, learning, and improvement span every function."},
    ]
    for stage in result["stages"]:
        stage["state"] = "Active" if stage["count"] else "No records"
    result["functional_ownership"] = {
        "see": "SalINTEL™", "decide": "SalTHIRA™ plus authorized decision-makers",
        "coordinate": "SalCAPA™", "act": "SalOPS™", "prove": "Cross-cutting assurance",
    }
    return result


core._protective_readiness_summary = _salcapa_operating_model_summary


def _preparedness_index() -> str:
    path = Path(core.BASE_DIR) / "static" / "index.html"
    text = path.read_text(encoding="utf-8")
    edits = (
        ('<link rel="stylesheet" href="/static/salintel-domains.css" />',
         '<link rel="stylesheet" href="/static/salintel-domains.css" />\n<link rel="stylesheet" href="/static/salops-preparedness.css" />',
         '/static/salops-preparedness.css'),
        ('<button data-view="salops">Operations & Requests</button>',
         '<button data-view="salops">Operations & Requests</button><button data-view="salops_preparedness">Preparedness, Planning & Exercises</button>',
         'data-view="salops_preparedness"'),
        ('<button data-view="salops_preparedness">Preparedness, Planning & Exercises</button>',
         '<button data-view="salops_preparedness">Preparedness, Planning & Exercises</button><button data-view="salops_plan_assembly" data-salus-only="true">Emergency Plan Assembly</button>',
         'data-view="salops_plan_assembly"'),
        ('<script src="/static/salintel-domains.js"></script>',
         '<script src="/static/salintel-domains.js"></script>\n<script src="/static/salops-preparedness.js"></script>',
         '/static/salops-preparedness.js'),
        ('<link rel="stylesheet" href="/static/salops-preparedness.css" />',
         '<link rel="stylesheet" href="/static/salops-preparedness.css" />\n<link rel="stylesheet" href="/static/personnel-assessment.css" />',
         '/static/personnel-assessment.css'),
        ('<link rel="stylesheet" href="/static/personnel-assessment.css" />',
         '<link rel="stylesheet" href="/static/personnel-assessment.css" />\n<link rel="stylesheet" href="/static/salintel-relationships.css" />',
         '/static/salintel-relationships.css'),
        ('<link rel="stylesheet" href="/static/salintel-relationships.css" />',
         '<link rel="stylesheet" href="/static/salintel-relationships.css" />\n<link rel="stylesheet" href="/static/salintel-research.css" />',
         '/static/salintel-research.css'),
        ('<link rel="stylesheet" href="/static/salintel-research.css" />',
         '<link rel="stylesheet" href="/static/salintel-research.css" />\n<link rel="stylesheet" href="/static/salintel-handoffs.css" />',
         '/static/salintel-handoffs.css'),
        ('<link rel="stylesheet" href="/static/salintel-handoffs.css" />',
         '<link rel="stylesheet" href="/static/salintel-handoffs.css" />\n<link rel="stylesheet" href="/static/facility-assessment.css" />',
         '/static/facility-assessment.css'),
        ('<link rel="stylesheet" href="/static/facility-assessment.css" />',
         '<link rel="stylesheet" href="/static/facility-assessment.css" />\n<link rel="stylesheet" href="/static/salintel-monitoring.css" />',
         '/static/salintel-monitoring.css'),
        ('<link rel="stylesheet" href="/static/salintel-monitoring.css" />',
         '<link rel="stylesheet" href="/static/salintel-monitoring.css" />\n<link rel="stylesheet" href="/static/salcapa-assurance.css" />',
         '/static/salcapa-assurance.css'),
        ('<link rel="stylesheet" href="/static/salcapa-assurance.css" />',
         '<link rel="stylesheet" href="/static/salcapa-assurance.css" />\n<link rel="stylesheet" href="/static/salcapa-contextual-guidance.css" />',
         '/static/salcapa-contextual-guidance.css'),
        ('<link rel="stylesheet" href="/static/salcapa-contextual-guidance.css" />',
         '<link rel="stylesheet" href="/static/salcapa-contextual-guidance.css" />\n<link rel="stylesheet" href="/static/salops-plan-assembly.css" />',
         '/static/salops-plan-assembly.css'),
        ('<button class="active" data-view="dashboard">Command Center</button><button data-view="common_operating_picture">Common Operating Picture</button><button data-view="reports">Reports</button>',
         '<button class="active" data-view="dashboard">Command Center</button><button data-view="common_operating_picture">Common Operating Picture</button><button data-view="prove">PROVE — Assurance & Results</button><button data-view="reports">Reports</button>',
         'data-view="prove"'),
        ('<button data-view="salintel_domains" data-salus-only="true">Investigative Domains</button>',
         '<button data-view="salintel_domains" data-salus-only="true">Investigative Domains</button><button data-view="personnel_assessments" data-salus-only="true">Personnel Assessment</button>',
         'data-view="personnel_assessments"'),
        ('<button data-view="personnel_assessments" data-salus-only="true">Personnel Assessment</button>',
         '<button data-view="personnel_assessments" data-salus-only="true">Personnel Assessment</button><button data-view="facility_assessments" data-salus-only="true">Facility Assessment</button>',
         'data-view="facility_assessments"'),
        ('<script src="/static/salops-preparedness.js"></script>',
         '<script src="/static/salops-preparedness.js"></script>\n<script src="/static/personnel-assessment.js"></script>',
         '/static/personnel-assessment.js'),
        ('<script src="/static/personnel-assessment.js"></script>',
         '<script src="/static/personnel-assessment.js"></script>\n<script src="/static/salintel-relationships.js"></script>',
         '/static/salintel-relationships.js'),
        ('<script src="/static/salintel-relationships.js"></script>',
         '<script src="/static/salintel-relationships.js"></script>\n<script src="/static/salintel-research.js"></script>',
         '/static/salintel-research.js'),
        ('<script src="/static/salintel-research.js"></script>',
         '<script src="/static/salintel-research.js"></script>\n<script src="/static/salintel-handoffs.js"></script>',
         '/static/salintel-handoffs.js'),
        ('<script src="/static/salintel-handoffs.js"></script>',
         '<script src="/static/salintel-handoffs.js"></script>\n<script src="/static/facility-assessment.js"></script>',
         '/static/facility-assessment.js'),
        ('<script src="/static/facility-assessment.js"></script>',
         '<script src="/static/facility-assessment.js"></script>\n<script src="/static/salintel-monitoring.js"></script>',
         '/static/salintel-monitoring.js'),
        ('<script src="/static/salintel-monitoring.js"></script>',
         '<script src="/static/salintel-monitoring.js"></script>\n<script src="/static/salcapa-display.js"></script>',
         '/static/salcapa-display.js'),
        ('<script src="/static/salcapa-display.js"></script>',
         '<script src="/static/salcapa-display.js"></script>\n<script src="/static/salcapa-assurance.js"></script>',
         '/static/salcapa-assurance.js'),
        ('<script src="/static/salcapa-assurance.js"></script>',
         '<script src="/static/salcapa-assurance.js"></script>\n<script src="/static/salops-plan-assembly.js"></script>',
         '/static/salops-plan-assembly.js'),
        ('<script src="/static/guidance.js"></script>',
         '<script src="/static/guidance.js"></script>\n<script src="/static/salcapa-contextual-guidance.js"></script>',
         '/static/salcapa-contextual-guidance.js'),
    )
    for marker, replacement, present in edits:
        if present in text:
            continue
        if text.count(marker) != 1:
            raise RuntimeError(f"Preparedness navigation marker is unavailable: {marker}")
        text = text.replace(marker, replacement, 1)
    return text


try:
    PREPAREDNESS_INDEX = _preparedness_index()
except (OSError, RuntimeError) as exc:
    raise RuntimeError("SalOPS preparedness interface composition failed") from exc

# Replace only the user-facing root document. The verified static source remains
# unchanged on disk and all API/static routes retain the core application's guards.
core.app.router.routes[:] = [
    route for route in core.app.router.routes
    if not (
        getattr(route, "path", None) in ("/", "/api/system/mode")
        and "GET" in (getattr(route, "methods", None) or set())
    )
]


@core.app.get("/", response_class=HTMLResponse, include_in_schema=False)
def preparedness_root():
    if not PREPAREDNESS_INDEX:
        raise HTTPException(503, "SalCAPA interface unavailable")
    return HTMLResponse(PREPAREDNESS_INDEX)


@core.app.get("/api/system/mode", include_in_schema=False)
def salcapa_system_mode():
    result = dict(core.system_mode())
    result["version"] = SALCAPA_RELEASE_VERSION
    return result


app = core.app
