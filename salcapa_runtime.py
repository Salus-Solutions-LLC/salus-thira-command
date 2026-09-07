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

register_salops_preparedness(core.app, core.__dict__)
register_salintel_relationships(core.app, core.__dict__)
register_salintel_research(core.app, core.__dict__)
register_personnel_assessment(core.app, core.__dict__)
register_salintel_handoffs(core.app, core.__dict__)
register_facility_assessment(core.app, core.__dict__)


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
    if not (getattr(route, "path", None) == "/" and "GET" in (getattr(route, "methods", None) or set()))
]


@core.app.get("/", response_class=HTMLResponse, include_in_schema=False)
def preparedness_root():
    if not PREPAREDNESS_INDEX:
        raise HTTPException(503, "SalCAPA interface unavailable")
    return HTMLResponse(PREPAREDNESS_INDEX)


app = core.app
