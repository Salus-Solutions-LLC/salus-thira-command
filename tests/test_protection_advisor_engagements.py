import sqlite3

from protection_advisor_engagements import (
    create_assessment_scope,
    initialize_engagement_schema,
    list_account_assessments,
)


def _database():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE advisor_public_accounts (account_key TEXT PRIMARY KEY);
        CREATE TABLE advisor_public_sessions (
          session_key TEXT PRIMARY KEY,
          organization_type TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          submitted_at TEXT NOT NULL DEFAULT '',
          deleted_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE advisor_public_account_assessments (
          account_key TEXT NOT NULL,
          session_key TEXT NOT NULL UNIQUE,
          detailed_assessment_acknowledged INTEGER NOT NULL,
          identifiable_retention_consent INTEGER NOT NULL,
          acknowledged_at TEXT NOT NULL,
          PRIMARY KEY (account_key,session_key)
        );
        """
    )
    initialize_engagement_schema(conn)
    conn.execute("INSERT INTO advisor_public_accounts VALUES('SPA-ACCOUNT-1')")
    return conn


def _add_session(conn, key):
    conn.execute(
        "INSERT INTO advisor_public_sessions VALUES(?,?,?,?,?,?)",
        (key, "Business", "Submitted", "2026-09-22T12:00:00Z", "2026-09-22T13:00:00Z", ""),
    )
    conn.execute(
        "INSERT INTO advisor_public_account_assessments VALUES(?,?,?,?,?)",
        ("SPA-ACCOUNT-1", key, 1, 1, "2026-09-22T12:30:00Z"),
    )


def test_one_relationship_supports_multiple_scoped_engagements():
    conn = _database()
    _add_session(conn, "SPA-SESSION-1")
    _add_session(conn, "SPA-SESSION-2")
    first = create_assessment_scope(
        conn,
        account_key="SPA-ACCOUNT-1",
        session_key="SPA-SESSION-1",
        organization_name="Acme Energy LLC",
        organization_type="Business",
        project_name="Houston Protection Review",
        location_description="Houston Headquarters",
        functional_area="Executive Protection",
        objective="Independent assessment and priorities",
        created_at="2026-09-22T13:00:00Z",
    )
    second = create_assessment_scope(
        conn,
        account_key="SPA-ACCOUNT-1",
        session_key="SPA-SESSION-2",
        organization_name="Acme Logistics LLC",
        organization_type="Business",
        project_name="Gulf Operations Review",
        location_description="Three Gulf Coast sites",
        functional_area="Continuity and Recovery",
        objective="Continuity and recovery capability",
        created_at="2026-09-22T14:00:00Z",
    )
    assert first["portfolio_key"] == second["portfolio_key"]
    assert first["engagement_key"] != second["engagement_key"]
    assessments = list_account_assessments(conn, "SPA-ACCOUNT-1")
    assert [item["engagement_name"] for item in assessments] == [
        "Gulf Operations Review", "Houston Protection Review"
    ]
    assert {item["organization_name"] for item in assessments} == {
        "Acme Energy LLC", "Acme Logistics LLC"
    }


def test_scope_creation_is_idempotent_for_one_assessment():
    conn = _database()
    _add_session(conn, "SPA-SESSION-1")
    kwargs = dict(
        account_key="SPA-ACCOUNT-1",
        session_key="SPA-SESSION-1",
        organization_name="Acme Energy LLC",
        organization_type="Business",
        project_name="Houston Protection Review",
        location_description="Houston Headquarters",
        functional_area="Executive Protection",
        objective="Independent assessment and priorities",
        created_at="2026-09-22T13:00:00Z",
    )
    first = create_assessment_scope(conn, **kwargs)
    second = create_assessment_scope(conn, **kwargs)
    assert first["engagement_key"] == second["engagement_key"]
    assert conn.execute("SELECT COUNT(*) FROM advisor_relationship_engagements").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM advisor_relationship_assessments").fetchone()[0] == 1
