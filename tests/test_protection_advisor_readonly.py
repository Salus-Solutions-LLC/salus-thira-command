"""Read-only boundary and source-completeness tests with fictional records only."""
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import protection_advisor_readonly as reader
from public_protection_advisor import _initialize


SESSION = "SPA-SESSION-" + "A" * 32
SUBMISSION = "SPA-SUBMISSION-" + "B" * 32
ANONYMOUS = "SPA-SESSION-" + "C" * 32
DELETED = "SPA-SESSION-" + "D" * 32
TOKEN = "fictional-test-credential-" + "z" * 40
BASE = "https://salcapa.example.test"


@pytest.fixture
def setup_reader(tmp_path, monkeypatch):
    path = tmp_path / "source.db"
    postgres = os.getenv("SALUS_ADVISOR_MCP_TEST_POSTGRES") == "1"
    schema = "advisor_reader_test_" + uuid.uuid4().hex
    if postgres:
        from database import PostgresConnection
        admin = PostgresConnection(os.environ["SALUS_DATABASE_URL"])
        admin.execute(f'CREATE SCHEMA "{schema}"')
        admin.commit()
        admin.close()

    def db():
        if postgres:
            conn = PostgresConnection(os.environ["SALUS_DATABASE_URL"])
            conn.execute(f'SET search_path TO "{schema}"')
            conn.commit()
            return conn
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = db()
    _initialize(conn)
    conn.execute("""CREATE TABLE security_events(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id INTEGER,ts TEXT,event_type TEXT,
        severity TEXT,user_name TEXT,source_ip TEXT,request_id TEXT,detail TEXT)""")
    for index, key in enumerate((SESSION, ANONYMOUS, DELETED)):
        conn.execute("INSERT INTO advisor_public_sessions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            key, "secret-token-hash-" + str(index), "secret-csrf-hash", "Faith-Based Organization",
            1, 0, "CONSENT-1", "RETENTION-1", "QUESTIONNAIRE-1", "Submitted" if key == SESSION else "Active",
            "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "2026-01-02T00:00:00Z", "gone" if key == DELETED else "",
        ))
    snapshot = json.dumps({"continuity": {"answer_state": "Partially", "note": "Fictional retained note", "revision_no": 2}})
    profile = json.dumps({"facility_locations": "Fictional site", "essential_functions": "Fictional function", "decision_authority": "Fictional director", "unrecognized_future_field": {"retain": True}})
    package = json.dumps({"recommendation": "Original retained recommendation", "version": "ORIGINAL-1"})
    conn.execute("INSERT INTO advisor_public_submissions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        SUBMISSION, SESSION, "Example House", "Fictional Contact", "fiction@example.test", snapshot,
        hashlib.sha256(snapshot.encode()).hexdigest(), "QUESTIONNAIRE-1", "RESULT-1", "CONSENT-1", "RETENTION-1",
        0, json.dumps({"recommendation": "Original result"}), "Awaiting Salus Review", "2026-01-02T00:00:00Z"))
    conn.execute("INSERT INTO advisor_public_service_profiles VALUES(?,?,?,?,?,?,?,?)", (
        "profile-1", SUBMISSION, "PROFILE-1", profile, hashlib.sha256(profile.encode()).hexdigest(), "PACKAGE-1", package, "2026-01-02T00:00:00Z"))
    conn.execute("INSERT INTO advisor_public_accounts VALUES(?,?,?,?,?,?,?,?)", (
        "account-1", "fiction@example.test", "must-not-return-salt", "must-not-return-password", "Active", "created", "", "verified"))
    conn.execute("INSERT INTO advisor_public_account_assessments VALUES(?,?,?,?,?)", ("account-1", SESSION, 1, 1, "acknowledged"))
    for revision in range(1, 4):
        conn.execute("INSERT INTO advisor_public_answer_revisions VALUES(?,?,?,?,?,?,?,?)", (
            "revision-" + str(revision), SESSION, "continuity", revision, "Partially", "Fictional note " + str(revision), "created", "history-hash"))
    conn.execute("INSERT INTO advisor_public_profile_drafts VALUES(?,?,?,?)", (ANONYMOUS, "account-1", '{"draft":"unfinished"}', "updated"))
    conn.commit()
    conn.close()
    monkeypatch.setenv("SALUS_ADVISOR_MCP_ENABLED", "1")
    monkeypatch.setenv("SALUS_ADVISOR_MCP_BASE_URL", BASE)
    monkeypatch.setenv("SALUS_ADVISOR_MCP_WORKSPACE_ID", reader.WORKSPACE_ID)
    monkeypatch.setenv("SALUS_ADVISOR_MCP_EXPIRES_AT", (datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    app = FastAPI()
    reader.register_advisor_readonly(app, {"db": db, "secret": lambda *_: hashlib.sha256(TOKEN.encode()).hexdigest()})
    client = TestClient(app, base_url=BASE, headers={"Authorization": "Bearer " + TOKEN})
    try:
        yield client, db
    finally:
        client.close()
        if postgres:
            admin = PostgresConnection(os.environ["SALUS_DATABASE_URL"])
            admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
            admin.commit()
            admin.close()


def rpc(client, method="tools/call", **params):
    return client.post(reader.ENDPOINT, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})


def fetch(client, **args):
    return rpc(client, name="fetch", arguments={"id": SUBMISSION, **args}).json()


def content(response):
    return json.loads(response["result"]["content"][0]["text"])


def test_complete_original_part2_and_answer_notes_no_auth_material(setup_reader):
    client, db = setup_reader
    response = fetch(client)
    data = content(response)
    assert data["answer_snapshot"]["continuity"]["note"] == "Fictional retained note"
    assert data["part2_profile"]["unrecognized_future_field"] == {"retain": True}
    assert data["part2_package"]["version"] == "ORIGINAL-1"
    assert data["part2_consent"]["identifiable_retention_consent"] == 1
    assert data["related_record_counts"]["answers"] == 3
    assert not data["assessment_started"]
    assert "secret-token" not in str(data) and "password" not in str(data) and "csrf" not in str(data)
    conn = db()
    assert conn.execute("SELECT status FROM advisor_public_submissions").fetchone()[0] == "Awaiting Salus Review"
    audit = conn.execute("SELECT * FROM security_events").fetchone()
    assert audit["event_type"] == "ADVISOR_MCP_READ"
    assert "Example House" not in audit["detail"] and SUBMISSION not in audit["detail"] and TOKEN not in str(dict(audit))
    conn.close()


def test_discovery_exposes_only_read_tools_and_no_mutation(setup_reader):
    client, _ = setup_reader
    initialized = rpc(client, "initialize", protocolVersion="2025-06-18").json()["result"]
    assert initialized["protocolVersion"] == "2025-06-18"
    tools = rpc(client, "tools/list").json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {"search", "fetch", "fetch_original"}
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)
    assert rpc(client, name="generate_report", arguments={}).json()["error"]["code"] == -32602
    assert rpc(client, "resources/subscribe").json()["error"]["code"] == -32601


