"""Public, isolated Salus Protection Advisor pilot.

Issue #290. This module intentionally has no Protected Member tenant relationship.
It persists only consented prospect assessment records and preserves versioned,
append-only answer lineage. Recommendations are preliminary and non-binding.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import secrets

import httpx
from azure.identity import ManagedIdentityCredential
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

QUESTIONNAIRE_VERSION = "SPA-PUBLIC-QUESTIONNAIRE-1.0.0"
RECOMMENDATION_VERSION = "SPA-PUBLIC-RECOMMENDATION-1.0.0"
CONSENT_NOTICE_VERSION = "SPA-PUBLIC-CONSENT-1.0.0"
RETENTION_POLICY_VERSION = "SPA-SPLIT-RETENTION-1.0.0"
SESSION_HOURS = 24
NOTIFICATION_MODE = os.getenv("SALUS_ADVISOR_NOTIFICATION_MODE", "outbox").strip().lower()
NOTIFICATION_TO = os.getenv("SALUS_ADVISOR_NOTIFICATION_TO", "mduncan@salus.solutions").strip().lower()
NOTIFICATION_FROM = os.getenv("SALUS_ADVISOR_NOTIFICATION_FROM", "mduncan@salus.solutions").strip().lower()
ANSWER_STATES = {"Answered", "Partially", "No", "Unknown", "Not Applicable", "Declined"}
ORGANIZATION_TYPES = {
    "Business", "Faith-Based Organization", "School or Educational Institution",
    "Nonprofit or Community Organization", "Healthcare or Human Services",
    "Government or Public Institution", "Property or Facility Operator",
    "Event Venue or Hospitality", "Other",
}
QUESTIONS = (
    ("risk_list", "Do you maintain a current list of threats and hazards that could affect your organization?", "risk"),
    ("consequence", "Have you assessed how serious the consequences could be for your most credible scenarios?", "risk"),
    ("reporting", "Are concerns and incident reports collected in one governed place for appropriate review?", "risk"),
    ("required_actions", "Do personnel understand what they may need to do during likely emergencies or disruptions?", "capability"),
    ("current_capability", "Has your organization compared what it can reliably do today with what it may need to do?", "capability"),
    ("integrated_test", "Have plans, communications, facilities, systems, and personnel been tested together?", "capability"),
    ("priority_gaps", "Can leadership identify the most important protection or readiness gaps in priority order?", "gap"),
    ("ownership", "Does a specific authorized person own each priority gap, with a plan and review date?", "gap"),
    ("training_test", "Have trained personnel demonstrated that they can perform their assigned actions?", "gap"),
    ("leadership_record", "Could leadership explain what was known, what was decided, and what action was underway?", "governance"),
    ("continuity", "Can essential operations continue if facilities, utilities, technology, suppliers, or personnel are disrupted?", "continuity"),
    ("recovery", "Are recovery priorities, alternate resources, and restoration responsibilities documented?", "continuity"),
)
FAITH_QUESTION = ("volunteer_roles", "Where volunteers have protective or emergency responsibilities, are their roles current, understood, and practiced?", "capability")
SCHOOL_QUESTION = ("reunification", "Have student accountability and family reunification procedures been tested with responsible personnel?", "capability")
PUBLIC_QUESTION = ("public_access", "Are public access, visitor management, and concerning-behavior reporting handled consistently?", "risk")


class StartCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_type: str
    primary_consent: bool
    secondary_deidentified_consent: bool = False

    @field_validator("organization_type")
    @classmethod
    def valid_org_type(cls, value: str) -> str:
        value = value.strip()
        if value not in ORGANIZATION_TYPES:
            raise ValueError("unsupported organization type")
        return value


class AnswerCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    answer_state: str
    note: str = Field(default="", max_length=500)

    @field_validator("answer_state")
    @classmethod
    def valid_state(cls, value: str) -> str:
        if value not in ANSWER_STATES:
            raise ValueError("unsupported answer state")
        return value

    @field_validator("note")
    @classmethod
    def clean_note(cls, value: str) -> str:
        return value.strip()


class SubmitCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_name: str = Field(min_length=1, max_length=160)
    contact_name: str = Field(min_length=1, max_length=160)
    contact_email: str = Field(min_length=3, max_length=254)

    @field_validator("organization_name", "contact_name", "contact_email")
    @classmethod
    def clean(cls, value: str) -> str:
        value = value.strip()
        if any(ch in value for ch in "\r\n"):
            raise ValueError("line breaks are not permitted")
        return value

    @field_validator("contact_email")
    @classmethod
    def email_shape(cls, value: str) -> str:
        value = value.casefold()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("enter a valid email address")
        return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _questions(org_type: str) -> list[dict[str, str]]:
    rows = [{"key": key, "text": text, "domain": domain} for key, text, domain in QUESTIONS]
    if org_type == "Faith-Based Organization":
        rows.append({"key": FAITH_QUESTION[0], "text": FAITH_QUESTION[1], "domain": FAITH_QUESTION[2]})
    if org_type == "School or Educational Institution":
        rows.append({"key": SCHOOL_QUESTION[0], "text": SCHOOL_QUESTION[1], "domain": SCHOOL_QUESTION[2]})
    if org_type in {"Faith-Based Organization", "School or Educational Institution", "Government or Public Institution", "Event Venue or Hospitality"}:
        rows.append({"key": PUBLIC_QUESTION[0], "text": PUBLIC_QUESTION[1], "domain": PUBLIC_QUESTION[2]})
    return rows


def _initialize(conn: Any) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS advisor_public_sessions (
      session_key TEXT PRIMARY KEY,
      token_sha256 TEXT NOT NULL UNIQUE,
      csrf_sha256 TEXT NOT NULL,
      organization_type TEXT NOT NULL,
      primary_consent INTEGER NOT NULL,
      secondary_deidentified_consent INTEGER NOT NULL,
      consent_notice_version TEXT NOT NULL,
      retention_policy_version TEXT NOT NULL,
      questionnaire_version TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      submitted_at TEXT NOT NULL DEFAULT '',
      deleted_at TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS advisor_public_answer_revisions (
      revision_key TEXT PRIMARY KEY,
      session_key TEXT NOT NULL,
      question_key TEXT NOT NULL,
      revision_no INTEGER NOT NULL,
      answer_state TEXT NOT NULL,
      note TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      content_sha256 TEXT NOT NULL,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE CASCADE,
      UNIQUE(session_key,question_key,revision_no)
    );
    CREATE INDEX IF NOT EXISTS idx_advisor_answers_session ON advisor_public_answer_revisions(session_key,question_key,revision_no);
    CREATE TABLE IF NOT EXISTS advisor_public_submissions (
      submission_key TEXT PRIMARY KEY,
      session_key TEXT NOT NULL UNIQUE,
      organization_name TEXT NOT NULL,
      contact_name TEXT NOT NULL,
      contact_email TEXT NOT NULL,
      answer_snapshot_json TEXT NOT NULL,
      answer_snapshot_sha256 TEXT NOT NULL,
      questionnaire_version TEXT NOT NULL,
      recommendation_version TEXT NOT NULL,
      consent_notice_version TEXT NOT NULL,
      retention_policy_version TEXT NOT NULL,
      secondary_deidentified_consent INTEGER NOT NULL,
      result_json TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE RESTRICT
    );
    CREATE TABLE IF NOT EXISTS advisor_public_lifecycle_events (
      event_key TEXT PRIMARY KEY,
      session_key TEXT NOT NULL,
      event_type TEXT NOT NULL,
      event_at TEXT NOT NULL,
      detail_sha256 TEXT NOT NULL,
      FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS advisor_public_notification_outbox (
      notification_key TEXT PRIMARY KEY,
      submission_key TEXT NOT NULL,
      audience TEXT NOT NULL,
      recipient_email TEXT NOT NULL,
      subject TEXT NOT NULL,
      body_text TEXT NOT NULL,
      state TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 0,
      last_attempt_at TEXT NOT NULL DEFAULT '',
      delivered_at TEXT NOT NULL DEFAULT '',
      error_code TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY (submission_key) REFERENCES advisor_public_submissions(submission_key) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_advisor_notification_state
      ON advisor_public_notification_outbox(state,created_at);
    """)


