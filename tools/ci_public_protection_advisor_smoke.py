#!/usr/bin/env python3
"""Focused acceptance for the public Protection Advisor."""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
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
        "SALUS_ADVISOR_NOTIFICATION_MODE":"outbox",
        "SALUS_ADVISOR_NOTIFICATION_FROM":"protectionadvisor@salus.solutions",
        "SALUS_ADVISOR_NOTIFICATION_TO":"mduncan@salus.solutions",
    })
    app_module=importlib.import_module("app")
    from fastapi.testclient import TestClient
    from public_protection_advisor import (
        CORE_CAPABILITIES, NOTIFICATION_FROM, QUESTION_BLUEPRINTS, _package_recommendation,
        _page, _questions, _review_detail, _review_page, _verification_page,
    )

    assert NOTIFICATION_FROM=="protectionadvisor@salus.solutions"
    assert len(CORE_CAPABILITIES)==32
    assert {cap for row in QUESTION_BLUEPRINTS for cap in row[3]}==set(CORE_CAPABILITIES)
    assert set(area for areas in CORE_CAPABILITIES.values() for area in areas)=={
        "Prevention","Protection","Mitigation","Response","Recovery"
    }

    client=TestClient(app_module.app)
    canonical=client.get("/protection-advisor",follow_redirects=False)
    assert canonical.status_code==307
    assert canonical.headers["location"]=="https://www.salus.solutions/protection-advisor"
    assert canonical.headers["cache-control"]=="no-store"
    page=client.get("/protection-advisor/embed")
    assert page.status_code==200
    assert "Protection Advisor" in page.text
    assert "Anonymous Protection Readiness Review" in page.text
    assert "Understand the detailed assessment" in page.text
    assert "answer truthfully from my current knowledge" in page.text
    assert "Return to Your Part 2 Assessment" in page.text
    assert 'onchange="saveAnswer(this.name,this.value)"' in page.text
    assert 'id="questionProgress"' in page.text
    assert 'id="previousQuestion"' in page.text
    assert 'id="nextQuestion"' in page.text
    assert 'id="reviewResults"' in page.text
    assert 'questions.map((q,i)=>' not in page.text
    assert 'const q=questions[questionIndex]' in page.text
    assert 'class="question-nav"' in page.text
    assert ".question-nav{position:sticky;bottom:0" in page.text
    assert '<aside class="assessment-important"><strong>Important notice:</strong>' in page.text
    assert 'document.getElementById("assessment").scrollIntoView' in page.text
    assert "saveAnswer(''+q.key+'',''+s+'')" not in page.text
    assert "Level '+s.level" in page.text
    shell_html=_page()
    assert "/static/salus-reticle.svg" in shell_html
    assert '<header class="salus-header">' in shell_html
    assert "font-size:56px" in shell_html
    assert "font-size:32px" in shell_html
    assert "font-size:28px" in shell_html
    assert 'aria-current="page">Protection Advisor &gt;' in shell_html
    for label, href in (
        ("Industries", "https://www.salus.solutions/industries"),
        ("Insights and Library", "https://www.salus.solutions/insights"),
        ("Payments", "https://www.salus.solutions/payments"),
        ("Protected Member Login &gt;", "https://salcapa.salus.solutions/"),
    ):
        assert f'<a href="{href}">{label}</a>' in shell_html

    embedded=client.get("/protection-advisor/embed")
    assert embedded.status_code==200
    assert '<header class="salus-header">' not in embedded.text
    assert '<h1>Protection Advisor™</h1>' not in embedded.text
    assert '<h1 class="visually-hidden">Protection Advisor</h1>' in embedded.text
    assert "main{padding-top:8px;padding-bottom:18px}" in embedded.text
    assert "salus-protection-advisor-height" in embedded.text
    assert "preferred_min_height:900" in embedded.text
    assert "Print or Save Preliminary Summary" in embedded.text
    assert "Download Professional Detailed Report" in embedded.text
    assert 'onclick="printAdvisor(&quot;part1&quot;)"' in embedded.text
    assert embedded.text.count('onclick="printAdvisor(&quot;part2&quot;)"') == 2
    assert embedded.text.count("Download Professional Detailed Report") == 2
    assert 'fetch("/public/protection-advisor/report.pdf"' in embedded.text
    assert 'credentials:"same-origin"' in embedded.text
    assert 'headers:{"X-CSRF-Token":csrf}' in embedded.text
    assert "response.blob()" in embedded.text
    assert "URL.createObjectURL(blob)" in embedded.text
    assert "link.download=filename" in embedded.text
    assert 'window.location.assign("/public/protection-advisor/report.pdf")' not in embedded.text
    assert "onclick=\"printAdvisor('part1')\"" not in embedded.text
    assert "onclick=\"printAdvisor('part2')\"" not in embedded.text
    assert "print-part1" in embedded.text and "print-part2" in embedded.text
    assert "CONFIDENTIAL" in embedded.text
    assert "Protected Member Code Name" in embedded.text
    assert "Requested report-handling profile" in embedded.text
    assert "SPA-REPORT-TEMPLATE-1.1.0" in embedded.text
    assert "CONFIDENTIAL — SALUS PROTECTED INFORMATION" in embedded.text
    assert 'href="https://salcapa.salus.solutions/protection-advisor/services" target="_blank" rel="noopener noreferrer"' in embedded.text
    assert "frame-ancestors https://www.salus.solutions https://salus.solutions" in embedded.headers["content-security-policy"]
    assert "x-frame-options" not in embedded.headers

    catalog=client.get("/protection-advisor/services")
    assert catalog.status_code==200
    assert "Salus THIRA Assessment" in catalog.text
    assert "Business Continuity and Recovery" in catalog.text
    assert '<header class="salus-header">' in catalog.text
    assert "font-size:56px" in catalog.text

    verification_html=_verification_page()
    assert '<header class="salus-header">' in verification_html
    assert "<h1>Email verified</h1>" in verification_html
    assert "retained assessment result does not expire" in verification_html

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
    headers={"X-CSRF-Token":csrf}
    questions=payload["questions"]
    assert payload["questionnaire_version"]=="SPA-PUBLIC-QUESTIONNAIRE-2.0.0"
    assert len([q for q in questions if q["key"] not in {"volunteer_roles","public_access"}])==28
    assert any(q["key"]=="volunteer_roles" for q in questions)
    assert all(q["capabilities"] and q["mission_areas"] and q["services"] for q in questions)

    for index,q in enumerate(questions):
        state="No" if index<4 else ("Unknown" if index==4 else "Validated")
        saved=client.post("/public/protection-advisor/answer",headers=headers,json={
            "question_key":q["key"],"answer_state":state,"note":""
        })
        assert saved.status_code==200,(q,saved.text)

    preliminary=client.post("/public/protection-advisor/preliminary",headers=headers,json={})
    assert preliminary.status_code==200,preliminary.text
    preliminary_result=preliminary.json()["result"]
    assert preliminary_result["attention_count"]==4
    assert preliminary_result["information_gap_count"]==1
    assert preliminary_result["core_capabilities_considered"]==32
    assert set(preliminary_result["mission_area_scores"])=={
        "Prevention","Protection","Mitigation","Response","Recovery"
    }

    no_account=client.post("/public/protection-advisor/submit",headers=headers,json={
        "protected_member_code_name":"Blocked Member","project_code_name":"Blocked Project",
        "handling_profile":"Commercial Confidential",
        "organization_name":"Blocked","contact_name":"Blocked","contact_email":"contact@example.com",
        "detailed_assessment_acknowledged":True,"identifiable_retention_consent":True,
        "facility_scope":"One facility","facility_locations":"Texas","personnel_range":"26–100",
        "affected_population_range":"101–500","annual_revenue_range":"$5 million–$25 million",
        "specific_activities":[],"essential_functions":"Services",
        "maximum_tolerable_downtime":"1–3 days",
        "existing_program_maturity":"Mostly informal",
        "internal_implementation_capacity":"Limited internal capacity",
        "primary_objective":"Independent assessment and priorities",
        "external_requirements":"Future planning or budget decision",
        "recent_concerns":"","desired_timing":"Within 90 days",
        "decision_authority":"Executive leadership","investment_range":"Need phased options",
    })
    assert no_account.status_code==401

    created=client.post("/public/protection-advisor/account",headers=headers,json={
        "email":"contact@example.com",
        "password":"Correct-Horse-Battery-2026",
        "detailed_assessment_acknowledged":True,
        "identifiable_retention_consent":True,
    })
    assert created.status_code==200,created.text
    assert created.json()["authenticated"] is True

    draft=client.post("/public/protection-advisor/draft",headers=headers,json={
        "fields":{"protected_member_code_name":"Blue Lantern","project_code_name":"Steady Harbor",
                  "handling_profile":"Federal CUI","handling_authority":"Federal contract clause",
                  "designating_agency":"Example Federal Agency","contract_reference":"TASK-TEST-001",
                  "dissemination_controls":"Authorized recipients only",
                  "organization_name":"Public Pilot Organization","personnel_range":"101–500"}
    })
    assert draft.status_code==200,draft.text

    logged_out=client.post("/public/protection-advisor/logout",headers=headers,json={})
    assert logged_out.status_code==200
    resumed=client.post("/public/protection-advisor/login",json={
        "email":"contact@example.com","password":"Correct-Horse-Battery-2026"
    })
    assert resumed.status_code==200,resumed.text
    resumed_payload=resumed.json()
    assert resumed_payload["draft"]["organization_name"]=="Public Pilot Organization"
    assert resumed_payload["draft"]["protected_member_code_name"]=="Blue Lantern"
    assert resumed_payload["draft"]["project_code_name"]=="Steady Harbor"
    headers={"X-CSRF-Token":resumed_payload["csrf_token"]}

    submitted=client.post("/public/protection-advisor/submit",headers=headers,json={
        "protected_member_code_name":"Blue Lantern",
        "project_code_name":"Steady Harbor",
        "handling_profile":"Federal CUI",
        "handling_authority":"Federal contract clause",
        "designating_agency":"Example Federal Agency",
        "contract_reference":"TASK-TEST-001",
        "dissemination_controls":"Authorized recipients only",
        "organization_name":"Public Pilot Organization",
        "contact_name":"Assessment Contact",
        "contact_email":"contact@example.com",
        "detailed_assessment_acknowledged":True,
        "identifiable_retention_consent":True,
        "facility_scope":"Several facilities",
        "facility_locations":"Central Texas",
        "personnel_range":"101–500",
        "affected_population_range":"501–2,500",
        "annual_revenue_range":"$25 million–$100 million",
        "specific_activities":[
            "Precious metals or other high-value materials",
            "Hazardous materials, fuels, chemicals, or regulated waste",
        ],
        "essential_functions":"Manufacturing and secure fulfillment",
        "maximum_tolerable_downtime":"4–24 hours",
        "existing_program_maturity":"Partially documented or inconsistently applied",
        "internal_implementation_capacity":"Need Salus implementation support",
        "primary_objective":"Facility or operational protection improvements",
        "external_requirements":"Insurance or underwriting concern",
        "recent_concerns":"Continuity and competing resources",
        "desired_timing":"Within 90 days",
        "decision_authority":"Executive leadership",
        "investment_range":"Need phased options",
    })
    assert submitted.status_code==200,submitted.text
    result=submitted.json()["result"]
    assert result["status"]=="Preliminary — Salus Review Required"
    package=submitted.json()["package"]
    assert package["version"]=="SPA-PACKAGE-RECOMMENDATION-2.0.0"
    assert 1<=len(package["services"])<=4
    assert all(item["level"] in {1,2,3} for item in package["services"])
    assert all(item["capabilities"] and item["why"] for item in package["services"])
    assert package["core_capabilities_considered"]==32
    assert package["sequence"]
    identity=submitted.json()["report_identity"]
    assert identity["protected_member_code_name"]=="Blue Lantern"
    assert identity["project_code_name"]=="Steady Harbor"
    assert identity["handling_profile"]=="Federal CUI"
    assert identity["handling_status"]=="Pending Salus Review"
    assert identity["revision_no"]==1
    notifications=submitted.json()["notifications"]
    assert {row["audience"] for row in notifications}=={"Participant","Salus Reviewer"}

    # The 24-hour advisor token is a security credential, not a result-retention limit.
    # Even after that token's stored expiry, a fresh account login must recover the
    # submitted result and exact package for the retained account record.
    conn=sqlite3.connect(db_path)
    conn.execute("UPDATE advisor_public_sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    conn.commit()
    conn.close()
    logged_out_after_submit=client.post("/public/protection-advisor/logout",headers=headers,json={})
    assert logged_out_after_submit.status_code==200
    retained=client.post("/public/protection-advisor/login",json={
        "email":"contact@example.com","password":"Correct-Horse-Battery-2026"
    })
    assert retained.status_code==200,retained.text
    retained_payload=retained.json()
    assert retained_payload["assessment_status"]=="Submitted"
    assert retained_payload["result"]==result
    assert retained_payload["package"]==package
    assert retained_payload["submitted_at"]
    assert retained_payload["report_identity"]["project_code_name"]=="Steady Harbor"
    headers={"X-CSRF-Token":retained_payload["csrf_token"]}

    revised=client.post("/public/protection-advisor/report-identity",headers=headers,json={
        "protected_member_code_name":"Blue Lantern",
        "project_code_name":"Steady Harbor Two",
        "handling_profile":"Commercial Confidential",
        "handling_authority":"","designating_agency":"","contract_reference":"",
        "dissemination_controls":"Authorized recipients only",
    })
    assert revised.status_code==200,revised.text
    revised_identity=revised.json()["report_identity"]
    assert revised_identity["revision_no"]==2
    assert revised_identity["project_code_name"]=="Steady Harbor Two"
    assert revised_identity["handling_status"]=="Approved by Default Policy"

    conn=sqlite3.connect(db_path)
    conn.row_factory=sqlite3.Row
    session=conn.execute("SELECT * FROM advisor_public_sessions").fetchone()
    submission=conn.execute("SELECT * FROM advisor_public_submissions").fetchone()
    profile=conn.execute("SELECT * FROM advisor_public_service_profiles").fetchone()
    account=conn.execute("SELECT * FROM advisor_public_accounts").fetchone()
    assert account["email"]=="contact@example.com"
    assert session["status"]=="Submitted"
    assert submission["questionnaire_version"]=="SPA-PUBLIC-QUESTIONNAIRE-2.0.0"
    assert profile["profile_version"]=="SPA-SERVICE-PROFILE-2.0.0"
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_profile_drafts").fetchone()[0]==0
    identity_rows=conn.execute("SELECT * FROM advisor_public_report_identity_revisions ORDER BY revision_no").fetchall()
    assert len(identity_rows)==2
    assert identity_rows[0]["project_code_name"]=="Steady Harbor"
    assert identity_rows[1]["project_code_name"]=="Steady Harbor Two"
    assert identity_rows[0]["content_sha256"]
    review_row=dict(submission)
    review_row["notification_state"]="Pending"
    submission_key=submission["submission_key"]
    conn.close()

    review_page_html=_review_page([review_row])
    review_detail_html=_review_detail(review_row,dict(identity_rows[-1]))
    assert "Public Pilot Organization" in review_page_html
    assert "Assessment Contact" in review_detail_html
    assert "Steady Harbor Two" in review_detail_html
    assert "Commercial Confidential" in review_detail_html
    assert '<header class="salus-header">' in review_page_html
    assert '<header class="salus-header">' in review_detail_html
    assert "font-size:56px" in review_page_html
    assert "font-size:56px" in review_detail_html

    # Different capability conditions and profile facts must produce different packages and levels.
    business_questions=_questions("Business")
    validated={q["key"]:{"answer_state":"Validated"} for q in business_questions}
    cyber_answers={k:dict(v) for k,v in validated.items()}
    for key in ("dependency_map","continuity","cyber_resilience","supplier_integrity"):
        cyber_answers[key]={"answer_state":"No"}
    threat_answers={k:dict(v) for k,v in validated.items()}
    for key in ("reporting","warning_thresholds","protective_controls"):
        threat_answers[key]={"answer_state":"No"}

    base_profile={
        "facility_scope":"One facility","personnel_range":"26–100",
        "affected_population_range":"101–500","specific_activities":[],
        "maximum_tolerable_downtime":"1–3 days",
        "existing_program_maturity":"Documented but not recently tested",
        "internal_implementation_capacity":"Shared or part-time personnel",
        "primary_objective":"Independent assessment and priorities",
        "external_requirements":"Future planning or budget decision",
        "desired_timing":"Within 90 days","decision_authority":"Executive leadership",
    }
    cyber_profile={**base_profile,
        "specific_activities":["Critical infrastructure, utilities, transportation, or logistics"],
        "maximum_tolerable_downtime":"Less than 4 hours",
        "primary_objective":"Continuity and recovery capability",
    }
    threat_profile={**base_profile,
        "specific_activities":["Public events, venues, hospitality, or mass gatherings"],
        "primary_objective":"Protective intelligence and monitoring",
        "external_requirements":"Recent incident or credible concern",
        "desired_timing":"Immediate concern",
    }
    cyber_package=_package_recommendation(business_questions,cyber_answers,cyber_profile)
    threat_package=_package_recommendation(business_questions,threat_answers,threat_profile)
    cyber_signature=[(x["key"],x["level"]) for x in cyber_package["services"]]
    threat_signature=[(x["key"],x["level"]) for x in threat_package["services"]]
    assert cyber_signature!=threat_signature
    assert "continuity" in {x["key"] for x in cyber_package["services"]}
    assert {"protective_intelligence","incident_support"} & {x["key"] for x in threat_package["services"]}

    deleted=client.post("/public/protection-advisor/delete",headers=headers,json={})
    assert deleted.status_code==200,deleted.text
    conn=sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_submissions").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_answer_revisions").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_notification_outbox").fetchone()[0]==0
    assert conn.execute("SELECT COUNT(*) FROM advisor_public_service_profiles").fetchone()[0]==0
    assert conn.execute("SELECT status FROM advisor_public_sessions").fetchone()[0]=="Deleted"
    conn.close()