@pytest.mark.parametrize("changes,status", [
    ({"SALUS_ADVISOR_MCP_ENABLED": "0"}, 404),
    ({"SALUS_ADVISOR_MCP_WORKSPACE_ID": "other-workspace"}, 503),
    ({"SALUS_ADVISOR_MCP_EXPIRES_AT": "2020-01-01T00:00:00Z"}, 503),
    ({"SALUS_ADVISOR_MCP_EXPIRES_AT": "2099-01-01"}, 503),
    ({"SALUS_ADVISOR_MCP_BASE_URL": "http://salcapa.example.test"}, 503),
])
def test_incomplete_expired_or_disabled_connection_fails_closed(setup_reader, monkeypatch, changes, status):
    client, _ = setup_reader
    for name, value in changes.items():
        monkeypatch.setenv(name, value)
    assert rpc(client, "tools/list").status_code == status


def test_cookie_prototype_headers_and_bad_bearer_do_not_grant_access(setup_reader):
    client, _ = setup_reader
    client.headers.pop("authorization")
    client.headers.update({"X-Salus-Role": "System Administrator", "Cookie": "salus_session=fictional"})
    assert rpc(client, "tools/list").status_code == 401
    client.headers["authorization"] = "Bearer " + "wrong" * 10
    assert rpc(client, "tools/list").status_code == 401