def _session(conn: Any, request: Request) -> tuple[Any, str]:
    token = request.cookies.get("salus_advisor_session", "")
    csrf = request.headers.get("x-csrf-token", "")
    if not token or not csrf:
        raise HTTPException(401, "Advisor session is required")
    row = conn.execute(
        "SELECT * FROM advisor_public_sessions WHERE token_sha256=?",
        (_sha(token),),
    ).fetchone()
    if not row or row["status"] not in ("Active", "Submitted") or row["deleted_at"]:
        raise HTTPException(401, "Advisor session is unavailable")
    if row["csrf_sha256"] != _sha(csrf):
        raise HTTPException(403, "Request verification failed")
    if row["expires_at"] <= _utc_text(_utc_now()) and row["status"] == "Active":
        raise HTTPException(401, "Advisor session has expired")
    return row, token


def _current_answers(conn: Any, session_key: str) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """SELECT a.* FROM advisor_public_answer_revisions a
           JOIN (SELECT question_key,MAX(revision_no) revision_no
                 FROM advisor_public_answer_revisions WHERE session_key=? GROUP BY question_key) latest
             ON latest.question_key=a.question_key AND latest.revision_no=a.revision_no
          WHERE a.session_key=? ORDER BY a.question_key""",
        (session_key, session_key),
    ).fetchall()
    return {row["question_key"]: dict(row) for row in rows}