# Exercise the repository's approved Word template through the production renderer.
# This guards against template page boundaries that are represented as Word
# section breaks rather than explicit page-break runs.
from protection_advisor_docx_report import render_protection_advisor_docx
from salcapa_m365_advisor_reports import _trusted_pdf_conversion_url
from protection_advisor_report_contract import build_report_context
from docx import Document

assert _trusted_pdf_conversion_url("https://eastus1-mediap.svc.ms/transform/pdf?provider=spo")
assert _trusted_pdf_conversion_url("https://salussolutions.sharepoint.com/download/report.pdf")
assert not _trusted_pdf_conversion_url("https://example.com/report.pdf")

with tempfile.TemporaryDirectory() as report_td:
    report_path = Path(report_td) / "acceptance.docx"
    render_protection_advisor_docx(
        template_path=ROOT / "Protection Advisor Report Template.docx",
        output_path=report_path,
        context=build_report_context(
            client_code_name="Acceptance Member",
            project_code_name="Acceptance Project",
            organization_type="Business",
            government_or_public_service_role="Not provided",
            assessment_authority_or_sponsor="Salus reviewer",
            information_handling="Confidential",
            report_reference="SPA-REPORT-CI-ACCEPTANCE",
            generated_at=datetime.now(timezone.utc),
        ),
        part1_text="Part 1 acceptance content",
        part2_text="Part 2 acceptance content",
    )
    rendered = Document(report_path)
    assert len(rendered.sections) >= 3
    rendered_text = [paragraph.text for paragraph in rendered.paragraphs]
    rendered_text.extend(
        paragraph.text
        for table in rendered.tables
        for row in table.rows
        for cell in row.cells
        for paragraph in cell.paragraphs
    )
    assert "Protection Advisor Assessment Report" in "\n".join(rendered_text)

    results_footer = rendered.sections[-1].footer
    image_relationships = [
        relationship
        for relationship in results_footer.part.rels.values()
        if relationship.reltype.endswith("/image")
    ]
    assert image_relationships, "results footer lost the template logo relationship"
    embedded_ids = set(results_footer._element.xpath(".//@r:embed"))
    assert embedded_ids <= set(results_footer.part.rels), (
        "results footer contains an unresolved embedded-image relationship"
    )

print("public Protection Advisor smoke passed")
