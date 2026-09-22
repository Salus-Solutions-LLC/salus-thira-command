"""Protected Member relationship and engagement foundation for Protection Advisor.

The public Advisor remains isolated from governed Protected Member tenants.  These
records describe a prospective relationship until an authorized Salus onboarding
decision promotes them through the normal SalCAPA process.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any


def _key(prefix: str) -> str:
    return prefix + secrets.token_hex(16).upper()


def initialize_engagement_schema(conn: Any) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS advisor_relationship_portfolios (
          portfolio_key TEXT PRIMARY KEY,
          display_name TEXT NOT NULL,
          relationship_status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS advisor_relationship_memberships (
          portfolio_key TEXT NOT NULL,
          account_key TEXT NOT NULL,
          role_name TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (portfolio_key,account_key),
          FOREIGN KEY (portfolio_key) REFERENCES advisor_relationship_portfolios(portfolio_key) ON DELETE CASCADE,
          FOREIGN KEY (account_key) REFERENCES advisor_public_accounts(account_key) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_advisor_relationship_membership_account
          ON advisor_relationship_memberships(account_key,status);
        CREATE TABLE IF NOT EXISTS advisor_relationship_organizations (
          organization_key TEXT PRIMARY KEY,
          portfolio_key TEXT NOT NULL,
          parent_organization_key TEXT,
          organization_name TEXT NOT NULL,
          organization_type TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (portfolio_key) REFERENCES advisor_relationship_portfolios(portfolio_key) ON DELETE CASCADE,
          FOREIGN KEY (parent_organization_key) REFERENCES advisor_relationship_organizations(organization_key) ON DELETE RESTRICT
        );
        CREATE INDEX IF NOT EXISTS idx_advisor_relationship_org_portfolio
          ON advisor_relationship_organizations(portfolio_key,status);
        CREATE TABLE IF NOT EXISTS advisor_relationship_locations (
          location_key TEXT PRIMARY KEY,
          portfolio_key TEXT NOT NULL,
          organization_key TEXT,
          location_name TEXT NOT NULL,
          location_description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (portfolio_key) REFERENCES advisor_relationship_portfolios(portfolio_key) ON DELETE CASCADE,
          FOREIGN KEY (organization_key) REFERENCES advisor_relationship_organizations(organization_key) ON DELETE RESTRICT
        );
        CREATE INDEX IF NOT EXISTS idx_advisor_relationship_location_portfolio
          ON advisor_relationship_locations(portfolio_key,status);
        CREATE TABLE IF NOT EXISTS advisor_relationship_functional_areas (
          functional_area_key TEXT PRIMARY KEY,
          portfolio_key TEXT NOT NULL,
          area_name TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (portfolio_key) REFERENCES advisor_relationship_portfolios(portfolio_key) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_advisor_relationship_function_portfolio
          ON advisor_relationship_functional_areas(portfolio_key,status);
        CREATE TABLE IF NOT EXISTS advisor_relationship_engagements (
          engagement_key TEXT PRIMARY KEY,
          portfolio_key TEXT NOT NULL,
          engagement_name TEXT NOT NULL,
          engagement_type TEXT NOT NULL,
          objective TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY (portfolio_key) REFERENCES advisor_relationship_portfolios(portfolio_key) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_advisor_relationship_engagement_portfolio
          ON advisor_relationship_engagements(portfolio_key,status);
        CREATE TABLE IF NOT EXISTS advisor_relationship_engagement_scope (
          engagement_key TEXT NOT NULL,
          scope_type TEXT NOT NULL,
          scope_key TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (engagement_key,scope_type,scope_key),
          FOREIGN KEY (engagement_key) REFERENCES advisor_relationship_engagements(engagement_key) ON DELETE CASCADE,
          CHECK (scope_type IN ('Organization','Location','Functional Area'))
        );
        CREATE TABLE IF NOT EXISTS advisor_relationship_assessments (
          session_key TEXT PRIMARY KEY,
          engagement_key TEXT NOT NULL,
          assessment_type TEXT NOT NULL,
          assessment_status TEXT NOT NULL,
          scope_snapshot_json TEXT NOT NULL,
          scope_snapshot_sha256 TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY (session_key) REFERENCES advisor_public_sessions(session_key) ON DELETE RESTRICT,
          FOREIGN KEY (engagement_key) REFERENCES advisor_relationship_engagements(engagement_key) ON DELETE RESTRICT
        );
        CREATE INDEX IF NOT EXISTS idx_advisor_relationship_assessment_engagement
          ON advisor_relationship_assessments(engagement_key,created_at);
        """
    )