def _result(questions: list[dict[str, str]], answers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    attention = []
    strengths = []
    unknowns = []
    for q in questions:
        answer = answers.get(q["key"], {})
        state = answer.get("answer_state", "Unknown")
        if state in {"No", "Partially"}:
            attention.append(q["text"])
        elif state == "Answered":
            strengths.append(q["text"])
        elif state in {"Unknown", "Declined"}:
            unknowns.append(q["text"])
    if len(attention) >= 6:
        level = "Comprehensive review recommended"
    elif len(attention) >= 3:
        level = "Focused review recommended"
    else:
        level = "Foundation review recommended"
    return {
        "status": "Preliminary — Salus Review Required",
        "recommendation": level,
        "attention_count": len(attention),
        "strength_count": len(strengths),
        "information_gap_count": len(unknowns),
        "attention_topics": attention[:6],
        "information_gaps": unknowns[:6],
        "notice": "This result is preliminary and non-binding. A qualified Salus professional must review scope, recommendations, and any price.",
        "manual_next_step": "Qualification, scoping, proposal, onboarding, and service delivery remain human-controlled.",
    }


def _page() -> str:
    options = "".join(f'<option value="{html.escape(item)}">{html.escape(item)}</option>' for item in sorted(ORGANIZATION_TYPES))
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protection Advisor | Salus Solutions</title>
<style>
:root{--blue:#477d9f;--ink:#14283a;--orange:#d9571e;--line:#d8e0e6;--soft:#f7f9fa}
*{box-sizing:border-box} body{margin:0;background:white;color:var(--ink);font:18px/1.55 Georgia,serif}
main{max-width:940px;margin:auto;padding:48px 28px 80px} h1,h2,h3,button,label,select,input{font-family:Arial,sans-serif}
h1{font-size:3rem;font-weight:300;color:var(--blue);margin:.2rem 0} h2{font-weight:400;font-size:1.9rem;margin-top:2rem}
.brand{font:28px Arial,sans-serif;color:#111;margin-bottom:44px;display:flex;align-items:center;gap:14px}.brand img{width:58px;height:58px;object-fit:contain} .muted{color:#536675} .panel{border-top:1px solid var(--line);padding-top:24px;margin-top:28px}
label{display:block;font-weight:600;margin:18px 0 7px} select,input[type=text],input[type=email]{width:100%;font-size:1rem;padding:13px;border:1px solid #8d9aa3;border-radius:2px}
.check{display:flex;gap:12px;align-items:flex-start;font-family:Georgia,serif;font-weight:400} .check input{margin-top:7px}
button{border:0;background:none;color:var(--orange);font-size:1.05rem;padding:14px 0;cursor:pointer;text-align:left} button:disabled{color:#888;cursor:not-allowed}
.question{padding:20px 0;border-bottom:1px solid var(--line)} .choices{display:flex;flex-wrap:wrap;gap:14px;margin-top:12px}
.choices label{font-weight:400;margin:0} .hidden{display:none} .error{color:#a12612} .result{background:var(--soft);padding:24px;margin-top:24px}
@media(max-width:600px){body{font-size:17px} main{padding:28px 20px} h1{font-size:2.4rem}}
</style></head><body><main>
<div class="brand"><img src="/static/salus-reticle.svg" alt="Salus Solutions reticle"> Salus Solutions</div>
<h1>Protection Advisor™</h1><p class="muted">Find Your Salus Package</p>
<h2>Understand what could affect your organization and what to do next</h2>
<p>The Protection Advisor provides a preliminary, non-binding review. It does not create membership, a contract, an approved scope, a price commitment, or operational authority.</p>
<section id="start" class="panel">
<label for="orgType">Organization type</label><select id="orgType"><option value="">Select your organization type</option>__OPTIONS__</select>
<label class="check"><input id="primary" type="checkbox"> <span>I consent to Salus retaining my assessment answers and contact information to prepare, review, and follow up on my preliminary recommendation. I understand I may request correction, withdrawal, or deletion.</span></label>
<label class="check"><input id="secondary" type="checkbox"> <span>Optional: I permit Salus to derive separately reviewed, appropriately deidentified knowledge for long-term protective research and service improvement. Declining does not prevent the assessment.</span></label>
<button onclick="startAssessment()">Begin Your Protection Assessment &gt;</button><p id="startError" class="error"></p>
</section>
<section id="assessment" class="hidden"><h2>Your assessment</h2><p>You may choose Not Sure, Not Applicable, or Prefer Not to Answer.</p><div id="questions"></div>
<button onclick="showContact()">Review and submit &gt;</button></section>
<section id="contact" class="hidden"><h2>Submit for Salus review</h2>
<label>Organization name<input id="organizationName" type="text" maxlength="160"></label>
<label>Your name<input id="contactName" type="text" maxlength="160"></label>
<label>Email address<input id="contactEmail" type="email" maxlength="254"></label>
<button onclick="submitAssessment()">Submit for Salus Review &gt;</button><p id="submitError" class="error"></p></section>
<section id="result" class="hidden result"></section>
<section class="panel"><h2>Important notice</h2><p>This is not an emergency reporting service, completed THIRA, professional security assessment, legal or insurance advice, or guarantee against loss. For an immediate threat to life or safety, contact 911 or the appropriate local emergency service.</p></section>
</main><script>
let csrf="",questions=[];
async function call(path,opts={}){opts.headers={"Content-Type":"application/json",...(csrf?{"X-CSRF-Token":csrf}:{}),...(opts.headers||{})};const r=await fetch(path,opts);const data=await r.json().catch(()=>({detail:"Request failed"}));if(!r.ok)throw new Error(data.detail||"Request failed");return data}
async function startAssessment(){const e=document.getElementById("startError");e.textContent="";try{const data=await call("/public/protection-advisor/session",{method:"POST",body:JSON.stringify({organization_type:orgType.value,primary_consent:primary.checked,secondary_deidentified_consent:secondary.checked})});csrf=data.csrf_token;questions=data.questions;start.classList.add("hidden");assessment.classList.remove("hidden");renderQuestions()}catch(x){e.textContent=x.message}}
function renderQuestions(){document.getElementById("questions").innerHTML=questions.map((q,i)=>`<div class="question"><strong>${i+1}. ${q.text}</strong><div class="choices">${["Answered","Partially","No","Unknown","Not Applicable","Declined"].map(s=>`<label><input type="radio" name="${q.key}" value="${s}" onchange="saveAnswer('${q.key}','${s}')"> ${s==="Answered"?"Yes":s==="Unknown"?"Not Sure":s==="Declined"?"Prefer Not to Answer":s}</label>`).join("")}</div></div>`).join("")}
async function saveAnswer(key,state){await call("/public/protection-advisor/answer",{method:"POST",body:JSON.stringify({question_key:key,answer_state:state,note:""})})}
function showContact(){contact.classList.remove("hidden");contact.scrollIntoView({behavior:"smooth"})}
async function submitAssessment(){const e=document.getElementById("submitError");e.textContent="";try{const data=await call("/public/protection-advisor/submit",{method:"POST",body:JSON.stringify({organization_name:organizationName.value,contact_name:contactName.value,contact_email:contactEmail.value})});assessment.classList.add("hidden");contact.classList.add("hidden");const r=data.result;result.innerHTML=`<h2>Your Salus Recommendation</h2><h3>${r.recommendation}</h3><p>${r.notice}</p><p><strong>Potential attention areas:</strong> ${r.attention_count}. <strong>Information gaps:</strong> ${r.information_gap_count}.</p><p>${r.manual_next_step}</p><button onclick="deleteRecord()">Withdraw and delete my submitted information &gt;</button>`;result.classList.remove("hidden");result.scrollIntoView({behavior:"smooth"})}catch(x){e.textContent=x.message}}
async function deleteRecord(){if(!confirm("Withdraw this assessment and delete its submitted content?"))return;await call("/public/protection-advisor/delete",{method:"POST",body:"{}"});result.innerHTML="<h2>Information withdrawn</h2><p>Your assessment content and contact information have been deleted. Content-free lifecycle evidence is retained for accountability.</p>"}
</script></body></html>""".replace("__OPTIONS__", options)


async def _send_graph_email(recipient: str, subject: str, body_text: str) -> tuple[bool, str]:
    if NOTIFICATION_MODE != "graph":
        return False, "delivery_not_configured"
    if not NOTIFICATION_FROM:
        return False, "sender_not_configured"
    try:
        credential = ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID") or None)
        token = credential.get_token("https://graph.microsoft.com/.default").token
        sender = NOTIFICATION_FROM.replace("'", "").replace("/", "")
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body_text},
                "toRecipients": [{"emailAddress": {"address": recipient}}],
            },
            "saveToSentItems": True,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code == 202:
            return True, ""
        return False, f"graph_http_{response.status_code}"
    except Exception as exc:
        return False, type(exc).__name__[:80]


async def _deliver_outbox(conn: Any, notification_key: str) -> None:
    row = conn.execute(
        "SELECT * FROM advisor_public_notification_outbox WHERE notification_key=?",
        (notification_key,),
    ).fetchone()
    if not row or row["state"] == "Delivered":
        return
    attempted = _utc_text(_utc_now())
    delivered, error_code = await _send_graph_email(
        row["recipient_email"], row["subject"], row["body_text"]
    )
    conn.execute(
        """UPDATE advisor_public_notification_outbox
           SET state=?,attempts=attempts+1,last_attempt_at=?,delivered_at=?,error_code=?
         WHERE notification_key=?""",
        (
            "Delivered" if delivered else "Pending",
            attempted,
            attempted if delivered else "",
            error_code,
            notification_key,
        ),
    )
    conn.commit()


def _review_page(rows: list[dict[str, Any]]) -> str:
    body_rows = []
    for row in rows:
        result = json.loads(row["result_json"])
        body_rows.append(
            "<tr>"
            f"<td>{html.escape(row['created_at'])}</td>"
            f"<td><a href='/protection-advisor/review/{html.escape(row['submission_key'])}'>"
            f"{html.escape(row['organization_name'])} &gt;</a></td>"
            f"<td>{html.escape(row['contact_name'])}<br>{html.escape(row['contact_email'])}</td>"
            f"<td>{html.escape(result.get('recommendation',''))}</td>"
            f"<td>{html.escape(row['status'])}</td>"
            f"<td>{html.escape(row['notification_state'])}</td>"
            "</tr>"
        )
    rows_html = "".join(body_rows) or "<tr><td colspan='6'>No Protection Advisor submissions yet.</td></tr>"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protection Advisor Review | Salus Solutions</title><style>
:root{{--orange:#dc4f17;--blue:#477fa4;--ink:#172938;--line:#dce3e8}}*{{box-sizing:border-box}}body{{margin:0;background:#fff;color:var(--ink);font:17px/1.55 Georgia,serif}}
main{{max-width:1180px;margin:auto;padding:44px 28px 80px}}header{{display:flex;align-items:center;gap:18px;margin-bottom:42px}}header img{{width:66px;height:66px;object-fit:contain}}
.brand{{font:30px Arial,sans-serif;color:#111}}h1{{font:300 2.7rem Arial,sans-serif;color:var(--blue)}}table{{width:100%;border-collapse:collapse}}th,td{{padding:14px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{font:600 .85rem Arial,sans-serif;text-transform:uppercase}}a{{color:var(--orange);text-decoration:none}}.notice{{background:#f6f8fa;padding:14px 18px;border-left:3px solid var(--blue)}}
@media(max-width:760px){{table,thead,tbody,tr,th,td{{display:block}}thead{{display:none}}tr{{margin:18px 0;border:1px solid var(--line)}}}}
</style></head><body><main><header><img src="/static/salus-reticle.svg" alt="Salus Solutions reticle"><div class="brand">Salus Solutions</div></header>
<h1>Protection Advisor Review</h1><p class="notice">Authorized Salus review workspace. Prospect records remain separate from Protected Member tenant records until an authorized person completes the governed intake decision.</p>
<table><thead><tr><th>Submitted</th><th>Organization</th><th>Contact</th><th>Recommendation</th><th>Status</th><th>Notification</th></tr></thead><tbody>{rows_html}</tbody></table>
<p><a href="/">&lt; SalCAPA Command Center</a></p></main></body></html>"""


def _review_detail(row: dict[str, Any]) -> str:
    result = json.loads(row["result_json"])
    answers = json.loads(row["answer_snapshot_json"])
    answer_rows = "".join(
        f"<tr><td>{html.escape(key.replace('_',' ').title())}</td><td>{html.escape(str(value.get('answer_state','')))}</td></tr>"
        for key, value in answers.items()
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Protection Advisor Submission | Salus Solutions</title><style>
body{{max-width:900px;margin:auto;padding:42px 26px 80px;color:#172938;font:17px/1.55 Georgia,serif}}header{{display:flex;align-items:center;gap:16px}}header img{{width:62px;height:62px;object-fit:contain}}h1{{font:300 2.5rem Arial,sans-serif;color:#477fa4}}h2{{font:400 1.55rem Arial,sans-serif}}a,button{{color:#dc4f17}}table{{width:100%;border-collapse:collapse}}td{{padding:11px;border-bottom:1px solid #dce3e8;vertical-align:top}}
.notice{{background:#f6f8fa;padding:14px 18px;border-left:3px solid #477fa4}}</style></head><body>
<header><img src="/static/salus-reticle.svg" alt="Salus Solutions reticle"><strong>Salus Solutions</strong></header>
<p><a href="/protection-advisor/review">&lt; All submissions</a></p><h1>{html.escape(row['organization_name'])}</h1>
<p><strong>Contact:</strong> {html.escape(row['contact_name'])} · <a href="mailto:{html.escape(row['contact_email'])}">{html.escape(row['contact_email'])}</a><br>
<strong>Submitted:</strong> {html.escape(row['created_at'])}<br><strong>Status:</strong> {html.escape(row['status'])}</p>
<h2>Preliminary result</h2><p class="notice"><strong>{html.escape(result.get('recommendation',''))}</strong><br>{html.escape(result.get('notice',''))}</p>
<p>Potential attention areas: {int(result.get('attention_count',0))}. Information gaps: {int(result.get('information_gap_count',0))}.</p>
<h2>Assessment answers</h2><table>{answer_rows}</table></body></html>"""


def register_public_protection_advisor(app: Any, ctx: dict[str, Any]) -> None:
    conn = ctx["db"]()
    try:
        _initialize(conn)
        conn.commit()
    finally:
        conn.close()

    def limited(request: Request, token: str = "") -> None:
        limiter = ctx["RATE_LIMITER"]
        source = request.client.host if request.client else ""
        key = "advisor:" + limiter.key(source, token)
        allowed, _, retry = limiter.allow(key)
        if not allowed:
            raise HTTPException(429, f"Please wait {retry} seconds before trying again")

    @app.get("/protection-advisor", response_class=HTMLResponse)
    def protection_advisor_page() -> HTMLResponse:
        return HTMLResponse(_page(), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})

    @app.get("/protection-advisor/review", response_class=HTMLResponse)
    def protection_advisor_review(request: Request) -> HTMLResponse:
        ctx["require"](request, "admin")
        conn = ctx["db"]()
        try:
            _initialize(conn)
            rows = [dict(row) for row in conn.execute(
                """SELECT s.*,
                   COALESCE((SELECT CASE WHEN SUM(CASE WHEN state='Delivered' THEN 1 ELSE 0 END)=COUNT(*)
                                        THEN 'Delivered' ELSE 'Pending' END
                               FROM advisor_public_notification_outbox n
                              WHERE n.submission_key=s.submission_key),'Not queued') notification_state
                     FROM advisor_public_submissions s
                    ORDER BY s.created_at DESC"""
            ).fetchall()]
            return HTMLResponse(_review_page(rows), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"})
        finally:
            conn.close()

    @app.get("/protection-advisor/review/{submission_key}", response_class=HTMLResponse)
    def protection_advisor_review_detail(submission_key: str, request: Request) -> HTMLResponse:
        ctx["require"](request, "admin")
        if not submission_key.startswith("SPA-SUBMISSION-"):
            raise HTTPException(404, "Submission not found")
        conn = ctx["db"]()
        try:
            row = conn.execute(
                "SELECT * FROM advisor_public_submissions WHERE submission_key=?",
                (submission_key,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Submission not found")
            return HTMLResponse(_review_detail(dict(row)), headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY"})
        finally:
            conn.close()

    @app.post("/api/protection-advisor/review/notifications/{notification_key}/retry")
    async def retry_protection_advisor_notification(notification_key: str, request: Request) -> dict[str, Any]:
        ctx["require"](request, "admin")
        conn = ctx["db"]()
        try:
            _initialize(conn)
            await _deliver_outbox(conn, notification_key)
            row = conn.execute(
                "SELECT state,attempts,last_attempt_at,delivered_at,error_code FROM advisor_public_notification_outbox WHERE notification_key=?",
                (notification_key,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Notification not found")
            return dict(row)
        finally:
            conn.close()

    @app.post("/public/protection-advisor/session")
    async def start_public_session(command: StartCommand, request: Request) -> JSONResponse:
        limited(request)
        if not command.primary_consent:
            raise HTTPException(400, "Consent is required before assessment information can be retained")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        session_key = "SPA-SESSION-" + secrets.token_hex(16).upper()
        created = _utc_now()
        conn = ctx["db"]()
        try:
            _initialize(conn)
            conn.execute(
                """INSERT INTO advisor_public_sessions
                (session_key,token_sha256,csrf_sha256,organization_type,primary_consent,
                 secondary_deidentified_consent,consent_notice_version,retention_policy_version,
                 questionnaire_version,status,created_at,expires_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (session_key,_sha(token),_sha(csrf),command.organization_type,1,
                 1 if command.secondary_deidentified_consent else 0,CONSENT_NOTICE_VERSION,
                 RETENTION_POLICY_VERSION,QUESTIONNAIRE_VERSION,"Active",_utc_text(created),
                 _utc_text(created+timedelta(hours=SESSION_HOURS))),
            )
            conn.execute("INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-"+secrets.token_hex(16).upper(),session_key,"Consent Recorded",
                 _utc_text(created),_sha(_json(command.model_dump()))))
            conn.commit()
        finally:
            conn.close()
        response = JSONResponse({"csrf_token": csrf, "questions": _questions(command.organization_type), "questionnaire_version": QUESTIONNAIRE_VERSION})
        response.set_cookie("salus_advisor_session", token, httponly=True, secure=ctx.get("COOKIE_SECURE", True), samesite="strict", max_age=SESSION_HOURS*3600, path="/")
        return response

    @app.post("/public/protection-advisor/answer")
    async def answer_public_question(command: AnswerCommand, request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            allowed = {q["key"] for q in _questions(session["organization_type"])}
            if command.question_key not in allowed:
                raise HTTPException(400, "Question is not part of this assessment")
            row = conn.execute("SELECT COALESCE(MAX(revision_no),0) n FROM advisor_public_answer_revisions WHERE session_key=? AND question_key=?",(session["session_key"],command.question_key)).fetchone()
            revision_no = int(row["n"])+1
            payload = {"question_key":command.question_key,"revision_no":revision_no,"answer_state":command.answer_state,"note":command.note}
            conn.execute("INSERT INTO advisor_public_answer_revisions VALUES(?,?,?,?,?,?,?,?)",
                ("SPA-ANSWER-"+secrets.token_hex(16).upper(),session["session_key"],command.question_key,
                 revision_no,command.answer_state,command.note,_utc_text(_utc_now()),_sha(_json(payload))))
            conn.commit()
            return {"saved": True, "revision_no": revision_no}
        finally:
            conn.close()

    @app.post("/public/protection-advisor/submit")
    async def submit_public_assessment(command: SubmitCommand, request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            if session["status"] != "Active":
                raise HTTPException(409, "Assessment has already been submitted")
            questions = _questions(session["organization_type"])
            answers = _current_answers(conn, session["session_key"])
            missing = [q["key"] for q in questions if q["key"] not in answers]
            if missing:
                raise HTTPException(400, "Answer every question before submitting")
            snapshot = {key:{"answer_state":value["answer_state"],"note":value["note"],"revision_no":value["revision_no"],"content_sha256":value["content_sha256"]} for key,value in sorted(answers.items())}
            result = _result(questions, answers)
            created = _utc_text(_utc_now())
            conn.execute(
                """INSERT INTO advisor_public_submissions
                (submission_key,session_key,organization_name,contact_name,contact_email,
                 answer_snapshot_json,answer_snapshot_sha256,questionnaire_version,
                 recommendation_version,consent_notice_version,retention_policy_version,
                 secondary_deidentified_consent,result_json,status,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                ("SPA-SUBMISSION-"+secrets.token_hex(16).upper(),session["session_key"],
                 command.organization_name,command.contact_name,command.contact_email,
                 _json(snapshot),_sha(_json(snapshot)),QUESTIONNAIRE_VERSION,RECOMMENDATION_VERSION,
                 CONSENT_NOTICE_VERSION,RETENTION_POLICY_VERSION,
                 session["secondary_deidentified_consent"],_json(result),
                 "Awaiting Salus Review",created),
            )
            conn.execute("UPDATE advisor_public_sessions SET status='Submitted',submitted_at=? WHERE session_key=?",(created,session["session_key"]))
            conn.execute("INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-"+secrets.token_hex(16).upper(),session["session_key"],"Submitted for Salus Review",created,_sha(_json({"snapshot_sha256":_sha(_json(snapshot))}))))
            conn.commit()

            review_url = str(request.base_url).rstrip("/") + "/protection-advisor/review/" + submission_key
            internal_key = "SPA-NOTIFY-" + secrets.token_hex(16).upper()
            participant_key = "SPA-NOTIFY-" + secrets.token_hex(16).upper()
            internal_body = (
                "A new Protection Advisor assessment is awaiting Salus review.\n\n"
                f"Organization: {command.organization_name}\n"
                f"Contact: {command.contact_name}\n"
                f"Email: {command.contact_email}\n"
                f"Preliminary recommendation: {result['recommendation']}\n"
                f"Attention areas: {result['attention_count']}\n"
                f"Information gaps: {result['information_gap_count']}\n\n"
                f"Review securely in SalCAPA: {review_url}\n\n"
                "Assessment answers are intentionally not included in email."
            )
            participant_body = (
                f"Hello {command.contact_name},\n\n"
                "Salus Solutions received your Protection Advisor assessment.\n\n"
                f"Preliminary recommendation: {result['recommendation']}\n"
                f"Potential attention areas: {result['attention_count']}\n"
                f"Information gaps: {result['information_gap_count']}\n\n"
                f"{result['notice']}\n\n"
                "A Salus professional may contact you to discuss appropriate next steps. "
                "Do not reply with passwords, financial information, medical records, government identifiers, "
                "classified information, or operational details whose disclosure could create an immediate security risk."
            )
            outbox_created = _utc_text(_utc_now())
            conn.execute(
                "INSERT INTO advisor_public_notification_outbox VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (internal_key,submission_key,"Salus Reviewer",NOTIFICATION_TO,
                 f"Protection Advisor submission: {command.organization_name}",internal_body,
                 "Pending",0,"","","",outbox_created),
            )
            conn.execute(
                "INSERT INTO advisor_public_notification_outbox VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (participant_key,submission_key,"Participant",command.contact_email,
                 "Your Salus Protection Advisor assessment",participant_body,
                 "Pending",0,"","","",outbox_created),
            )
            conn.commit()
            await _deliver_outbox(conn, internal_key)
            await _deliver_outbox(conn, participant_key)
            notification_rows = conn.execute(
                "SELECT audience,state,error_code FROM advisor_public_notification_outbox WHERE submission_key=? ORDER BY audience",
                (submission_key,),
            ).fetchall()
            return {
                "submitted": True,
                "result": result,
                "notifications": [dict(row) for row in notification_rows],
            }
        finally:
            conn.close()

    @app.post("/public/protection-advisor/delete")
    async def delete_public_assessment(request: Request) -> dict[str, Any]:
        limited(request, request.cookies.get("salus_advisor_session", ""))
        conn = ctx["db"]()
        try:
            session, _ = _session(conn, request)
            deleted = _utc_text(_utc_now())
            conn.execute("DELETE FROM advisor_public_submissions WHERE session_key=?",(session["session_key"],))
            conn.execute("DELETE FROM advisor_public_answer_revisions WHERE session_key=?",(session["session_key"],))
            conn.execute("UPDATE advisor_public_sessions SET status='Deleted',deleted_at=? WHERE session_key=?",(deleted,session["session_key"]))
            conn.execute("INSERT INTO advisor_public_lifecycle_events VALUES(?,?,?,?,?)",
                ("SPA-EVENT-"+secrets.token_hex(16).upper(),session["session_key"],"Content Deleted",deleted,_sha("content deleted at prospect request")))
            conn.commit()
            return {"deleted": True}
        finally:
            conn.close()