def test_origin_host_transport_and_request_limits(setup_reader):
    client, _ = setup_reader
    assert client.post(reader.ENDPOINT, headers={"Origin": "https://attacker.example"}, json={}).status_code == 403
    assert client.post(reader.ENDPOINT, headers={"Host": "attacker.example"}, json={}).status_code == 403
    assert client.post(reader.ENDPOINT, headers={"mcp-protocol-version": "unknown"}, json={}).status_code == 400
    assert client.post(reader.ENDPOINT, content="x", headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.post(reader.ENDPOINT, content="x" * 17000, headers={"Content-Type": "application/json"}).status_code == 413
    assert client.post(reader.ENDPOINT, content="{", headers={"Content-Type": "application/json"}).json()["error"]["code"] == -32700
    assert client.get(reader.ENDPOINT).status_code == 405


def test_search_literal_wildcards_pagination_and_deleted_boundary(setup_reader):
    client, _ = setup_reader
    data = content(rpc(client, name="search", arguments={"query": "example"}).json())
    assert [row["id"] for row in data["results"]] == [SUBMISSION]
    assert content(rpc(client, name="search", arguments={"query": "%"}).json())["results"] == []
    assert content(rpc(client, name="search", arguments={"query": "' OR 1=1 --"}).json())["results"] == []
    first = content(rpc(client, name="search", arguments={"query": "", "kind": "sessions", "limit": 1}).json())
    second = content(rpc(client, name="search", arguments={"query": "", "kind": "sessions", "limit": 1, "after": first["next_after"]}).json())
    assert [first["results"][0]["id"], second["results"][0]["id"]] == [SESSION, ANONYMOUS]
    assert second["next_after"] is None
    assert "error" in fetch(client, id=DELETED)
    assert "error" in fetch(client, id=SUBMISSION + "' OR 1=1")


def test_missing_part2_and_draft_are_explicit(setup_reader):
    client, _ = setup_reader
    data = content(fetch(client, id=ANONYMOUS))
    assert data["part2_profile"] is None
    assert "do not infer completion" in data["part2_status"]
    draft = content(fetch(client, id=ANONYMOUS, section="draft"))
    assert draft["items"][0]["status"].startswith("Unsubmitted draft")


def test_history_is_paginated_and_content_is_not_truncated(setup_reader):
    client, _ = setup_reader
    first = content(fetch(client, section="answers", limit=2))
    assert [r["revision_no"] for r in first["items"]] == [1, 2]
    assert first["next_offset"] == 2
    last = content(fetch(client, section="answers", limit=2, offset=2))
    assert [r["revision_no"] for r in last["items"]] == [3]
    assert last["next_offset"] is None


@pytest.mark.parametrize("column,table", [("answer_snapshot_json", "advisor_public_submissions"), ("profile_json", "advisor_public_service_profiles")])
def test_corrupt_source_hash_returns_no_record_data(setup_reader, column, table):
    client, db = setup_reader
    conn = db()
    conn.execute(f"UPDATE {table} SET {column}='{{\"corrupt\":true}}'")
    conn.commit()
    conn.close()
    result = fetch(client)
    assert "result" not in result and "integrity" in result["error"]["message"]


def test_business_database_is_enforced_readonly(setup_reader, monkeypatch):
    client, db = setup_reader

    def malicious_query(conn, *_):
        conn.execute("UPDATE advisor_public_submissions SET status='Changed'")
        return {}

    monkeypatch.setattr(reader, "search_records", malicious_query)
    assert "error" in rpc(client, name="search", arguments={"query": "Example"}).json()
    conn = db()
    assert conn.execute("SELECT status FROM advisor_public_submissions").fetchone()[0] == "Awaiting Salus Review"
    conn.close()


def test_missing_audit_sink_fails_closed_without_source_disclosure(setup_reader):
    client, db = setup_reader
    conn = db()
    conn.execute("DROP TABLE security_events")
    conn.commit()
    conn.close()
    result = fetch(client)
    assert "result" not in result
    assert result["error"]["code"] == -32603


def test_oversize_response_is_not_silently_truncated(setup_reader, monkeypatch):
    client, _ = setup_reader
    monkeypatch.setattr(reader, "MAX_BYTES", 100)
    result = fetch(client)
    assert "result" not in result and "exceeds response limit" in result["error"]["message"]


def test_no_sensitive_request_is_executed_as_notification(setup_reader):
    client, _ = setup_reader
    assert client.post(reader.ENDPOINT, json={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "fetch", "arguments": {"id": SUBMISSION}}}).status_code == 400
    assert client.post(reader.ENDPOINT, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202


def test_original_pdf_verification_and_page_provenance(setup_reader, monkeypatch):
    import io
    from reportlab.pdfgen.canvas import Canvas
    import protection_advisor_member_reports

    client, db = setup_reader
    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(72, 720, "Fictional retained original")
    canvas.showPage()
    canvas.drawString(72, 720, "Fictional second page")
    canvas.save()
    original = stream.getvalue()
    conn = db()
    conn.execute("INSERT INTO advisor_public_member_report_snapshots VALUES(?,?,?,?,?,?,?,?)", (SESSION, 1, "PACKAGE-ORIGINAL", "TEMPLATE-ORIGINAL", "original-item-1", hashlib.sha256(original).hexdigest(), len(original), "created"))
    conn.commit()
    conn.close()
    calls = []

    def read_bytes(item_id, digest, size):
        calls.append((item_id, digest, size))
        return original

    monkeypatch.setattr(protection_advisor_member_reports, "read_member_pdf", read_bytes)
    result = content(rpc(client, name="fetch_original", arguments={"id": SUBMISSION, "kind": "member_report", "revision": 1, "limit": 1}).json())
    assert result["original_bytes_verified"] and not result["regenerated"]
    assert result["next_page"] == 2 and result["page_count"] == 2
    assert "Fictional retained original" in result["pages"][0]["text"]
    assert calls[0][0] == "original-item-1"
    monkeypatch.setattr(protection_advisor_member_reports, "read_member_pdf", lambda *_: b"corrupt")
    response = rpc(client, name="fetch_original", arguments={"id": SUBMISSION, "kind": "member_report", "revision": 1}).json()
    assert "result" not in response and "integrity" in response["error"]["message"]
    assert "error" in rpc(client, name="fetch_original", arguments={"id": SUBMISSION, "kind": "member_report", "revision": 2}).json()