def ensure_account_portfolio(
    conn: Any, *, account_key: str, display_name: str, created_at: str
) -> str:
    row = conn.execute(
        """SELECT p.portfolio_key FROM advisor_relationship_portfolios p
             JOIN advisor_relationship_memberships m ON m.portfolio_key=p.portfolio_key
            WHERE m.account_key=? AND m.status='Active'
            ORDER BY m.created_at LIMIT 1""",
        (account_key,),
    ).fetchone()
    if row:
        return str(row["portfolio_key"])
    portfolio_key = _key("SPA-PORTFOLIO-")
    conn.execute(
        "INSERT INTO advisor_relationship_portfolios VALUES(?,?,?,?,?)",
        (portfolio_key, display_name, "Prospective", created_at, created_at),
    )
    conn.execute(
        "INSERT INTO advisor_relationship_memberships VALUES(?,?,?,?,?)",
        (portfolio_key, account_key, "Relationship Owner", "Active", created_at),
    )
    return portfolio_key


def create_assessment_scope(
    conn: Any,
    *,
    account_key: str,
    session_key: str,
    organization_name: str,
    organization_type: str,
    project_name: str,
    location_description: str,
    functional_area: str,
    objective: str,
    created_at: str,
) -> dict[str, str]:
    """Create one engagement scope and link an assessment exactly once."""
    existing = conn.execute(
        "SELECT engagement_key,scope_snapshot_json FROM advisor_relationship_assessments WHERE session_key=?",
        (session_key,),
    ).fetchone()
    if existing:
        snapshot = json.loads(existing["scope_snapshot_json"])
        snapshot["engagement_key"] = existing["engagement_key"]
        return snapshot

    portfolio_key = ensure_account_portfolio(
        conn, account_key=account_key, display_name=organization_name, created_at=created_at
    )
    organization_key = _key("SPA-ORG-")
    location_key = _key("SPA-LOCATION-")
    functional_area_key = _key("SPA-FUNCTION-")
    engagement_key = _key("SPA-ENGAGEMENT-")
    conn.execute(
        "INSERT INTO advisor_relationship_organizations VALUES(?,?,?,?,?,?,?,?)",
        (organization_key, portfolio_key, None, organization_name, organization_type,
         "Prospective", created_at, created_at),
    )
    conn.execute(
        "INSERT INTO advisor_relationship_locations VALUES(?,?,?,?,?,?,?,?)",
        (location_key, portfolio_key, organization_key, "Assessment scope",
         location_description, "Active", created_at, created_at),
    )
    conn.execute(
        "INSERT INTO advisor_relationship_functional_areas VALUES(?,?,?,?,?,?)",
        (functional_area_key, portfolio_key, functional_area or "Enterprise protection and resilience",
         "Active", created_at, created_at),
    )
    conn.execute(
        "INSERT INTO advisor_relationship_engagements VALUES(?,?,?,?,?,?,?,?)",
        (engagement_key, portfolio_key, project_name, "Protection Advisor",
         objective, "Prospective", created_at, created_at),
    )
    for scope_type, scope_key in (
        ("Organization", organization_key),
        ("Location", location_key),
        ("Functional Area", functional_area_key),
    ):
        conn.execute(
            "INSERT INTO advisor_relationship_engagement_scope VALUES(?,?,?,?)",
            (engagement_key, scope_type, scope_key, created_at),
        )
    snapshot = {
        "portfolio_key": portfolio_key,
        "organization_key": organization_key,
        "organization_name": organization_name,
        "organization_type": organization_type,
        "location_key": location_key,
        "location_description": location_description,
        "functional_area_key": functional_area_key,
        "functional_area": functional_area or "Enterprise protection and resilience",
        "engagement_key": engagement_key,
        "engagement_name": project_name,
        "objective": objective,
    }
    snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    conn.execute(
        "INSERT INTO advisor_relationship_assessments VALUES(?,?,?,?,?,?,?)",
        (session_key, engagement_key, "Protection Advisor", "Active", snapshot_json,
         hashlib.sha256(snapshot_json.encode()).hexdigest(), created_at),
    )
    return snapshot


def list_account_assessments(conn: Any, account_key: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT s.session_key,s.organization_type,s.status,s.created_at,s.submitted_at,
                  a.engagement_key,a.scope_snapshot_json
             FROM advisor_public_account_assessments aa
             JOIN advisor_public_sessions s ON s.session_key=aa.session_key
        LEFT JOIN advisor_relationship_assessments a ON a.session_key=s.session_key
            WHERE aa.account_key=? AND s.deleted_at=''
            ORDER BY COALESCE(a.created_at,NULLIF(s.submitted_at,''),s.created_at) DESC""",
        (account_key,),
    ).fetchall()
    result = []
    for row in rows:
        scope = json.loads(row["scope_snapshot_json"]) if row["scope_snapshot_json"] else {}
        result.append({
            "session_key": row["session_key"],
            "engagement_key": row["engagement_key"] or "",
            "engagement_name": scope.get("engagement_name", "Unscoped assessment"),
            "organization_name": scope.get("organization_name", "Not yet provided"),
            "functional_area": scope.get("functional_area", "Not yet provided"),
            "organization_type": row["organization_type"],
            "status": row["status"],
            "created_at": row["created_at"],
            "submitted_at": row["submitted_at"],
        })
    return result
