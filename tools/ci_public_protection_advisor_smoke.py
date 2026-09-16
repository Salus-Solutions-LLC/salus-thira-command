#!/usr/bin/env python3
"""Focused acceptance for the public Protection Advisor pilot."""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

with tempfile.TemporaryDirectory() as td:
    db_path=str(Path(td)/"advisor.db")
    os.environ.update({
        "SALUS_DB_BACKEND":"sqlite",
        "SALUS_DB_PATH":db_path,
        "SALUS_ENV":"development",
        "SALUS_AUTH_MODE":"prototype",
        "SALUS_COOKIE_SECURE":"0",
        "SALUS_RATE_LIMIT_ENABLED":"1",
        "SALUS_RATE_LIMIT_REQUESTS":"500",
    })
    app_module=importlib.import_module("app")
    from fastapi.testclient import TestClient

    client=TestClient(app_module.app)
    page=client.get("/protection-advisor")
    assert page.status_code==200
    assert "Protection Advisor" in page.text
    assert "optional" in page.text.casefold()
    assert "preliminary" in page.text.casefold()
    assert "/static/salus-reticle.svg" in page.text

    refused=client.post("/public/protection-advisor/session",json={
        "organization_type":"Business",
        "primary_consent":False,
        "secondary_deidentified_consent":False,
    })
    assert refused.status_code==400

    started=client.post("/public/protection-advisor/session",json={
        "organization_type":"Faith-Based Organization",
        "primary_consent":True,
        "secondary_deidentified_consent":False,
    })
    assert started.status_code==200,started.text
    payload=started.json()
    csrf=payload["csrf_token"]
    questions=payload["questions"]
    assert any(q["key"]=="volunteer_roles" for q in questions)
    assert not any("student" in q["text"].casefold() for q in questions)
    headers={"X-CSRF-Token":csrf}

    assert client.post("/public/protection-advisor/answer",json={
        "question_key":"risk_list","answer_state":"Answered","note":""
    }).status_code in (401,403)

    for index,q in enumerate(questions):
        state="No" if index<4 else ("Unknown" if index==4 else "Answered")
        saved=client.post("/public/protection-advisor/answer",headers=headers,json={
            "question_key":q["key"],"answer_state":state,"note":""
        })
        assert saved.status_code==200,(q,saved.text)

    submitted=client.post("/public/protection-advisor/submit",headers=headers,json={
        "organization_name":"Public Pilot Organization",
        "contact_name":"Assessment Contact",
        "contact_email":"contact@example.com",
    })
    assert submitted.status_code==200,submitted.text
    result=submitted.json()["result"]
    assert result["status"]=="Preliminary — Salus Review Required"
    assert result["attention_count"]==4
    assert result["information_gap_count"]==1
    assert "human-controlled" in result["manual_next_step"]
    notifications=submitted.json()["notifications"]
    assert len(notifications)==2
    assert {row["audience"] for row in notifications}=={"Participant","Salus Reviewer"}
    assert all(row["state"]=="Pending" for row in notifications)
    assert all(row["error_code"]=="delivery_not_configured" for row in notifications)

    conn=sqlite3.connect(db_path)
    conn.row_factory=sqlite3.Row
    session=conn.execute("SELECT * FROM advisor_public_sessions").fetchone()
    submission=conn.execute("SELECT * FROM advisor_public_submissions").fetchone()
    assert session["primary_consent"]==1
    assert session["secondary_deidentified_consent"]==0
    assert session["status"]=="Submitted"
    assert submission["status"]=="Awaiting Salus Review"
    assert submission["questionnaire_version"]=="SPA-PUBLIC-QUESTIONNAIRE-1.0.0"
    assert len(submission["answer_snapshot_sha256"])==64
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_answer_revisions").fetchone()[0]==len(questions)
    outbox=conn.execute("SELECT * FROM advisor_public_notification_outbox ORDER BY audience").fetchall()
    assert len(outbox)==2
    assert all(row["attempts"]==1 for row in outbox)
    assert all("Assessment answers are intentionally not included in email." in row["body_text"] for row in outbox if row["audience"]=="Salus Reviewer")
    submission_key=submission["submission_key"]
    conn.close()

    review=client.get("/protection-advisor/review")
    assert review.status_code==403,review.text
    detail=client.get(f"/protection-advisor/review/{submission_key}")
    assert detail.status_code==403,detail.text

    from public_protection_advisor import _review_page, _review_detail
    review_row=dict(submission)
    review_row["notification_state"]="Pending"
    review_html=_review_page([review_row])
    assert "Public Pilot Organization" in review_html
    assert "/static/salus-reticle.svg" in review_html
    detail_html=_review_detail(review_row)
    assert "Assessment Contact" in detail_html
    assert "Risk List" in detail_html

    deleted=client.post("/public/protection-advisor/delete",headers=headers,json={})
    assert deleted.status_code==200,deleted.text
    conn=sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_submissions").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_answer_revisions").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_notification_outbox").fetchone()[0]==0
    assert conn.execute("SELECT status FROM advisor_public_sessions").fetchone()[0]=="Deleted"
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_lifecycle_events").fetchone()[0]>=3
    conn.close()

print("public Protection Advisor smoke passed")
