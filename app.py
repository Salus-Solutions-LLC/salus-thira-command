from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from typing import Optional, Any, Literal
from decimal import Decimal, ROUND_HALF_UP
import sqlite3, json, os, hashlib, re, secrets, zipfile, shutil, tempfile, csv, io, html, uuid, subprocess
import urllib.parse
import httpx, jwt
from azure.identity import ManagedIdentityCredential
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from storage import build_storage, StorageError
from security_controls import scan_bytes, retention_active, scanner_configuration, AV_MODE, AV_REQUIRED
from secret_provider import secret, readiness as secret_readiness
from salus_package_path import validate_requested_package_path
from salus_package_quote import validate_quote, quote_digest, assessment_scope_digest
from salus_package_intake import CATALOG_VERSION as PACKAGE_INTAKE_VERSION, ITEMS as PACKAGE_INTAKE_ITEMS, catalog_rows as package_intake_catalog
from rate_limit import RateLimiter
from telemetry import emit as telemetry_emit, readiness as telemetry_readiness
from managed_database import runtime_database_status, managed_target_status
from database import connect_database, backend_name, is_sqlite, is_postgres
from portable_backup import collect_tenant_records, validate_records, replace_tenant_records

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.getenv('SALUS_DB_PATH', os.path.join(BASE_DIR, 'thira.db'))
DB_BACKEND = backend_name()
if DB_BACKEND == 'sqlite': os.makedirs(os.path.dirname(DB_PATH) or BASE_DIR, exist_ok=True)
ATTACHMENTS_DIR = os.getenv('SALUS_LOCAL_STORAGE_DIR', os.path.join(BASE_DIR, 'attachments'))
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
STORAGE_BACKEND = os.getenv('SALUS_STORAGE_BACKEND','local').strip().lower()
storage = build_storage(BASE_DIR)
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024
BACKUPS_DIR = os.getenv('SALUS_BACKUP_DIR', os.path.join(BASE_DIR, 'backups'))
os.makedirs(BACKUPS_DIR, exist_ok=True)
AUTH_MODE = os.getenv('SALUS_AUTH_MODE', 'prototype').strip().lower()
SESSION_HOURS = int(os.getenv('SALUS_SESSION_HOURS', '12'))
ALLOW_RESTORE = os.getenv('SALUS_ALLOW_RESTORE', '0').lower() in ('1','true','yes')
COOKIE_SECURE = os.getenv('SALUS_COOKIE_SECURE', '0').lower() in ('1','true','yes')
ENVIRONMENT = os.getenv('SALUS_ENV','development').strip().lower()
PACKAGE_COMMERCIAL_WORKFLOW_ENABLED = os.getenv('SALUS_PACKAGE_COMMERCIAL_WORKFLOW_ENABLED','0').lower() in ('1','true','yes')
RETENTION_DEFAULT_DAYS = int(os.getenv('SALUS_RETENTION_DEFAULT_DAYS','2555'))
OIDC_DISCOVERY_URL = os.getenv('SALUS_OIDC_DISCOVERY_URL','').strip()
OIDC_CLIENT_ID = os.getenv('SALUS_OIDC_CLIENT_ID','').strip()
OIDC_CLIENT_AUTH_METHOD = os.getenv('SALUS_OIDC_CLIENT_AUTH_METHOD','client_secret').strip().lower()
OIDC_CLIENT_SECRET = (
    ''
    if OIDC_CLIENT_AUTH_METHOD == 'managed_identity'
    else secret('SALUS_OIDC_CLIENT_SECRET','').strip()
)
OIDC_TENANT_ID = os.getenv('SALUS_OIDC_TENANT_ID','').strip()
OIDC_MANAGED_IDENTITY_CLIENT_ID = os.getenv('SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID','').strip()
OIDC_REDIRECT_URI = os.getenv('SALUS_OIDC_REDIRECT_URI','').strip()
OIDC_DEFAULT_TENANT_SLUG = os.getenv('SALUS_OIDC_DEFAULT_TENANT_SLUG','salus-prototype').strip()
OIDC_AUTO_PROVISION = os.getenv('SALUS_OIDC_AUTO_PROVISION','0').lower() in ('1','true','yes')
OIDC_SCOPES = os.getenv('SALUS_OIDC_SCOPES','openid profile email').strip()
OIDC_PROVIDER_NAME = os.getenv('SALUS_OIDC_PROVIDER_NAME','oidc').strip() or 'oidc'
OIDC_STATE_MINUTES = int(os.getenv('SALUS_OIDC_STATE_MINUTES','10'))
ALLOW_SQLITE_PRODUCTION = os.getenv('SALUS_ALLOW_SQLITE_PRODUCTION','0').lower() in ('1','true','yes')
SEED_DEMO = os.getenv('SALUS_SEED_DEMO','1' if ENVIRONMENT!='production' else '0').lower() in ('1','true','yes')
RATE_LIMITER = RateLimiter()

APP_VERSION = '1.16.0'
RISK_METHODOLOGY_VERSION = '1.1.0'

app = FastAPI(title='SalCAPA', version=APP_VERSION)
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'static')), name='static')


def now():
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def db():
    return connect_database()


def record_internal_failure(component: str, error_id: str, exc: Exception) -> None:
    """Record a correlation ID and exception class without retaining sensitive detail."""
    try:
        telemetry_emit('INTERNAL_FAILURE','High',tenant_id=None,user_name='system',source_ip='',request_id=error_id,detail=f'{component}: {type(exc).__name__}'[:2000])
    except Exception:
        pass


def audit(conn, action: str, entity_type: str, entity_id: int | None, detail: str = '', user_name: str = 'prototype-user'):
    tenant=1
    try:
        fn=globals().get('infer_tenant'); tenant=fn(conn,entity_type,entity_id) if fn else 1
    except Exception:
        pass
    cols={r['name'] for r in conn.execute('PRAGMA table_info(audit_log)')}
    if 'tenant_id' in cols:
        conn.execute('INSERT INTO audit_log(ts, user_name, action, entity_type, entity_id, detail, tenant_id) VALUES(?,?,?,?,?,?,?)',(now(),user_name,action,entity_type,entity_id,detail,tenant))
    else:
        conn.execute('INSERT INTO audit_log(ts, user_name, action, entity_type, entity_id, detail) VALUES(?,?,?,?,?,?)',(now(),user_name,action,entity_type,entity_id,detail))


def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS tenants (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      slug TEXT NOT NULL UNIQUE,
      status TEXT NOT NULL DEFAULT 'Active',
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      username TEXT NOT NULL UNIQUE,
      display_name TEXT NOT NULL DEFAULT '',
      password_hash TEXT NOT NULL DEFAULT '',
      role TEXT NOT NULL DEFAULT 'Contributor',
      sensitivity_clearance TEXT NOT NULL DEFAULT 'Standard',
      status TEXT NOT NULL DEFAULT 'Active',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS auth_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      token_hash TEXT NOT NULL UNIQUE,
      expires_at TEXT NOT NULL,
      created_at TEXT NOT NULL,
      last_seen_at TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS identity_acceptance_events (
      event_key TEXT PRIMARY KEY,
      tenant_id INTEGER NOT NULL,
      user_id INTEGER NOT NULL,
      identity_provider TEXT NOT NULL,
      external_subject_sha256 TEXT NOT NULL,
      mapped_role TEXT NOT NULL,
      mapped_clearance TEXT NOT NULL,
      authority_source TEXT NOT NULL,
      authentication_method TEXT NOT NULL,
      oidc_issuer_sha256 TEXT NOT NULL,
      accepted_at TEXT NOT NULL,
      session_expires_at TEXT NOT NULL,
      request_id TEXT NOT NULL DEFAULT '',
      source_network_sha256 TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_identity_acceptance_tenant_time ON identity_acceptance_events(tenant_id,accepted_at,event_key);
    CREATE INDEX IF NOT EXISTS idx_identity_acceptance_user_time ON identity_acceptance_events(user_id,accepted_at,event_key);

    CREATE TABLE IF NOT EXISTS oidc_states (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      state_hash TEXT NOT NULL UNIQUE,
      nonce TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS assessment_access (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      role_override TEXT NOT NULL DEFAULT '',
      sensitivity_clearance TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      UNIQUE(user_id, assessment_id),
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS backup_history (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL DEFAULT 1,
      filename TEXT NOT NULL,
      sha256 TEXT NOT NULL,
      size_bytes INTEGER NOT NULL DEFAULT 0,
      created_by TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      verified_at TEXT NOT NULL DEFAULT '',
      restore_status TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS industry_profiles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      profile_key TEXT NOT NULL,
      version_no INTEGER NOT NULL,
      supersedes_id INTEGER,
      industry_code TEXT NOT NULL,
      name TEXT NOT NULL,
      member_summary TEXT NOT NULL,
      internal_rationale TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Draft',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      last_material_editor TEXT NOT NULL, last_material_edit_at TEXT NOT NULL,
      submitted_by TEXT NOT NULL DEFAULT '', submitted_at TEXT NOT NULL DEFAULT '',
      reviewed_by TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '', review_reason TEXT NOT NULL DEFAULT '',
      approved_by TEXT NOT NULL DEFAULT '', approved_at TEXT NOT NULL DEFAULT '', approval_reason TEXT NOT NULL DEFAULT '',
      published_by TEXT NOT NULL DEFAULT '', published_at TEXT NOT NULL DEFAULT '', publish_reason TEXT NOT NULL DEFAULT '',
      retired_by TEXT NOT NULL DEFAULT '', retired_at TEXT NOT NULL DEFAULT '', retirement_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (supersedes_id) REFERENCES industry_profiles(id) ON DELETE SET NULL,
      UNIQUE(tenant_id,profile_key,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_industry_profiles_scope ON industry_profiles(tenant_id,status,industry_code,id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_industry_profiles_published ON industry_profiles(tenant_id,profile_key) WHERE status='Published';
    CREATE TABLE IF NOT EXISTS industry_profile_items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      profile_id INTEGER NOT NULL,
      item_type TEXT NOT NULL,
      item_key TEXT NOT NULL,
      member_label TEXT NOT NULL,
      member_guidance TEXT NOT NULL DEFAULT '',
      internal_definition TEXT NOT NULL DEFAULT '',
      reference_metadata TEXT NOT NULL DEFAULT '',
      default_payload_json TEXT NOT NULL DEFAULT '{}',
      member_visible INTEGER NOT NULL DEFAULT 1,
      sort_order INTEGER NOT NULL DEFAULT 0,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (profile_id) REFERENCES industry_profiles(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,profile_id,item_type,item_key)
    );
    CREATE INDEX IF NOT EXISTS idx_industry_profile_items_scope ON industry_profile_items(tenant_id,profile_id,item_type,sort_order,id);
    CREATE TABLE IF NOT EXISTS industry_profile_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      profile_id INTEGER NOT NULL,
      version_no INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      summary TEXT NOT NULL,
      snapshot_json TEXT NOT NULL,
      changed_by TEXT NOT NULL,
      changed_by_role TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (profile_id) REFERENCES industry_profiles(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,profile_id,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_industry_profile_events_scope ON industry_profile_events(tenant_id,profile_id,version_no);
    CREATE TABLE IF NOT EXISTS tenant_industry_configurations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      profile_id INTEGER NOT NULL,
      profile_key_snapshot TEXT NOT NULL,
      profile_version_snapshot INTEGER NOT NULL,
      profile_name_snapshot TEXT NOT NULL,
      industry_code_snapshot TEXT NOT NULL,
      member_summary_snapshot TEXT NOT NULL,
      defaults_snapshot_json TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Active',
      selected_by TEXT NOT NULL, selected_at TEXT NOT NULL,
      deactivated_by TEXT NOT NULL DEFAULT '', deactivated_at TEXT NOT NULL DEFAULT '', deactivation_reason TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (profile_id) REFERENCES industry_profiles(id) ON DELETE RESTRICT,
      UNIQUE(tenant_id,profile_id)
    );
    CREATE INDEX IF NOT EXISTS idx_tenant_industry_config_scope ON tenant_industry_configurations(tenant_id,status,industry_code_snapshot,id);

    CREATE TABLE IF NOT EXISTS assessments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      organization TEXT NOT NULL,
      assessment_type TEXT NOT NULL DEFAULT 'Enterprise',
      purpose TEXT NOT NULL DEFAULT '',
      mission TEXT NOT NULL DEFAULT '',
      scope TEXT NOT NULL DEFAULT '',
      covered_operation TEXT NOT NULL DEFAULT '',
      requested_package_level INTEGER NOT NULL DEFAULT 0,
      requested_scope_band TEXT NOT NULL DEFAULT '',
      requested_access_variant TEXT NOT NULL DEFAULT '',
      exclusions TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Draft',
      executive_sponsor TEXT NOT NULL DEFAULT '',
      assessment_director TEXT NOT NULL DEFAULT '',
      lead_assessor TEXT NOT NULL DEFAULT '',
      start_date TEXT NOT NULL DEFAULT '',
      target_completion TEXT NOT NULL DEFAULT '',
      reassessment_date TEXT NOT NULL DEFAULT '',
      reassessment_lifecycle_status TEXT NOT NULL DEFAULT 'Current',
      reassessment_overdue_reason TEXT NOT NULL DEFAULT '',
      reassessment_overdue_at TEXT NOT NULL DEFAULT '',
      last_reassessment_review_at TEXT NOT NULL DEFAULT '',
      last_reassessment_review_by TEXT NOT NULL DEFAULT '',
      classification TEXT NOT NULL DEFAULT 'Standard',
      industry_profile_id INTEGER,
      industry_profile_key_snapshot TEXT NOT NULL DEFAULT '',
      industry_profile_version_snapshot INTEGER,
      industry_profile_name_snapshot TEXT NOT NULL DEFAULT '',
      industry_member_summary_snapshot TEXT NOT NULL DEFAULT '',
      industry_defaults_snapshot_json TEXT NOT NULL DEFAULT '{}',
      industry_profile_applied_by TEXT NOT NULL DEFAULT '',
      industry_profile_applied_at TEXT NOT NULL DEFAULT '',
      scope_locked INTEGER NOT NULL DEFAULT 0,
      version INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (industry_profile_id) REFERENCES industry_profiles(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS threats (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      category TEXT NOT NULL,
      subcategory TEXT NOT NULL DEFAULT '',
      description TEXT NOT NULL DEFAULT '',
      likelihood INTEGER NOT NULL DEFAULT 1,
      vulnerability INTEGER NOT NULL DEFAULT 1,
      consequence INTEGER NOT NULL DEFAULT 1,
      confidence TEXT NOT NULL DEFAULT 'Medium',
      trend TEXT NOT NULL DEFAULT 'Stable',
      inclusion_status TEXT NOT NULL DEFAULT 'Included - Scenario Required',
      basis TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Active',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS scenarios (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      threat_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      narrative TEXT NOT NULL DEFAULT '',
      initiating_event TEXT NOT NULL DEFAULT '',
      location TEXT NOT NULL DEFAULT '',
      duration TEXT NOT NULL DEFAULT '',
      operating_conditions TEXT NOT NULL DEFAULT '',
      dependencies TEXT NOT NULL DEFAULT '',
      decision_points TEXT NOT NULL DEFAULT '',
      assumptions TEXT NOT NULL DEFAULT '',
      uncertainties TEXT NOT NULL DEFAULT '',
      life_safety INTEGER NOT NULL DEFAULT 1,
      mission INTEGER NOT NULL DEFAULT 1,
      operations INTEGER NOT NULL DEFAULT 1,
      financial INTEGER NOT NULL DEFAULT 1,
      legal_regulatory INTEGER NOT NULL DEFAULT 1,
      reputation INTEGER NOT NULL DEFAULT 1,
      recovery INTEGER NOT NULL DEFAULT 1,
      evidence_confidence TEXT NOT NULL DEFAULT 'Medium',
      professional_override TEXT NOT NULL DEFAULT '',
      override_reason TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (threat_id) REFERENCES threats(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS capabilities (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      scenario_id INTEGER,
      name TEXT NOT NULL,
      mission_area TEXT NOT NULL DEFAULT '',
      capability_family TEXT NOT NULL DEFAULT '',
      required_outcome TEXT NOT NULL DEFAULT '',
      operating_conditions TEXT NOT NULL DEFAULT '',
      performance_metric TEXT NOT NULL DEFAULT '',
      measurement_type TEXT NOT NULL DEFAULT 'Percentage',
      measurement_unit TEXT NOT NULL DEFAULT '%',
      comparator TEXT NOT NULL DEFAULT '>=',
      required_standard REAL NOT NULL DEFAULT 100,
      current_performance REAL NOT NULL DEFAULT 0,
      responsible_function TEXT NOT NULL DEFAULT '',
      owner TEXT NOT NULL DEFAULT '',
      dependencies TEXT NOT NULL DEFAULT '',
      evidence_required TEXT NOT NULL DEFAULT '',
      confidence TEXT NOT NULL DEFAULT 'Medium',
      last_validated TEXT NOT NULL DEFAULT '',
      next_validation TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS evidence (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      capability_id INTEGER,
      scenario_id INTEGER,
      title TEXT NOT NULL,
      evidence_type TEXT NOT NULL DEFAULT 'Document',
      source TEXT NOT NULL DEFAULT '',
      owner TEXT NOT NULL DEFAULT '',
      evidence_date TEXT NOT NULL DEFAULT '',
      reliability TEXT NOT NULL DEFAULT 'Medium',
      verification_status TEXT NOT NULL DEFAULT 'Pending',
      sensitivity TEXT NOT NULL DEFAULT 'Standard',
      valid_until TEXT NOT NULL DEFAULT '',
      lifecycle_status TEXT NOT NULL DEFAULT 'Current',
      stale_reason TEXT NOT NULL DEFAULT '',
      stale_at TEXT NOT NULL DEFAULT '',
      last_lifecycle_review_at TEXT NOT NULL DEFAULT '',
      last_lifecycle_review_by TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (capability_id) REFERENCES capabilities(id) ON DELETE SET NULL,
      FOREIGN KEY (scenario_id) REFERENCES scenarios(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS gaps (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      capability_id INTEGER NOT NULL,
      gap_type TEXT NOT NULL DEFAULT 'Other',
      description TEXT NOT NULL,
      severity TEXT NOT NULL DEFAULT 'Moderate',
      root_cause TEXT NOT NULL DEFAULT '',
      owner TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Open',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (capability_id) REFERENCES capabilities(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS improvements (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      gap_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      initial_cost REAL NOT NULL DEFAULT 0,
      recurring_cost REAL NOT NULL DEFAULT 0,
      implementation_days INTEGER NOT NULL DEFAULT 0,
      feasibility INTEGER NOT NULL DEFAULT 3,
      consequence_reduction INTEGER NOT NULL DEFAULT 3,
      mission_benefit INTEGER NOT NULL DEFAULT 3,
      sustainability INTEGER NOT NULL DEFAULT 3,
      dependencies TEXT NOT NULL DEFAULT '',
      owner TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Proposed',
      validation_status TEXT NOT NULL DEFAULT 'Pending',
      validation_evidence_id INTEGER,
      validation_outcome TEXT NOT NULL DEFAULT '',
      validated_effectiveness_percent REAL NOT NULL DEFAULT 0,
      validated_by TEXT NOT NULL DEFAULT '',
      validated_at TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (gap_id) REFERENCES gaps(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS decisions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      improvement_id INTEGER,
      decision_type TEXT NOT NULL,
      authority TEXT NOT NULL DEFAULT '',
      rationale TEXT NOT NULL DEFAULT '',
      funding_authorized REAL NOT NULL DEFAULT 0,
      conditions TEXT NOT NULL DEFAULT '',
      implementation_owner TEXT NOT NULL DEFAULT '',
      target_completion TEXT NOT NULL DEFAULT '',
      expected_residual_risk TEXT NOT NULL DEFAULT '',
      review_date TEXT NOT NULL DEFAULT '',
      review_lifecycle_status TEXT NOT NULL DEFAULT 'Current',
      review_overdue_reason TEXT NOT NULL DEFAULT '',
      review_overdue_at TEXT NOT NULL DEFAULT '',
      last_review_at TEXT NOT NULL DEFAULT '',
      last_review_by TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (improvement_id) REFERENCES improvements(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS accepted_risks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      decision_id INTEGER NOT NULL UNIQUE,
      improvement_id INTEGER,
      gap_id INTEGER,
      title TEXT NOT NULL,
      risk_statement TEXT NOT NULL,
      authority TEXT NOT NULL,
      residual_exposure TEXT NOT NULL,
      acceptance_date TEXT NOT NULL,
      review_date TEXT NOT NULL,
      reconsideration_trigger TEXT NOT NULL,
      owner TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Active',
      closure_basis TEXT NOT NULL DEFAULT '',
      review_lifecycle_status TEXT NOT NULL DEFAULT 'Current',
      review_overdue_reason TEXT NOT NULL DEFAULT '',
      review_overdue_at TEXT NOT NULL DEFAULT '',
      last_review_at TEXT NOT NULL DEFAULT '',
      last_review_by TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE,
      FOREIGN KEY (improvement_id) REFERENCES improvements(id) ON DELETE SET NULL,
      FOREIGN KEY (gap_id) REFERENCES gaps(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_accepted_risks_assessment_status ON accepted_risks(assessment_id,status);
    CREATE INDEX IF NOT EXISTS idx_accepted_risks_review_date ON accepted_risks(review_date);

    CREATE TABLE IF NOT EXISTS risk_overrides (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      threat_id INTEGER NOT NULL,
      calculated_score REAL NOT NULL,
      calculated_band TEXT NOT NULL,
      assigned_score REAL NOT NULL,
      assigned_band TEXT NOT NULL,
      reason TEXT NOT NULL,
      evidence_id INTEGER,
      authority TEXT NOT NULL,
      review_date TEXT NOT NULL DEFAULT '',
      review_lifecycle_status TEXT NOT NULL DEFAULT 'Current',
      review_overdue_reason TEXT NOT NULL DEFAULT '',
      review_overdue_at TEXT NOT NULL DEFAULT '',
      last_review_at TEXT NOT NULL DEFAULT '',
      last_review_by TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Active',
      supersedes_id INTEGER,
      withdrawn_reason TEXT NOT NULL DEFAULT '',
      created_by TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      withdrawn_by TEXT NOT NULL DEFAULT '',
      withdrawn_at TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (threat_id) REFERENCES threats(id) ON DELETE CASCADE,
      FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE SET NULL,
      FOREIGN KEY (supersedes_id) REFERENCES risk_overrides(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_risk_overrides_assessment_threat ON risk_overrides(assessment_id,threat_id,id);
    CREATE INDEX IF NOT EXISTS idx_risk_overrides_status ON risk_overrides(status);

    CREATE TABLE IF NOT EXISTS governed_intake (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      record_key TEXT NOT NULL UNIQUE,
      record_type TEXT NOT NULL,
      title TEXT NOT NULL,
      details TEXT NOT NULL,
      source_context TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Draft',
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      version INTEGER NOT NULL DEFAULT 1,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_governed_intake_tenant_created ON governed_intake(tenant_id,created_at,id);
    CREATE INDEX IF NOT EXISTS idx_governed_intake_tenant_type_status ON governed_intake(tenant_id,record_type,status);

    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT NOT NULL,
      user_name TEXT NOT NULL,
      action TEXT NOT NULL,
      entity_type TEXT NOT NULL,
      entity_id INTEGER,
      detail TEXT NOT NULL DEFAULT ''
    );
    ''')
    # v0.2 additive schema extensions. Existing prototype data remains usable.
    def ensure_column(table, column, ddl):
        cols={r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
        if column not in cols:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}')

    ensure_column('assessments','tenant_id','INTEGER NOT NULL DEFAULT 1')
    ensure_column('assessments','reassessment_lifecycle_status',"TEXT NOT NULL DEFAULT 'Current'")
    ensure_column('assessments','reassessment_overdue_reason',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','reassessment_overdue_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','last_reassessment_review_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','last_reassessment_review_by',"TEXT NOT NULL DEFAULT ''")
    ensure_column('audit_log','tenant_id','INTEGER NOT NULL DEFAULT 1')
    ensure_column('evidence','sensitivity',"TEXT NOT NULL DEFAULT 'Standard'")
    ensure_column('evidence','valid_until',"TEXT NOT NULL DEFAULT ''")
    ensure_column('evidence','lifecycle_status',"TEXT NOT NULL DEFAULT 'Current'")
    ensure_column('evidence','stale_reason',"TEXT NOT NULL DEFAULT ''")
    ensure_column('evidence','stale_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('evidence','last_lifecycle_review_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('evidence','last_lifecycle_review_by',"TEXT NOT NULL DEFAULT ''")
    ensure_column('accepted_risks','review_lifecycle_status',"TEXT NOT NULL DEFAULT 'Current'")
    ensure_column('accepted_risks','review_overdue_reason',"TEXT NOT NULL DEFAULT ''")
    ensure_column('accepted_risks','review_overdue_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('accepted_risks','last_review_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('accepted_risks','last_review_by',"TEXT NOT NULL DEFAULT ''")
    ensure_column('risk_overrides','review_lifecycle_status',"TEXT NOT NULL DEFAULT 'Current'")
    ensure_column('risk_overrides','review_overdue_reason',"TEXT NOT NULL DEFAULT ''")
    ensure_column('risk_overrides','review_overdue_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('risk_overrides','last_review_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('risk_overrides','last_review_by',"TEXT NOT NULL DEFAULT ''")
    ensure_column('decisions','review_lifecycle_status',"TEXT NOT NULL DEFAULT 'Current'")
    ensure_column('decisions','review_overdue_reason',"TEXT NOT NULL DEFAULT ''")
    ensure_column('decisions','review_overdue_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('decisions','last_review_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('decisions','last_review_by',"TEXT NOT NULL DEFAULT ''")
    ensure_column('decisions','updated_at',"TEXT NOT NULL DEFAULT ''")
    conn.execute("UPDATE evidence SET lifecycle_status='Stale',stale_reason=CASE WHEN stale_reason='' THEN 'Legacy evidence status indicated stale evidence.' ELSE stale_reason END,stale_at=CASE WHEN stale_at='' THEN updated_at ELSE stale_at END WHERE verification_status='Stale' AND lifecycle_status='Current'")
    ensure_column('capabilities','measurement_type',"TEXT NOT NULL DEFAULT 'Percentage'")
    ensure_column('capabilities','measurement_unit',"TEXT NOT NULL DEFAULT '%'")
    ensure_column('capabilities','comparator',"TEXT NOT NULL DEFAULT '>='")
    ensure_column('gaps','owner',"TEXT NOT NULL DEFAULT ''")
    ensure_column('improvements','compliance_impact','INTEGER NOT NULL DEFAULT 3')
    ensure_column('improvements','staffing_impact','INTEGER NOT NULL DEFAULT 3')
    ensure_column('improvements','expected_capability_gain','REAL NOT NULL DEFAULT 0')
    ensure_column('improvements','priority_score','REAL NOT NULL DEFAULT 0')
    ensure_column('improvements','validation_status',"TEXT NOT NULL DEFAULT 'Pending'")
    ensure_column('improvements','validation_evidence_id','INTEGER')
    ensure_column('improvements','validation_outcome','TEXT NOT NULL DEFAULT ""')
    ensure_column('improvements','validated_effectiveness_percent','REAL NOT NULL DEFAULT 0')
    ensure_column('improvements','validated_by','TEXT NOT NULL DEFAULT ""')
    ensure_column('improvements','validated_at','TEXT NOT NULL DEFAULT ""')
    ensure_column('threats','last_reviewed','TEXT NOT NULL DEFAULT \"\"')
    ensure_column('threats','review_owner','TEXT NOT NULL DEFAULT \"\"')
    ensure_column('users','email','TEXT NOT NULL DEFAULT \"\"')
    ensure_column('users','external_subject','TEXT NOT NULL DEFAULT \"\"')
    ensure_column('users','identity_provider','TEXT NOT NULL DEFAULT \"local\"')
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS security_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER,
      ts TEXT NOT NULL,
      event_type TEXT NOT NULL,
      severity TEXT NOT NULL DEFAULT 'Info',
      user_name TEXT NOT NULL DEFAULT '',
      source_ip TEXT NOT NULL DEFAULT '',
      request_id TEXT NOT NULL DEFAULT '',
      detail TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_security_events_tenant_ts ON security_events(tenant_id,ts);
    CREATE TABLE IF NOT EXISTS reassessment_triggers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL, source TEXT NOT NULL DEFAULT 'Manual',
      trigger_type TEXT NOT NULL, description TEXT NOT NULL, severity TEXT NOT NULL DEFAULT 'Moderate',
      affected_record_type TEXT NOT NULL DEFAULT '', affected_record_id INTEGER,
      status TEXT NOT NULL DEFAULT 'Open', assigned_to TEXT NOT NULL DEFAULT '', due_date TEXT NOT NULL DEFAULT '',
      resolution TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS assessment_weights (
      assessment_id INTEGER PRIMARY KEY, life_safety REAL NOT NULL DEFAULT 1.0, mission REAL NOT NULL DEFAULT 1.0,
      operations REAL NOT NULL DEFAULT 1.0, financial REAL NOT NULL DEFAULT 1.0, legal_regulatory REAL NOT NULL DEFAULT 1.0,
      reputation REAL NOT NULL DEFAULT 1.0, recovery REAL NOT NULL DEFAULT 1.0,
      risk_methodology_version TEXT NOT NULL DEFAULT '1.1.0',
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS evidence_attachments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      evidence_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      original_name TEXT NOT NULL,
      stored_name TEXT NOT NULL,
      content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
      size_bytes INTEGER NOT NULL DEFAULT 0,
      sha256 TEXT NOT NULL,
      uploaded_by TEXT NOT NULL DEFAULT '',
      scan_status TEXT NOT NULL DEFAULT 'Legacy/Unscanned',
      scan_detail TEXT NOT NULL DEFAULT '',
      scanned_at TEXT NOT NULL DEFAULT '',
      retention_until TEXT NOT NULL DEFAULT '',
      legal_hold INTEGER NOT NULL DEFAULT 0,
      disposition_status TEXT NOT NULL DEFAULT 'Active',
      created_at TEXT NOT NULL,
      FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS entity_versions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      entity_type TEXT NOT NULL,
      entity_id INTEGER NOT NULL,
      version_no INTEGER NOT NULL,
      snapshot_json TEXT NOT NULL,
      change_reason TEXT NOT NULL DEFAULT '',
      changed_by TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_versions_unique ON entity_versions(entity_type,entity_id,version_no);
    CREATE TABLE IF NOT EXISTS scope_changes (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      new_purpose TEXT,
      new_mission TEXT,
      new_scope TEXT,
      new_exclusions TEXT,
      reason TEXT NOT NULL,
      schedule_impact TEXT NOT NULL DEFAULT '',
      cost_impact REAL NOT NULL DEFAULT 0,
      assessment_impact TEXT NOT NULL DEFAULT '',
      requested_by TEXT NOT NULL DEFAULT '',
      decision TEXT NOT NULL DEFAULT 'Pending',
      approved_by TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      decided_at TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS workflow_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      assessment_id INTEGER NOT NULL,
      from_status TEXT NOT NULL,
      to_status TEXT NOT NULL,
      reason TEXT NOT NULL DEFAULT '',
      changed_by TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS dr_validations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      backup_id INTEGER NOT NULL,
      status TEXT NOT NULL,
      database_integrity TEXT NOT NULL DEFAULT '',
      assessment_count INTEGER NOT NULL DEFAULT 0,
      attachment_count INTEGER NOT NULL DEFAULT 0,
      errors_json TEXT NOT NULL DEFAULT '[]',
      validated_by TEXT NOT NULL DEFAULT '',
      validated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (backup_id) REFERENCES backup_history(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_dr_validations_tenant ON dr_validations(tenant_id,validated_at);
    CREATE TABLE IF NOT EXISTS report_versions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      assessment_version INTEGER NOT NULL,
      report_type TEXT NOT NULL DEFAULT 'Executive',
      status TEXT NOT NULL DEFAULT 'Draft',
      snapshot_json TEXT NOT NULL,
      snapshot_sha256 TEXT NOT NULL,
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      reviewed_by TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '',
      approved_by TEXT NOT NULL DEFAULT '', approved_at TEXT NOT NULL DEFAULT '',
      released_by TEXT NOT NULL DEFAULT '', released_at TEXT NOT NULL DEFAULT '',
      transition_reason TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_report_versions_scope ON report_versions(tenant_id,assessment_id,id);
    CREATE TABLE IF NOT EXISTS package_agreement_artifacts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      original_name TEXT NOT NULL,
      stored_name TEXT NOT NULL UNIQUE,
      content_sha256 TEXT NOT NULL,
      size_bytes INTEGER NOT NULL,
      scan_status TEXT NOT NULL,
      retention_until TEXT NOT NULL DEFAULT '',
      legal_hold INTEGER NOT NULL DEFAULT 0,
      uploaded_by TEXT NOT NULL,
      uploaded_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,assessment_id,content_sha256)
    );
    CREATE INDEX IF NOT EXISTS idx_package_agreement_scope ON package_agreement_artifacts(tenant_id,assessment_id,id);
    CREATE TABLE IF NOT EXISTS package_quote_versions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      version_no INTEGER NOT NULL,
      assessment_version INTEGER NOT NULL,
      assessment_scope_sha256 TEXT NOT NULL DEFAULT '',
      level INTEGER NOT NULL,
      band TEXT NOT NULL,
      variant TEXT NOT NULL,
      covered_operation TEXT NOT NULL,
      exclusions TEXT NOT NULL,
      scope_basis TEXT NOT NULL,
      included_work TEXT NOT NULL DEFAULT '',
      report_deliverables TEXT NOT NULL DEFAULT '',
      member_inputs TEXT NOT NULL DEFAULT '',
      evidence_allowance TEXT NOT NULL DEFAULT '',
      clarification_allowance TEXT NOT NULL DEFAULT '',
      field_specialist_terms TEXT NOT NULL DEFAULT '',
      payment_terms TEXT NOT NULL DEFAULT '',
      tax_treatment TEXT NOT NULL DEFAULT '',
      change_triggers TEXT NOT NULL DEFAULT '',
      decision_owner TEXT NOT NULL,
      source_receipt_id TEXT NOT NULL DEFAULT '',
      fee_cents INTEGER NOT NULL,
      currency TEXT NOT NULL,
      valid_until TEXT NOT NULL,
      start_date TEXT NOT NULL DEFAULT '',
      delivery_date TEXT NOT NULL DEFAULT '',
      capacity_confirmed INTEGER NOT NULL,
      access_eligibility_confirmed INTEGER NOT NULL,
      access_eligibility_basis TEXT NOT NULL DEFAULT '',
      agreement_artifact_id INTEGER NOT NULL DEFAULT 0,
      agreement_reference TEXT NOT NULL,
      agreement_sha256 TEXT NOT NULL,
      separate_services_excluded INTEGER NOT NULL,
      content_sha256 TEXT NOT NULL,
      approved_by TEXT NOT NULL,
      approved_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (agreement_artifact_id) REFERENCES package_agreement_artifacts(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,assessment_id,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_package_quote_scope ON package_quote_versions(tenant_id,assessment_id,id);
    CREATE TABLE IF NOT EXISTS package_agreement_downloads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL,
      agreement_artifact_id INTEGER NOT NULL,
      member_user_id INTEGER NOT NULL,
      content_sha256 TEXT NOT NULL,
      downloaded_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (agreement_artifact_id) REFERENCES package_agreement_artifacts(id) ON DELETE RESTRICT,
      FOREIGN KEY (member_user_id) REFERENCES users(id) ON DELETE RESTRICT
    );
    CREATE INDEX IF NOT EXISTS idx_package_agreement_download_scope ON package_agreement_downloads(tenant_id,assessment_id,quote_id,member_user_id);
    CREATE TABLE IF NOT EXISTS package_member_authority_reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL UNIQUE,
      member_user_id INTEGER NOT NULL,
      authority_basis TEXT NOT NULL,
      evidence_reference TEXT NOT NULL,
      reviewed_by_user_id INTEGER NOT NULL,
      reviewed_at TEXT NOT NULL,
      record_sha256 TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (member_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id) ON DELETE RESTRICT
    );
    CREATE INDEX IF NOT EXISTS idx_package_member_authority_scope ON package_member_authority_reviews(tenant_id,assessment_id,quote_id);
    CREATE TABLE IF NOT EXISTS package_acceptances (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL,
      quote_sha256 TEXT NOT NULL,
      agreement_sha256 TEXT NOT NULL,
      member_user_id INTEGER NOT NULL,
      agreement_download_id INTEGER NOT NULL DEFAULT 0,
      member_authority_basis TEXT NOT NULL,
      idempotency_key TEXT NOT NULL,
      accepted_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (member_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      FOREIGN KEY (agreement_download_id) REFERENCES package_agreement_downloads(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,assessment_id,idempotency_key),
      UNIQUE (quote_id)
    );
    CREATE INDEX IF NOT EXISTS idx_package_acceptance_scope ON package_acceptances(tenant_id,assessment_id,id);
    CREATE TABLE IF NOT EXISTS package_intake_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL,
      item_key TEXT NOT NULL,
      catalog_version TEXT NOT NULL,
      title TEXT NOT NULL,
      decision_use TEXT NOT NULL,
      requested_form TEXT NOT NULL,
      acceptable_equivalent TEXT NOT NULL,
      request_reason TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Requested',
      requested_by TEXT NOT NULL,
      requested_at TEXT NOT NULL,
      response_user_id INTEGER,
      responded_at TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (response_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,assessment_id,quote_id,item_key)
    );
    CREATE INDEX IF NOT EXISTS idx_package_intake_scope ON package_intake_requests(tenant_id,assessment_id,quote_id,id);
    CREATE TABLE IF NOT EXISTS package_intake_uploads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL,
      intake_request_id INTEGER NOT NULL,
      member_user_id INTEGER NOT NULL,
      original_name TEXT NOT NULL,
      stored_name TEXT NOT NULL UNIQUE,
      content_sha256 TEXT NOT NULL,
      size_bytes INTEGER NOT NULL,
      scan_status TEXT NOT NULL,
      retention_until TEXT NOT NULL,
      legal_hold INTEGER NOT NULL DEFAULT 0,
      uploaded_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (intake_request_id) REFERENCES package_intake_requests(id) ON DELETE RESTRICT,
      FOREIGN KEY (member_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,intake_request_id,content_sha256)
    );
    CREATE INDEX IF NOT EXISTS idx_package_intake_upload_scope ON package_intake_uploads(tenant_id,assessment_id,quote_id,intake_request_id,id);
    CREATE TABLE IF NOT EXISTS package_product_report_versions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL,
      product TEXT NOT NULL,
      report_identity TEXT NOT NULL,
      display_title TEXT NOT NULL,
      version_no INTEGER NOT NULL,
      assessment_scope_sha256 TEXT NOT NULL,
      method_version TEXT NOT NULL,
      template_version TEXT NOT NULL,
      original_name TEXT NOT NULL,
      stored_name TEXT NOT NULL UNIQUE,
      content_sha256 TEXT NOT NULL,
      size_bytes INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'Draft',
      retention_until TEXT NOT NULL DEFAULT '',
      legal_hold INTEGER NOT NULL DEFAULT 0,
      disposition_status TEXT NOT NULL DEFAULT 'Active',
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      supersedes_id INTEGER,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (supersedes_id) REFERENCES package_product_report_versions(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,assessment_id,product,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_package_product_report_scope ON package_product_report_versions(tenant_id,assessment_id,product,id);
    CREATE TABLE IF NOT EXISTS package_report_conformance (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      report_id INTEGER NOT NULL,
      content_sha256 TEXT NOT NULL,
      checks_json TEXT NOT NULL,
      summary TEXT NOT NULL,
      matrix_status TEXT NOT NULL,
      record_sha256 TEXT NOT NULL UNIQUE,
      recorded_by TEXT NOT NULL,
      recorded_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (report_id) REFERENCES package_product_report_versions(id) ON DELETE RESTRICT
    );
    CREATE INDEX IF NOT EXISTS idx_package_report_conformance_report ON package_report_conformance(tenant_id,report_id,id);
    CREATE TABLE IF NOT EXISTS package_report_reconciliations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL,
      salcapa_report_id INTEGER NOT NULL,
      salcapa_sha256 TEXT NOT NULL,
      sources_json TEXT NOT NULL,
      summary TEXT NOT NULL,
      comparison_status TEXT NOT NULL,
      record_sha256 TEXT NOT NULL UNIQUE,
      recorded_by TEXT NOT NULL,
      recorded_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (salcapa_report_id) REFERENCES package_product_report_versions(id) ON DELETE RESTRICT
    );
    CREATE INDEX IF NOT EXISTS idx_package_report_reconciliation ON package_report_reconciliations(tenant_id,salcapa_report_id,id);
    CREATE TABLE IF NOT EXISTS package_report_qa_evidence (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      report_id INTEGER NOT NULL,
      content_sha256 TEXT NOT NULL,
      stored_name TEXT NOT NULL UNIQUE,
      archive_sha256 TEXT NOT NULL,
      archive_size_bytes INTEGER NOT NULL,
      manifest_json TEXT NOT NULL,
      manifest_sha256 TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Submitted',
      retention_until TEXT NOT NULL,
      legal_hold INTEGER NOT NULL DEFAULT 0,
      submitted_by TEXT NOT NULL,
      submitted_user_id INTEGER,
      submitted_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (report_id) REFERENCES package_product_report_versions(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,report_id,archive_sha256)
    );
    CREATE INDEX IF NOT EXISTS idx_package_report_qa_evidence ON package_report_qa_evidence(tenant_id,report_id,id);
    CREATE TABLE IF NOT EXISTS package_report_qa_reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      report_id INTEGER NOT NULL,
      evidence_id INTEGER NOT NULL,
      content_sha256 TEXT NOT NULL,
      archive_sha256 TEXT NOT NULL,
      decision TEXT NOT NULL,
      checks_json TEXT NOT NULL,
      qualification_basis TEXT NOT NULL,
      review_note TEXT NOT NULL,
      record_sha256 TEXT NOT NULL,
      reviewer_user_id INTEGER NOT NULL,
      reviewer_at TEXT NOT NULL,
      FOREIGN KEY (report_id) REFERENCES package_product_report_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (evidence_id) REFERENCES package_report_qa_evidence(id) ON DELETE RESTRICT,
      FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,evidence_id,record_sha256)
    );
    CREATE INDEX IF NOT EXISTS idx_package_report_qa_reviews ON package_report_qa_reviews(tenant_id,report_id,id);
    CREATE TABLE IF NOT EXISTS package_report_issue_packets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL,
      assessment_scope_sha256 TEXT NOT NULL,
      recipient_user_id INTEGER NOT NULL,
      reports_json TEXT NOT NULL,
      comparison_id INTEGER NOT NULL,
      issue_basis TEXT NOT NULL,
      record_sha256 TEXT NOT NULL,
      issued_by_user_id INTEGER NOT NULL,
      issued_at TEXT NOT NULL,
      supersedes_id INTEGER,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      FOREIGN KEY (comparison_id) REFERENCES package_report_reconciliations(id) ON DELETE RESTRICT,
      FOREIGN KEY (issued_by_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      FOREIGN KEY (supersedes_id) REFERENCES package_report_issue_packets(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,assessment_id,record_sha256)
    );
    CREATE INDEX IF NOT EXISTS idx_package_report_issues ON package_report_issue_packets(tenant_id,assessment_id,id);
    CREATE TABLE IF NOT EXISTS package_report_issue_deliveries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      issue_id INTEGER NOT NULL,
      report_id INTEGER NOT NULL,
      product TEXT NOT NULL,
      format TEXT NOT NULL,
      content_sha256 TEXT NOT NULL,
      recipient_user_id INTEGER NOT NULL,
      downloaded_at TEXT NOT NULL,
      FOREIGN KEY (issue_id) REFERENCES package_report_issue_packets(id) ON DELETE RESTRICT,
      FOREIGN KEY (report_id) REFERENCES package_product_report_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE RESTRICT
    );
    CREATE INDEX IF NOT EXISTS idx_package_report_deliveries ON package_report_issue_deliveries(tenant_id,issue_id,recipient_user_id,id);
    CREATE TABLE IF NOT EXISTS package_report_issue_acknowledgments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      issue_id INTEGER NOT NULL,
      issue_sha256 TEXT NOT NULL,
      recipient_user_id INTEGER NOT NULL,
      acknowledgment_note TEXT NOT NULL,
      idempotency_key TEXT NOT NULL,
      record_sha256 TEXT NOT NULL,
      acknowledged_at TEXT NOT NULL,
      FOREIGN KEY (issue_id) REFERENCES package_report_issue_packets(id) ON DELETE RESTRICT,
      FOREIGN KEY (recipient_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,issue_id),
      UNIQUE (tenant_id,idempotency_key)
    );
    CREATE INDEX IF NOT EXISTS idx_package_report_acknowledgments ON package_report_issue_acknowledgments(tenant_id,assessment_id,issue_id);
    CREATE TABLE IF NOT EXISTS package_predecessor_qualifications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      issue_id INTEGER NOT NULL,
      issue_sha256 TEXT NOT NULL,
      acknowledgment_id INTEGER NOT NULL,
      acknowledgment_sha256 TEXT NOT NULL,
      quote_id INTEGER NOT NULL,
      level INTEGER NOT NULL,
      band TEXT NOT NULL,
      covered_operation TEXT NOT NULL,
      exclusions TEXT NOT NULL,
      assessment_scope_sha256 TEXT NOT NULL,
      qualification_basis TEXT NOT NULL,
      limitations_disposition TEXT NOT NULL,
      reviewer_user_id INTEGER NOT NULL,
      record_sha256 TEXT NOT NULL,
      qualified_at TEXT NOT NULL,
      FOREIGN KEY (issue_id) REFERENCES package_report_issue_packets(id) ON DELETE RESTRICT,
      FOREIGN KEY (acknowledgment_id) REFERENCES package_report_issue_acknowledgments(id) ON DELETE RESTRICT,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (reviewer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,issue_id)
    );
    CREATE INDEX IF NOT EXISTS idx_package_predecessors ON package_predecessor_qualifications(tenant_id,assessment_id,id);
    CREATE TABLE IF NOT EXISTS package_quote_predecessor_links (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      quote_id INTEGER NOT NULL,
      qualification_id INTEGER NOT NULL,
      qualification_sha256 TEXT NOT NULL,
      record_sha256 TEXT NOT NULL,
      linked_at TEXT NOT NULL,
      FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
      FOREIGN KEY (qualification_id) REFERENCES package_predecessor_qualifications(id) ON DELETE RESTRICT,
      UNIQUE (tenant_id,quote_id)
    );
    CREATE INDEX IF NOT EXISTS idx_package_quote_predecessors ON package_quote_predecessor_links(tenant_id,assessment_id,quote_id);
    CREATE TABLE IF NOT EXISTS restore_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL, backup_id INTEGER NOT NULL,
      scope TEXT NOT NULL, reason TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Pending',
      requested_by TEXT NOT NULL, requested_at TEXT NOT NULL,
      authorized_by TEXT NOT NULL DEFAULT '', authorized_at TEXT NOT NULL DEFAULT '',
      executed_by TEXT NOT NULL DEFAULT '', executed_at TEXT NOT NULL DEFAULT '',
      validation_id INTEGER, decision_reason TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (backup_id) REFERENCES backup_history(id) ON DELETE CASCADE,
      FOREIGN KEY (validation_id) REFERENCES dr_validations(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_restore_requests_tenant ON restore_requests(tenant_id,requested_at,id);
    CREATE TABLE IF NOT EXISTS intel_findings (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER,
      title TEXT NOT NULL,
      details TEXT NOT NULL DEFAULT '',
      source TEXT NOT NULL,
      source_locator TEXT NOT NULL DEFAULT '',
      relevance TEXT NOT NULL DEFAULT 'Pending',
      credibility TEXT NOT NULL DEFAULT 'Unrated',
      validation_status TEXT NOT NULL DEFAULT 'Unvalidated',
      operational_significance TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Collected',
      qualified_by TEXT NOT NULL DEFAULT '', qualified_at TEXT NOT NULL DEFAULT '',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_intel_findings_scope ON intel_findings(tenant_id,status,id);
    CREATE TABLE IF NOT EXISTS observation_intake_channels (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      token_hash TEXT NOT NULL UNIQUE,
      status TEXT NOT NULL DEFAULT 'Active',
      expires_at TEXT NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      disabled_by TEXT NOT NULL DEFAULT '', disabled_at TEXT NOT NULL DEFAULT '', disable_reason TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_observation_channels_scope ON observation_intake_channels(tenant_id,status,id);
    CREATE TABLE IF NOT EXISTS observations (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      record_key TEXT NOT NULL UNIQUE,
      intake_type TEXT NOT NULL,
      channel_id INTEGER,
      receipt_hash TEXT NOT NULL DEFAULT '',
      reporter_choice TEXT NOT NULL,
      reporter_name TEXT NOT NULL DEFAULT '',
      reporter_contact TEXT NOT NULL DEFAULT '',
      report_on_behalf_of TEXT NOT NULL DEFAULT '',
      title TEXT NOT NULL,
      narrative TEXT NOT NULL,
      location TEXT NOT NULL DEFAULT '',
      observed_at TEXT NOT NULL,
      context TEXT NOT NULL DEFAULT '',
      reported_urgency TEXT NOT NULL DEFAULT 'Routine',
      source_protection TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Submitted',
      acknowledged_by TEXT NOT NULL DEFAULT '', acknowledged_at TEXT NOT NULL DEFAULT '', acknowledgement_reason TEXT NOT NULL DEFAULT '',
      triage_category TEXT NOT NULL DEFAULT '', triage_priority TEXT NOT NULL DEFAULT '', triage_notes TEXT NOT NULL DEFAULT '',
      assigned_to TEXT NOT NULL DEFAULT '', triaged_by TEXT NOT NULL DEFAULT '', triaged_at TEXT NOT NULL DEFAULT '',
      route_target TEXT NOT NULL DEFAULT '', routed_record_type TEXT NOT NULL DEFAULT '', routed_record_id INTEGER,
      route_reason TEXT NOT NULL DEFAULT '', routed_by TEXT NOT NULL DEFAULT '', routed_at TEXT NOT NULL DEFAULT '',
      disposition TEXT NOT NULL DEFAULT '', closed_by TEXT NOT NULL DEFAULT '', closed_at TEXT NOT NULL DEFAULT '',
      retention_until TEXT NOT NULL, legal_hold INTEGER NOT NULL DEFAULT 0,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (channel_id) REFERENCES observation_intake_channels(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_observations_scope ON observations(tenant_id,status,id);
    CREATE TABLE IF NOT EXISTS observation_attachments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      observation_id INTEGER NOT NULL,
      original_name TEXT NOT NULL,
      stored_name TEXT NOT NULL,
      content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
      size_bytes INTEGER NOT NULL DEFAULT 0,
      sha256 TEXT NOT NULL,
      uploaded_by TEXT NOT NULL DEFAULT '',
      scan_status TEXT NOT NULL, scan_detail TEXT NOT NULL DEFAULT '', scanned_at TEXT NOT NULL,
      retention_until TEXT NOT NULL, legal_hold INTEGER NOT NULL DEFAULT 0,
      disposition_status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_observation_attachments_scope ON observation_attachments(tenant_id,observation_id,id);
    CREATE TABLE IF NOT EXISTS observation_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      observation_id INTEGER NOT NULL,
      version_no INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      reason TEXT NOT NULL DEFAULT '',
      snapshot_json TEXT NOT NULL,
      changed_by TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE,
      UNIQUE(observation_id,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_observation_events_scope ON observation_events(tenant_id,observation_id,version_no);
    CREATE TABLE IF NOT EXISTS cop_coordination_threads (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER,
      subject TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Open',
      assigned_contact TEXT NOT NULL DEFAULT '',
      assigned_contact_summary TEXT NOT NULL DEFAULT '',
      created_by TEXT NOT NULL,
      created_by_role TEXT NOT NULL,
      created_at TEXT NOT NULL,
      assigned_by TEXT NOT NULL DEFAULT '', assigned_at TEXT NOT NULL DEFAULT '',
      closed_by TEXT NOT NULL DEFAULT '', closed_at TEXT NOT NULL DEFAULT '', close_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_cop_threads_scope ON cop_coordination_threads(tenant_id,status,id);
    CREATE TABLE IF NOT EXISTS cop_coordination_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      thread_id INTEGER NOT NULL,
      audience TEXT NOT NULL DEFAULT 'Shared',
      body TEXT NOT NULL,
      author TEXT NOT NULL,
      author_role TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (thread_id) REFERENCES cop_coordination_threads(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_cop_messages_scope ON cop_coordination_messages(tenant_id,thread_id,id);
    CREATE TABLE IF NOT EXISTS cop_decision_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER,
      source_type TEXT NOT NULL,
      source_id INTEGER NOT NULL,
      action_type TEXT NOT NULL,
      title TEXT NOT NULL,
      member_summary TEXT NOT NULL,
      allowed_choices_json TEXT NOT NULL,
      due_at TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Awaiting Decision',
      requested_by TEXT NOT NULL,
      requested_at TEXT NOT NULL,
      decision TEXT NOT NULL DEFAULT '',
      rationale TEXT NOT NULL DEFAULT '',
      conditions TEXT NOT NULL DEFAULT '',
      authorized_amount_cents INTEGER NOT NULL DEFAULT 0,
      decided_by TEXT NOT NULL DEFAULT '', decided_by_role TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL DEFAULT '',
      withdrawn_by TEXT NOT NULL DEFAULT '', withdrawn_at TEXT NOT NULL DEFAULT '', withdrawal_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_cop_decisions_scope ON cop_decision_requests(tenant_id,status,due_at,id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_cop_decisions_one_pending ON cop_decision_requests(tenant_id,source_type,source_id,action_type) WHERE status='Awaiting Decision';
    CREATE TABLE IF NOT EXISTS cop_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      record_type TEXT NOT NULL,
      record_id INTEGER NOT NULL,
      version_no INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      summary TEXT NOT NULL,
      snapshot_json TEXT NOT NULL,
      changed_by TEXT NOT NULL,
      changed_by_role TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,record_type,record_id,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_cop_events_scope ON cop_events(tenant_id,record_type,record_id,version_no);
    CREATE TABLE IF NOT EXISTS ops_service_pillars (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      pillar_code TEXT NOT NULL,
      name TEXT NOT NULL,
      description TEXT NOT NULL,
      sort_order INTEGER NOT NULL,
      status TEXT NOT NULL DEFAULT 'Active',
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,pillar_code)
    );
    CREATE INDEX IF NOT EXISTS idx_ops_service_pillars_scope ON ops_service_pillars(tenant_id,status,sort_order);
    CREATE TABLE IF NOT EXISTS ops_service_catalog (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      pillar_id INTEGER NOT NULL,
      service_key TEXT NOT NULL,
      version_no INTEGER NOT NULL,
      supersedes_id INTEGER,
      name TEXT NOT NULL,
      member_description TEXT NOT NULL,
      internal_scope TEXT NOT NULL,
      default_deliverables TEXT NOT NULL,
      readiness_inputs TEXT NOT NULL,
      authorization_requirements TEXT NOT NULL,
      industry_profile_id INTEGER,
      industry_profile_key_snapshot TEXT NOT NULL DEFAULT '',
      industry_profile_version_snapshot INTEGER,
      industry_profile_name_snapshot TEXT NOT NULL DEFAULT '',
      industry_defaults_snapshot_json TEXT NOT NULL DEFAULT '{}',
      member_visible INTEGER NOT NULL DEFAULT 1,
      status TEXT NOT NULL DEFAULT 'Draft',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      last_material_editor TEXT NOT NULL, last_material_edit_at TEXT NOT NULL,
      submitted_by TEXT NOT NULL DEFAULT '', submitted_at TEXT NOT NULL DEFAULT '',
      reviewed_by TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '', review_reason TEXT NOT NULL DEFAULT '',
      approved_by TEXT NOT NULL DEFAULT '', approved_at TEXT NOT NULL DEFAULT '', approval_reason TEXT NOT NULL DEFAULT '',
      published_by TEXT NOT NULL DEFAULT '', published_at TEXT NOT NULL DEFAULT '', publish_reason TEXT NOT NULL DEFAULT '',
      retired_by TEXT NOT NULL DEFAULT '', retired_at TEXT NOT NULL DEFAULT '', retirement_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (pillar_id) REFERENCES ops_service_pillars(id) ON DELETE RESTRICT,
      FOREIGN KEY (supersedes_id) REFERENCES ops_service_catalog(id) ON DELETE SET NULL,
      FOREIGN KEY (industry_profile_id) REFERENCES industry_profiles(id) ON DELETE SET NULL,
      UNIQUE(tenant_id,service_key,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_ops_service_catalog_scope ON ops_service_catalog(tenant_id,status,pillar_id,id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ops_service_catalog_published ON ops_service_catalog(tenant_id,service_key) WHERE status='Published';
    CREATE TABLE IF NOT EXISTS ops_catalog_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      service_id INTEGER NOT NULL,
      version_no INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      summary TEXT NOT NULL,
      snapshot_json TEXT NOT NULL,
      changed_by TEXT NOT NULL,
      changed_by_role TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (service_id) REFERENCES ops_service_catalog(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,service_id,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_ops_catalog_events_scope ON ops_catalog_events(tenant_id,service_id,version_no);
    CREATE TABLE IF NOT EXISTS expert_profiles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      profile_key TEXT NOT NULL,
      expert_actor TEXT NOT NULL,
      member_display_name TEXT NOT NULL,
      member_role_title TEXT NOT NULL,
      member_biography TEXT NOT NULL,
      member_contact_summary TEXT NOT NULL DEFAULT '',
      internal_biography TEXT NOT NULL,
      disciplines TEXT NOT NULL,
      jurisdictions TEXT NOT NULL,
      regions TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Draft',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      last_material_editor TEXT NOT NULL, last_material_edit_at TEXT NOT NULL,
      activated_by TEXT NOT NULL DEFAULT '', activated_at TEXT NOT NULL DEFAULT '', activation_reason TEXT NOT NULL DEFAULT '',
      deactivated_by TEXT NOT NULL DEFAULT '', deactivated_at TEXT NOT NULL DEFAULT '', deactivation_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,profile_key), UNIQUE(tenant_id,expert_actor)
    );
    CREATE INDEX IF NOT EXISTS idx_expert_profiles_scope ON expert_profiles(tenant_id,status,id);
    CREATE TABLE IF NOT EXISTS expert_credentials (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      profile_id INTEGER NOT NULL,
      credential_type TEXT NOT NULL,
      issuer TEXT NOT NULL,
      jurisdiction TEXT NOT NULL DEFAULT '',
      effective_on TEXT NOT NULL,
      expires_on TEXT NOT NULL DEFAULT '',
      evidence_id INTEGER,
      status TEXT NOT NULL DEFAULT 'Unverified',
      entered_by TEXT NOT NULL, entered_at TEXT NOT NULL,
      verified_by TEXT NOT NULL DEFAULT '', verified_at TEXT NOT NULL DEFAULT '', verification_reason TEXT NOT NULL DEFAULT '',
      withdrawn_by TEXT NOT NULL DEFAULT '', withdrawn_at TEXT NOT NULL DEFAULT '', withdrawal_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (profile_id) REFERENCES expert_profiles(id) ON DELETE CASCADE,
      FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_expert_credentials_scope ON expert_credentials(tenant_id,profile_id,status,id);
    CREATE TABLE IF NOT EXISTS expert_availability (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      profile_id INTEGER NOT NULL,
      available_from TEXT NOT NULL,
      available_until TEXT NOT NULL,
      region TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Available',
      recorded_by TEXT NOT NULL, recorded_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (profile_id) REFERENCES expert_profiles(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_expert_availability_scope ON expert_availability(tenant_id,profile_id,status,available_from,available_until);
    CREATE TABLE IF NOT EXISTS ops_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER,
      source_type TEXT NOT NULL,
      source_id INTEGER,
      service_catalog_id INTEGER,
      service_key_snapshot TEXT NOT NULL DEFAULT '',
      service_version_snapshot INTEGER,
      service_name_snapshot TEXT NOT NULL DEFAULT '',
      service_member_description_snapshot TEXT NOT NULL DEFAULT '',
      service_deliverables_snapshot TEXT NOT NULL DEFAULT '',
      title TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      priority TEXT NOT NULL DEFAULT 'Routine',
      status TEXT NOT NULL DEFAULT 'Requested',
      requested_by TEXT NOT NULL, requested_at TEXT NOT NULL,
      authorized_by TEXT NOT NULL DEFAULT '', authorized_at TEXT NOT NULL DEFAULT '',
      assigned_to TEXT NOT NULL DEFAULT '',
      result_summary TEXT NOT NULL DEFAULT '', completed_by TEXT NOT NULL DEFAULT '', completed_at TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE SET NULL,
      FOREIGN KEY (service_catalog_id) REFERENCES ops_service_catalog(id) ON DELETE SET NULL,
      UNIQUE(tenant_id,source_type,source_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ops_requests_scope ON ops_requests(tenant_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_engagements (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      ops_request_id INTEGER NOT NULL,
      service_catalog_id INTEGER,
      service_key_snapshot TEXT NOT NULL DEFAULT '',
      service_version_snapshot INTEGER,
      service_member_scope_snapshot TEXT NOT NULL DEFAULT '',
      service_deliverables_snapshot TEXT NOT NULL DEFAULT '',
      assessment_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      service_type TEXT NOT NULL,
      objective TEXT NOT NULL,
      location TEXT NOT NULL DEFAULT '',
      planned_start TEXT NOT NULL,
      planned_end TEXT NOT NULL,
      operational_lead TEXT NOT NULL,
      communications_plan TEXT NOT NULL,
      member_status_summary TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Planning',
      authorized_by TEXT NOT NULL,
      authorized_at TEXT NOT NULL,
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_by TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      closed_by TEXT NOT NULL DEFAULT '',
      closed_at TEXT NOT NULL DEFAULT '',
      closure_summary TEXT NOT NULL DEFAULT '',
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (ops_request_id) REFERENCES ops_requests(id) ON DELETE CASCADE,
      FOREIGN KEY (service_catalog_id) REFERENCES ops_service_catalog(id) ON DELETE SET NULL,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,ops_request_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ops_engagements_scope ON ops_engagements(tenant_id,assessment_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_engagement_readiness (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      label TEXT NOT NULL,
      member_summary TEXT NOT NULL,
      internal_requirement TEXT NOT NULL,
      member_visible INTEGER NOT NULL DEFAULT 1,
      due_at TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Pending',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      completed_by TEXT NOT NULL DEFAULT '', completed_at TEXT NOT NULL DEFAULT '', completion_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_ops_engagement_readiness_scope ON ops_engagement_readiness(tenant_id,engagement_id,status,id);
    CREATE TABLE IF NOT EXISTS expert_conflicts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      profile_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      disclosure TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Pending',
      disclosed_by TEXT NOT NULL, disclosed_at TEXT NOT NULL,
      reviewed_by TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '', review_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (profile_id) REFERENCES expert_profiles(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,profile_id,engagement_id)
    );
    CREATE INDEX IF NOT EXISTS idx_expert_conflicts_scope ON expert_conflicts(tenant_id,engagement_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_engagement_assignments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      profile_id INTEGER NOT NULL,
      conflict_id INTEGER NOT NULL,
      assignment_role TEXT NOT NULL,
      member_display_name_snapshot TEXT NOT NULL,
      member_role_title_snapshot TEXT NOT NULL,
      member_biography_snapshot TEXT NOT NULL,
      member_contact_summary_snapshot TEXT NOT NULL DEFAULT '',
      qualification_snapshot TEXT NOT NULL,
      member_visible INTEGER NOT NULL DEFAULT 1,
      status TEXT NOT NULL DEFAULT 'Proposed',
      proposed_by TEXT NOT NULL, proposed_at TEXT NOT NULL,
      accepted_by TEXT NOT NULL DEFAULT '', accepted_at TEXT NOT NULL DEFAULT '', acceptance_reason TEXT NOT NULL DEFAULT '',
      released_by TEXT NOT NULL DEFAULT '', released_at TEXT NOT NULL DEFAULT '', release_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (profile_id) REFERENCES expert_profiles(id) ON DELETE RESTRICT,
      FOREIGN KEY (conflict_id) REFERENCES expert_conflicts(id) ON DELETE RESTRICT
    );
    CREATE INDEX IF NOT EXISTS idx_ops_assignments_scope ON ops_engagement_assignments(tenant_id,engagement_id,status,id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ops_assignments_active ON ops_engagement_assignments(tenant_id,engagement_id,profile_id) WHERE status IN ('Proposed','Accepted');
    CREATE TABLE IF NOT EXISTS expert_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      record_type TEXT NOT NULL,
      record_id INTEGER NOT NULL,
      version_no INTEGER NOT NULL,
      event_type TEXT NOT NULL,
      summary TEXT NOT NULL,
      snapshot_json TEXT NOT NULL,
      changed_by TEXT NOT NULL,
      changed_by_role TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,record_type,record_id,version_no)
    );
    CREATE INDEX IF NOT EXISTS idx_expert_events_scope ON expert_events(tenant_id,record_type,record_id,version_no);
    CREATE TABLE IF NOT EXISTS ops_tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      assignment_id INTEGER,
      title TEXT NOT NULL,
      instructions TEXT NOT NULL,
      assigned_to TEXT NOT NULL,
      priority TEXT NOT NULL DEFAULT 'Routine',
      status TEXT NOT NULL DEFAULT 'Assigned',
      created_by TEXT NOT NULL,
      created_at TEXT NOT NULL,
      started_by TEXT NOT NULL DEFAULT '',
      started_at TEXT NOT NULL DEFAULT '',
      completed_by TEXT NOT NULL DEFAULT '',
      completed_at TEXT NOT NULL DEFAULT '',
      result_summary TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (assignment_id) REFERENCES ops_engagement_assignments(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_ops_tasks_scope ON ops_tasks(tenant_id,engagement_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_field_reports (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      task_id INTEGER,
      report_type TEXT NOT NULL,
      occurred_at TEXT NOT NULL,
      member_summary TEXT NOT NULL,
      internal_details TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Draft',
      submitted_by TEXT NOT NULL,
      submitted_at TEXT NOT NULL,
      released_by TEXT NOT NULL DEFAULT '',
      released_at TEXT NOT NULL DEFAULT '',
      release_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (task_id) REFERENCES ops_tasks(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_ops_field_reports_scope ON ops_field_reports(tenant_id,engagement_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_estimates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      currency TEXT NOT NULL DEFAULT 'USD',
      member_summary TEXT NOT NULL,
      internal_basis TEXT NOT NULL,
      total_cents INTEGER NOT NULL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'Draft',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      submitted_by TEXT NOT NULL DEFAULT '', submitted_at TEXT NOT NULL DEFAULT '',
      decided_by TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL DEFAULT '', decision_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_ops_estimates_scope ON ops_estimates(tenant_id,engagement_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_estimate_lines (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      estimate_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      category TEXT NOT NULL,
      description TEXT NOT NULL,
      quantity TEXT NOT NULL,
      unit TEXT NOT NULL,
      unit_rate_cents INTEGER NOT NULL,
      line_total_cents INTEGER NOT NULL,
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (estimate_id) REFERENCES ops_estimates(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_ops_estimate_lines_scope ON ops_estimate_lines(tenant_id,estimate_id,id);
    CREATE TABLE IF NOT EXISTS ops_expenses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      task_id INTEGER,
      evidence_id INTEGER,
      category TEXT NOT NULL,
      description TEXT NOT NULL,
      member_description TEXT NOT NULL,
      vendor TEXT NOT NULL DEFAULT '',
      incurred_on TEXT NOT NULL,
      amount_cents INTEGER NOT NULL,
      currency TEXT NOT NULL DEFAULT 'USD',
      reimbursable INTEGER NOT NULL DEFAULT 1,
      status TEXT NOT NULL DEFAULT 'Draft',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      submitted_by TEXT NOT NULL DEFAULT '', submitted_at TEXT NOT NULL DEFAULT '',
      decided_by TEXT NOT NULL DEFAULT '', decided_at TEXT NOT NULL DEFAULT '', decision_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      FOREIGN KEY (task_id) REFERENCES ops_tasks(id) ON DELETE SET NULL,
      FOREIGN KEY (evidence_id) REFERENCES evidence(id) ON DELETE SET NULL
    );
    CREATE INDEX IF NOT EXISTS idx_ops_expenses_scope ON ops_expenses(tenant_id,engagement_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_invoice_statements (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
      statement_number TEXT NOT NULL,
      billing_period_start TEXT NOT NULL,
      billing_period_end TEXT NOT NULL,
      service_summary TEXT NOT NULL,
      currency TEXT NOT NULL DEFAULT 'USD',
      estimate_total_cents INTEGER NOT NULL,
      approved_actual_total_cents INTEGER NOT NULL,
      billable_total_cents INTEGER NOT NULL,
      variance_cents INTEGER NOT NULL,
      snapshot_json TEXT NOT NULL,
      snapshot_sha256 TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Draft',
      created_by TEXT NOT NULL, created_at TEXT NOT NULL,
      reviewed_by TEXT NOT NULL DEFAULT '', reviewed_at TEXT NOT NULL DEFAULT '', review_reason TEXT NOT NULL DEFAULT '',
      approved_by TEXT NOT NULL DEFAULT '', approved_at TEXT NOT NULL DEFAULT '', approval_reason TEXT NOT NULL DEFAULT '',
      released_by TEXT NOT NULL DEFAULT '', released_at TEXT NOT NULL DEFAULT '', release_reason TEXT NOT NULL DEFAULT '',
      updated_at TEXT NOT NULL,
      FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
      FOREIGN KEY (engagement_id) REFERENCES ops_engagements(id) ON DELETE CASCADE,
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,engagement_id),
      UNIQUE(tenant_id,statement_number)
    );
    CREATE INDEX IF NOT EXISTS idx_ops_invoice_statements_scope ON ops_invoice_statements(tenant_id,assessment_id,status,id);
    ''')
    ensure_column('evidence_attachments','scan_status','TEXT NOT NULL DEFAULT "Legacy/Unscanned"')
    ensure_column('evidence_attachments','scan_detail','TEXT NOT NULL DEFAULT ""')
    ensure_column('evidence_attachments','scanned_at','TEXT NOT NULL DEFAULT ""')
    ensure_column('evidence_attachments','retention_until','TEXT NOT NULL DEFAULT ""')
    ensure_column('evidence_attachments','legal_hold','INTEGER NOT NULL DEFAULT 0')
    ensure_column('evidence_attachments','disposition_status','TEXT NOT NULL DEFAULT "Active"')
    ensure_column('assessment_weights','risk_methodology_version',"TEXT NOT NULL DEFAULT '1.1.0'")
    ensure_column('ops_requests','service_catalog_id','INTEGER')
    ensure_column('ops_requests','service_key_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_requests','service_version_snapshot','INTEGER')
    ensure_column('ops_requests','service_name_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_requests','service_member_description_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_requests','service_deliverables_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_engagements','service_catalog_id','INTEGER')
    ensure_column('ops_engagements','service_key_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_engagements','service_version_snapshot','INTEGER')
    ensure_column('ops_engagements','service_member_scope_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_engagements','service_deliverables_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_tasks','assignment_id','INTEGER')
    ensure_column('assessments','industry_profile_id','INTEGER')
    ensure_column('assessments','industry_profile_key_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','industry_profile_version_snapshot','INTEGER')
    ensure_column('assessments','industry_profile_name_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','industry_member_summary_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','industry_defaults_snapshot_json',"TEXT NOT NULL DEFAULT '{}'")
    ensure_column('assessments','industry_profile_applied_by',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','industry_profile_applied_at',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','covered_operation',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','requested_package_level','INTEGER NOT NULL DEFAULT 0')
    ensure_column('assessments','requested_scope_band',"TEXT NOT NULL DEFAULT ''")
    ensure_column('assessments','requested_access_variant',"TEXT NOT NULL DEFAULT ''")
    ensure_column('package_quote_versions','agreement_artifact_id','INTEGER NOT NULL DEFAULT 0')
    ensure_column('package_quote_versions','assessment_scope_sha256',"TEXT NOT NULL DEFAULT ''")
    ensure_column('package_product_report_versions','display_title',"TEXT NOT NULL DEFAULT ''")
    ensure_column('package_product_report_versions','retention_until',"TEXT NOT NULL DEFAULT ''")
    ensure_column('package_product_report_versions','legal_hold','INTEGER NOT NULL DEFAULT 0')
    ensure_column('package_product_report_versions','disposition_status',"TEXT NOT NULL DEFAULT 'Active'")
    ensure_column('package_report_qa_evidence','submitted_user_id','INTEGER')
    report_retention=(datetime.now(timezone.utc)+timedelta(days=max(1,RETENTION_DEFAULT_DAYS))).replace(microsecond=0).isoformat().replace('+00:00','Z')
    conn.execute("UPDATE package_product_report_versions SET retention_until=? WHERE retention_until=''",(report_retention,))
    for field in ('included_work','report_deliverables','member_inputs','evidence_allowance','clarification_allowance','field_specialist_terms','payment_terms','tax_treatment','change_triggers'):
        ensure_column('package_quote_versions',field,"TEXT NOT NULL DEFAULT ''")
    ensure_column('package_acceptances','agreement_download_id','INTEGER NOT NULL DEFAULT 0')
    ensure_column('ops_service_catalog','industry_profile_id','INTEGER')
    ensure_column('ops_service_catalog','industry_profile_key_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_service_catalog','industry_profile_version_snapshot','INTEGER')
    ensure_column('ops_service_catalog','industry_profile_name_snapshot',"TEXT NOT NULL DEFAULT ''")
    ensure_column('ops_service_catalog','industry_defaults_snapshot_json',"TEXT NOT NULL DEFAULT '{}'")
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('0.8.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('0.9.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.0.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.1.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.2.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.3.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.4.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.6.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.7.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.8.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.9.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.10.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.11.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.12.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.13.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('2.14.0',now()))

    # v0.6 tenant/bootstrap migration. Existing records are assigned to the default tenant.
    if conn.execute('SELECT COUNT(*) c FROM tenants').fetchone()['c'] == 0:
        conn.execute('INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)',('Salus Prototype','salus-prototype','Active',now()))
    default_tenant=conn.execute('SELECT id FROM tenants ORDER BY id LIMIT 1').fetchone()['id']
    pillars=(
        ('readiness','Readiness and Preparedness','Risk, preparedness, planning, training, exercise, and readiness services.',10),
        ('protective','Protective Operations','Protective intelligence, executive protection, security, and investigation services.',20),
        ('incident','Incident and Crisis Support','Incident management, disaster response, crisis communications, and urgent support services.',30),
        ('recovery','Recovery and Sustainment','Recovery, continuity, after-action, improvement, and sustained-support services.',40),
    )
    for tenant in conn.execute('SELECT id FROM tenants ORDER BY id'):
        for code,name,description,sort_order in pillars:
            conn.execute('INSERT INTO ops_service_pillars(tenant_id,pillar_code,name,description,sort_order,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,pillar_code) DO NOTHING',(tenant['id'],code,name,description,sort_order,'Active','system-migration',now()))
    conn.execute('UPDATE assessments SET tenant_id=? WHERE tenant_id IS NULL OR tenant_id=0',(default_tenant,))
    conn.execute('UPDATE audit_log SET tenant_id=? WHERE tenant_id IS NULL OR tenant_id=0',(default_tenant,))

    # Normalize legacy prototype improvement state to the recorded executive decision.
    conn.execute("""UPDATE improvements SET status='Approved' WHERE id IN (SELECT improvement_id FROM decisions WHERE improvement_id IS NOT NULL AND decision_type IN ('Approve','Approve with Conditions')) AND status='Decision Recorded'""")
    conn.commit()

    count = conn.execute('SELECT COUNT(*) c FROM assessments').fetchone()['c']
    if count == 0 and SEED_DEMO:
        ts = now()
        cur = conn.execute('''INSERT INTO assessments(tenant_id,name,organization,assessment_type,purpose,mission,scope,status,executive_sponsor,assessment_director,lead_assessor,start_date,target_completion,reassessment_date,classification,scope_locked,version,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(default_tenant,
          'Demonstration Enterprise THIRA','Example Client','Enterprise','Demonstrate Salus THIRA Command','Maintain critical operations and protect people during disruptive events','Enterprise critical operations','Analysis','Executive Sponsor','Salus Assessment Director','Lead Assessor','2026-08-29','2026-09-30','2026-12-31','Standard',1,1,ts,ts))
        aid=cur.lastrowid
        audit(conn,'CREATE','assessment',aid,'Seed assessment')
        cur=conn.execute('''INSERT INTO threats(assessment_id,name,category,subcategory,description,likelihood,vulnerability,consequence,confidence,trend,inclusion_status,basis,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(aid,'Severe Weather / Extended Power Loss','Natural','Severe Weather','Major storm causes regional power and telecom disruption',4,4,5,'High','Increasing','Included - Scenario Required','Historical occurrence and regional exposure','Active',ts,ts))
        tid=cur.lastrowid
        audit(conn,'CREATE','threat',tid,'Seed threat')
        cur=conn.execute('''INSERT INTO scenarios(assessment_id,threat_id,title,narrative,initiating_event,location,duration,operating_conditions,dependencies,decision_points,assumptions,uncertainties,life_safety,mission,operations,financial,legal_regulatory,reputation,recovery,evidence_confidence,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(aid,tid,'72-Hour Regional Outage','Severe storm causes prolonged outage, telecom congestion, workforce disruption, and fuel resupply constraints.','Severe storm impact','Primary operating region','72 hours','Grid outage; cellular congestion; constrained road access','Generator fuel; telecom; workforce; suppliers','Activate crisis team; reduce service; request mutual aid','Generator starts successfully','Duration of telecom degradation',3,5,5,4,3,4,5,'Medium',ts,ts))
        sid=cur.lastrowid
        audit(conn,'CREATE','scenario',sid,'Seed scenario')
        cur=conn.execute('''INSERT INTO capabilities(assessment_id,scenario_id,name,mission_area,capability_family,required_outcome,operating_conditions,performance_metric,required_standard,current_performance,responsible_function,owner,dependencies,evidence_required,confidence,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(aid,sid,'Emergency Notification','Protection / Response','Communications','Notify affected workforce rapidly','Commercial power outage and cellular congestion','Percent reached within 15 minutes',95,72,'Security Operations','Program Owner','HR contact data; multi-channel platform','Exercise logs; platform delivery report','High',ts,ts))
        cid=cur.lastrowid
        audit(conn,'CREATE','capability',cid,'Seed capability')
        cur=conn.execute('''INSERT INTO gaps(assessment_id,capability_id,gap_type,description,severity,root_cause,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)''',(aid,cid,'Communications','Required performance is 95% within 15 minutes; demonstrated performance is 72%.','High','Incomplete contact data and no secondary delivery mechanism','Open',ts,ts))
        gid=cur.lastrowid
        audit(conn,'CREATE','gap',gid,'Seed gap')
        cur=conn.execute('''INSERT INTO improvements(assessment_id,gap_id,title,description,initial_cost,recurring_cost,implementation_days,feasibility,consequence_reduction,mission_benefit,sustainability,dependencies,owner,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(aid,gid,'Implement redundant notification channels','Clean contact data and add secondary delivery path.',25000,6000,60,4,4,5,4,'HR data cleanup','Program Owner','Proposed',ts,ts))
        iid=cur.lastrowid
        audit(conn,'CREATE','improvement',iid,'Seed improvement')
        conn.commit()
    conn.close()

init_db()

class AssessmentIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str = Field(min_length=1, max_length=160)
    organization: str = Field(min_length=1, max_length=160)
    assessment_type: str = Field(default='Enterprise', max_length=80)
    purpose: str = Field(default='', max_length=2000)
    mission: str = Field(default='', max_length=2000)
    scope: str = Field(default='', max_length=4000)
    covered_operation: str = Field(default='', max_length=240)
    requested_package_level: Literal[0,1,2,3] = 0
    requested_scope_band: Literal['','A','B','C'] = ''
    requested_access_variant: Literal['','Access','Standard'] = ''
    exclusions: str = Field(default='', max_length=2000)
    executive_sponsor: str = Field(default='', max_length=160)
    assessment_director: str = Field(default='', max_length=160)
    lead_assessor: str = Field(default='', max_length=160)
    start_date: str = Field(default='', max_length=10)
    target_completion: str = Field(default='', max_length=10)
    reassessment_date: str = Field(default='', max_length=10)
    classification: Literal['Standard','Restricted','Sensitive','Highly Sensitive'] = 'Standard'
    industry_profile_id: Optional[int] = Field(default=None, gt=0)

    @field_validator('name','organization')
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('assessment_type','purpose','mission','scope','covered_operation','exclusions','executive_sponsor','assessment_director','lead_assessor')
    @classmethod
    def normalized_text(cls, value: str) -> str:
        return value.strip()

class PackageQuoteIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessment_version: int = Field(gt=0)
    level: Literal[1,2,3]
    predecessor_qualification_id: int = Field(default=0,ge=0)
    band: Literal['A','B','C']
    variant: Literal['','Access','Standard'] = ''
    covered_operation: str = Field(min_length=1,max_length=240)
    exclusions: str = Field(min_length=1,max_length=2000)
    scope_basis: str = Field(min_length=1,max_length=2000)
    included_work: str = Field(min_length=1,max_length=2000)
    report_deliverables: Literal['SalINTEL, SalTHIRA, SalOPS, SalCAPA'] = 'SalINTEL, SalTHIRA, SalOPS, SalCAPA'
    member_inputs: str = Field(min_length=1,max_length=2000)
    evidence_allowance: str = Field(min_length=1,max_length=2000)
    clarification_allowance: str = Field(min_length=1,max_length=2000)
    field_specialist_terms: str = Field(min_length=1,max_length=2000)
    payment_terms: str = Field(min_length=1,max_length=2000)
    tax_treatment: str = Field(min_length=1,max_length=2000)
    change_triggers: str = Field(min_length=1,max_length=2000)
    decision_owner: str = Field(min_length=1,max_length=160)
    source_receipt_id: str = Field(default='',max_length=160)
    fee_cents: int = Field(gt=0,le=1_000_000_000)
    currency: Literal['USD'] = 'USD'
    valid_until: str = Field(min_length=10,max_length=10)
    start_date: str = Field(default='',max_length=10)
    delivery_date: str = Field(default='',max_length=10)
    capacity_confirmed: bool
    access_eligibility_confirmed: bool = False
    access_eligibility_basis: str = Field(default='',max_length=2000)
    agreement_artifact_id: int = Field(gt=0)
    agreement_reference: str = Field(min_length=1,max_length=240)
    agreement_sha256: str = Field(pattern=r'^[a-fA-F0-9]{64}$')
    separate_services_excluded: bool

class PackageAcceptanceIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quote_id: int = Field(gt=0)
    quote_sha256: str = Field(pattern=r'^[a-fA-F0-9]{64}$')
    agreement_sha256: str = Field(pattern=r'^[a-fA-F0-9]{64}$')
    member_authority_basis: str = Field(min_length=3,max_length=1000)
    idempotency_key: str = Field(pattern=r'^[A-Za-z0-9_-]{16,120}$')
    accept_quote_and_agreement: Literal[True]

class PackageMemberAuthorityReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quote_id: int = Field(gt=0)
    member_user_id: int = Field(gt=0)
    authority_basis: str = Field(min_length=12,max_length=1000)
    evidence_reference: str = Field(min_length=8,max_length=500)
    confirm_external_authority: Literal[True]

class PackageIntakeSelectionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_keys: list[str] = Field(min_length=1,max_length=11)
    request_reason: str = Field(min_length=12,max_length=1000)

class PackageIntakeResponseIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Not held','Not known','Prefer to discuss']

class PackageHandoffClaimIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    claim_code: str = Field(min_length=32,max_length=120)
    confirm_requested_boundary: Literal[True]

class PackageHandoffReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessment_version: int = Field(gt=0)
    organization_match_basis: str = Field(min_length=12,max_length=1000)
    covered_boundary_basis: str = Field(min_length=12,max_length=1000)
    decision_role_basis: str = Field(min_length=12,max_length=1000)
    confirm_exact_receipt: Literal[True]

def verified_package_quote(conn,row,request:Request):
    content={key:row[key] for key in PackageQuoteIn.model_fields if key!='predecessor_qualification_id'}
    if row['assessment_scope_sha256']:
        content['assessment_scope_sha256']=row['assessment_scope_sha256']
    for key in ('capacity_confirmed','access_eligibility_confirmed','separate_services_excluded'):
        content[key]=bool(content[key])
    content.update(assessment_id=row['assessment_id'],tenant_id=row['tenant_id'],version_no=row['version_no'])
    if quote_digest(content)!=row['content_sha256']:
        security_event(request,'PACKAGE_QUOTE_INTEGRITY_FAILURE','High',f'quote_id={row["id"]}')
        raise HTTPException(409,'The quote failed integrity verification.')
    agreement=conn.execute('''SELECT content_sha256,scan_status FROM package_agreement_artifacts
        WHERE id=? AND tenant_id=? AND assessment_id=?''',
        (row['agreement_artifact_id'],row['tenant_id'],row['assessment_id'])).fetchone()
    if (not agreement or agreement['content_sha256']!=row['agreement_sha256'].lower()
            or agreement['scan_status']!='Clean'):
        raise HTTPException(409,'The quoted agreement has not passed the file security check.')
    return row

def _member_authority_review_digest(row):
    fields=('tenant_id','assessment_id','quote_id','member_user_id','authority_basis',
            'evidence_reference','reviewed_by_user_id','reviewed_at')
    content={key:row[key] for key in fields}
    return hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def verified_member_authority_review(conn,quote,member_user_id:int):
    review=conn.execute('''SELECT * FROM package_member_authority_reviews
        WHERE tenant_id=? AND assessment_id=? AND quote_id=?''',
        (quote['tenant_id'],quote['assessment_id'],quote['id'])).fetchone()
    if (not review or review['member_user_id']!=member_user_id
            or review['record_sha256']!=_member_authority_review_digest(review)):
        raise HTTPException(409,'Salus must verify this Member signer for the exact quote before acceptance.')
    return review

def lock_package_assessment(conn, assessment_id:int):
    """Serialize a package-boundary decision with other assessment writes."""
    if is_sqlite():
        conn.execute('BEGIN IMMEDIATE')
    else:
        conn.execute('SELECT id FROM assessments WHERE id=? FOR UPDATE',(assessment_id,))

def verified_package_predecessor(conn,qualification_id:int,request:Request,current,level:int):
    tid=tenant_id(request)
    qualification=conn.execute('''SELECT * FROM package_predecessor_qualifications
        WHERE id=? AND tenant_id=?''',(qualification_id,tid)).fetchone()
    if not qualification: raise HTTPException(409,'A qualified prior package is required.')
    keys=('assessment_id','issue_id','issue_sha256','acknowledgment_id',
        'acknowledgment_sha256','quote_id','level','band','covered_operation',
        'exclusions','assessment_scope_sha256','qualification_basis',
        'limitations_disposition','reviewer_user_id')
    record={key:qualification[key] for key in keys}
    if hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=qualification['record_sha256']:
        raise HTTPException(409,'The predecessor qualification failed integrity verification.')
    prior_assessment=conn.execute('SELECT * FROM assessments WHERE id=? AND tenant_id=?',
        (qualification['assessment_id'],tid)).fetchone()
    issue=conn.execute('''SELECT * FROM package_report_issue_packets WHERE id=? AND tenant_id=?''',
        (qualification['issue_id'],tid)).fetchone()
    acknowledgment=conn.execute('''SELECT * FROM package_report_issue_acknowledgments
        WHERE id=? AND tenant_id=?''',(qualification['acknowledgment_id'],tid)).fetchone()
    prior_quote=conn.execute('SELECT * FROM package_quote_versions WHERE id=? AND tenant_id=?',
        (qualification['quote_id'],tid)).fetchone()
    reviewer=conn.execute('SELECT role,status FROM users WHERE id=? AND tenant_id=?',
        (qualification['reviewer_user_id'],tid)).fetchone()
    if not prior_assessment or not issue or not acknowledgment or not prior_quote or not reviewer:
        raise HTTPException(409,'The predecessor source package is incomplete.')
    reports=verified_package_issue_record(issue)
    latest=conn.execute('''SELECT id FROM package_report_issue_packets WHERE tenant_id=?
        AND assessment_id=? ORDER BY id DESC LIMIT 1''',(tid,qualification['assessment_id'])).fetchone()
    acknowledgment_record={key:acknowledgment[key] for key in
        ('issue_id','issue_sha256','recipient_user_id','acknowledgment_note','idempotency_key')}
    acknowledgment_digest=hashlib.sha256(json.dumps(acknowledgment_record,
        sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if (not latest or latest['id']!=issue['id'] or issue['assessment_id']!=prior_assessment['id']
            or qualification['issue_sha256']!=issue['record_sha256']
            or acknowledgment['issue_id']!=issue['id']
            or acknowledgment['issue_sha256']!=issue['record_sha256']
            or acknowledgment['recipient_user_id']!=issue['recipient_user_id']
            or acknowledgment['record_sha256']!=acknowledgment_digest
            or qualification['acknowledgment_sha256']!=acknowledgment_digest
            or qualification['reviewer_user_id']==issue['issued_by_user_id']
            or qualification['quote_id']!=issue['quote_id']
            or prior_quote['assessment_id']!=prior_assessment['id']
            or qualification['level']!=prior_quote['level']
            or qualification['band']!=prior_quote['band']
            or qualification['assessment_scope_sha256']!=prior_quote['assessment_scope_sha256']
            or qualification['assessment_scope_sha256']!=assessment_scope_digest(prior_assessment)
            or reviewer['status']!='Active'
            or reviewer['role'] not in ('System Administrator','Assessment Director')
            or qualification['level']!=level-1
            or qualification['assessment_id']==current['id']
            or prior_assessment['organization']!=current['organization']
            or qualification['covered_operation']!=current['covered_operation']
            or qualification['exclusions']!=current['exclusions']):
        raise HTTPException(409,'The predecessor does not match this Member, sequence or decision boundary.')
    verified_package_quote(conn,prior_quote,request)
    for product,snapshot in reports.items():
        report=conn.execute('''SELECT * FROM package_product_report_versions
            WHERE tenant_id=? AND assessment_id=? AND product=? ORDER BY version_no DESC LIMIT 1''',
            (tid,prior_assessment['id'],product)).fetchone()
        if (not report or report['id']!=snapshot['report_id'] or report['status']!='Issued'
                or report['content_sha256']!=snapshot['content_sha256']):
            raise HTTPException(409,f'{product}: the predecessor report changed.')
    return qualification

def verified_quote_predecessor_link(conn,quote,request:Request,current):
    link=conn.execute('''SELECT * FROM package_quote_predecessor_links WHERE tenant_id=?
        AND quote_id=? AND assessment_id=?''',(tenant_id(request),quote['id'],current['id'])).fetchone()
    if not link: raise HTTPException(409,'The later-level quote lacks its predecessor link.')
    record={'assessment_id':link['assessment_id'],'quote_id':link['quote_id'],
        'qualification_id':link['qualification_id'],
        'qualification_sha256':link['qualification_sha256']}
    digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=link['record_sha256']:
        raise HTTPException(409,'The predecessor quote link failed integrity verification.')
    qualification=verified_package_predecessor(conn,link['qualification_id'],request,current,quote['level'])
    if qualification['record_sha256']!=link['qualification_sha256']:
        raise HTTPException(409,'The predecessor qualification version changed.')
    return link

def require_package_commercial_candidate():
    if not PACKAGE_COMMERCIAL_WORKFLOW_ENABLED or ENVIRONMENT=='production':
        raise HTTPException(503,'Package quotes and acceptance are held for governed agreement delivery and release review.')

class ThreatIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    assessment_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    subcategory: str = Field(default='', max_length=120)
    description: str = Field(default='', max_length=4000)
    likelihood: int = Field(default=1, ge=1, le=5)
    vulnerability: int = Field(default=1, ge=1, le=5)
    consequence: int = Field(default=1, ge=1, le=5)
    confidence: Literal['Low','Medium','High'] = 'Medium'
    trend: Literal['Increasing','Stable','Decreasing','Unknown'] = 'Stable'
    inclusion_status: Literal['Included - Scenario Required','Included - Monitor Only','Screened Out','Deferred Pending Evidence'] = 'Included - Scenario Required'
    basis: str = Field(default='', max_length=4000)

    @field_validator('name','category')
    @classmethod
    def required_threat_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('subcategory','description','basis')
    @classmethod
    def normalized_threat_text(cls, value: str) -> str:
        return value.strip()

class ScenarioIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    assessment_id: int = Field(gt=0)
    threat_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    narrative: str = Field(min_length=1, max_length=6000)
    initiating_event: str = Field(default='', max_length=1000)
    location: str = Field(default='', max_length=500)
    duration: str = Field(default='', max_length=250)
    operating_conditions: str = Field(default='', max_length=4000)
    dependencies: str = Field(default='', max_length=4000)
    decision_points: str = Field(default='', max_length=4000)
    assumptions: str = Field(default='', max_length=4000)
    uncertainties: str = Field(default='', max_length=4000)
    life_safety: int = Field(default=1, ge=1, le=5)
    mission: int = Field(default=1, ge=1, le=5)
    operations: int = Field(default=1, ge=1, le=5)
    financial: int = Field(default=1, ge=1, le=5)
    legal_regulatory: int = Field(default=1, ge=1, le=5)
    reputation: int = Field(default=1, ge=1, le=5)
    recovery: int = Field(default=1, ge=1, le=5)
    evidence_confidence: Literal['Low','Medium','High'] = 'Medium'

    @field_validator('title','narrative')
    @classmethod
    def required_scenario_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('initiating_event','location','duration','operating_conditions','dependencies','decision_points','assumptions','uncertainties')
    @classmethod
    def normalized_scenario_text(cls, value: str) -> str:
        return value.strip()

class CapabilityIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    assessment_id: int = Field(gt=0)
    scenario_id: Optional[int] = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=200)
    mission_area: str = Field(default='', max_length=160)
    capability_family: str = Field(default='', max_length=200)
    required_outcome: str = Field(default='', max_length=4000)
    operating_conditions: str = Field(default='', max_length=4000)
    performance_metric: str = Field(default='', max_length=500)
    measurement_type: Literal['Percentage','Time','Count','Rate','Binary','Currency','Qualitative Rubric'] = 'Percentage'
    measurement_unit: str = Field(default='', max_length=80)
    comparator: Literal['>=','<=','='] = '>='
    required_standard: float = Field(default=100, allow_inf_nan=False)
    current_performance: float = Field(default=0, allow_inf_nan=False)
    responsible_function: str = Field(default='', max_length=200)
    owner: str = Field(default='', max_length=160)
    dependencies: str = Field(default='', max_length=4000)
    evidence_required: str = Field(default='', max_length=4000)
    confidence: Literal['Low','Medium','High'] = 'Medium'
    last_validated: str = Field(default='', max_length=10)
    next_validation: str = Field(default='', max_length=10)

    @field_validator('name')
    @classmethod
    def required_capability_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('mission_area','capability_family','required_outcome','operating_conditions','performance_metric','measurement_unit','responsible_function','owner','dependencies','evidence_required')
    @classmethod
    def normalized_capability_text(cls, value: str) -> str:
        return value.strip()

class EvidenceIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    assessment_id: int = Field(gt=0)
    capability_id: Optional[int] = Field(default=None, gt=0)
    scenario_id: Optional[int] = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=240)
    evidence_type: Literal['Document','Policy','Plan','SOP','Contract','Training Record','Exercise','Exercise Result','Test','Interview','Observation','Inspection','System Record','Performance Data','Incident History','Photograph','Video','Financial Record','External Study','Regulatory Requirement','Intelligence','SME Judgment','Other'] = 'Document'
    source: str = Field(default='', max_length=1000)
    owner: str = Field(default='', max_length=200)
    evidence_date: str = Field(default='', max_length=10)
    reliability: Literal['Low','Medium','High'] = 'Medium'
    verification_status: Literal['Pending','Verified','Conflicting','Rejected'] = 'Pending'
    sensitivity: Literal['Standard','Restricted','Sensitive','Highly Sensitive'] = 'Standard'
    valid_until: str = Field(default='', max_length=10)
    notes: str = Field(default='', max_length=6000)

    @field_validator('title')
    @classmethod
    def required_evidence_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('source','owner','notes')
    @classmethod
    def normalized_evidence_text(cls, value: str) -> str:
        return value.strip()

class EvidenceLifecycleReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    valid_until: str = Field(min_length=1, max_length=10)
    review_note: str = Field(min_length=1, max_length=4000)

class GovernedIntakeIn(BaseModel):
    model_config = ConfigDict(extra='forbid',populate_by_name=True)
    record_type: Literal['Observation','Evidence Lead','Discovery','Decision Input'] = Field(alias='recordType')
    title: str = Field(min_length=1,max_length=160)
    details: str = Field(min_length=1,max_length=4000)
    source_context: str = Field(min_length=1,max_length=500,alias='sourceContext')

class AssessmentReassessmentReviewIn(BaseModel):
    next_reassessment_date: str
    review_outcome: str

class GapIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    assessment_id: int = Field(gt=0)
    capability_id: int = Field(gt=0)
    gap_type: Literal['People','Plans/Procedures','Policy/Governance','Training','Equipment','Technology','Facilities','Communications','Intelligence/Information','Logistics','Staffing','Contracts','Partnerships','Finance','Authority','Compliance','Continuity','Leadership/Decision Authority','Other'] = 'Other'
    description: str = Field(min_length=1, max_length=6000)
    severity: Literal['Low','Moderate','High','Critical'] = 'Moderate'
    root_cause: str = Field(default='', max_length=6000)
    owner: str = Field(default='', max_length=200)

    @field_validator('description')
    @classmethod
    def required_gap_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('root_cause','owner')
    @classmethod
    def normalized_gap_text(cls, value: str) -> str:
        return value.strip()

class GapTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Open','Under Review','Mitigating','Closed']
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator('reason')
    @classmethod
    def required_gap_transition_reason(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A documented transition reason is required.')
        return normalized

class ImprovementIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

    assessment_id: int = Field(gt=0)
    gap_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(default='', max_length=6000)
    initial_cost: float = Field(default=0, ge=0, allow_inf_nan=False)
    recurring_cost: float = Field(default=0, ge=0, allow_inf_nan=False)
    implementation_days: int = Field(default=0, ge=0, le=36500)
    feasibility: int = Field(default=3, ge=1, le=5)
    consequence_reduction: int = Field(default=3, ge=1, le=5)
    mission_benefit: int = Field(default=3, ge=1, le=5)
    sustainability: int = Field(default=3, ge=1, le=5)
    compliance_impact: int = Field(default=3, ge=1, le=5)
    staffing_impact: int = Field(default=3, ge=1, le=5)
    expected_capability_gain: float = Field(default=0, ge=0, allow_inf_nan=False)
    dependencies: str = Field(default='', max_length=6000)
    owner: str = Field(default='', max_length=200)

    @field_validator('title')
    @classmethod
    def required_improvement_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('description','dependencies','owner')
    @classmethod
    def normalized_improvement_text(cls, value: str) -> str:
        return value.strip()

class ImprovementTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Proposed','Under Review','Approved','In Progress','Complete','Deferred','Rejected']
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator('reason')
    @classmethod
    def required_improvement_transition_reason(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A documented transition reason is required.')
        return normalized

class ImprovementValidationIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    evidence_id: int = Field(gt=0)
    validation_status: Literal['Validated','Partially Validated','Failed'] = 'Validated'
    validation_outcome: str = Field(min_length=1, max_length=6000)
    validated_effectiveness_percent: float = Field(default=100, ge=0, le=100, allow_inf_nan=False)

    @field_validator('validation_outcome')
    @classmethod
    def required_validation_outcome(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A documented validation outcome is required.')
        return normalized

class DecisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessment_id: int = Field(gt=0)
    improvement_id: Optional[int] = Field(default=None, gt=0)
    decision_type: Literal['Approve','Approve with Conditions','Modify','Defer','Reject','Transfer Risk','Accept Risk','Continue Monitoring']
    authority: str = Field(min_length=1, max_length=240)
    rationale: str = Field(min_length=1, max_length=6000)
    funding_authorized: float = Field(default=0, ge=0, allow_inf_nan=False)
    conditions: str = Field(default='', max_length=6000)
    implementation_owner: str = Field(default='', max_length=240)
    target_completion: str = ''
    expected_residual_risk: str = Field(default='', max_length=6000)
    review_date: str = ''

    @field_validator('rationale')
    @classmethod
    def required_decision_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('conditions','implementation_owner','expected_residual_risk')
    @classmethod
    def normalized_decision_text(cls, value: str) -> str:
        return value.strip()

class DecisionReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    next_review_date: str
    review_outcome: str = Field(min_length=1, max_length=6000)

class RiskOverrideIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessment_id: int = Field(gt=0)
    threat_id: int = Field(gt=0)
    assigned_score: float = Field(ge=0, le=100, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=6000)
    authority: str = Field(min_length=1, max_length=240)
    evidence_id: Optional[int] = None
    review_date: str = ''

    @field_validator('reason')
    @classmethod
    def required_risk_override_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

class RiskOverrideWithdrawIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=4000)

class RiskOverrideReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    next_review_date: str
    review_outcome: str = Field(min_length=1, max_length=6000)

class AcceptedRiskUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    risk_statement: Optional[str] = Field(default=None, min_length=1, max_length=6000)
    residual_exposure: Optional[str] = Field(default=None, min_length=1, max_length=6000)
    owner: Optional[str] = Field(default=None, min_length=1, max_length=240)
    reconsideration_trigger: Optional[str] = Field(default=None, min_length=1, max_length=6000)

    @field_validator('title','risk_statement','residual_exposure','owner','reconsideration_trigger')
    @classmethod
    def normalized_accepted_risk_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None: return None
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

class AcceptedRiskTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Under Review','Closed','Superseded']
    reason: str = Field(min_length=1, max_length=6000)

    @field_validator('reason')
    @classmethod
    def required_accepted_risk_transition_reason(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A documented transition basis is required.')
        return normalized

class AcceptedRiskReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    next_review_date: str
    review_outcome: str = Field(min_length=1, max_length=6000)

class TriggerIn(BaseModel):
    assessment_id: int
    source: str = 'Manual'
    trigger_type: str
    description: str
    severity: str = 'Moderate'
    affected_record_type: str = ''
    affected_record_id: Optional[int] = None
    status: str = 'Open'
    assigned_to: str = ''
    due_date: str = ''
    resolution: str = ''

class WeightIn(BaseModel):
    life_safety: float = 1.0
    mission: float = 1.0
    operations: float = 1.0
    financial: float = 1.0
    legal_regulatory: float = 1.0
    reputation: float = 1.0
    recovery: float = 1.0

class ReportTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Reviewed','Approved','Released']
    reason: str = Field(min_length=1, max_length=6000)

class ReportCreateIn(BaseModel):
    model_config = ConfigDict(extra='forbid')

class RestoreRequestIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    backup_id: int
    scope: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=6000)

class RestoreDecisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['Authorized','Rejected']
    reason: str = Field(min_length=1, max_length=6000)

class IntelFindingIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessment_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=500)
    details: str = Field(default='', max_length=12000)
    source: str = Field(min_length=1, max_length=500)
    source_locator: str = Field(default='', max_length=2000)

class IntelQualificationIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    relevance: Literal['Relevant','Partially Relevant','Not Relevant']
    credibility: Literal['Low','Medium','High']
    validation_status: Literal['Qualified','Conflicting','Rejected']
    operational_significance: str = Field(min_length=1, max_length=6000)

class ObservationIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reporter_choice: Literal['Identified','Confidential Contact','Anonymous']
    reporter_name: str = Field(default='', max_length=500)
    reporter_contact: str = Field(default='', max_length=1000)
    report_on_behalf_of: str = Field(default='', max_length=500)
    title: str = Field(min_length=1, max_length=500)
    narrative: str = Field(min_length=1, max_length=12000)
    location: str = Field(default='', max_length=1000)
    observed_at: str = Field(min_length=1, max_length=40)
    context: str = Field(default='', max_length=4000)
    reported_urgency: Literal['Routine','Priority','Urgent','Critical'] = 'Routine'
    emergency_acknowledged: bool

class ObservationChannelIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    expires_at: str = Field(min_length=1, max_length=40)

class ObservationChannelDisableIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=2000)

class ObservationAcknowledgeIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=4000)

class ObservationTriageIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Literal['Security Concern','Safety or Hazard','Behavioral Concern','Fraud or Misconduct','Operational','Information','Other']
    priority: Literal['Routine','Priority','Urgent','Critical']
    assigned_to: str = Field(min_length=1, max_length=500)
    notes: str = Field(min_length=1, max_length=6000)

class ObservationRouteIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    target: Literal['SalINTEL','SalTHIRA','SalOPS','External Escalation']
    assessment_id: Optional[int] = None
    member_summary: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=6000)
    external_reference: str = Field(default='', max_length=1000)

class ObservationCloseIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    disposition: Literal['Information Only','Not Actionable','Duplicate','Resolved','Referred']
    reason: str = Field(min_length=1, max_length=6000)

class CopThreadIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    subject: str = Field(min_length=1, max_length=500)
    message: str = Field(min_length=1, max_length=12000)
    assessment_id: Optional[int] = Field(default=None, gt=0)

    @field_validator('subject','message')
    @classmethod
    def normalized_cop_thread_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

class CopMessageIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(min_length=1, max_length=12000)
    audience: Literal['Shared','Internal'] = 'Shared'

    @field_validator('body')
    @classmethod
    def normalized_cop_message(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A message is required.')
        return normalized

class CopAssignmentIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assigned_contact: str = Field(min_length=1, max_length=500)
    member_contact_summary: str = Field(min_length=1, max_length=1000)

class CopThreadCloseIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=6000)

class CopDecisionRequestIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_type: Literal['intel_finding','reassessment_trigger','improvement','accepted_risk','ops_request','ops_estimate']
    source_id: int = Field(gt=0)
    action_type: Literal['Set Priority','Approve Recommendation','Authorize Resources','Risk Decision','Request Action']
    title: str = Field(min_length=1, max_length=500)
    member_summary: str = Field(min_length=1, max_length=4000)
    due_at: str = Field(default='', max_length=40)

class CopMemberDecisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=6000)
    conditions: str = Field(default='', max_length=6000)
    authorized_amount: Decimal = Field(default=Decimal('0'), ge=0, le=100000000, max_digits=14, decimal_places=2)

class CopDecisionWithdrawIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=6000)

class OpsCatalogServiceIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pillar_code: Literal['readiness','protective','incident','recovery']
    name: str = Field(min_length=1, max_length=300)
    member_description: str = Field(min_length=1, max_length=4000)
    internal_scope: str = Field(min_length=1, max_length=12000)
    default_deliverables: str = Field(min_length=1, max_length=6000)
    readiness_inputs: str = Field(min_length=1, max_length=6000)
    authorization_requirements: str = Field(min_length=1, max_length=6000)
    industry_profile_id: Optional[int] = Field(default=None, gt=0)
    member_visible: bool = True

class IndustryProfileItemIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_type: Literal['Terminology','Capability','Scenario','Regulatory Reference','Service Default']
    item_key: str = Field(min_length=1,max_length=120,pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
    member_label: str = Field(min_length=1,max_length=300)
    member_guidance: str = Field(default='',max_length=6000)
    internal_definition: str = Field(default='',max_length=12000)
    reference_metadata: str = Field(default='',max_length=6000)
    default_payload: dict[str,Any] = Field(default_factory=dict)
    member_visible: bool = True
    sort_order: int = Field(default=0,ge=0,le=100000)

class IndustryProfileIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    industry_code: Literal['government-public-safety','critical-infrastructure-energy','aviation-transportation-logistics','healthcare-ems-public-health','education-faith-community','hospitality-events-complex-venues']
    name: str = Field(min_length=1,max_length=300)
    member_summary: str = Field(min_length=1,max_length=6000)
    internal_rationale: str = Field(min_length=1,max_length=12000)
    items: list[IndustryProfileItemIn] = Field(min_length=1,max_length=200)

class IndustryProfileTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['Submit','Review','Approve','Publish','Retire']
    reason: str = Field(min_length=1,max_length=6000)

class IndustryConfigurationIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    profile_id: int = Field(gt=0)

class IndustryConfigurationDeactivateIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1,max_length=6000)

class OpsCatalogTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['Submit','Review','Approve','Publish','Retire']
    reason: str = Field(min_length=1, max_length=6000)

class OpsRequestIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessment_id: Optional[int] = None
    service_catalog_id: Optional[int] = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default='', max_length=12000)
    priority: Literal['Routine','Priority','Urgent','Critical'] = 'Routine'

class OpsRequestDecisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['Authorized','Rejected']
    reason: str = Field(min_length=1, max_length=6000)
    assigned_to: str = Field(default='', max_length=500)

class OpsResultIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    result_summary: str = Field(min_length=1, max_length=12000)

class OpsEngagementIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    service_type: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=6000)
    location: str = Field(default='', max_length=1000)
    planned_start: str = Field(min_length=1, max_length=40)
    planned_end: str = Field(min_length=1, max_length=40)
    operational_lead: str = Field(min_length=1, max_length=500)
    communications_plan: str = Field(min_length=1, max_length=6000)
    member_status_summary: str = Field(min_length=1, max_length=2000)

class OpsEngagementTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Mobilizing','Active','Demobilizing','Closed']
    reason: str = Field(min_length=1, max_length=6000)
    member_status_summary: str = Field(min_length=1, max_length=2000)

class OpsReadinessIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str = Field(min_length=1, max_length=300)
    member_summary: str = Field(min_length=1, max_length=2000)
    internal_requirement: str = Field(min_length=1, max_length=6000)
    member_visible: bool = True
    due_at: str = Field(default='', max_length=40)

class OpsReadinessTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Complete','Exception']
    reason: str = Field(min_length=1, max_length=6000)

class ExpertProfileIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expert_actor: str = Field(min_length=1, max_length=500)
    member_display_name: str = Field(min_length=1, max_length=500)
    member_role_title: str = Field(min_length=1, max_length=500)
    member_biography: str = Field(min_length=1, max_length=4000)
    member_contact_summary: str = Field(default='', max_length=1000)
    internal_biography: str = Field(min_length=1, max_length=12000)
    disciplines: str = Field(min_length=1, max_length=4000)
    jurisdictions: str = Field(min_length=1, max_length=4000)
    regions: str = Field(min_length=1, max_length=4000)

class ExpertProfileTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['Activate','Deactivate']
    reason: str = Field(min_length=1, max_length=6000)

class ExpertCredentialIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    credential_type: str = Field(min_length=1, max_length=500)
    issuer: str = Field(min_length=1, max_length=500)
    jurisdiction: str = Field(default='', max_length=500)
    effective_on: str = Field(min_length=1, max_length=10)
    expires_on: str = Field(default='', max_length=10)
    evidence_id: Optional[int] = Field(default=None, gt=0)

class ExpertCredentialTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['Verify','Withdraw']
    reason: str = Field(min_length=1, max_length=6000)

class ExpertAvailabilityIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    available_from: str = Field(min_length=1, max_length=40)
    available_until: str = Field(min_length=1, max_length=40)
    region: str = Field(default='', max_length=500)

class ExpertConflictIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    profile_id: int = Field(gt=0)
    disclosure: str = Field(min_length=1, max_length=6000)

class ExpertConflictReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['Cleared','Restricted']
    reason: str = Field(min_length=1, max_length=6000)

class ExpertAssignmentIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    profile_id: int = Field(gt=0)
    conflict_id: int = Field(gt=0)
    assignment_role: str = Field(min_length=1, max_length=500)
    member_visible: bool = True

class ExpertAssignmentTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['Accept','Release']
    reason: str = Field(min_length=1, max_length=6000)

class OpsTaskIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=500)
    instructions: str = Field(min_length=1, max_length=12000)
    assigned_to: str = Field(min_length=1, max_length=500)
    priority: Literal['Routine','Priority','Urgent','Critical'] = 'Routine'
    assignment_id: Optional[int] = Field(default=None, gt=0)

class OpsTaskTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['In Progress','Completed','Cancelled']
    reason: str = Field(min_length=1, max_length=6000)
    result_summary: str = Field(default='', max_length=12000)

class OpsFieldReportIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: Optional[int] = None
    report_type: str = Field(min_length=1, max_length=200)
    occurred_at: str = Field(min_length=1, max_length=40)
    member_summary: str = Field(min_length=1, max_length=2000)
    internal_details: str = Field(min_length=1, max_length=12000)

class OpsFieldReportReleaseIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=6000)

class OpsEstimateLineIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Literal['Labor','Travel','Lodging','Per Diem','Equipment','Subcontractor','Other']
    description: str = Field(min_length=1, max_length=1000)
    quantity: Decimal = Field(gt=0, le=1000000, max_digits=14, decimal_places=4)
    unit: str = Field(min_length=1, max_length=80)
    unit_rate: Decimal = Field(ge=0, le=100000000, max_digits=14, decimal_places=2)

class OpsEstimateIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    currency: Literal['USD'] = 'USD'
    member_summary: str = Field(min_length=1, max_length=2000)
    internal_basis: str = Field(min_length=1, max_length=6000)
    lines: list[OpsEstimateLineIn] = Field(min_length=1, max_length=100)

class OpsFinancialTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Submitted','Approved','Rejected']
    reason: str = Field(min_length=1, max_length=6000)

class OpsExpenseIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: Optional[int] = None
    evidence_id: Optional[int] = None
    category: Literal['Labor','Travel','Lodging','Per Diem','Equipment','Subcontractor','Other']
    description: str = Field(min_length=1, max_length=2000)
    member_description: str = Field(min_length=1, max_length=1000)
    vendor: str = Field(default='', max_length=500)
    incurred_on: str = Field(min_length=1, max_length=40)
    amount: Decimal = Field(gt=0, le=100000000, max_digits=14, decimal_places=2)
    currency: Literal['USD'] = 'USD'
    reimbursable: bool = True

class OpsInvoiceStatementIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    billing_period_start: str = Field(min_length=1, max_length=40)
    billing_period_end: str = Field(min_length=1, max_length=40)
    service_summary: str = Field(min_length=1, max_length=2000)

class OpsInvoiceTransitionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Reviewed','Approved','Released']
    reason: str = Field(min_length=1, max_length=6000)

class ScopeChangeIn(BaseModel):
    assessment_id: int
    new_purpose: Optional[str] = None
    new_mission: Optional[str] = None
    new_scope: Optional[str] = None
    new_exclusions: Optional[str] = None
    reason: str
    schedule_impact: str = ''
    cost_impact: float = 0
    assessment_impact: str = ''

class ScopeDecisionIn(BaseModel):
    decision: str
    reason: str = ''

class WorkflowTransitionIn(BaseModel):
    to_status: str
    reason: str = ''

class LoginIn(BaseModel):
    username: str
    password: str

class PilotTenantIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')

class PilotUserIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=5, max_length=320)
    display_name: str = Field(min_length=2, max_length=200)
    tenant_id: int = Field(gt=0)
    role: Literal['System Administrator','Assessment Director','Lead Assessor','SME Assessor','Client Executive','Program Owner','Contributor','Auditor']
    sensitivity_clearance: Literal['Standard','Restricted','Sensitive','Highly Sensitive'] = 'Standard'

class PilotUserStatusIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['Active','Disabled']

class PilotAssessmentAccessIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessment_ids: list[int] = Field(default_factory=list, max_length=500)
    role_override: str = Field(default='', max_length=100)
    sensitivity_clearance: Literal['','Standard','Restricted','Sensitive','Highly Sensitive'] = ''

class AttachmentGovernanceIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    retention_until: Optional[str] = None
    legal_hold: Optional[bool] = None
    disposition_status: Optional[str] = None

class PackageReportConformanceIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    content_sha256: str = Field(min_length=64,max_length=64,pattern=r'^[0-9a-f]{64}$')
    checks: dict[str,dict[str,str]]
    summary: str = Field(min_length=20,max_length=4000)

class PackageSourceDispositionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    report_id: int = Field(gt=0)
    content_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    alignment: Literal['Aligned','Qualified difference','Unresolved']
    explanation: str = Field(min_length=20,max_length=2000)

class PackageReportReconciliationIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    salcapa_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    sources: dict[str,PackageSourceDispositionIn]
    summary: str = Field(min_length=20,max_length=4000)

class PackageReportRetentionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    retention_until: Optional[str] = Field(default=None,max_length=40)
    legal_hold: Optional[Literal[True]] = None
    reason: str = Field(min_length=20,max_length=2000)

class PackageReportQaReviewIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    evidence_id: int = Field(gt=0)
    decision: Literal['Reviewed','Returned']
    checks: dict[str,bool]
    qualification_basis: str = Field(min_length=20,max_length=2000)
    review_note: str = Field(min_length=20,max_length=4000)

class PackageReportIssueIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    report_ids: dict[str,int]
    recipient_user_id: int = Field(gt=0)
    issue_basis: str = Field(min_length=40,max_length=4000)
    confirm_qualified_release: Literal[True]

class PackageReportAcknowledgmentIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    issue_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirm_received: Literal[True]
    confirm_reviewed_limitations: Literal[True]
    acknowledgment_note: str = Field(min_length=20,max_length=1000)
    idempotency_key: str = Field(min_length=8,max_length=100)

class PackagePredecessorQualificationIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    issue_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    acknowledgment_id: int = Field(gt=0)
    qualification_basis: str = Field(min_length=40,max_length=4000)
    limitations_disposition: str = Field(min_length=40,max_length=4000)
    confirm_independent_review: Literal[True]

ROLE_PERMISSIONS={
    'System Administrator': {'read','write','decide','admin'},
    'Assessment Director': {'read','write','decide'},
    'Lead Assessor': {'read','write'}, 'SME Assessor': {'read','write'},
    'Client Executive': {'read','decide'}, 'Program Owner': {'read','write'},
    'Contributor': {'read','write'}, 'Auditor': {'read'},
}
SENSITIVITY_LEVELS={'Standard':1,'Restricted':2,'Sensitive':3,'Highly Sensitive':4}
ROLE_CLEARANCE={'System Administrator':4,'Assessment Director':4,'Lead Assessor':4,'SME Assessor':3,'Client Executive':3,'Program Owner':2,'Contributor':1,'Auditor':3}

def _iso_now_dt(): return datetime.now(timezone.utc)
def _hash_token(token:str): return hashlib.sha256(token.encode('utf-8')).hexdigest()
def hash_password(password:str, salt:str|None=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(salt),240000).hex()
    return f'pbkdf2_sha256$240000${salt}${digest}'
def verify_password(password:str, encoded:str):
    try:
        algo,rounds,salt,digest=encoded.split('$',3)
        if algo!='pbkdf2_sha256': return False
        calc=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(salt),int(rounds)).hex()
        return secrets.compare_digest(calc,digest)
    except Exception: return False

def request_id(request:Request):
    return getattr(request.state,'request_id','') or ''

def request_ip(request:Request):
    forwarded=request.headers.get('x-forwarded-for','').split(',')[0].strip()
    return forwarded or (request.client.host if request.client else '')

def security_event(request:Request|None,event_type:str,severity:str='Info',detail:str='',tenant:int|None=None,user_name:str=''):
    source_ip=request_ip(request) if request else ''
    req_id=request_id(request) if request else ''
    try:
        if request is not None:
            try: ctx=auth_context(request); tenant=tenant if tenant is not None else int(ctx.get('tenant_id') or 0); user_name=user_name or ctx.get('user','')
            except Exception: pass
        conn=db(); conn.execute('INSERT INTO security_events(tenant_id,ts,event_type,severity,user_name,source_ip,request_id,detail) VALUES(?,?,?,?,?,?,?,?)',(tenant,now(),event_type,severity,user_name,source_ip,req_id,detail[:2000])); conn.commit(); conn.close()
    except Exception:
        pass
    try:
        telemetry_emit(event_type,severity,tenant_id=tenant,user_name=user_name,source_ip=source_ip,request_id=req_id,detail=detail[:2000])
    except Exception:
        pass

@app.middleware('http')
async def request_context_middleware(request:Request,call_next):
    request.state.request_id=request.headers.get('X-Request-ID') or uuid.uuid4().hex
    session_token=request.cookies.get('salus_session','')
    rl_key=RATE_LIMITER.key(request_ip(request),session_token)
    allowed,remaining,retry_after=RATE_LIMITER.allow(rl_key)
    if not allowed and request.url.path not in ('/health/live','/health/ready'):
        security_event(request,'RATE_LIMIT_EXCEEDED','Medium',f'path={request.url.path}')
        return JSONResponse({'detail':'Rate limit exceeded','request_id':request.state.request_id},status_code=429,headers={'Retry-After':str(retry_after),'X-RateLimit-Remaining':'0','X-Request-ID':request.state.request_id})
    try:
        response=await call_next(request)
    except Exception as exc:
        security_event(request,'UNHANDLED_EXCEPTION','High',type(exc).__name__)
        raise
    response.headers['X-Request-ID']=request.state.request_id
    response.headers['X-RateLimit-Remaining']=str(remaining)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
    if ENVIRONMENT=='production': response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    return response

_oidc_cache={}
_oidc_credential=None
OIDC_ASSERTION_SCOPE='api://AzureADTokenExchange/.default'
OIDC_CLIENT_ASSERTION_TYPE='urn:ietf:params:oauth:client-assertion-type:jwt-bearer'

def oidc_configured():
    common=all([OIDC_DISCOVERY_URL,OIDC_CLIENT_ID,OIDC_TENANT_ID])
    if ENVIRONMENT=='production':
        common=common and bool(OIDC_REDIRECT_URI) and not OIDC_AUTO_PROVISION
    if OIDC_CLIENT_AUTH_METHOD=='managed_identity':
        return common and bool(OIDC_MANAGED_IDENTITY_CLIENT_ID)
    if OIDC_CLIENT_AUTH_METHOD=='client_secret':
        return common and bool(OIDC_CLIENT_SECRET)
    return False

def oidc_client_auth_payload():
    global _oidc_credential
    if OIDC_CLIENT_AUTH_METHOD=='client_secret':
        if not OIDC_CLIENT_SECRET: raise RuntimeError('OIDC client secret authentication is not configured')
        return {'client_secret':OIDC_CLIENT_SECRET}
    if OIDC_CLIENT_AUTH_METHOD!='managed_identity':
        raise RuntimeError('Unsupported OIDC client authentication method')
    if not OIDC_MANAGED_IDENTITY_CLIENT_ID:
        raise RuntimeError('OIDC managed identity client ID is not configured')
    current=int(datetime.now(timezone.utc).timestamp())
    cached=_oidc_cache.get('client_assertion')
    if cached and cached['expires_on']>current+60:
        assertion=cached['token']
    else:
        if _oidc_credential is None:
            _oidc_credential=ManagedIdentityCredential(client_id=OIDC_MANAGED_IDENTITY_CLIENT_ID)
        access_token=_oidc_credential.get_token(OIDC_ASSERTION_SCOPE)
        assertion=str(getattr(access_token,'token','') or '')
        if not assertion: raise RuntimeError('Managed identity returned an empty client assertion')
        _oidc_cache['client_assertion']={'token':assertion,'expires_on':int(getattr(access_token,'expires_on',current+300))}
    return {'client_assertion_type':OIDC_CLIENT_ASSERTION_TYPE,'client_assertion':assertion}

def oidc_federation_status():
    status={'configured':oidc_configured(),'healthy':False,'mode':OIDC_CLIENT_AUTH_METHOD,'provider':OIDC_PROVIDER_NAME}
    if not status['configured']: return status
    if OIDC_CLIENT_AUTH_METHOD=='client_secret':
        status['healthy']=True
        return status
    try:
        oidc_client_auth_payload()
        status['healthy']=True
    except Exception as exc:
        error_id=uuid.uuid4().hex
        record_internal_failure('OIDC managed identity federation',error_id,exc)
    return status

def oidc_discovery():
    if not oidc_configured(): raise HTTPException(503,'OIDC is not fully configured')
    if _oidc_cache.get('config'): return _oidc_cache['config']
    try:
        r=httpx.get(OIDC_DISCOVERY_URL,timeout=10); r.raise_for_status(); data=r.json()
    except Exception as exc:
        error_id=uuid.uuid4().hex; record_internal_failure('OIDC discovery',error_id,exc)
        raise HTTPException(503,f'OIDC discovery failed. Reference: {error_id}')
    required=['authorization_endpoint','token_endpoint','jwks_uri','issuer']
    if any(not data.get(k) for k in required): raise HTTPException(503,'OIDC discovery document is incomplete')
    expected_issuer=f'https://login.microsoftonline.com/{OIDC_TENANT_ID}/v2.0'
    if data['issuer'].rstrip('/')!=expected_issuer:
        raise HTTPException(503,'OIDC issuer does not match the governed Microsoft Entra tenant')
    for key in ('authorization_endpoint','token_endpoint','jwks_uri'):
        parsed=urllib.parse.urlparse(data[key])
        if parsed.scheme!='https' or parsed.hostname!='login.microsoftonline.com':
            raise HTTPException(503,'OIDC endpoint is outside the governed Microsoft Entra authority')
    _oidc_cache['config']=data; return data

def oidc_redirect_uri(request:Request):
    return OIDC_REDIRECT_URI or str(request.url_for('oidc_callback'))

def production_readiness():
    issues=[]
    secret_status=secret_readiness()
    rate_status=RATE_LIMITER.health()
    telemetry_status=telemetry_readiness()
    runtime_db=runtime_database_status(DB_PATH)
    managed_db=managed_target_status()
    oidc_status=oidc_federation_status() if AUTH_MODE=='oidc' else {'configured':False,'healthy':False,'mode':OIDC_CLIENT_AUTH_METHOD,'provider':OIDC_PROVIDER_NAME}
    scanner_status=scanner_configuration()
    if ENVIRONMENT=='production':
        if AUTH_MODE not in ('session','oidc'): issues.append('Production requires session or OIDC authentication.')
        if not COOKIE_SECURE: issues.append('SALUS_COOKIE_SECURE=1 is required in production.')
        if STORAGE_BACKEND=='local': issues.append('Managed object storage is required for production; local evidence storage is not production-grade.')
        if not AV_REQUIRED: issues.append('SALUS_REQUIRE_AV=1 should be enabled for production evidence uploads.')
        if PACKAGE_COMMERCIAL_WORKFLOW_ENABLED and not scanner_status['configured']: issues.append('A configured malware scanner executable is required for production package uploads; verify signatures and scan results before release.')
        if AUTH_MODE=='oidc' and not oidc_configured(): issues.append('OIDC mode is selected but provider configuration is incomplete.')
        if AUTH_MODE=='oidc' and OIDC_CLIENT_AUTH_METHOD!='managed_identity': issues.append('Production OIDC must use managed identity federation without a client secret.')
        if AUTH_MODE=='oidc' and OIDC_AUTO_PROVISION: issues.append('Production OIDC automatic user provisioning must remain disabled.')
        if AUTH_MODE=='oidc' and oidc_configured() and not oidc_status.get('healthy'): issues.append('OIDC managed identity federation is unavailable.')
        if DB_BACKEND=='sqlite' and not ALLOW_SQLITE_PRODUCTION: issues.append('SQLite remains the active runtime database. Use SALUS_DB_BACKEND=postgres with SALUS_DATABASE_URL for production, or explicitly authorize SALUS_ALLOW_SQLITE_PRODUCTION=1 for a controlled exception.')
        if secret_status.get('backend')=='env': issues.append('Azure Key Vault or another managed secret provider is recommended for production secrets.')
        if not rate_status.get('enabled'): issues.append('Rate limiting must be enabled in production.')
        if rate_status.get('backend')=='memory': issues.append('Distributed production deployment should use SALUS_RATE_LIMIT_BACKEND=redis rather than per-process memory limiting.')
        if managed_db.get('configured') and not managed_db.get('healthy'): issues.append('Managed database target unavailable.')
    db_ok=bool(runtime_db.get('healthy'))
    storage_ok=True
    try:
        storage_ok=bool(storage.health())
    except Exception as exc:
        storage_ok=False
        error_id=uuid.uuid4().hex; record_internal_failure('storage readiness',error_id,exc)
        issues.append(f'Storage unavailable. Reference: {error_id}')
    if not secret_status.get('configured',False): issues.append('Secret provider unavailable.')
    if not rate_status.get('healthy',False): issues.append('Rate limiter unavailable.')
    if not telemetry_status.get('healthy',False): issues.append('Telemetry unavailable.')
    if not db_ok: issues.append('Database unavailable.')
    blocking=not db_ok or not storage_ok or not secret_status.get('configured',False) or not rate_status.get('healthy',False) or (ENVIRONMENT=='production' and bool(issues))
    def public_status(value):
        allowed=('configured','healthy','enabled','backend','provider','mode','target')
        return {key:value[key] for key in allowed if key in value and isinstance(value[key],(str,bool,int,float,type(None)))}
    return {'ready':not blocking,'version':APP_VERSION,'environment':ENVIRONMENT,'auth_mode':AUTH_MODE,'storage_backend':STORAGE_BACKEND,'av_mode':AV_MODE,'package_scanner':scanner_status,'secret_provider':public_status(secret_status),'rate_limit':public_status(rate_status),'telemetry':public_status(telemetry_status),'runtime_database':public_status(runtime_db),'managed_database_target':public_status(managed_db),'oidc':public_status(oidc_status),'issues':issues}

@app.get('/health/live')
def health_live(): return {'status':'ok','version':APP_VERSION}

@app.get('/health/ready')
def health_ready():
    r=production_readiness()
    return JSONResponse(r,status_code=200 if r['ready'] else 503)

def auth_context(request:Request):
    cached=getattr(request.state,'salus_auth',None)
    if cached: return cached
    if AUTH_MODE in ('session','oidc'):
        raw=request.cookies.get('salus_session','')
        if not raw: raise HTTPException(401,'Authentication required')
        conn=db(); row=conn.execute("""SELECT s.id session_id,s.expires_at,u.id user_id,u.tenant_id,u.username,u.display_name,u.role,u.sensitivity_clearance,u.status
          FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?""",(_hash_token(raw),)).fetchone()
        if not row: conn.close(); raise HTTPException(401,'Invalid session')
        try: expires=datetime.fromisoformat(str(row['expires_at']).replace('Z','+00:00'))
        except Exception: expires=_iso_now_dt()-timedelta(seconds=1)
        if expires <= _iso_now_dt() or row['status']!='Active':
            conn.execute('DELETE FROM auth_sessions WHERE id=?',(row['session_id'],)); conn.commit(); conn.close(); raise HTTPException(401,'Session expired')
        conn.execute('UPDATE auth_sessions SET last_seen_at=? WHERE id=?',(now(),row['session_id'])); conn.commit(); conn.close()
        ctx={'user':row['display_name'] or row['username'],'username':row['username'],'user_id':row['user_id'],'tenant_id':row['tenant_id'],'role':row['role'],'clearance':row['sensitivity_clearance'] or 'Standard','auth_mode':AUTH_MODE}
    else:
        try: tenant=int(request.headers.get('X-Salus-Tenant','1'))
        except Exception: tenant=1
        r=request.headers.get('X-Salus-Role','Assessment Director')
        level=ROLE_CLEARANCE.get(r,1); clearance=next((k for k,v in SENSITIVITY_LEVELS.items() if v==level),'Standard')
        ctx={'user':request.headers.get('X-Salus-User','Prototype User'),'username':request.headers.get('X-Salus-User','Prototype User'),'user_id':None,'tenant_id':tenant,'role':r,'clearance':clearance,'auth_mode':'prototype'}
    request.state.salus_auth=ctx
    return ctx

def actor(request:Request): return auth_context(request)['user']
def role(request:Request): return auth_context(request)['role']
def tenant_id(request:Request): return int(auth_context(request)['tenant_id'])
def clearance_level(request:Request): return SENSITIVITY_LEVELS.get(auth_context(request).get('clearance','Standard'),1)
def require(request: Request, permission: str):
    r=role(request)
    if permission not in ROLE_PERMISSIONS.get(r, {'read'}): raise HTTPException(403, f'{r} does not have {permission} permission')

def require_protected_member_authority(request: Request, action: str):
    require(request,'decide')
    if role(request)!='Client Executive':
        security_event(request,'MEMBER_AUTHORITY_DENIED','High',f'action={action}')
        raise HTTPException(403,'Only a Protected Member authority can exercise this decision authority.')

def accessible_assessment_ids(request:Request):
    tid=tenant_id(request); conn=db(); ctx=auth_context(request)
    all_ids=[r['id'] for r in conn.execute('SELECT id FROM assessments WHERE tenant_id=? ORDER BY id',(tid,))]
    if AUTH_MODE in ('session','oidc') and ctx.get('user_id') and role(request)!='System Administrator':
        mapped=[r['assessment_id'] for r in conn.execute('SELECT assessment_id FROM assessment_access WHERE user_id=?',(ctx['user_id'],))]
        if mapped: all_ids=[x for x in all_ids if x in set(mapped)]
    conn.close(); return all_ids

def assessment_row_for_request(request:Request, assessment_id:int):
    conn=db(); a=conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone()
    if not a: conn.close(); raise HTTPException(404,'Assessment not found')
    if int(a['tenant_id'])!=tenant_id(request):
        conn.close(); security_event(request,'TENANT_BOUNDARY_VIOLATION','High',f'assessment_id={assessment_id}'); raise HTTPException(403,'Tenant boundary violation')
    ctx=auth_context(request)
    if AUTH_MODE in ('session','oidc') and ctx.get('user_id') and role(request)!='System Administrator':
        mappings=conn.execute('SELECT COUNT(*) c FROM assessment_access WHERE user_id=?',(ctx['user_id'],)).fetchone()['c']
        if mappings:
            m=conn.execute('SELECT * FROM assessment_access WHERE user_id=? AND assessment_id=?',(ctx['user_id'],assessment_id)).fetchone()
            if not m:
                conn.close(); security_event(request,'ASSESSMENT_ACCESS_DENIED','Medium',f'assessment_id={assessment_id}'); raise HTTPException(403,'No access to this assessment')
    conn.close(); return dict(a)

def require_sensitivity(request:Request, sensitivity:str):
    if SENSITIVITY_LEVELS.get(sensitivity or 'Standard',1)>clearance_level(request): raise HTTPException(403,'Record sensitivity exceeds user clearance')

def infer_tenant(conn, entity_type:str, entity_id:int|None):
    if entity_id is None: return 1
    table_map={'assessment':'assessments','threat':'threats','scenario':'scenarios','capability':'capabilities','evidence':'evidence','gap':'gaps','improvement':'improvements','decision':'decisions','accepted_risk':'accepted_risks','risk_override':'risk_overrides','reassessment_trigger':'reassessment_triggers','scope_change':'scope_changes','workflow_event':'workflow_events','backup_history':'backup_history','governed_intake':'governed_intake','report_version':'report_versions','restore_request':'restore_requests','intel_finding':'intel_findings','observation_intake_channel':'observation_intake_channels','observation':'observations','observation_attachment':'observation_attachments','observation_event':'observation_events','coordination_thread':'cop_coordination_threads','coordination_message':'cop_coordination_messages','decision_request':'cop_decision_requests','cop_event':'cop_events','industry_profile':'industry_profiles','industry_profile_item':'industry_profile_items','industry_profile_event':'industry_profile_events','tenant_industry_configuration':'tenant_industry_configurations','ops_service_pillar':'ops_service_pillars','ops_service_catalog':'ops_service_catalog','ops_catalog_event':'ops_catalog_events','expert_profile':'expert_profiles','expert_credential':'expert_credentials','expert_availability':'expert_availability','expert_conflict':'expert_conflicts','expert_assignment':'ops_engagement_assignments','expert_event':'expert_events','ops_request':'ops_requests','ops_engagement':'ops_engagements','ops_engagement_readiness':'ops_engagement_readiness','ops_task':'ops_tasks','ops_field_report':'ops_field_reports','ops_estimate':'ops_estimates','ops_estimate_line':'ops_estimate_lines','ops_expense':'ops_expenses','ops_invoice_statement':'ops_invoice_statements'}
    table=table_map.get(entity_type,entity_type if entity_type in table_map.values() else '')
    try:
        if table in ('assessments','backup_history','governed_intake','report_versions','restore_requests','intel_findings','observation_intake_channels','observations','observation_attachments','observation_events','cop_coordination_threads','cop_coordination_messages','cop_decision_requests','cop_events','industry_profiles','industry_profile_items','industry_profile_events','tenant_industry_configurations','ops_service_pillars','ops_service_catalog','ops_catalog_events','expert_profiles','expert_credentials','expert_availability','expert_conflicts','ops_engagement_assignments','expert_events','ops_requests','ops_engagements','ops_engagement_readiness','ops_tasks','ops_field_reports','ops_estimates','ops_estimate_lines','ops_expenses','ops_invoice_statements'): r=conn.execute(f'SELECT tenant_id FROM {table} WHERE id=?',(entity_id,)).fetchone()
        elif table: r=conn.execute(f'SELECT a.tenant_id FROM {table} t JOIN assessments a ON a.id=t.assessment_id WHERE t.id=?',(entity_id,)).fetchone()
        else: r=None
        return int(r['tenant_id']) if r else 1
    except Exception: return 1

def clamp(v,lo,hi): return max(lo,min(hi,v))
def risk_band(score):
    return 'Critical' if score>=80 else 'High' if score>=60 else 'Moderate' if score>=40 else 'Guarded' if score>=20 else 'Low'
def threat_inherent_score(t): return round(float(t['likelihood'])*float(t['vulnerability'])*float(t['consequence'])/125*100,1)
CAPABILITY_MEASUREMENT_TYPES={'Percentage','Time','Count','Rate','Binary','Currency','Qualitative Rubric'}
CAPABILITY_COMPARATORS={'>=','<=','='}

def validate_capability_measurement(measurement_type, comparator, required, current):
    measurement_type=str(measurement_type or 'Percentage').strip()
    comparator=str(comparator or '>=').strip()
    if measurement_type not in CAPABILITY_MEASUREMENT_TYPES:
        raise HTTPException(422,f'Unsupported capability measurement type: {measurement_type}')
    if comparator not in CAPABILITY_COMPARATORS:
        raise HTTPException(422,f'Unsupported capability comparator: {comparator}')
    try:
        required=float(required); current=float(current)
    except (TypeError,ValueError):
        raise HTTPException(422,'Capability required standard and current performance must be numeric.')
    if measurement_type=='Binary':
        if comparator!='=':
            raise HTTPException(422,"Binary capability measurements require the '=' comparator.")
        if required not in (0.0,1.0) or current not in (0.0,1.0):
            raise HTTPException(422,'Binary capability measurements must use 0 or 1 for required standard and current performance.')
    return measurement_type,comparator,required,current

def capability_effectiveness(required,current,comparator='>=',measurement_type='Percentage'):
    measurement_type,comparator,required,current=validate_capability_measurement(measurement_type,comparator,required,current)
    if measurement_type=='Binary':
        return 100.0 if current==required else 0.0
    if comparator=='>=':
        if required==0: return 100.0 if current>=required else 0.0
        if required<0: return 100.0 if current>=required else 0.0
        return round(clamp(current/required*100,0,100),1)
    if comparator=='<=':
        if current<=required: return 100.0
        if current==0: return 0.0
        if required<=0: return 0.0
        return round(clamp(required/current*100,0,100),1)
    # Equality targets use relative distance from the required standard.
    denom=max(abs(required),1.0)
    return round(clamp((1-abs(current-required)/denom)*100,0,100),1)

def capability_gap(required,current,comparator='>='):
    required=float(required or 0); current=float(current or 0); comparator=str(comparator or '>=').strip()
    if comparator=='<=': return round(max(current-required,0),4)
    if comparator=='=': return round(abs(current-required),4)
    return round(max(required-current,0),4)

def capability_summary(row):
    r=dict(row)
    eff=capability_effectiveness(r.get('required_standard'),r.get('current_performance'),r.get('comparator','>='),r.get('measurement_type','Percentage'))
    gap=capability_gap(r.get('required_standard'),r.get('current_performance'),r.get('comparator','>='))
    r['attainment_percent']=eff
    r['performance_gap']=gap
    r['target_status']='Met' if eff>=100 else ('Near Target' if eff>=80 else 'Below Target')
    return r
def improvement_priority(i):
    cost=float(i.get('initial_cost') or 0); days=int(i.get('implementation_days') or 0)
    cost_score=5 if cost<=25000 else 4 if cost<=100000 else 3 if cost<=500000 else 2 if cost<=2000000 else 1
    time_score=5 if days<=30 else 4 if days<=90 else 3 if days<=180 else 2 if days<=365 else 1
    vals={'consequence':clamp(float(i.get('consequence_reduction') or 1),1,5),'mission':clamp(float(i.get('mission_benefit') or 1),1,5),'feasibility':clamp(float(i.get('feasibility') or 1),1,5),'sustainability':clamp(float(i.get('sustainability') or 1),1,5),'compliance':clamp(float(i.get('compliance_impact') or 1),1,5),'staffing':clamp(float(i.get('staffing_impact') or 1),1,5),'cost':cost_score,'time':time_score}
    weighted=.22*vals['consequence']+.18*vals['mission']+.12*vals['feasibility']+.10*vals['sustainability']+.10*vals['compliance']+.08*vals['staffing']+.10*vals['cost']+.10*vals['time']
    return round(weighted/5*100,1),vals

WORKFLOW_STATES=['Draft','Scope Approved','Evidence Collection','Analysis','SME Review','Salus QA','Client Validation','Findings Finalized','Executive Decisions','Implementation','Validation','Active Monitoring','Reassessment']
VERSIONED_TABLES={'assessments','threats','scenarios','capabilities','evidence','gaps','improvements','decisions','accepted_risks','risk_overrides','reassessment_triggers','ops_engagements','ops_tasks','ops_field_reports','ops_estimates','ops_expenses','ops_invoice_statements'}
CHILD_ASSESSMENT_TABLES=VERSIONED_TABLES-{'assessments'}
SQL_TABLE_NAMES={
    'assessments':'assessments','threats':'threats','scenarios':'scenarios',
    'capabilities':'capabilities','evidence':'evidence','gaps':'gaps',
    'improvements':'improvements','decisions':'decisions',
    'accepted_risks':'accepted_risks','risk_overrides':'risk_overrides',
    'reassessment_triggers':'reassessment_triggers','audit_log':'audit_log',
    'entity_versions':'entity_versions','scope_changes':'scope_changes',
    'workflow_events':'workflow_events','evidence_attachments':'evidence_attachments',
    'ops_engagements':'ops_engagements','ops_tasks':'ops_tasks','ops_field_reports':'ops_field_reports','ops_estimates':'ops_estimates','ops_expenses':'ops_expenses','ops_invoice_statements':'ops_invoice_statements',
}

def sql_table_name(value: str) -> str:
    """Return only a compile-time table identifier; never echo route input into SQL."""
    try:
        return SQL_TABLE_NAMES[value]
    except (KeyError,TypeError):
        raise HTTPException(404)
RELATION_RULES={
    'scenarios': {'threat_id': ('threats', False, 'Threat / Hazard')},
    'capabilities': {'scenario_id': ('scenarios', True, 'Scenario')},
    'evidence': {
        'capability_id': ('capabilities', True, 'Capability'),
        'scenario_id': ('scenarios', True, 'Scenario'),
    },
    'gaps': {'capability_id': ('capabilities', False, 'Capability')},
    'improvements': {'gap_id': ('gaps', False, 'Gap')},
    'decisions': {'improvement_id': ('improvements', True, 'Improvement')},
    'risk_overrides': {
        'threat_id': ('threats', False, 'Threat / Hazard'),
        'evidence_id': ('evidence', True, 'Evidence'),
    },
}
TRIGGER_RECORD_TABLES={
    'assessment':'assessments','assessments':'assessments',
    'threat':'threats','threats':'threats','threat_hazard':'threats',
    'scenario':'scenarios','scenarios':'scenarios',
    'capability':'capabilities','capabilities':'capabilities',
    'evidence':'evidence',
    'gap':'gaps','gaps':'gaps',
    'improvement':'improvements','improvements':'improvements',
    'accepted_risk':'accepted_risks','accepted_risks':'accepted_risks',
    'risk_override':'risk_overrides','risk_overrides':'risk_overrides',
    'reassessment_trigger':'reassessment_triggers','reassessment_triggers':'reassessment_triggers',
    'ops_engagement':'ops_engagements','ops_engagements':'ops_engagements',
}

def _relationship_id(value, label:str, optional:bool):
    if value in (None,''):
        if optional: return None
        raise HTTPException(422,f'{label} is required.')
    try: return int(value)
    except (TypeError,ValueError): raise HTTPException(422,f'{label} must reference a valid record ID.')

def validate_entity_relationships(conn, table:str, assessment_id:int, data:dict[str,Any]):
    """Fail closed when a governed relationship crosses assessment boundaries."""
    assessment_id=int(assessment_id)
    for field,(related_table,optional,label) in RELATION_RULES.get(table,{}).items():
        related_id=_relationship_id(data.get(field),label,optional)
        if related_id is None: continue
        row=conn.execute(f'SELECT id,assessment_id FROM {related_table} WHERE id=?',(related_id,)).fetchone()
        if not row: raise HTTPException(422,f'{label} #{related_id} does not exist.')
        if int(row['assessment_id'])!=assessment_id:
            raise HTTPException(422,f'{label} #{related_id} belongs to a different assessment. Cross-assessment relationships are not permitted.')
    if table=='reassessment_triggers' and data.get('affected_record_id') not in (None,''):
        related_id=_relationship_id(data.get('affected_record_id'),'Affected record',False)
        record_type=str(data.get('affected_record_type') or '').strip().lower().replace(' ','_').replace('/','_')
        related_table=TRIGGER_RECORD_TABLES.get(record_type)
        if not related_table:
            raise HTTPException(422,'Affected record type must identify a governed assessment record when an affected record ID is supplied.')
        if related_table=='assessments':
            if related_id!=assessment_id: raise HTTPException(422,'Affected assessment must match the trigger assessment.')
        else:
            row=conn.execute(f'SELECT id,assessment_id FROM {related_table} WHERE id=?',(related_id,)).fetchone()
            if not row: raise HTTPException(422,f'Affected record #{related_id} does not exist.')
            if int(row['assessment_id'])!=assessment_id:
                raise HTTPException(422,'Affected record belongs to a different assessment. Cross-assessment relationships are not permitted.')

def validate_relationship_payload(table:str, assessment_id:int, data:dict[str,Any]):
    conn=db()
    try: validate_entity_relationships(conn,table,assessment_id,data)
    finally: conn.close()

def entity_assessment_id(table, row):
    return int(row['id']) if table=='assessments' else int(row['assessment_id'])

def snapshot_entity(conn, table:str, entity_id:int, changed_by:str, reason:str):
    if table not in VERSIONED_TABLES: return
    table=sql_table_name(table)
    row=conn.execute(f'SELECT * FROM {table} WHERE id=?',(entity_id,)).fetchone()
    if not row: return
    assessment_id=entity_assessment_id(table,row)
    version_no=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM entity_versions WHERE entity_type=? AND entity_id=?',(table,entity_id)).fetchone()['n']
    conn.execute('INSERT INTO entity_versions(assessment_id,entity_type,entity_id,version_no,snapshot_json,change_reason,changed_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                 (assessment_id,table,entity_id,version_no,json.dumps(dict(row),default=str,sort_keys=True),reason,changed_by,now()))

def _normalize_date(value:str, label:str='Date', required:bool=False):
    text=str(value or '').strip()
    if not text:
        if required: raise HTTPException(422,f'{label} is required.')
        return ''
    try:
        return datetime.strptime(text[:10],'%Y-%m-%d').date().isoformat()
    except Exception:
        raise HTTPException(422,f'{label} must use YYYY-MM-DD format.')


def evidence_is_current(row, as_of=None):
    r=dict(row)
    if str(r.get('lifecycle_status') or 'Current')!='Current': return False
    valid_until=str(r.get('valid_until') or '').strip()
    if not valid_until: return True
    try: expiry=datetime.strptime(valid_until[:10],'%Y-%m-%d').date()
    except Exception: return False
    today=as_of or datetime.now(timezone.utc).date()
    return expiry>=today


def evidence_is_effective(row):
    r=dict(row)
    return str(r.get('verification_status') or '')=='Verified' and evidence_is_current(r)


def _open_evidence_stale_trigger(conn, evidence_row, reason, who='system-lifecycle'):
    existing=conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Evidence Lifecycle' AND trigger_type='Evidence Stale' AND affected_record_type='evidence' AND affected_record_id=? AND status!='Resolved' ORDER BY id DESC LIMIT 1",(evidence_row['assessment_id'],evidence_row['id'])).fetchone()
    if existing: return int(existing['id'])
    ts=now()
    supports_validation=bool(conn.execute("SELECT 1 FROM improvements WHERE assessment_id=? AND validation_evidence_id=? AND validation_status IN ('Validated','Partially Validated') LIMIT 1",(evidence_row['assessment_id'],evidence_row['id'])).fetchone())
    supports_override=bool(conn.execute("SELECT 1 FROM risk_overrides WHERE assessment_id=? AND evidence_id=? AND status='Active' LIMIT 1",(evidence_row['assessment_id'],evidence_row['id'])).fetchone())
    severity='High' if supports_validation or supports_override else 'Moderate'
    cur=conn.execute('''INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (evidence_row['assessment_id'],'Evidence Lifecycle','Evidence Stale',f'Evidence became stale: {evidence_row["title"]}. {reason}',severity,'evidence',evidence_row['id'],'Open',evidence_row['owner'],'','',ts,ts))
    tid=cur.lastrowid
    audit(conn,'CREATE','reassessment_trigger',tid,f'Automatically created because evidence #{evidence_row["id"]} became stale',who)
    snapshot_entity(conn,'reassessment_triggers',tid,who,'Automatic stale-evidence reassessment trigger')
    return tid


def sweep_stale_evidence(assessment_ids=None, who='system-lifecycle'):
    if not assessment_ids: return []
    conn=db(); changed=[]
    try:
        ids=[int(x) for x in assessment_ids]
        marks=','.join('?'*len(ids)); params=tuple(ids)
        where=f"valid_until<>'' AND lifecycle_status<>'Stale' AND assessment_id IN ({marks})"
        rows=[dict(r) for r in conn.execute(f'SELECT * FROM evidence WHERE {where} ORDER BY id',params)]
        today=datetime.now(timezone.utc).date(); ts=now()
        for ev in rows:
            try: expiry=datetime.strptime(str(ev.get('valid_until') or '')[:10],'%Y-%m-%d').date()
            except Exception: continue
            if expiry>=today: continue
            reason=f'Validity date expired on {expiry.isoformat()}.'
            conn.execute("UPDATE evidence SET lifecycle_status='Stale',stale_reason=?,stale_at=?,updated_at=? WHERE id=?",(reason,ts,ts,ev['id']))
            refreshed=dict(ev); refreshed.update({'lifecycle_status':'Stale','stale_reason':reason,'stale_at':ts,'updated_at':ts})
            _open_evidence_stale_trigger(conn,refreshed,reason,who)
            audit(conn,'EVIDENCE_STALE','evidence',ev['id'],reason,who)
            snapshot_entity(conn,'evidence',ev['id'],who,'Evidence automatically marked stale after validity expiry')
            changed.append(ev['id'])
        conn.commit(); return changed
    finally:
        conn.close()


def _open_accepted_risk_overdue_trigger(conn, risk_row, reason, who='system-lifecycle'):
    existing=conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Accepted Risk Lifecycle' AND trigger_type='Accepted Risk Review Overdue' AND affected_record_type='accepted_risk' AND affected_record_id=? AND status!='Resolved' ORDER BY id DESC LIMIT 1",(risk_row['assessment_id'],risk_row['id'])).fetchone()
    if existing: return int(existing['id'])
    ts=now()
    cur=conn.execute('''INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (risk_row['assessment_id'],'Accepted Risk Lifecycle','Accepted Risk Review Overdue',f'Accepted-risk review became overdue: {risk_row["title"]}. {reason}','High','accepted_risk',risk_row['id'],'Open',risk_row['owner'],risk_row['review_date'],'',ts,ts))
    trigger_id=cur.lastrowid
    audit(conn,'CREATE','reassessment_trigger',trigger_id,f'Automatically created because accepted risk #{risk_row["id"]} review became overdue',who)
    snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Automatic accepted-risk review trigger')
    return trigger_id


def sweep_overdue_accepted_risks(assessment_ids=None, who='system-lifecycle'):
    if not assessment_ids: return []
    conn=db(); changed=[]
    try:
        ids=[int(x) for x in assessment_ids]; marks=','.join('?'*len(ids)); params=tuple(ids)
        rows=[dict(r) for r in conn.execute(f"SELECT * FROM accepted_risks WHERE review_date<>'' AND review_lifecycle_status<>'Review Overdue' AND status IN ('Active','Under Review') AND assessment_id IN ({marks}) ORDER BY id",params)]
        today=datetime.now(timezone.utc).date(); ts=now()
        for risk in rows:
            try: due=datetime.strptime(str(risk.get('review_date') or '')[:10],'%Y-%m-%d').date()
            except Exception: continue
            if due>=today: continue
            reason=f'Review date passed on {due.isoformat()}.'
            conn.execute("UPDATE accepted_risks SET review_lifecycle_status='Review Overdue',review_overdue_reason=?,review_overdue_at=?,updated_at=? WHERE id=?",(reason,ts,ts,risk['id']))
            refreshed=dict(risk); refreshed.update({'review_lifecycle_status':'Review Overdue','review_overdue_reason':reason,'review_overdue_at':ts,'updated_at':ts})
            _open_accepted_risk_overdue_trigger(conn,refreshed,reason,who)
            audit(conn,'ACCEPTED_RISK_REVIEW_OVERDUE','accepted_risk',risk['id'],reason,who)
            snapshot_entity(conn,'accepted_risks',risk['id'],who,'Accepted-risk review automatically marked overdue')
            changed.append(risk['id'])
        conn.commit(); return changed
    finally:
        conn.close()

def _open_override_overdue_trigger(conn, override, reason, who='system-lifecycle'):
    existing=conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Risk Override Lifecycle' AND trigger_type='Professional Risk Override Review Overdue' AND affected_record_type='risk_override' AND affected_record_id=? AND status!='Resolved' ORDER BY id DESC LIMIT 1",(override['assessment_id'],override['id'])).fetchone()
    if existing: return int(existing['id'])
    ts=now(); cur=conn.execute('''INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(override['assessment_id'],'Risk Override Lifecycle','Professional Risk Override Review Overdue',f'Professional risk override review became overdue for threat #{override["threat_id"]}. {reason}','High','risk_override',override['id'],'Open',override['authority'],override['review_date'],'',ts,ts))
    trigger_id=cur.lastrowid; audit(conn,'CREATE','reassessment_trigger',trigger_id,f'Automatically created because professional risk override #{override["id"]} review became overdue',who); snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Automatic professional risk-override review trigger'); return trigger_id

def sweep_overdue_risk_overrides(assessment_ids=None, who='system-lifecycle'):
    if not assessment_ids: return []
    conn=db(); changed=[]
    try:
        ids=[int(x) for x in assessment_ids]; marks=','.join('?'*len(ids)); params=tuple(ids); today=datetime.now(timezone.utc).date(); ts=now()
        rows=[dict(r) for r in conn.execute(f"SELECT * FROM risk_overrides WHERE review_date<>'' AND review_lifecycle_status<>'Review Overdue' AND status='Active' AND assessment_id IN ({marks}) ORDER BY id",params)]
        for override in rows:
            try: due=datetime.strptime(str(override['review_date'])[:10],'%Y-%m-%d').date()
            except Exception: continue
            if due>=today: continue
            reason=f'Review date passed on {due.isoformat()}.'
            conn.execute("UPDATE risk_overrides SET review_lifecycle_status='Review Overdue',review_overdue_reason=?,review_overdue_at=?,updated_at=? WHERE id=?",(reason,ts,ts,override['id']))
            refreshed=dict(override); refreshed.update({'review_lifecycle_status':'Review Overdue','review_overdue_reason':reason,'review_overdue_at':ts,'updated_at':ts})
            _open_override_overdue_trigger(conn,refreshed,reason,who); audit(conn,'RISK_OVERRIDE_REVIEW_OVERDUE','risk_override',override['id'],reason,who); snapshot_entity(conn,'risk_overrides',override['id'],who,'Professional risk-override review automatically marked overdue'); changed.append(override['id'])
        conn.commit(); return changed
    finally: conn.close()

def sweep_overdue_assessments(assessment_ids=None, who='system-lifecycle'):
    if not assessment_ids: return []
    conn=db(); changed=[]
    try:
        ids=[int(x) for x in assessment_ids]; marks=','.join('?'*len(ids)); params=tuple(ids); today=datetime.now(timezone.utc).date(); ts=now()
        rows=[dict(r) for r in conn.execute(f"SELECT * FROM assessments WHERE reassessment_date<>'' AND reassessment_lifecycle_status<>'Reassessment Overdue' AND id IN ({marks}) ORDER BY id",params)]
        for assessment in rows:
            try: due=datetime.strptime(str(assessment['reassessment_date'])[:10],'%Y-%m-%d').date()
            except Exception: continue
            if due>=today: continue
            reason=f'Reassessment date passed on {due.isoformat()}.'
            conn.execute("UPDATE assessments SET reassessment_lifecycle_status='Reassessment Overdue',reassessment_overdue_reason=?,reassessment_overdue_at=?,updated_at=? WHERE id=?",(reason,ts,ts,assessment['id']))
            existing=conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Assessment Lifecycle' AND trigger_type='Assessment Reassessment Overdue' AND affected_record_type='assessment' AND affected_record_id=? AND status!='Resolved' ORDER BY id DESC LIMIT 1",(assessment['id'],assessment['id'])).fetchone()
            if not existing:
                cur=conn.execute('''INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(assessment['id'],'Assessment Lifecycle','Assessment Reassessment Overdue',f'Assessment reassessment became overdue: {assessment["name"]}. {reason}','High','assessment',assessment['id'],'Open',assessment['lead_assessor'],assessment['reassessment_date'],'',ts,ts)); audit(conn,'CREATE','reassessment_trigger',cur.lastrowid,f'Automatically created because assessment #{assessment["id"]} reassessment became overdue',who); snapshot_entity(conn,'reassessment_triggers',cur.lastrowid,who,'Automatic assessment reassessment trigger')
            audit(conn,'ASSESSMENT_REASSESSMENT_OVERDUE','assessment',assessment['id'],reason,who); snapshot_entity(conn,'assessments',assessment['id'],who,'Assessment reassessment automatically marked overdue'); changed.append(assessment['id'])
        conn.commit(); return changed
    finally: conn.close()

def sweep_overdue_decisions(assessment_ids=None, who='system-lifecycle'):
    if not assessment_ids: return []
    conn=db(); changed=[]
    try:
        ids=[int(x) for x in assessment_ids]; marks=','.join('?'*len(ids)); params=tuple(ids); today=datetime.now(timezone.utc).date(); ts=now()
        rows=[dict(r) for r in conn.execute(f"SELECT * FROM decisions WHERE review_date<>'' AND review_lifecycle_status<>'Review Overdue' AND assessment_id IN ({marks}) ORDER BY id",params)]
        for decision in rows:
            try: due=datetime.strptime(str(decision['review_date'])[:10],'%Y-%m-%d').date()
            except Exception: continue
            if due>=today: continue
            reason=f'Review date passed on {due.isoformat()}.'
            conn.execute("UPDATE decisions SET review_lifecycle_status='Review Overdue',review_overdue_reason=?,review_overdue_at=?,updated_at=? WHERE id=?",(reason,ts,ts,decision['id']))
            existing=conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Decision Lifecycle' AND trigger_type='Executive Decision Review Overdue' AND affected_record_type='decision' AND affected_record_id=? AND status!='Resolved' ORDER BY id DESC LIMIT 1",(decision['assessment_id'],decision['id'])).fetchone()
            if not existing:
                cur=conn.execute('''INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(decision['assessment_id'],'Decision Lifecycle','Executive Decision Review Overdue',f'Executive decision review became overdue: {decision["decision_type"]}. {reason}','High','decision',decision['id'],'Open',decision['authority'],decision['review_date'],'',ts,ts))
                audit(conn,'CREATE','reassessment_trigger',cur.lastrowid,f'Automatically created because executive decision #{decision["id"]} review became overdue',who); snapshot_entity(conn,'reassessment_triggers',cur.lastrowid,who,'Automatic executive-decision review trigger')
            audit(conn,'DECISION_REVIEW_OVERDUE','decision',decision['id'],reason,who); snapshot_entity(conn,'decisions',decision['id'],who,'Executive decision review automatically marked overdue'); changed.append(decision['id'])
        conn.commit(); return changed
    finally: conn.close()


def safe_filename(name:str):
    base=os.path.basename(name or 'attachment')
    base=re.sub(r'[^A-Za-z0-9._-]+','_',base).strip('._') or 'attachment'
    return base[:180]

def executive_package(assessment_id:int):
    sweep_overdue_assessments([assessment_id])
    sweep_overdue_decisions([assessment_id])
    sweep_stale_evidence([assessment_id])
    sweep_overdue_accepted_risks([assessment_id])
    sweep_overdue_risk_overrides([assessment_id])
    conn=db()
    a=conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone()
    if not a: conn.close(); raise HTTPException(404)
    tables=['threats','scenarios','capabilities','evidence','gaps','improvements','decisions','accepted_risks','risk_overrides','reassessment_triggers','scope_changes','workflow_events']
    data={'generated_at':now(),'assessment':dict(a)}
    for table in tables:
        data[table]=[dict(r) for r in conn.execute(f'SELECT * FROM {table} WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    data['weights']=dict(conn.execute('SELECT * FROM assessment_weights WHERE assessment_id=?',(assessment_id,)).fetchone() or {})
    data['capability_performance']=[capability_summary(r) for r in conn.execute('SELECT * FROM capabilities WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    data['versions']=[dict(r) for r in conn.execute('SELECT id,assessment_id,entity_type,entity_id,version_no,change_reason,changed_by,created_at FROM entity_versions WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    conn.close()
    data['risk']=risk_summary(assessment_id)
    data['risk_methodology_version']=(data['weights'].get('risk_methodology_version') or RISK_METHODOLOGY_VERSION)
    data['priorities']=priorities(assessment_id)
    return data

def backfill_baseline_versions():
    conn=db()
    for table in VERSIONED_TABLES:
        for row in conn.execute(f'SELECT * FROM {table} ORDER BY id'):
            exists=conn.execute('SELECT 1 FROM entity_versions WHERE entity_type=? AND entity_id=? LIMIT 1',(table,row['id'])).fetchone()
            if not exists:
                snapshot_entity(conn,table,row['id'],'system-migration','v0.3 baseline snapshot')
    conn.commit(); conn.close()

backfill_baseline_versions()

@app.get('/api/system/mode')
def system_mode(): return {'auth_mode':AUTH_MODE,'version':APP_VERSION,'db_backend':DB_BACKEND,'restore_enabled':ALLOW_RESTORE,'environment':ENVIRONMENT,'storage_backend':STORAGE_BACKEND,'av_mode':AV_MODE,'av_required':AV_REQUIRED,'oidc_configured':oidc_configured(),'rate_limit_backend':RATE_LIMITER.backend,'secret_backend':secret_readiness().get('backend'),'managed_db_target':managed_target_status().get('target'),'package_handoff_candidate_available':PACKAGE_COMMERCIAL_WORKFLOW_ENABLED and ENVIRONMENT!='production' and AUTH_MODE in ('session','oidc')}

@app.get('/api/auth/oidc/start')
def oidc_start(request:Request):
    if AUTH_MODE!='oidc': raise HTTPException(409,'OIDC authentication is not enabled.')
    cfg=oidc_discovery(); state=secrets.token_urlsafe(32); nonce=secrets.token_urlsafe(24)
    expires=(_iso_now_dt()+timedelta(minutes=OIDC_STATE_MINUTES)).replace(microsecond=0).isoformat().replace('+00:00','Z')
    conn=db(); conn.execute('DELETE FROM oidc_states WHERE expires_at<?',(now(),)); conn.execute('INSERT INTO oidc_states(state_hash,nonce,expires_at,created_at) VALUES(?,?,?,?)',(_hash_token(state),nonce,expires,now())); conn.commit(); conn.close()
    params={'client_id':OIDC_CLIENT_ID,'response_type':'code','redirect_uri':oidc_redirect_uri(request),'scope':OIDC_SCOPES,'state':state,'nonce':nonce}
    url=cfg['authorization_endpoint']+'?'+urllib.parse.urlencode(params)
    response=RedirectResponse(url,status_code=302); response.set_cookie('salus_oidc_state',state,httponly=True,secure=COOKIE_SECURE,samesite='lax',max_age=OIDC_STATE_MINUTES*60,path='/')
    return response

@app.get('/api/auth/oidc/callback',name='oidc_callback')
def oidc_callback(request:Request,code:str='',state:str='',error:str=''):
    if AUTH_MODE!='oidc': raise HTTPException(409,'OIDC authentication is not enabled.')
    if error:
        security_event(request,'OIDC_LOGIN_FAILURE','Medium',f'Provider error: {error}'); raise HTTPException(401,'Identity provider rejected authentication')
    cookie_state=request.cookies.get('salus_oidc_state','')
    if not state or not cookie_state or not secrets.compare_digest(state,cookie_state):
        security_event(request,'OIDC_STATE_MISMATCH','High','OIDC state validation failed'); raise HTTPException(401,'OIDC state validation failed')
    conn=db(); row=conn.execute('SELECT * FROM oidc_states WHERE state_hash=?',(_hash_token(state),)).fetchone()
    if not row: conn.close(); raise HTTPException(401,'OIDC state is invalid or expired')
    try: expires=datetime.fromisoformat(row['expires_at'].replace('Z','+00:00'))
    except Exception: expires=_iso_now_dt()-timedelta(seconds=1)
    if expires<=_iso_now_dt(): conn.execute('DELETE FROM oidc_states WHERE id=?',(row['id'],)); conn.commit(); conn.close(); raise HTTPException(401,'OIDC state expired')
    nonce=row['nonce']; conn.execute('DELETE FROM oidc_states WHERE id=?',(row['id'],)); conn.commit(); conn.close()
    cfg=oidc_discovery()
    try:
        token_data={'grant_type':'authorization_code','code':code,'redirect_uri':oidc_redirect_uri(request),'client_id':OIDC_CLIENT_ID}; token_data.update(oidc_client_auth_payload())
        tr=httpx.post(cfg['token_endpoint'],data=token_data,timeout=15); tr.raise_for_status(); tokens=tr.json(); id_token=tokens.get('id_token','')
        if not id_token: raise RuntimeError('No ID token returned')
        signing_key=jwt.PyJWKClient(cfg['jwks_uri']).get_signing_key_from_jwt(id_token).key
        claims=jwt.decode(id_token,signing_key,algorithms=['RS256','RS384','RS512','ES256','ES384','ES512'],audience=OIDC_CLIENT_ID,issuer=cfg['issuer'])
        if claims.get('nonce')!=nonce: raise RuntimeError('OIDC nonce mismatch')
        if str(claims.get('tid') or '')!=OIDC_TENANT_ID: raise RuntimeError('OIDC tenant mismatch')
    except Exception as exc:
        security_event(request,'OIDC_TOKEN_FAILURE','High',type(exc).__name__); raise HTTPException(401,'OIDC token validation failed')
    standard_subject=str(claims.get('sub') or '').strip(); entra_object_id=str(claims.get('oid') or '').strip(); subject=entra_object_id or standard_subject
    preferred_username=str(claims.get('preferred_username') or '').strip().lower()
    email=str(claims.get('email') or '').strip().lower()
    if not email and '@' in preferred_username: email=preferred_username
    display=str(claims.get('name') or preferred_username or email or subject)
    if not standard_subject or (OIDC_PROVIDER_NAME=='entra' and not entra_object_id): raise HTTPException(401,'OIDC subject claim missing')
    conn=db(); user=conn.execute("SELECT * FROM users WHERE identity_provider=? AND external_subject=? AND status='Active'",(OIDC_PROVIDER_NAME,subject)).fetchone()
    if not user and not OIDC_AUTO_PROVISION and email:
        candidates=list(conn.execute(
            "SELECT * FROM users WHERE identity_provider=? AND lower(email)=? AND external_subject='' AND status='Active' ORDER BY id",
            (OIDC_PROVIDER_NAME,email),
        ))
        if len(candidates)==1:
            user=candidates[0]
            conn.execute(
                "UPDATE users SET external_subject=?,updated_at=? WHERE id=? AND external_subject=''",
                (subject,now(),user['id']),
            )
            conn.commit()
            user=conn.execute("SELECT * FROM users WHERE id=?",(user['id'],)).fetchone()
            security_event(request,'OIDC_PREAUTHORIZED_IDENTITY_BOUND','Info',f'user_id={user["id"]}',tenant=int(user['tenant_id']),user_name=display)
        elif len(candidates)>1:
            conn.close(); security_event(request,'OIDC_PREAUTHORIZATION_AMBIGUOUS','High',f'email={email}'); raise HTTPException(403,'User preauthorization is ambiguous; contact a Salus administrator')
    if not user:
        if not OIDC_AUTO_PROVISION:
            conn.close(); security_event(request,'OIDC_USER_NOT_PROVISIONED','Medium',f'subject={subject} email={email}'); raise HTTPException(403,'User is not provisioned for SalCAPA')
        tenant=conn.execute("SELECT * FROM tenants WHERE slug=? AND status='Active'",(OIDC_DEFAULT_TENANT_SLUG,)).fetchone()
        if not tenant: conn.close(); raise HTTPException(503,'OIDC default tenant is not configured')
        username=email or f'{OIDC_PROVIDER_NAME}-{subject[:40]}'
        cur=conn.execute('INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email,external_subject,identity_provider) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tenant['id'],username,display,'','Contributor','Standard','Active',now(),now(),email,subject,OIDC_PROVIDER_NAME)); conn.commit(); user=conn.execute('SELECT * FROM users WHERE id=?',(cur.lastrowid,)).fetchone()
    token=secrets.token_urlsafe(32); session_expires=(_iso_now_dt()+timedelta(hours=SESSION_HOURS)).replace(microsecond=0).isoformat().replace('+00:00','Z'); accepted_at=now()
    conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',(user['id'],_hash_token(token),session_expires,accepted_at,accepted_at))
    acceptance_key=uuid.uuid4().hex
    conn.execute('INSERT INTO identity_acceptance_events(event_key,tenant_id,user_id,identity_provider,external_subject_sha256,mapped_role,mapped_clearance,authority_source,authentication_method,oidc_issuer_sha256,accepted_at,session_expires_at,request_id,source_network_sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(acceptance_key,int(user['tenant_id']),int(user['id']),OIDC_PROVIDER_NAME,_hash_token(subject),user['role'],user['sensitivity_clearance'] or 'Standard','server_user_mapping','oidc_authorization_code',_hash_token(cfg['issuer']),accepted_at,session_expires,request_id(request),_hash_token(request_ip(request)) if request_ip(request) else ''))
    conn.commit(); conn.close()
    security_event(request,'OIDC_LOGIN_SUCCESS','Info',f'user_id={user["id"]}; acceptance={acceptance_key}',tenant=int(user['tenant_id']),user_name=display)
    response=RedirectResponse('/',status_code=302); response.set_cookie('salus_session',token,httponly=True,secure=COOKIE_SECURE,samesite='strict',max_age=SESSION_HOURS*3600,path='/'); response.delete_cookie('salus_oidc_state',path='/'); return response

def _normalized_pilot_email(value:str):
    email=str(value or '').strip().lower()
    if any(ch.isspace() for ch in email) or email.count('@') != 1:
        raise HTTPException(422,'A valid email address is required.')
    local,domain=email.split('@',1)
    domain_parts=domain.split('.')
    if not local or len(local)>64 or len(email)>320 or len(domain_parts)<2 or any(not part for part in domain_parts):
        raise HTTPException(422,'A valid email address is required.')
    return email

@app.get('/api/admin/pilot/tenants')
def list_pilot_tenants(request:Request):
    require(request,'admin'); conn=db()
    rows=[dict(r) for r in conn.execute("SELECT id,name,slug,status,created_at FROM tenants ORDER BY name,id")]
    conn.close(); return rows

@app.post('/api/admin/pilot/tenants')
def create_pilot_tenant(p:PilotTenantIn,request:Request):
    require(request,'admin'); conn=db(); ts=now()
    try:
        cur=conn.execute("INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,'Active',?)",(p.name.strip(),p.slug.strip().lower(),ts))
        audit(conn,'PILOT_TENANT_CREATE','tenant',cur.lastrowid,f'slug={p.slug.strip().lower()}',actor(request))
        conn.commit(); row=dict(conn.execute("SELECT id,name,slug,status,created_at FROM tenants WHERE id=?",(cur.lastrowid,)).fetchone())
    except Exception as exc:
        conn.rollback(); conn.close()
        if 'unique' in str(exc).lower(): raise HTTPException(409,'That organization slug already exists.')
        raise
    conn.close(); return row

@app.get('/api/admin/pilot/users')
def list_pilot_users(request:Request):
    require(request,'admin'); conn=db()
    rows=[dict(r) for r in conn.execute(
        """SELECT u.id,u.tenant_id,t.name tenant_name,u.username,u.display_name,u.email,
                  u.identity_provider,u.role,u.sensitivity_clearance,u.status,u.created_at,u.updated_at,
                  CASE WHEN u.external_subject<>'' THEN 1 ELSE 0 END identity_bound
             FROM users u JOIN tenants t ON t.id=u.tenant_id ORDER BY t.name,u.display_name,u.id"""
    )]
    for row in rows: row.pop('username',None)
    conn.close(); return rows

@app.post('/api/admin/pilot/users')
def preauthorize_pilot_user(p:PilotUserIn,request:Request):
    require(request,'admin'); email=_normalized_pilot_email(p.email); conn=db()
    tenant=conn.execute("SELECT id FROM tenants WHERE id=? AND status='Active'",(p.tenant_id,)).fetchone()
    if not tenant: conn.close(); raise HTTPException(422,'Select an active Protected Member organization.')
    duplicate=conn.execute("SELECT id FROM users WHERE lower(email)=? AND status='Active'",(email,)).fetchone()
    if duplicate: conn.close(); raise HTTPException(409,'An active SalCAPA account already uses this email address.')
    ts=now(); username=email
    cur=conn.execute(
        """INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,
                             created_at,updated_at,email,external_subject,identity_provider)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (p.tenant_id,username,p.display_name.strip(),'',
         p.role,p.sensitivity_clearance,'Active',ts,ts,email,'',OIDC_PROVIDER_NAME),
    )
    audit(conn,'PILOT_USER_PREAUTHORIZE','user',cur.lastrowid,
          f'tenant={p.tenant_id}; role={p.role}; clearance={p.sensitivity_clearance}',actor(request))
    conn.commit(); user_id=cur.lastrowid
    row=dict(conn.execute(
        """SELECT u.id,u.tenant_id,t.name tenant_name,u.display_name,u.email,u.identity_provider,
                  u.role,u.sensitivity_clearance,u.status,u.created_at,u.updated_at,0 identity_bound
             FROM users u JOIN tenants t ON t.id=u.tenant_id WHERE u.id=?""",(user_id,)
    ).fetchone())
    conn.close(); return row

@app.post('/api/admin/pilot/users/{user_id}/status')
def set_pilot_user_status(user_id:int,p:PilotUserStatusIn,request:Request):
    require(request,'admin'); ctx=auth_context(request); conn=db()
    row=conn.execute("SELECT id,tenant_id,display_name,status FROM users WHERE id=?",(user_id,)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'User not found.')
    if int(row['id'])==int(ctx.get('user_id') or 0) and p.status=='Disabled':
        conn.close(); raise HTTPException(409,'Administrators cannot disable their own active session account.')
    ts=now(); conn.execute("UPDATE users SET status=?,updated_at=? WHERE id=?",(p.status,ts,user_id))
    if p.status=='Disabled': conn.execute("DELETE FROM auth_sessions WHERE user_id=?",(user_id,))
    audit(conn,'PILOT_USER_STATUS','user',user_id,f'{row["status"]}->{p.status}',actor(request))
    conn.commit(); result={'id':user_id,'status':p.status,'sessions_revoked':p.status=='Disabled'}
    conn.close(); return result

@app.post('/api/admin/pilot/users/{user_id}/assessment-access')
def set_pilot_assessment_access(user_id:int,p:PilotAssessmentAccessIn,request:Request):
    require(request,'admin'); conn=db()
    user=conn.execute("SELECT id,tenant_id FROM users WHERE id=?",(user_id,)).fetchone()
    if not user: conn.close(); raise HTTPException(404,'User not found.')
    ids=sorted(set(int(value) for value in p.assessment_ids if int(value)>0))
    if ids:
        marks=','.join('?'*len(ids))
        rows=list(conn.execute(f"SELECT id,tenant_id FROM assessments WHERE id IN ({marks})",tuple(ids)))
        if len(rows)!=len(ids) or any(int(row['tenant_id'])!=int(user['tenant_id']) for row in rows):
            conn.close(); raise HTTPException(422,'Every assessment must belong to the user organization.')
    conn.execute("DELETE FROM assessment_access WHERE user_id=?",(user_id,))
    ts=now()
    for assessment_id in ids:
        conn.execute(
            "INSERT INTO assessment_access(user_id,assessment_id,role_override,sensitivity_clearance,created_at) VALUES(?,?,?,?,?)",
            (user_id,assessment_id,p.role_override.strip(),p.sensitivity_clearance,ts),
        )
    audit(conn,'PILOT_USER_ASSESSMENT_ACCESS','user',user_id,
          f'assessments={",".join(str(value) for value in ids) or "tenant-wide"}',actor(request))
    conn.commit(); result={'user_id':user_id,'assessment_ids':ids,'tenant_wide':not bool(ids)}
    conn.close(); return result

@app.post('/api/auth/login')
def login(p:LoginIn, request:Request):
    if AUTH_MODE!='session': raise HTTPException(409,'Session authentication is not enabled. Set SALUS_AUTH_MODE=session.')
    conn=db(); u=conn.execute("SELECT * FROM users WHERE lower(username)=lower(?) AND status='Active'",(p.username.strip(),)).fetchone()
    if not u or not verify_password(p.password,u['password_hash']):
        conn.close(); security_event(request,'LOGIN_FAILURE','Medium',f'username={p.username.strip()}'); raise HTTPException(401,'Invalid credentials')
    token=secrets.token_urlsafe(32); expires=(_iso_now_dt()+timedelta(hours=SESSION_HOURS)).replace(microsecond=0).isoformat().replace('+00:00','Z')
    conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',(u['id'],_hash_token(token),expires,now(),now())); conn.commit(); conn.close()
    security_event(request,'LOGIN_SUCCESS','Info',f'user_id={u["id"]}',tenant=int(u['tenant_id']),user_name=u['display_name'] or u['username'])
    response=JSONResponse({'ok':True,'user':u['display_name'] or u['username'],'role':u['role'],'tenant_id':u['tenant_id'],'expires_at':expires})
    response.set_cookie('salus_session',token,httponly=True,secure=COOKIE_SECURE,samesite='strict',max_age=SESSION_HOURS*3600,path='/')
    return response

@app.post('/api/auth/logout')
def logout(request:Request):
    raw=request.cookies.get('salus_session',''); conn=db()
    if raw: conn.execute('DELETE FROM auth_sessions WHERE token_hash=?',(_hash_token(raw),)); conn.commit()
    conn.close(); response=JSONResponse({'ok':True}); response.delete_cookie('salus_session',path='/'); return response

@app.get('/api/auth/session')
def session_info(request:Request):
    ctx=auth_context(request); return {'authenticated':AUTH_MODE in ('session','oidc'),'auth_mode':AUTH_MODE,**ctx}

def create_backup_archive(request:Request, reason:str='Manual backup'):
    require(request,'admin'); tid=tenant_id(request); ts=datetime.utcnow().strftime('%Y%m%dT%H%M%S%fZ'); nonce=uuid.uuid4().hex[:12]; name=f'salus-thira-tenant-{tid}-backup-{ts}-{nonce}.zip'; final=os.path.join(BACKUPS_DIR,name)
    conn=db(); assessment_ids=[r['id'] for r in conn.execute('SELECT id FROM assessments WHERE tenant_id=?',(tid,))]; conn.close()
    if assessment_ids:
        sweep_overdue_assessments(assessment_ids)
        sweep_overdue_decisions(assessment_ids)
        sweep_stale_evidence(assessment_ids)
        sweep_overdue_accepted_risks(assessment_ids)
        sweep_overdue_risk_overrides(assessment_ids)
    conn=db(); records=collect_tenant_records(conn,tid); conn.close()
    record_errors=validate_records(records,tid)
    if record_errors: raise HTTPException(409,'Backup record validation failed: '+'; '.join(record_errors))
    records_bytes=json.dumps({'format':'salus-thira-records-v1','tenant_id':tid,'tables':records},sort_keys=True,separators=(',',':'),default=str).encode('utf-8')
    manifest={'format':'salus-thira-portable-backup-v1','created_at':now(),'created_by':actor(request),'tenant_id':tid,'reason':reason,'application_version':APP_VERSION,'database_backend':DB_BACKEND,'files':[]}
    with zipfile.ZipFile(final,'w',compression=zipfile.ZIP_DEFLATED) as z:
        manifest['files'].append({'path':'records.json','sha256':hashlib.sha256(records_bytes).hexdigest(),'size_bytes':len(records_bytes)}); z.writestr('records.json',records_bytes)
        stored_records=(records.get('evidence_attachments',[])+records.get('materials',[])
            +records.get('package_agreement_artifacts',[])+records.get('package_intake_uploads',[])
            +records.get('package_product_report_versions',[])
            +records.get('package_report_qa_evidence',[]))
        backed_up_objects=set()
        for item in sorted(stored_records,key=lambda x:str(x.get('stored_name',''))):
            fn=str(item.get('stored_name','')).strip()
            if not fn or fn in backed_up_objects: continue
            try: b=storage.get_bytes(fn)
            except Exception as exc:
                error_id=uuid.uuid4().hex; record_internal_failure('backup governed material read',error_id,exc)
                raise HTTPException(409,f'Backup cannot read a governed material object. Reference: {error_id}')
            expected_object_sha=item.get('archive_sha256') if item.get('archive_sha256') else item.get('content_sha256')
            if expected_object_sha and hashlib.sha256(b).hexdigest()!=expected_object_sha:
                raise HTTPException(409,'Backup stopped because a governed artifact failed integrity verification.')
            backed_up_objects.add(fn)
            arc=f'attachments/{fn}'; manifest['files'].append({'path':arc,'sha256':hashlib.sha256(b).hexdigest(),'size_bytes':len(b)}); z.writestr(arc,b)
        z.writestr('manifest.json',json.dumps(manifest,indent=2,sort_keys=True))
    data=Path(final).read_bytes(); digest=hashlib.sha256(data).hexdigest(); conn=db(); cur=conn.execute('INSERT INTO backup_history(tenant_id,filename,sha256,size_bytes,created_by,created_at) VALUES(?,?,?,?,?,?)',(tid,name,digest,len(data),actor(request),now())); bid=cur.lastrowid; audit(conn,'BACKUP','backup_history',bid,reason,actor(request)); conn.commit(); conn.close(); return {'id':bid,'filename':name,'sha256':digest,'size_bytes':len(data),'created_at':manifest['created_at'],'format':manifest['format']}

def verify_backup_file(path:str):
    with zipfile.ZipFile(path,'r') as z:
        manifest=json.loads(z.read('manifest.json').decode('utf-8')); errors=[]
        for item in manifest.get('files',[]):
            try: b=z.read(item['path'])
            except KeyError: errors.append(f"Missing {item['path']}"); continue
            if hashlib.sha256(b).hexdigest()!=item['sha256']: errors.append(f"Hash mismatch {item['path']}")
        if 'records.json' in z.namelist():
            try:
                package=json.loads(z.read('records.json').decode('utf-8')); records=package.get('tables',{}); errors.extend(validate_records(records,manifest.get('tenant_id')))
                for agreement in records.get('package_agreement_artifacts',[]):
                    archive_path='attachments/'+str(agreement.get('stored_name') or '')
                    if archive_path not in z.namelist():
                        errors.append(f'Missing package agreement artifact {agreement.get("id")}')
                    elif hashlib.sha256(z.read(archive_path)).hexdigest()!=agreement.get('content_sha256'):
                        errors.append(f'Package agreement artifact hash mismatch {agreement.get("id")}')
                for upload in records.get('package_intake_uploads',[]):
                    archive_path='attachments/'+str(upload.get('stored_name') or '')
                    if archive_path not in z.namelist():
                        errors.append(f'Missing package intake file {upload.get("id")}')
                    elif hashlib.sha256(z.read(archive_path)).hexdigest()!=upload.get('content_sha256'):
                        errors.append(f'Package intake file hash mismatch {upload.get("id")}')
                for report in records.get('package_product_report_versions',[]):
                    archive_path='attachments/'+str(report.get('stored_name') or '')
                    if archive_path not in z.namelist():
                        errors.append(f'Missing package product report {report.get("id")}')
                    elif hashlib.sha256(z.read(archive_path)).hexdigest()!=report.get('content_sha256'):
                        errors.append(f'Package product report hash mismatch {report.get("id")}')
                for evidence in records.get('package_report_qa_evidence',[]):
                    archive_path='attachments/'+str(evidence.get('stored_name') or '')
                    if archive_path not in z.namelist():
                        errors.append(f'Missing package report QA evidence {evidence.get("id")}')
                    elif hashlib.sha256(z.read(archive_path)).hexdigest()!=evidence.get('archive_sha256'):
                        errors.append(f'Package report QA evidence hash mismatch {evidence.get("id")}')
            except Exception as exc:
                error_id=uuid.uuid4().hex; record_internal_failure('backup record validation',error_id,exc)
                errors.append(f'Record package invalid. Reference: {error_id}')
        elif 'thira.db' in z.namelist():
            # Backward-compatible verification for v0.7 and earlier SQLite backups.
            dbbytes=z.read('thira.db'); fd,tmp=tempfile.mkstemp(suffix='.db'); os.close(fd); Path(tmp).write_bytes(dbbytes); c=sqlite3.connect(tmp); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; c.close(); os.unlink(tmp)
            if integrity!='ok': errors.append(f'Database integrity: {integrity}')
        else: errors.append('Backup contains neither records.json nor thira.db')
        return {'ok':not errors,'errors':errors,'manifest':manifest}

def dr_validate_backup_file(path:str):
    base=verify_backup_file(path); errors=list(base.get('errors',[])); assessment_count=attachment_count=0; db_integrity='unknown'
    if errors: return {'ok':False,'errors':errors,'database_integrity':db_integrity,'assessment_count':0,'attachment_count':0,'manifest':base.get('manifest',{})}
    with zipfile.ZipFile(path,'r') as z:
        if 'records.json' in z.namelist():
            package=json.loads(z.read('records.json').decode('utf-8')); records=package.get('tables',{}); db_integrity='portable-record-integrity-ok'
            assessment_count=len(records.get('assessments',[]))
            attachment_count=len({
                str(row.get('stored_name','')).strip()
                for table in ('evidence_attachments','materials','package_agreement_artifacts','package_intake_uploads','package_product_report_versions','package_report_qa_evidence')
                for row in records.get(table,[])
                if str(row.get('stored_name','')).strip()
            })
            errors.extend(validate_records(records,base.get('manifest',{}).get('tenant_id')))
        else:
            fd,tmp=tempfile.mkstemp(suffix='.db'); os.close(fd); Path(tmp).write_bytes(z.read('thira.db'))
            try:
                c=sqlite3.connect(tmp); c.row_factory=sqlite3.Row; db_integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
                required=['tenants','users','assessments','threats','scenarios','capabilities','evidence','gaps','improvements','decisions','audit_log']; existing={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                missing=[x for x in required if x not in existing]
                if missing: errors.append('Missing required tables: '+', '.join(missing))
                if 'assessments' in existing: assessment_count=c.execute('SELECT COUNT(*) FROM assessments').fetchone()[0]
                if 'evidence_attachments' in existing: attachment_count=c.execute('SELECT COUNT(*) FROM evidence_attachments').fetchone()[0]
                c.close()
            except Exception as exc:
                error_id=uuid.uuid4().hex; record_internal_failure('recovery database validation',error_id,exc)
                errors.append(f'Recovery database query failed. Reference: {error_id}')
            finally:
                try: os.unlink(tmp)
                except OSError: pass
        manifest_attachment_count=sum(1 for x in base.get('manifest',{}).get('files',[]) if str(x.get('path','')).startswith('attachments/'))
        if attachment_count!=manifest_attachment_count: errors.append(f'Attachment count mismatch: database/records={attachment_count}, package={manifest_attachment_count}')
        if assessment_count==0: errors.append('Recovery package contains no assessments')
    return {'ok':not errors,'errors':errors,'database_integrity':db_integrity,'assessment_count':assessment_count,'attachment_count':attachment_count,'manifest':base.get('manifest',{})}

@app.get('/api/admin/identity-acceptance')
def list_identity_acceptance(request:Request,limit:int=200):
    require(request,'admin'); conn=db(); rows=[dict(r) for r in conn.execute('SELECT event_key,user_id,identity_provider,external_subject_sha256,mapped_role,mapped_clearance,authority_source,authentication_method,oidc_issuer_sha256,accepted_at,session_expires_at,request_id,source_network_sha256 FROM identity_acceptance_events WHERE tenant_id=? ORDER BY accepted_at DESC,event_key DESC LIMIT ?',(tenant_id(request),max(1,min(limit,1000))))]; conn.close(); return rows

@app.get('/api/admin/security-events')
def list_security_events(request:Request,limit:int=200):
    require(request,'admin'); conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM security_events WHERE tenant_id=? OR tenant_id IS NULL ORDER BY id DESC LIMIT ?',(tenant_id(request),max(1,min(limit,1000))))]; conn.close(); return rows

@app.get('/api/admin/readiness')
def admin_readiness(request:Request):
    require(request,'admin'); return production_readiness()

@app.get('/api/admin/backups')
def list_backups(request:Request):
    require(request,'admin'); conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM backup_history WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]; conn.close(); return rows

@app.post('/api/admin/backups')
def create_backup(request:Request): return create_backup_archive(request)

@app.post('/api/admin/backups/{backup_id}/verify')
def verify_backup(backup_id:int,request:Request):
    require(request,'admin'); conn=db(); r=conn.execute('SELECT * FROM backup_history WHERE id=? AND tenant_id=?',(backup_id,tenant_id(request))).fetchone(); conn.close()
    if not r: raise HTTPException(404)
    path=os.path.join(BACKUPS_DIR,r['filename']); result=verify_backup_file(path)
    if result['ok']:
        conn=db(); conn.execute('UPDATE backup_history SET verified_at=? WHERE id=?',(now(),backup_id)); audit(conn,'VERIFY_BACKUP','backup_history',backup_id,'Backup integrity verified',actor(request)); conn.commit(); conn.close()
    return result

@app.post('/api/admin/backups/{backup_id}/dr-validate')
def dr_validate_backup(backup_id:int,request:Request):
    require(request,'admin'); tid=tenant_id(request); conn=db(); r=conn.execute('SELECT * FROM backup_history WHERE id=? AND tenant_id=?',(backup_id,tid)).fetchone(); conn.close()
    if not r: raise HTTPException(404)
    path=os.path.join(BACKUPS_DIR,r['filename']); result=dr_validate_backup_file(path)
    conn=db(); cur=conn.execute('INSERT INTO dr_validations(tenant_id,backup_id,status,database_integrity,assessment_count,attachment_count,errors_json,validated_by,validated_at) VALUES(?,?,?,?,?,?,?,?,?)',(tid,backup_id,'Passed' if result['ok'] else 'Failed',result['database_integrity'],result['assessment_count'],result['attachment_count'],json.dumps(result['errors']),actor(request),now())); audit(conn,'DR_VALIDATE','backup_history',backup_id,f"status={'Passed' if result['ok'] else 'Failed'} validation_id={cur.lastrowid}",actor(request)); conn.commit(); conn.close()
    security_event(request,'DR_VALIDATION_PASSED' if result['ok'] else 'DR_VALIDATION_FAILED','Info' if result['ok'] else 'High',f'backup_id={backup_id}; errors={result["errors"]}')
    return result

@app.get('/api/admin/dr-validations')
def list_dr_validations(request:Request,limit:int=100):
    require(request,'admin'); conn=db(); rows=[dict(r) for r in conn.execute('SELECT d.*,b.filename FROM dr_validations d JOIN backup_history b ON b.id=d.backup_id WHERE d.tenant_id=? ORDER BY d.id DESC LIMIT ?',(tenant_id(request),max(1,min(limit,500))))]; conn.close(); return rows

@app.get('/api/admin/backups/{backup_id}/download')
def download_backup(backup_id:int,request:Request):
    require(request,'admin'); conn=db(); r=conn.execute('SELECT * FROM backup_history WHERE id=? AND tenant_id=?',(backup_id,tenant_id(request))).fetchone(); conn.close()
    if not r: raise HTTPException(404)
    path=os.path.join(BACKUPS_DIR,r['filename']); return FileResponse(path,media_type='application/zip',filename=r['filename'])

@app.post('/api/admin/backups/{backup_id}/restore')
def restore_backup(backup_id:int,restore_request_id:int,request:Request):
    require(request,'admin')
    if not ALLOW_RESTORE: raise HTTPException(403,'Restore is disabled. Set SALUS_ALLOW_RESTORE=1 only during an authorized maintenance window.')
    tid=tenant_id(request); conn=db(); r=conn.execute('SELECT * FROM backup_history WHERE id=? AND tenant_id=?',(backup_id,tid)).fetchone(); authorization=conn.execute("SELECT * FROM restore_requests WHERE id=? AND tenant_id=? AND backup_id=? AND status='Authorized'",(restore_request_id,tid,backup_id)).fetchone(); conn.close()
    if not r: raise HTTPException(404)
    if not authorization: raise HTTPException(403,'An authorized restore request for this tenant and backup is required.')
    path=os.path.join(BACKUPS_DIR,r['filename']); check=verify_backup_file(path)
    if not check['ok']: raise HTTPException(409,'Backup failed integrity verification')
    create_backup_archive(request,'Automatic pre-restore safety backup')
    with zipfile.ZipFile(path,'r') as z:
        if 'records.json' in z.namelist():
            package=json.loads(z.read('records.json').decode('utf-8')); records=package.get('tables',{})
            if int(package.get('tenant_id',tid))!=tid: raise HTTPException(409,'Backup tenant does not match the active tenant')
            conn=db()
            old_keys=[r['stored_name'] for r in conn.execute('SELECT ea.stored_name FROM evidence_attachments ea JOIN assessments a ON a.id=ea.assessment_id WHERE a.tenant_id=?',(tid,))]
            old_keys.extend(r['stored_name'] for r in conn.execute("SELECT stored_name FROM materials WHERE tenant_id=? AND stored_name<>''",(tid,)))
            old_keys.extend(r['stored_name'] for r in conn.execute('SELECT stored_name FROM package_agreement_artifacts WHERE tenant_id=?',(tid,)))
            old_keys.extend(r['stored_name'] for r in conn.execute('SELECT stored_name FROM package_intake_uploads WHERE tenant_id=?',(tid,)))
            old_keys.extend(r['stored_name'] for r in conn.execute('SELECT stored_name FROM package_product_report_versions WHERE tenant_id=?',(tid,)))
            old_keys.extend(r['stored_name'] for r in conn.execute('SELECT stored_name FROM package_report_qa_evidence WHERE tenant_id=?',(tid,)))
            old_keys=list(dict.fromkeys(old_keys)); conn.close()
            new_objects={}
            for item in z.namelist():
                if item.startswith('attachments/') and not item.endswith('/'):
                    key=item[len('attachments/'):].lstrip('/')
                    if '..' in key.split('/'): raise HTTPException(409,'Unsafe attachment path in backup')
                    new_objects[key]=z.read(item)
            for key,data in new_objects.items(): storage.put_bytes(key,data)
            conn=db()
            try:
                replace_tenant_records(conn,tid,records); conn.commit()
            except Exception as exc:
                conn.rollback(); conn.close(); error_id=uuid.uuid4().hex; record_internal_failure('tenant restore',error_id,exc); raise HTTPException(409,f'Tenant restore failed. Reference: {error_id}')
            conn.close()
            for key in old_keys:
                if key not in new_objects:
                    try: storage.delete(key)
                    except Exception: pass
        elif 'thira.db' in z.namelist():
            if not is_sqlite(): raise HTTPException(409,'Legacy SQLite backup restore is available only when the active runtime database is SQLite. Convert the backup to the v0.8 portable format before PostgreSQL restore.')
            conn=db(); tenant_count=conn.execute('SELECT COUNT(*) c FROM tenants').fetchone()['c']; conn.close()
            if tenant_count>1: raise HTTPException(409,'Legacy full SQLite restore is blocked in a multi-tenant database.')
            fd,tmp=tempfile.mkstemp(suffix='.db'); os.close(fd); Path(tmp).write_bytes(z.read('thira.db')); os.replace(tmp,DB_PATH)
            storage.delete_prefix('')
            for item in z.namelist():
                if item.startswith('attachments/') and not item.endswith('/'):
                    key=item[len('attachments/'):].lstrip('/')
                    if '..' in key.split('/'): raise HTTPException(409,'Unsafe attachment path in backup')
                    storage.put_bytes(key,z.read(item))
        else: raise HTTPException(409,'Unsupported backup format')
    conn=db(); ts=now(); conn.execute('UPDATE backup_history SET restore_status=? WHERE id=?',(f'Restored {ts}',backup_id)); conn.execute("UPDATE restore_requests SET status='Executed',executed_by=?,executed_at=? WHERE id=?",(actor(request),ts,restore_request_id)); audit(conn,'RESTORE_EXECUTED','restore_request',restore_request_id,f'backup_id={backup_id}; scope={authorization["scope"]}',actor(request)); conn.commit(); conn.close(); security_event(request,'RESTORE_EXECUTED','Critical',f'restore_request_id={restore_request_id}; backup_id={backup_id}'); return {'ok':True,'restored_backup_id':backup_id,'restore_request_id':restore_request_id,'database_backend':DB_BACKEND}

@app.get('/')
def root():
    return FileResponse(os.path.join(BASE_DIR,'static','index.html'))

PROTECTED_MEMBER_ROLES={'Client Executive','Contributor'}
OPS_AUTHORITY_ROLES={'System Administrator','Assessment Director','Program Owner'}
COP_DECISION_CHOICES={
    'Set Priority':['Routine','Priority','Urgent','Critical'],
    'Approve Recommendation':['Approve','Approve with Conditions','Decline','Defer'],
    'Authorize Resources':['Authorize','Authorize with Conditions','Decline','Defer'],
    'Risk Decision':['Accept Risk','Mitigate','Transfer','Avoid','Defer'],
    'Request Action':['Request Action','No Action','Defer'],
}
COP_ACTION_SOURCES={
    'Set Priority':{'intel_finding','reassessment_trigger','ops_request'},
    'Approve Recommendation':{'improvement'},
    'Authorize Resources':{'improvement','ops_estimate'},
    'Risk Decision':{'improvement','accepted_risk'},
    'Request Action':{'intel_finding','reassessment_trigger','improvement'},
}

def protected_member_request(request:Request):
    return role(request) in PROTECTED_MEMBER_ROLES

def require_salus_component_authority(request:Request,component:str):
    if protected_member_request(request) or role(request)=='Auditor':
        raise HTTPException(403,f'{component} lifecycle authority is restricted to authorized Salus personnel.')

def require_ops_authority(request:Request):
    require_salus_component_authority(request,'SalOPS')
    if role(request) not in OPS_AUTHORITY_ROLES:
        raise HTTPException(403,f'{role(request)} cannot exercise SalOPS operational authority.')

def salcapa_workspace_contract(request:Request):
    current_role=role(request)
    protected_member=current_role in PROTECTED_MEMBER_ROLES
    workspaces=['SalCAPA']
    if not protected_member:
        workspaces.extend(['SalINTEL','SalTHIRA','SalOPS'])
    else:
        workspaces.extend(['Intelligence','Assessments','Requests & Operations'])
    return {
        'platform':'SalCAPA',
        'experience':'Protected Member' if protected_member else 'Salus Personnel',
        'user':actor(request),'role':current_role,'workspaces':workspaces,
        'navigation':['Command Center','Common Operating Picture','Intelligence','Assessments','Requests & Operations','Reports','Messages'],
        'component_authority':{
            'SalINTEL':not protected_member and current_role not in {'Auditor'},
            'SalTHIRA':not protected_member and current_role not in {'Auditor'},
            'SalOPS':not protected_member and current_role not in {'Auditor'},
        }
    }

def _cop_event(conn,record_type:str,record_id:int,event_type:str,summary:str,request:Request):
    tables={'coordination_thread':'cop_coordination_threads','decision_request':'cop_decision_requests'}
    table=tables.get(record_type)
    if not table: raise ValueError('Unsupported COP event record type')
    row=conn.execute(f'SELECT * FROM {table} WHERE id=?',(record_id,)).fetchone()
    if not row: raise ValueError('COP event record unavailable')
    version=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM cop_events WHERE tenant_id=? AND record_type=? AND record_id=?',(row['tenant_id'],record_type,record_id)).fetchone()['n']
    conn.execute('INSERT INTO cop_events(tenant_id,record_type,record_id,version_no,event_type,summary,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(row['tenant_id'],record_type,record_id,version,event_type,summary,json.dumps(dict(row),sort_keys=True,default=str),actor(request),role(request),now()))

def _cop_source(conn,request:Request,source_type:str,source_id:int):
    queries={
        'intel_finding':('SELECT *,tenant_id AS source_tenant FROM intel_findings WHERE id=?','title'),
        'reassessment_trigger':('SELECT r.*,a.tenant_id AS source_tenant FROM reassessment_triggers r JOIN assessments a ON a.id=r.assessment_id WHERE r.id=?','trigger_type'),
        'improvement':('SELECT i.*,a.tenant_id AS source_tenant FROM improvements i JOIN assessments a ON a.id=i.assessment_id WHERE i.id=?','title'),
        'accepted_risk':('SELECT r.*,a.tenant_id AS source_tenant FROM accepted_risks r JOIN assessments a ON a.id=r.assessment_id WHERE r.id=?','title'),
        'ops_request':('SELECT *,tenant_id AS source_tenant FROM ops_requests WHERE id=?','title'),
        'ops_estimate':("SELECT e.*,g.title, e.tenant_id AS source_tenant FROM ops_estimates e JOIN ops_engagements g ON g.id=e.engagement_id WHERE e.id=?",'title'),
    }
    spec=queries.get(source_type)
    if not spec: conn.close(); raise HTTPException(422,'Unsupported decision-request source.')
    row=conn.execute(spec[0],(source_id,)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Decision-request source not found.')
    if int(row['source_tenant'])!=tenant_id(request):
        conn.close()
        security_event(request,'COP_TENANT_BOUNDARY_VIOLATION','High',f'{source_type}={source_id}')
        raise HTTPException(403,'Tenant boundary violation')
    item=dict(row); assessment_id=item.get('assessment_id')
    if assessment_id is not None:
        try: assessment_row_for_request(request,int(assessment_id))
        except Exception: conn.close(); raise
    return item,str(item.get(spec[1]) or f'{source_type} #{source_id}')

def _cop_member_thread(row,messages):
    return {'id':row['id'],'assessment_id':row['assessment_id'],'subject':row['subject'],'status':row['status'],'assigned_contact':row['assigned_contact'],'assigned_contact_summary':row['assigned_contact_summary'],'created_by':row['created_by'],'created_at':row['created_at'],'updated_at':row['updated_at'],'messages':[{'id':m['id'],'body':m['body'],'author':m['author'],'author_role':m['author_role'],'created_at':m['created_at']} for m in messages if m['audience']=='Shared']}

def _cop_thread_for_request(conn,thread_id:int,request:Request):
    row=conn.execute('SELECT * FROM cop_coordination_threads WHERE id=?',(thread_id,)).fetchone()
    if not row: raise HTTPException(404,'Coordination thread not found')
    if int(row['tenant_id'])!=tenant_id(request):
        conn.close()
        security_event(request,'COP_TENANT_BOUNDARY_VIOLATION','High',f'coordination_thread={thread_id}')
        raise HTTPException(403,'Tenant boundary violation')
    if row['assessment_id'] is not None:
        try: assessment_row_for_request(request,int(row['assessment_id']))
        except Exception: conn.close(); raise
    return row

def _list_cop_threads(conn,request:Request):
    tid=tenant_id(request); ids=set(accessible_assessment_ids(request)); internal=not protected_member_request(request) and role(request)!='Auditor'; result=[]
    for row in conn.execute('SELECT * FROM cop_coordination_threads WHERE tenant_id=? ORDER BY CASE status WHEN \'Open\' THEN 0 ELSE 1 END,updated_at DESC,id DESC',(tid,)):
        if row['assessment_id'] is not None and int(row['assessment_id']) not in ids: continue
        messages=[dict(m) for m in conn.execute('SELECT * FROM cop_coordination_messages WHERE thread_id=? AND tenant_id=? ORDER BY id',(row['id'],tid))]
        if internal:
            item=dict(row); item['messages']=messages
        else: item=_cop_member_thread(row,messages)
        result.append(item)
    return result

def _decision_request_view(row,member_safe=True):
    item=dict(row); item['allowed_choices']=json.loads(item.pop('allowed_choices_json'))
    item['authorized_amount']=_money(item.pop('authorized_amount_cents'))
    if member_safe:
        allowed={'id','assessment_id','source_type','source_id','action_type','title','member_summary','allowed_choices','due_at','status','requested_at','decision','rationale','conditions','authorized_amount','decided_by','decided_at','updated_at'}
        item={key:value for key,value in item.items() if key in allowed}
    return item

def _list_cop_decisions(conn,request:Request):
    ids=set(accessible_assessment_ids(request)); member_safe=protected_member_request(request) or role(request)=='Auditor'; result=[]
    for row in conn.execute("SELECT * FROM cop_decision_requests WHERE tenant_id=? ORDER BY CASE status WHEN 'Awaiting Decision' THEN 0 ELSE 1 END,due_at,id DESC",(tenant_id(request),)):
        if row['assessment_id'] is not None and int(row['assessment_id']) not in ids: continue
        result.append(_decision_request_view(row,member_safe))
    return result

@app.get('/api/salcapa/workspace')
def get_salcapa_workspace(request:Request):
    require(request,'read'); return salcapa_workspace_contract(request)

def _protective_readiness_summary(conn, assessment_ids:list[int], tenant:int):
    promise='See, Decide, Coordinate, Act, and Prove progress from an unverified condition toward demonstrated protective assurance.'
    lifecycle='Signal or observation -> qualification -> assessment -> capability priority -> executive decision -> coordination -> responsible owner -> authorized action -> completion evidence -> testing or verification -> result -> reassessment.'
    trace={
        'qualified_signals':0,
        'assessed_capability_gaps':0,
        'prioritized_improvements':0,
        'executive_decisions':0,
        'coordination_threads':0,
        'owned_actions':0,
        'authorized_actions':0,
        'completed_actions':0,
        'verified_actions':0,
        'current_verified_evidence':0,
        'released_proof_records':0,
        'reassessment_triggers':0,
    }
    if assessment_ids:
        marks=','.join('?'*len(assessment_ids)); params=tuple(assessment_ids)
        trace['qualified_signals']=conn.execute(
            f"SELECT COUNT(*) c FROM intel_findings WHERE tenant_id=? AND status IN ('Qualified','Sent to SalTHIRA') AND (assessment_id IS NULL OR assessment_id IN ({marks}))",
            (tenant,)+params,
        ).fetchone()['c']
        trace['assessed_capability_gaps']=conn.execute(
            f"SELECT COUNT(*) c FROM gaps WHERE assessment_id IN ({marks})",params
        ).fetchone()['c']
        trace['prioritized_improvements']=conn.execute(
            f"SELECT COUNT(*) c FROM improvements WHERE assessment_id IN ({marks})",params
        ).fetchone()['c']
        trace['executive_decisions']=conn.execute(
            f"SELECT COUNT(*) c FROM decisions WHERE assessment_id IN ({marks})",params
        ).fetchone()['c']
        trace['owned_actions']=conn.execute(
            f"SELECT COUNT(*) c FROM improvements WHERE assessment_id IN ({marks}) AND TRIM(owner)<>''",params
        ).fetchone()['c']
        trace['authorized_actions']=conn.execute(
            f"SELECT COUNT(*) c FROM ops_requests WHERE tenant_id=? AND assessment_id IN ({marks}) AND status IN ('Authorized','In Progress','Completed')",
            (tenant,)+params,
        ).fetchone()['c']
        completed_requests=conn.execute(
            f"SELECT COUNT(*) c FROM ops_requests WHERE tenant_id=? AND assessment_id IN ({marks}) AND status='Completed'",
            (tenant,)+params,
        ).fetchone()['c']
        completed_tasks=conn.execute(
            f"SELECT COUNT(*) c FROM ops_tasks WHERE tenant_id=? AND assessment_id IN ({marks}) AND status='Completed'",
            (tenant,)+params,
        ).fetchone()['c']
        trace['completed_actions']=completed_requests+completed_tasks
        trace['verified_actions']=conn.execute(
            f"SELECT COUNT(*) c FROM improvements WHERE assessment_id IN ({marks}) AND status='Complete' AND validation_status IN ('Validated','Partially Validated')",
            params,
        ).fetchone()['c']
        trace['current_verified_evidence']=conn.execute(
            f"SELECT COUNT(*) c FROM evidence WHERE assessment_id IN ({marks}) AND verification_status='Verified' AND lifecycle_status='Current'",
            params,
        ).fetchone()['c']
        released_reports=conn.execute(
            f"SELECT COUNT(*) c FROM report_versions WHERE tenant_id=? AND assessment_id IN ({marks}) AND status='Released'",
            (tenant,)+params,
        ).fetchone()['c']
        released_field_reports=conn.execute(
            f"SELECT COUNT(*) c FROM ops_field_reports WHERE tenant_id=? AND assessment_id IN ({marks}) AND status='Released'",
            (tenant,)+params,
        ).fetchone()['c']
        trace['released_proof_records']=released_reports+released_field_reports
        trace['reassessment_triggers']=conn.execute(
            f"SELECT COUNT(*) c FROM reassessment_triggers WHERE assessment_id IN ({marks})",params
        ).fetchone()['c']
    trace['coordination_threads']=conn.execute(
        "SELECT COUNT(*) c FROM cop_coordination_threads WHERE tenant_id=?",(tenant,)
    ).fetchone()['c']
    stages=[
        {'key':'see','label':'See','count':trace['qualified_signals']+trace['assessed_capability_gaps'],'description':'Red: an unverified condition requires understanding; this is not a conclusion that the organization is unsafe.'},
        {'key':'decide','label':'Decide','count':trace['executive_decisions'],'description':'Orange: authorized people evaluate risk and priorities and decide what should happen.'},
        {'key':'coordinate','label':'Coordinate','count':trace['coordination_threads'],'description':'Yellow: people, authority, resources, dependencies, and timing are being aligned.'},
        {'key':'act','label':'Act','count':trace['authorized_actions'],'description':'Light green: approved protective action is underway but is not yet fully verified.'},
        {'key':'prove','label':'Prove','count':trace['completed_actions']+trace['verified_actions']+trace['released_proof_records'],'description':'Full green: current evidence demonstrates the highest reasonably achievable protective condition within scope—not absolute safety.'},
    ]
    for stage in stages: stage['state']='Active' if stage['count'] else 'No records'
    return {'source':'persisted_server_controlled_records','promise':promise,'lifecycle':lifecycle,'stages':stages,'trace':trace}

@app.get('/api/salcapa/common-operating-picture')
def salcapa_common_operating_picture(request:Request):
    require(request,'read'); tid=tenant_id(request); ids=accessible_assessment_ids(request); member_safe=protected_member_request(request) or role(request)=='Auditor'; conn=db()
    if ids:
        marks=','.join('?'*len(ids)); params=tuple(ids)
        trigger_rows=[dict(r) for r in conn.execute(f"SELECT * FROM reassessment_triggers WHERE assessment_id IN ({marks}) AND status<>'Resolved' ORDER BY CASE severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 ELSE 3 END,id DESC LIMIT 20",params)]
        stale=conn.execute(f"SELECT COUNT(*) c FROM evidence WHERE assessment_id IN ({marks}) AND lifecycle_status='Stale'",params).fetchone()['c']
        risk_rows=[dict(r) for r in conn.execute(f"SELECT * FROM accepted_risks WHERE assessment_id IN ({marks}) AND status IN ('Active','Under Review') ORDER BY review_date,id DESC LIMIT 20",params)]
        report_rows=[dict(r) for r in conn.execute(f"SELECT id,assessment_id,assessment_version,report_type,status,released_at,snapshot_sha256 FROM report_versions WHERE tenant_id=? AND assessment_id IN ({marks}) AND status='Released' ORDER BY released_at DESC,id DESC LIMIT 20",(tid,)+params)]
    else: trigger_rows=[]; risk_rows=[]; report_rows=[]; stale=0
    open_triggers=[{'id':r['id'],'assessment_id':r['assessment_id'],'title':r['trigger_type'],'priority':r['severity'],'status':r['status'],'due_at':r['due_date'],'updated_at':r['updated_at']} for r in trigger_rows]
    risks=[{'id':r['id'],'assessment_id':r['assessment_id'],'title':r['title'],'residual_exposure':r['residual_exposure'],'owner':r['owner'],'status':r['status'],'review_date':r['review_date'],'review_lifecycle_status':r['review_lifecycle_status'],'updated_at':r['updated_at']} for r in risk_rows]
    if member_safe:
        if ids:
            intel=[dict(r) for r in conn.execute(f"SELECT id,assessment_id,title,relevance,credibility,validation_status,operational_significance,status,qualified_at,updated_at FROM intel_findings WHERE tenant_id=? AND status IN ('Qualified','Sent to SalTHIRA') AND (assessment_id IS NULL OR assessment_id IN ({marks})) ORDER BY id DESC LIMIT 20",(tid,)+params)]
            ops=[dict(r) for r in conn.execute(f"SELECT id,assessment_id,source_type,source_id,title,priority,status,result_summary,completed_at,updated_at FROM ops_requests WHERE tenant_id=? AND (assessment_id IS NULL OR assessment_id IN ({marks})) ORDER BY id DESC LIMIT 20",(tid,)+params)]
            engagements=[dict(r) for r in conn.execute(f"SELECT id,assessment_id,title,service_type,planned_start,planned_end,member_status_summary,status,updated_at FROM ops_engagements WHERE tenant_id=? AND assessment_id IN ({marks}) ORDER BY id DESC LIMIT 20",(tid,)+params)]
        else:
            intel=[dict(r) for r in conn.execute("SELECT id,assessment_id,title,relevance,credibility,validation_status,operational_significance,status,qualified_at,updated_at FROM intel_findings WHERE tenant_id=? AND assessment_id IS NULL AND status IN ('Qualified','Sent to SalTHIRA') ORDER BY id DESC LIMIT 20",(tid,))]
            ops=[dict(r) for r in conn.execute("SELECT id,assessment_id,source_type,source_id,title,priority,status,result_summary,completed_at,updated_at FROM ops_requests WHERE tenant_id=? AND assessment_id IS NULL ORDER BY id DESC LIMIT 20",(tid,))]
            engagements=[]
    else:
        intel=[dict(r) for r in conn.execute("SELECT * FROM intel_findings WHERE tenant_id=? AND status IN ('Qualified','Sent to SalTHIRA') ORDER BY id DESC LIMIT 20",(tid,))]
        ops=[dict(r) for r in conn.execute("SELECT * FROM ops_requests WHERE tenant_id=? ORDER BY id DESC LIMIT 20",(tid,))]
        engagements=[dict(r) for r in conn.execute("SELECT * FROM ops_engagements WHERE tenant_id=? ORDER BY id DESC LIMIT 20",(tid,))]
    observations=[]
    if protected_member_request(request):
        sql="SELECT id,record_key,title,reported_urgency,status,disposition,created_at,updated_at FROM observations WHERE tenant_id=? AND intake_type='Authenticated'"
        p=[tid]
        if role(request)=='Contributor': sql+=' AND created_by=?'; p.append(actor(request))
        observations=[dict(r) for r in conn.execute(sql+' ORDER BY id DESC LIMIT 20',tuple(p))]
    decisions=_list_cop_decisions(conn,request); threads=_list_cop_threads(conn,request)
    readiness=_protective_readiness_summary(conn,ids,tid)
    conn.close()
    pending=sum(1 for item in decisions if item['status']=='Awaiting Decision')
    active_operations=sum(1 for item in ops if item['status'] in {'Requested','Authorized','In Progress'})
    return {'workspace':salcapa_workspace_contract(request),'protective_readiness':readiness,'metrics':{'qualified_intelligence':len(intel),'priority_actions':len(open_triggers),'pending_member_decisions':pending,'active_operations':active_operations,'stale_evidence':stale,'active_accepted_risks':len(risks)},'see':{'intelligence':intel,'alerts':open_triggers,'accepted_risks':risks,'operations':ops,'engagements':engagements,'deliverables':report_rows,'observations':observations},'coordinate':{'threads':threads},'act':{'decision_requests':decisions},'attention':{'intelligence':intel,'reassessment':open_triggers,'operations':ops}}

@app.post('/api/salcapa/coordination/threads')
def create_cop_thread(p:CopThreadIn,request:Request):
    require(request,'write'); tid=tenant_id(request); who=actor(request); ts=now()
    if p.assessment_id is not None: assessment_row_for_request(request,p.assessment_id)
    conn=db(); cur=conn.execute("INSERT INTO cop_coordination_threads(tenant_id,assessment_id,subject,status,created_by,created_by_role,created_at,updated_at) VALUES(?,?,?,'Open',?,?,?,?)",(tid,p.assessment_id,p.subject,who,role(request),ts,ts)); thread_id=cur.lastrowid
    conn.execute("INSERT INTO cop_coordination_messages(tenant_id,thread_id,audience,body,author,author_role,created_at) VALUES(?,?,'Shared',?,?,?,?)",(tid,thread_id,p.message,who,role(request),ts)); _cop_event(conn,'coordination_thread',thread_id,'Opened',p.subject,request); audit(conn,'COP_THREAD_OPEN','coordination_thread',thread_id,p.subject,who); conn.commit(); row=conn.execute('SELECT * FROM cop_coordination_threads WHERE id=?',(thread_id,)).fetchone(); messages=[dict(m) for m in conn.execute('SELECT * FROM cop_coordination_messages WHERE thread_id=? ORDER BY id',(thread_id,))]; result=_cop_member_thread(row,messages); conn.close(); return result

@app.post('/api/salcapa/coordination/threads/{thread_id}/messages')
def add_cop_message(thread_id:int,p:CopMessageIn,request:Request):
    require(request,'write'); conn=db(); thread=_cop_thread_for_request(conn,thread_id,request)
    if thread['status']!='Open': conn.close(); raise HTTPException(409,'Closed coordination threads cannot receive messages.')
    if protected_member_request(request) and p.audience!='Shared': conn.close(); raise HTTPException(403,'Protected Members can add Shared messages only.')
    if role(request)=='Auditor': conn.close(); raise HTTPException(403,'Auditors cannot add coordination messages.')
    ts=now(); who=actor(request); cur=conn.execute('INSERT INTO cop_coordination_messages(tenant_id,thread_id,audience,body,author,author_role,created_at) VALUES(?,?,?,?,?,?,?)',(tenant_id(request),thread_id,p.audience,p.body,who,role(request),ts)); conn.execute('UPDATE cop_coordination_threads SET updated_at=? WHERE id=?',(ts,thread_id)); _cop_event(conn,'coordination_thread',thread_id,'Message Added',f'{p.audience} message #{cur.lastrowid}',request); audit(conn,'COP_MESSAGE_CREATE','coordination_message',cur.lastrowid,f'thread={thread_id}; audience={p.audience}',who); conn.commit(); result={'id':cur.lastrowid,'thread_id':thread_id,'audience':p.audience,'body':p.body,'author':who,'author_role':role(request),'created_at':ts}; conn.close(); return result

@app.post('/api/salcapa/coordination/threads/{thread_id}/assign')
def assign_cop_thread(thread_id:int,p:CopAssignmentIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalCAPA coordination'); conn=db(); thread=_cop_thread_for_request(conn,thread_id,request)
    if thread['status']!='Open': conn.close(); raise HTTPException(409,'Only open coordination threads can be assigned.')
    ts=now(); who=actor(request); conn.execute('UPDATE cop_coordination_threads SET assigned_contact=?,assigned_contact_summary=?,assigned_by=?,assigned_at=?,updated_at=? WHERE id=?',(p.assigned_contact.strip(),p.member_contact_summary.strip(),who,ts,ts,thread_id)); _cop_event(conn,'coordination_thread',thread_id,'Assigned',p.member_contact_summary,request); audit(conn,'COP_THREAD_ASSIGN','coordination_thread',thread_id,p.member_contact_summary,who); conn.commit(); result=dict(conn.execute('SELECT * FROM cop_coordination_threads WHERE id=?',(thread_id,)).fetchone()); conn.close(); return result

@app.post('/api/salcapa/coordination/threads/{thread_id}/close')
def close_cop_thread(thread_id:int,p:CopThreadCloseIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalCAPA coordination'); conn=db(); thread=_cop_thread_for_request(conn,thread_id,request)
    if thread['status']!='Open': conn.close(); raise HTTPException(409,'Coordination thread is already closed.')
    ts=now(); who=actor(request); conn.execute("UPDATE cop_coordination_threads SET status='Closed',closed_by=?,closed_at=?,close_reason=?,updated_at=? WHERE id=?",(who,ts,p.reason.strip(),ts,thread_id)); _cop_event(conn,'coordination_thread',thread_id,'Closed',p.reason,request); audit(conn,'COP_THREAD_CLOSE','coordination_thread',thread_id,p.reason,who); conn.commit(); result=dict(conn.execute('SELECT * FROM cop_coordination_threads WHERE id=?',(thread_id,)).fetchone()); conn.close(); return result

@app.post('/api/salcapa/decision-requests')
def create_cop_decision_request(p:CopDecisionRequestIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalCAPA decision request'); conn=db(); source,source_title=_cop_source(conn,request,p.source_type,p.source_id)
    if p.source_type not in COP_ACTION_SOURCES[p.action_type]: conn.close(); raise HTTPException(422,f'{p.action_type} cannot use a {p.source_type} source.')
    due=''
    if p.due_at:
        try: due=datetime.fromisoformat(p.due_at.replace('Z','+00:00')).astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        except ValueError: conn.close(); raise HTTPException(422,'Decision due time must be an ISO 8601 date or timestamp.')
    if p.source_type=='intel_finding' and source['status'] not in {'Qualified','Sent to SalTHIRA'}: conn.close(); raise HTTPException(409,'Only qualified intelligence can be presented for member decision.')
    if p.source_type=='ops_estimate' and source['status']!='Submitted': conn.close(); raise HTTPException(409,'Only a submitted operational estimate can be presented for resource authorization.')
    if conn.execute("SELECT id FROM cop_decision_requests WHERE tenant_id=? AND source_type=? AND source_id=? AND action_type=? AND status='Awaiting Decision'",(tenant_id(request),p.source_type,p.source_id,p.action_type)).fetchone(): conn.close(); raise HTTPException(409,'An active decision request already exists for this source and action.')
    who=actor(request); ts=now(); choices=json.dumps(COP_DECISION_CHOICES[p.action_type],separators=(',',':')); assessment_id=source.get('assessment_id')
    cur=conn.execute("INSERT INTO cop_decision_requests(tenant_id,assessment_id,source_type,source_id,action_type,title,member_summary,allowed_choices_json,due_at,status,requested_by,requested_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,'Awaiting Decision',?,?,?)",(tenant_id(request),assessment_id,p.source_type,p.source_id,p.action_type,p.title.strip(),p.member_summary.strip(),choices,due,who,ts,ts))
    request_id=cur.lastrowid; _cop_event(conn,'decision_request',request_id,'Issued',f'{p.action_type}: {source_title}',request); audit(conn,'COP_DECISION_REQUEST_CREATE','decision_request',request_id,f'{p.action_type}; {p.source_type}={p.source_id}',who); conn.commit(); result=_decision_request_view(conn.execute('SELECT * FROM cop_decision_requests WHERE id=?',(request_id,)).fetchone(),False); conn.close(); return result

@app.post('/api/salcapa/decision-requests/{decision_request_id}/decide')
def decide_cop_request(decision_request_id:int,p:CopMemberDecisionIn,request:Request):
    require_protected_member_authority(request,'salcapa_decision')
    conn=db(); row=conn.execute('SELECT * FROM cop_decision_requests WHERE id=?',(decision_request_id,)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Decision request not found')
    if int(row['tenant_id'])!=tenant_id(request): conn.close(); security_event(request,'COP_TENANT_BOUNDARY_VIOLATION','High',f'decision_request={decision_request_id}'); raise HTTPException(403,'Tenant boundary violation')
    if row['assessment_id'] is not None: assessment_row_for_request(request,int(row['assessment_id']))
    if row['status']!='Awaiting Decision': conn.close(); raise HTTPException(409,'This decision request is no longer awaiting a decision.')
    choices=json.loads(row['allowed_choices_json'])
    if p.decision not in choices: conn.close(); raise HTTPException(422,'Decision must be one of the choices issued by Salus.')
    cents=_money_cents(p.authorized_amount)
    authorized=p.decision in {'Authorize','Authorize with Conditions'} and row['action_type']=='Authorize Resources'
    if cents and not authorized: conn.close(); raise HTTPException(422,'An authorized amount is permitted only with a resource-authorization decision.')
    if p.decision.endswith('with Conditions') and not p.conditions.strip(): conn.close(); raise HTTPException(422,'A conditional decision requires documented conditions.')
    who=actor(request); ts=now(); conn.execute("UPDATE cop_decision_requests SET status='Decision Recorded',decision=?,rationale=?,conditions=?,authorized_amount_cents=?,decided_by=?,decided_by_role=?,decided_at=?,updated_at=? WHERE id=?",(p.decision,p.rationale.strip(),p.conditions.strip(),cents,who,role(request),ts,ts,decision_request_id)); _cop_event(conn,'decision_request',decision_request_id,'Decision Recorded',p.decision,request); audit(conn,'COP_MEMBER_DECISION','decision_request',decision_request_id,f'{p.decision}; authorized_amount_cents={cents}',who); conn.commit(); result=_decision_request_view(conn.execute('SELECT * FROM cop_decision_requests WHERE id=?',(decision_request_id,)).fetchone(),True); conn.close(); return result

@app.post('/api/salcapa/decision-requests/{decision_request_id}/withdraw')
def withdraw_cop_request(decision_request_id:int,p:CopDecisionWithdrawIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalCAPA decision request'); conn=db(); row=conn.execute('SELECT * FROM cop_decision_requests WHERE id=?',(decision_request_id,)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Decision request not found')
    if int(row['tenant_id'])!=tenant_id(request): conn.close(); security_event(request,'COP_TENANT_BOUNDARY_VIOLATION','High',f'decision_request={decision_request_id}'); raise HTTPException(403,'Tenant boundary violation')
    if row['status']!='Awaiting Decision': conn.close(); raise HTTPException(409,'Only a pending decision request can be withdrawn.')
    who=actor(request); ts=now(); conn.execute("UPDATE cop_decision_requests SET status='Withdrawn',withdrawn_by=?,withdrawn_at=?,withdrawal_reason=?,updated_at=? WHERE id=?",(who,ts,p.reason.strip(),ts,decision_request_id)); _cop_event(conn,'decision_request',decision_request_id,'Withdrawn',p.reason,request); audit(conn,'COP_DECISION_REQUEST_WITHDRAW','decision_request',decision_request_id,p.reason,who); conn.commit(); result=_decision_request_view(conn.execute('SELECT * FROM cop_decision_requests WHERE id=?',(decision_request_id,)).fetchone(),False); conn.close(); return result

@app.get('/api/salintel/findings')
def list_intel_findings(request:Request):
    require(request,'read'); conn=db()
    if protected_member_request(request):
        rows=[dict(r) for r in conn.execute("SELECT id,assessment_id,title,relevance,credibility,validation_status,operational_significance,status,qualified_at,updated_at FROM intel_findings WHERE tenant_id=? AND status IN ('Qualified','Sent to SalTHIRA') ORDER BY id DESC",(tenant_id(request),))]
    else: rows=[dict(r) for r in conn.execute('SELECT * FROM intel_findings WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]
    conn.close(); return rows

@app.post('/api/salintel/findings')
def create_intel_finding(p:IntelFindingIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalINTEL'); tid=tenant_id(request); who=actor(request)
    if p.assessment_id is not None: assessment_row_for_request(request,p.assessment_id)
    ts=now(); conn=db(); cur=conn.execute('INSERT INTO intel_findings(tenant_id,assessment_id,title,details,source,source_locator,relevance,credibility,validation_status,operational_significance,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,p.assessment_id,p.title,p.details,p.source,p.source_locator,'Pending','Unrated','Unvalidated','','Collected',who,ts,ts)); fid=cur.lastrowid
    audit(conn,'SALINTEL_COLLECT','intel_finding',fid,f'source={p.source}; title={p.title}',who); conn.commit(); row=dict(conn.execute('SELECT * FROM intel_findings WHERE id=?',(fid,)).fetchone()); conn.close(); return row

@app.post('/api/salintel/findings/{finding_id}/qualify')
def qualify_intel_finding(finding_id:int,p:IntelQualificationIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalINTEL'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute('SELECT * FROM intel_findings WHERE id=? AND tenant_id=?',(finding_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Intelligence finding not found')
    if row['status'] not in ('Collected','Qualified'): conn.close(); raise HTTPException(409,'This intelligence lifecycle state cannot be qualified.')
    status='Qualified' if p.validation_status=='Qualified' and p.relevance!='Not Relevant' else p.validation_status; ts=now()
    conn.execute('UPDATE intel_findings SET relevance=?,credibility=?,validation_status=?,operational_significance=?,status=?,qualified_by=?,qualified_at=?,updated_at=? WHERE id=?',(p.relevance,p.credibility,p.validation_status,p.operational_significance,status,who,ts,ts,finding_id)); audit(conn,'SALINTEL_QUALIFY','intel_finding',finding_id,f'{p.validation_status}; relevance={p.relevance}; credibility={p.credibility}',who); conn.commit(); result=dict(conn.execute('SELECT * FROM intel_findings WHERE id=?',(finding_id,)).fetchone()); conn.close(); return result

@app.post('/api/salintel/findings/{finding_id}/send-to-salthira')
def send_intel_to_salthira(finding_id:int,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalINTEL'); tid=tenant_id(request); who=actor(request); conn=db(); finding=conn.execute('SELECT * FROM intel_findings WHERE id=? AND tenant_id=?',(finding_id,tid)).fetchone()
    if not finding: conn.close(); raise HTTPException(404,'Intelligence finding not found')
    if finding['status']=='Sent to SalTHIRA': conn.close(); raise HTTPException(409,'This finding has already been sent to SalTHIRA.')
    if finding['status']!='Qualified' or not finding['assessment_id']: conn.close(); raise HTTPException(409,'Only qualified intelligence linked to an assessment can be sent to SalTHIRA.')
    assessment_row_for_request(request,finding['assessment_id']); ts=now(); cur=conn.execute("INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(finding['assessment_id'],'SalINTEL','Qualified Intelligence',f"{finding['title']}: {finding['operational_significance']}",'High','intel_finding',finding_id,'Open','','','',ts,ts)); trigger_id=cur.lastrowid
    conn.execute("UPDATE intel_findings SET status='Sent to SalTHIRA',updated_at=? WHERE id=?",(ts,finding_id)); audit(conn,'SALINTEL_TO_SALTHIRA','intel_finding',finding_id,f'reassessment_trigger={trigger_id}',who); audit(conn,'CREATE','reassessment_trigger',trigger_id,f'Created from qualified SalINTEL finding #{finding_id}',who); conn.commit(); conn.close(); return {'finding_id':finding_id,'reassessment_trigger_id':trigger_id,'status':'Sent to SalTHIRA'}

def _observation_time(value:str,label:str):
    text=str(value or '').strip()
    try:
        parsed=datetime.fromisoformat(text.replace('Z','+00:00'))
    except Exception:
        raise HTTPException(422,f'{label} must be a valid ISO 8601 date/time.')
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def _observation_retention():
    return (_iso_now_dt()+timedelta(days=max(1,RETENTION_DEFAULT_DAYS))).replace(microsecond=0).isoformat().replace('+00:00','Z')

def _observation_event(conn,observation_id:int,event_type:str,reason:str,who:str):
    row=conn.execute('SELECT * FROM observations WHERE id=?',(observation_id,)).fetchone()
    if not row: return
    version=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM observation_events WHERE observation_id=?',(observation_id,)).fetchone()['n']
    conn.execute('INSERT INTO observation_events(tenant_id,observation_id,version_no,event_type,reason,snapshot_json,changed_by,created_at) VALUES(?,?,?,?,?,?,?,?)',(row['tenant_id'],observation_id,version,event_type,reason,json.dumps(dict(row),sort_keys=True,default=str),who,now()))

def _observation_internal_view(row):
    result=dict(row); result.pop('receipt_hash',None); return result

def _observation_member_view(row):
    r=dict(row)
    return {k:r.get(k) for k in ('id','record_key','title','observed_at','reported_urgency','status','acknowledged_at','route_target','disposition','created_at','updated_at')}

def _validate_observation_payload(p:ObservationIn):
    if not p.emergency_acknowledged:
        raise HTTPException(422,'Acknowledge that this intake is not an emergency-response channel. Call emergency services for immediate danger.')
    if p.reporter_choice!='Anonymous' and (not p.reporter_name.strip() or not p.reporter_contact.strip()):
        raise HTTPException(422,'Reporter name and contact are required for the selected contact choice.')
    return _observation_time(p.observed_at,'Observed time')

def _create_observation(conn,p:ObservationIn,tenant:int,intake_type:str,who:str,channel_id=None,receipt_hash=''):
    observed=_validate_observation_payload(p); ts=now(); key=f'OBS-{secrets.token_hex(10).upper()}'
    name='' if p.reporter_choice=='Anonymous' else p.reporter_name.strip()
    contact='' if p.reporter_choice=='Anonymous' else p.reporter_contact.strip()
    protection='Salus Restricted' if intake_type=='Public' or p.reporter_choice in {'Confidential Contact','Anonymous'} else 'Member Restricted'
    cur=conn.execute('''INSERT INTO observations(tenant_id,record_key,intake_type,channel_id,receipt_hash,reporter_choice,reporter_name,reporter_contact,report_on_behalf_of,title,narrative,location,observed_at,context,reported_urgency,source_protection,status,retention_until,legal_hold,created_by,created_at,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tenant,key,intake_type,channel_id,receipt_hash,p.reporter_choice,name,contact,p.report_on_behalf_of.strip(),p.title.strip(),p.narrative.strip(),p.location.strip(),observed,p.context.strip(),p.reported_urgency,protection,'Submitted',_observation_retention(),0,who,ts,ts))
    oid=cur.lastrowid; _observation_event(conn,oid,'Submitted','Observation captured as unverified source information.',who)
    audit(conn,'OBSERVATION_SUBMITTED','observation',oid,f'{intake_type}; reported_urgency={p.reported_urgency}; reporter_choice={p.reporter_choice}',who)
    return oid,key

def _active_observation_channel(token:str):
    if len(token)<32 or len(token)>200: raise HTTPException(404,'Public observation channel unavailable')
    conn=db(); row=conn.execute("SELECT * FROM observation_intake_channels WHERE token_hash=? AND status='Active'",(_hash_token(token),)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Public observation channel unavailable')
    try: expired=datetime.fromisoformat(str(row['expires_at']).replace('Z','+00:00'))<=_iso_now_dt()
    except Exception: expired=True
    if expired: conn.close(); raise HTTPException(410,'Public observation channel expired')
    result=dict(row); conn.close(); return result

@app.get('/api/observation-channels')
def list_observation_channels(request:Request):
    require(request,'admin'); conn=db(); rows=[]
    for row in conn.execute('SELECT * FROM observation_intake_channels WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),)):
        item=dict(row); item.pop('token_hash',None); rows.append(item)
    conn.close(); return rows

@app.post('/api/observation-channels')
def create_observation_channel(p:ObservationChannelIn,request:Request):
    require(request,'admin'); expires=_observation_time(p.expires_at,'Channel expiry')
    if datetime.fromisoformat(expires.replace('Z','+00:00'))<=_iso_now_dt(): raise HTTPException(422,'Channel expiry must be in the future.')
    token=secrets.token_urlsafe(36); tid=tenant_id(request); who=actor(request); ts=now(); conn=db()
    cur=conn.execute('INSERT INTO observation_intake_channels(tenant_id,name,token_hash,status,expires_at,created_by,created_at) VALUES(?,?,?,?,?,?,?)',(tid,p.name.strip(),_hash_token(token),'Active',expires,who,ts)); cid=cur.lastrowid
    audit(conn,'OBSERVATION_CHANNEL_CREATED','observation_intake_channel',cid,f'name={p.name.strip()}; expires={expires}',who); conn.commit(); conn.close()
    return {'id':cid,'name':p.name.strip(),'status':'Active','expires_at':expires,'channel_token':token,'notice':'The channel token is shown once. Store and distribute it through an approved protected process.'}

@app.post('/api/observation-channels/{channel_id}/disable')
def disable_observation_channel(channel_id:int,p:ObservationChannelDisableIn,request:Request):
    require(request,'admin'); tid=tenant_id(request); who=actor(request); ts=now(); conn=db(); row=conn.execute("SELECT * FROM observation_intake_channels WHERE id=? AND tenant_id=? AND status='Active'",(channel_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Active observation channel not found')
    conn.execute("UPDATE observation_intake_channels SET status='Disabled',disabled_by=?,disabled_at=?,disable_reason=? WHERE id=?",(who,ts,p.reason,channel_id)); audit(conn,'OBSERVATION_CHANNEL_DISABLED','observation_intake_channel',channel_id,p.reason,who); conn.commit(); conn.close(); return {'id':channel_id,'status':'Disabled'}

@app.post('/api/public/observations')
def public_observation(p:ObservationIn,request:Request):
    channel=_active_observation_channel(request.headers.get('X-Salus-Observation-Channel','')); receipt=secrets.token_urlsafe(32); conn=db()
    oid,key=_create_observation(conn,p,int(channel['tenant_id']),'Public','Public intake',channel['id'],_hash_token(receipt)); conn.commit(); conn.close()
    return {'record_key':key,'status':'Submitted','receipt_token':receipt,'emergency_notice':'This service does not provide emergency response. Call emergency services for immediate danger.','notice':'Submission does not establish that the report is verified intelligence, evidence, a threat finding, or an operational order.'}

@app.post('/api/observations')
def create_observation(p:ObservationIn,request:Request):
    require(request,'write'); tid=tenant_id(request); who=actor(request); conn=db(); oid,key=_create_observation(conn,p,tid,'Authenticated',who); conn.commit(); row=conn.execute('SELECT * FROM observations WHERE id=?',(oid,)).fetchone(); conn.close(); return _observation_member_view(row) if protected_member_request(request) else _observation_internal_view(row)

@app.get('/api/observations')
def list_observations(request:Request):
    require(request,'read'); tid=tenant_id(request); conn=db()
    if protected_member_request(request):
        if role(request)=='Contributor': rows=conn.execute("SELECT * FROM observations WHERE tenant_id=? AND intake_type='Authenticated' AND created_by=? ORDER BY id DESC",(tid,actor(request)))
        else: rows=conn.execute("SELECT * FROM observations WHERE tenant_id=? AND intake_type='Authenticated' ORDER BY id DESC",(tid,))
        result=[_observation_member_view(r) for r in rows]
    elif role(request)=='Auditor': result=[_observation_member_view(r) for r in conn.execute('SELECT * FROM observations WHERE tenant_id=? ORDER BY id DESC',(tid,))]
    else: result=[_observation_internal_view(r) for r in conn.execute('SELECT * FROM observations WHERE tenant_id=? ORDER BY id DESC',(tid,))]
    conn.close(); return result

def _observation_for_request(conn,observation_id:int,request:Request,internal=False):
    row=conn.execute('SELECT * FROM observations WHERE id=?',(observation_id,)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Observation not found')
    if int(row['tenant_id'])!=tenant_id(request):
        conn.close(); security_event(request,'OBSERVATION_TENANT_BOUNDARY_VIOLATION','High',f'observation_id={observation_id}'); raise HTTPException(403,'Tenant boundary violation')
    if protected_member_request(request):
        if internal or row['intake_type']!='Authenticated' or (role(request)=='Contributor' and row['created_by']!=actor(request)): conn.close(); raise HTTPException(403,'Observation access denied')
    return row

def _require_observation_authority(request:Request):
    require(request,'write'); require_salus_component_authority(request,'Observation triage')

@app.post('/api/observations/{observation_id}/acknowledge')
def acknowledge_observation(observation_id:int,p:ObservationAcknowledgeIn,request:Request):
    _require_observation_authority(request); conn=db(); row=_observation_for_request(conn,observation_id,request,True)
    if row['status']!='Submitted': conn.close(); raise HTTPException(409,'Only Submitted observations can be acknowledged.')
    who=actor(request); ts=now(); conn.execute("UPDATE observations SET status='Acknowledged',acknowledged_by=?,acknowledged_at=?,acknowledgement_reason=?,updated_at=? WHERE id=?",(who,ts,p.reason,ts,observation_id)); _observation_event(conn,observation_id,'Acknowledged',p.reason,who); audit(conn,'OBSERVATION_ACKNOWLEDGED','observation',observation_id,p.reason,who); conn.commit(); result=_observation_internal_view(conn.execute('SELECT * FROM observations WHERE id=?',(observation_id,)).fetchone()); conn.close(); return result

@app.post('/api/observations/{observation_id}/triage')
def triage_observation(observation_id:int,p:ObservationTriageIn,request:Request):
    _require_observation_authority(request); conn=db(); row=_observation_for_request(conn,observation_id,request,True)
    if row['status']!='Acknowledged': conn.close(); raise HTTPException(409,'Only Acknowledged observations can be triaged.')
    who=actor(request); ts=now(); conn.execute("UPDATE observations SET status='Triaged',triage_category=?,triage_priority=?,triage_notes=?,assigned_to=?,triaged_by=?,triaged_at=?,updated_at=? WHERE id=?",(p.category,p.priority,p.notes,p.assigned_to,who,ts,ts,observation_id)); _observation_event(conn,observation_id,'Triaged',p.notes,who); audit(conn,'OBSERVATION_TRIAGED','observation',observation_id,f'{p.category}; priority={p.priority}; assigned={p.assigned_to}',who); conn.commit(); result=_observation_internal_view(conn.execute('SELECT * FROM observations WHERE id=?',(observation_id,)).fetchone()); conn.close(); return result

@app.post('/api/observations/{observation_id}/route')
def route_observation(observation_id:int,p:ObservationRouteIn,request:Request):
    _require_observation_authority(request); tid=tenant_id(request); who=actor(request); conn=db(); row=_observation_for_request(conn,observation_id,request,True)
    if row['status']!='Triaged': conn.close(); raise HTTPException(409,'Only Triaged observations can be routed.')
    assessment_id=p.assessment_id
    if p.target in {'SalTHIRA','SalOPS'} and not assessment_id: conn.close(); raise HTTPException(422,f'{p.target} routing requires an assessment.')
    if assessment_id: assessment_row_for_request(request,assessment_id)
    ts=now(); routed_type=''; routed_id=None
    if p.target=='SalINTEL':
        cur=conn.execute('INSERT INTO intel_findings(tenant_id,assessment_id,title,details,source,source_locator,relevance,credibility,validation_status,operational_significance,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,assessment_id,row['title'],f"{row['narrative']}\n\nContext: {row['context']}\nLocation: {row['location']}",'Observation',row['record_key'],'Pending','Unrated','Unvalidated','','Collected',who,ts,ts)); routed_type='intel_finding'; routed_id=cur.lastrowid; audit(conn,'SALINTEL_COLLECT','intel_finding',routed_id,f'Created by authorized routing of {row["record_key"]}',who)
    elif p.target=='SalTHIRA':
        cur=conn.execute('INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(assessment_id,'Observation','Observation Requiring Assessment',p.member_summary,row['triage_priority'],'observation',observation_id,'Open','','','',ts,ts)); routed_type='reassessment_trigger'; routed_id=cur.lastrowid; audit(conn,'CREATE','reassessment_trigger',routed_id,f'Created by authorized routing of {row["record_key"]}',who)
    elif p.target=='SalOPS':
        cur=conn.execute('INSERT INTO ops_requests(tenant_id,assessment_id,source_type,source_id,title,description,priority,status,requested_by,requested_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,assessment_id,'Observation',observation_id,p.member_summary,f"Authorized observation routing: {row['narrative']}",row['triage_priority'],'Requested',who,ts,ts)); routed_type='ops_request'; routed_id=cur.lastrowid; audit(conn,'SALOPS_REQUEST','ops_request',routed_id,f'Created by authorized routing of {row["record_key"]}',who)
    else:
        if not p.external_reference.strip(): conn.close(); raise HTTPException(422,'A recorded external reference is required. SalCAPA does not transmit the observation.')
        routed_type='external_reference'
    conn.execute("UPDATE observations SET status='Routed',route_target=?,routed_record_type=?,routed_record_id=?,route_reason=?,disposition=?,routed_by=?,routed_at=?,updated_at=? WHERE id=?",(p.target,routed_type,routed_id,p.reason,p.external_reference.strip() if p.target=='External Escalation' else p.member_summary,who,ts,ts,observation_id)); _observation_event(conn,observation_id,'Routed',p.reason,who); audit(conn,'OBSERVATION_ROUTED','observation',observation_id,f'target={p.target}; linked={routed_type}:{routed_id or "recorded"}',who); conn.commit(); result=_observation_internal_view(conn.execute('SELECT * FROM observations WHERE id=?',(observation_id,)).fetchone()); conn.close(); return result

@app.post('/api/observations/{observation_id}/close')
def close_observation(observation_id:int,p:ObservationCloseIn,request:Request):
    _require_observation_authority(request); conn=db(); row=_observation_for_request(conn,observation_id,request,True)
    if row['status'] not in {'Triaged','Routed'}: conn.close(); raise HTTPException(409,'Only Triaged or Routed observations can be closed.')
    who=actor(request); ts=now(); conn.execute("UPDATE observations SET status='Closed',disposition=?,closed_by=?,closed_at=?,updated_at=? WHERE id=?",(p.disposition,who,ts,ts,observation_id)); _observation_event(conn,observation_id,'Closed',p.reason,who); audit(conn,'OBSERVATION_CLOSED','observation',observation_id,f'{p.disposition}: {p.reason}',who); conn.commit(); result=_observation_internal_view(conn.execute('SELECT * FROM observations WHERE id=?',(observation_id,)).fetchone()); conn.close(); return result

@app.get('/api/observations/{observation_id}/history')
def observation_history(observation_id:int,request:Request):
    require(request,'read'); require_salus_component_authority(request,'Observation history'); conn=db(); _observation_for_request(conn,observation_id,request,True); rows=[dict(r) for r in conn.execute('SELECT id,observation_id,version_no,event_type,reason,changed_by,created_at FROM observation_events WHERE observation_id=? AND tenant_id=? ORDER BY version_no DESC',(observation_id,tenant_id(request)))]; conn.close(); return rows

@app.patch('/api/observations/{observation_id}/governance')
def observation_governance(observation_id:int,p:AttachmentGovernanceIn,request:Request):
    require(request,'decide'); require_salus_component_authority(request,'Observation governance'); conn=db(); row=_observation_for_request(conn,observation_id,request,True); changes={}
    if p.retention_until is not None: changes['retention_until']=_observation_time(p.retention_until,'Retention date')
    if p.legal_hold is not None: changes['legal_hold']=1 if p.legal_hold else 0
    if not changes: conn.close(); return _observation_internal_view(row)
    sets=','.join(f'{k}=?' for k in changes); conn.execute(f'UPDATE observations SET {sets},updated_at=? WHERE id=?',tuple(changes.values())+(now(),observation_id)); conn.execute(f'UPDATE observation_attachments SET {sets} WHERE observation_id=?',tuple(changes.values())+(observation_id,)); who=actor(request); _observation_event(conn,observation_id,'Governance Updated',json.dumps(changes,sort_keys=True),who); audit(conn,'OBSERVATION_GOVERNANCE','observation',observation_id,json.dumps(changes,sort_keys=True),who); conn.commit(); result=_observation_internal_view(conn.execute('SELECT * FROM observations WHERE id=?',(observation_id,)).fetchone()); conn.close(); return result

async def _store_observation_attachment(conn,row,file:UploadFile,uploader:str,request:Request):
    if row['status'] in {'Triaged','Routed','Closed'}: raise HTTPException(409,'Attachments cannot be added after triage begins.')
    content=await file.read(MAX_ATTACHMENT_BYTES+1)
    if len(content)>MAX_ATTACHMENT_BYTES: raise HTTPException(413,'Attachment exceeds 25 MB limit')
    original=safe_filename(file.filename or 'attachment'); scan=scan_bytes(content,original)
    if not scan['ok']:
        security_event(request,'OBSERVATION_UPLOAD_REJECTED','High' if scan['status']=='Infected' else 'Medium',f'{original}: {scan["status"]}'); raise HTTPException(422 if scan['status']=='Infected' else 503,f'Upload rejected: {scan["status"]}')
    digest=hashlib.sha256(content).hexdigest(); stored=f'tenant-{row["tenant_id"]}/observation-{row["id"]}/{digest[:16]}_{original}'
    try: storage.put_bytes(stored,content)
    except Exception as exc: security_event(request,'STORAGE_WRITE_FAILURE','High',type(exc).__name__,tenant=int(row['tenant_id']),user_name=uploader); raise HTTPException(503,'Observation storage unavailable')
    cur=conn.execute('INSERT INTO observation_attachments(tenant_id,observation_id,original_name,stored_name,content_type,size_bytes,sha256,uploaded_by,scan_status,scan_detail,scanned_at,retention_until,legal_hold,disposition_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(row['tenant_id'],row['id'],original,stored,file.content_type or 'application/octet-stream',len(content),digest,uploader,scan['status'],scan['detail'][:1000],now(),row['retention_until'],row['legal_hold'],'Active',now())); audit(conn,'OBSERVATION_ATTACHMENT_ADDED','observation_attachment',cur.lastrowid,f'observation={row["record_key"]}; file={original}; sha256={digest}',uploader); return cur.lastrowid

@app.post('/api/observations/{observation_id}/attachments')
async def upload_observation_attachment(observation_id:int,request:Request,file:UploadFile=File(...)):
    require(request,'write'); conn=db(); row=_observation_for_request(conn,observation_id,request,False); aid=await _store_observation_attachment(conn,row,file,actor(request),request); conn.commit(); result=dict(conn.execute('SELECT * FROM observation_attachments WHERE id=?',(aid,)).fetchone()); conn.close(); result.pop('stored_name',None); result.pop('scan_detail',None); return result

@app.post('/api/public/observations/{record_key}/attachments')
async def upload_public_observation_attachment(record_key:str,request:Request,file:UploadFile=File(...)):
    channel=_active_observation_channel(request.headers.get('X-Salus-Observation-Channel','')); receipt=request.headers.get('X-Salus-Observation-Receipt',''); conn=db(); row=conn.execute("SELECT * FROM observations WHERE record_key=? AND tenant_id=? AND channel_id=? AND intake_type='Public' AND receipt_hash=?",(record_key,channel['tenant_id'],channel['id'],_hash_token(receipt))).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Public observation receipt not found')
    aid=await _store_observation_attachment(conn,row,file,'Public intake',request); conn.commit(); result=dict(conn.execute('SELECT * FROM observation_attachments WHERE id=?',(aid,)).fetchone()); conn.close(); return {k:result[k] for k in ('id','observation_id','original_name','size_bytes','sha256','scan_status','created_at')}

@app.get('/api/observations/{observation_id}/attachments')
def list_observation_attachments(observation_id:int,request:Request):
    require(request,'read');
    if role(request)=='Auditor': raise HTTPException(403,'Observation source attachments are restricted to authorized operational personnel.')
    conn=db(); row=_observation_for_request(conn,observation_id,request,False)
    if protected_member_request(request) and row['created_by']!=actor(request): conn.close(); raise HTTPException(403,'Observation attachments are available only to the submitter and authorized Salus personnel.')
    result=[]
    for item in conn.execute('SELECT * FROM observation_attachments WHERE observation_id=? AND tenant_id=? ORDER BY id',(observation_id,tenant_id(request))):
        value=dict(item); value.pop('stored_name',None); value.pop('scan_detail',None); result.append(value)
    conn.close(); return result

@app.get('/api/observation-attachments/{attachment_id}/download')
def download_observation_attachment(attachment_id:int,request:Request):
    require(request,'read');
    if role(request)=='Auditor': raise HTTPException(403,'Observation source attachments are restricted to authorized operational personnel.')
    conn=db(); item=conn.execute('SELECT * FROM observation_attachments WHERE id=? AND tenant_id=?',(attachment_id,tenant_id(request))).fetchone()
    if not item: conn.close(); raise HTTPException(404,'Observation attachment not found')
    row=_observation_for_request(conn,item['observation_id'],request,False)
    if protected_member_request(request) and row['created_by']!=actor(request): conn.close(); raise HTTPException(403,'Observation attachment access denied')
    conn.close()
    try: data=storage.get_bytes(item['stored_name'])
    except FileNotFoundError: raise HTTPException(404,'Stored attachment missing')
    except Exception as exc: security_event(request,'STORAGE_READ_FAILURE','High',type(exc).__name__); raise HTTPException(503,'Observation storage unavailable')
    if hashlib.sha256(data).hexdigest()!=item['sha256']: security_event(request,'OBSERVATION_ATTACHMENT_HASH_MISMATCH','Critical',f'attachment_id={attachment_id}'); raise HTTPException(409,'Observation attachment integrity verification failed')
    conn=db(); audit(conn,'OBSERVATION_ATTACHMENT_DOWNLOADED','observation_attachment',attachment_id,'Hash verified before download',actor(request)); conn.commit(); conn.close(); return Response(content=data,media_type=item['content_type'],headers={'Content-Disposition':f'attachment; filename="{safe_filename(item["original_name"])}"','X-Content-SHA256':item['sha256']})

def _industry_profile_record(request:Request,profile_id:int):
    conn=db(); row=conn.execute('SELECT * FROM industry_profiles WHERE id=?',(profile_id,)).fetchone(); conn.close()
    if not row: raise HTTPException(404,'Industry profile not found')
    if int(row['tenant_id'])!=tenant_id(request):
        security_event(request,'INDUSTRY_PROFILE_TENANT_BOUNDARY_VIOLATION','High',f'profile_id={profile_id}')
        raise HTTPException(403,'Industry profile tenant boundary violation')
    return dict(row)

def _industry_items(conn,profile_id:int):
    return [dict(r) for r in conn.execute('SELECT * FROM industry_profile_items WHERE profile_id=? ORDER BY item_type,sort_order,id',(profile_id,))]

def _industry_defaults(items):
    values=[]
    for item in items:
        if item['item_type']!='Service Default': continue
        try: payload=json.loads(item.get('default_payload_json') or '{}')
        except Exception: payload={}
        values.append({'item_key':item['item_key'],'member_label':item['member_label'],'payload':payload})
    return json.dumps(values,sort_keys=True,separators=(',',':'),default=str)

def _member_assessment_view(row):
    item=dict(row)
    for field in ('industry_defaults_snapshot_json','industry_profile_applied_by'):
        item.pop(field,None)
    return item

def _industry_event(conn,row,event_type:str,summary:str,request:Request):
    version=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM industry_profile_events WHERE tenant_id=? AND profile_id=?',(row['tenant_id'],row['id'])).fetchone()['n']
    snapshot={'profile':dict(row),'items':_industry_items(conn,row['id'])}
    conn.execute('INSERT INTO industry_profile_events(tenant_id,profile_id,version_no,event_type,summary,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(row['tenant_id'],row['id'],version,event_type,summary,json.dumps(snapshot,sort_keys=True,separators=(',',':'),default=str),actor(request),role(request),now()))

def _industry_profile_view(conn,row,member:bool):
    profile=dict(row); items=_industry_items(conn,row['id'])
    if member:
        profile={k:profile[k] for k in ('id','profile_key','version_no','industry_code','name','member_summary','status','published_at')}
        profile['items']=[{k:item[k] for k in ('id','item_type','item_key','member_label','member_guidance','sort_order')} for item in items if item['member_visible']]
    else:
        for item in items:
            try: item['default_payload']=json.loads(item.pop('default_payload_json') or '{}')
            except Exception: item['default_payload']={}
        profile['items']=items
    return profile

def _validate_industry_items(items):
    seen=set()
    for item in items:
        key=(item.item_type,item.item_key.lower())
        if key in seen: raise HTTPException(422,f'Duplicate industry profile item: {item.item_type} / {item.item_key}')
        seen.add(key)
        encoded=json.dumps(item.default_payload,sort_keys=True,separators=(',',':'),default=str)
        if len(encoded)>20000: raise HTTPException(422,f'Default payload for {item.item_key} exceeds the governed size limit.')

def _insert_industry_profile(conn,p:IndustryProfileIn,request:Request,profile_key:str,version_no:int,supersedes_id=None):
    _validate_industry_items(p.items); tid=tenant_id(request); who=actor(request); ts=now()
    cur=conn.execute('''INSERT INTO industry_profiles(tenant_id,profile_key,version_no,supersedes_id,industry_code,name,member_summary,internal_rationale,status,created_by,created_at,last_material_editor,last_material_edit_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,profile_key,version_no,supersedes_id,p.industry_code,p.name.strip(),p.member_summary.strip(),p.internal_rationale.strip(),'Draft',who,ts,who,ts,ts)); profile_id=cur.lastrowid
    for item in p.items:
        conn.execute('''INSERT INTO industry_profile_items(tenant_id,profile_id,item_type,item_key,member_label,member_guidance,internal_definition,reference_metadata,default_payload_json,member_visible,sort_order,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,profile_id,item.item_type,item.item_key,item.member_label.strip(),item.member_guidance.strip(),item.internal_definition.strip(),item.reference_metadata.strip(),json.dumps(item.default_payload,sort_keys=True,separators=(',',':'),default=str),1 if item.member_visible else 0,item.sort_order,who,ts))
    row=conn.execute('SELECT * FROM industry_profiles WHERE id=?',(profile_id,)).fetchone(); _industry_event(conn,row,'Draft Created',f'profile_key={profile_key}; version={version_no}',request); audit(conn,'INDUSTRY_PROFILE_DRAFT','industry_profile',profile_id,f'profile_key={profile_key}; version={version_no}',who); return profile_id

@app.get('/api/industry-profiles')
def list_industry_profiles(request:Request):
    require(request,'read'); tid=tenant_id(request); member=protected_member_request(request); conn=db()
    if member:
        rows=conn.execute("SELECT p.* FROM industry_profiles p JOIN tenant_industry_configurations c ON c.profile_id=p.id AND c.tenant_id=p.tenant_id WHERE p.tenant_id=? AND c.status='Active' ORDER BY p.industry_code,p.name",(tid,))
    else: rows=conn.execute('SELECT * FROM industry_profiles WHERE tenant_id=? ORDER BY industry_code,profile_key,version_no DESC',(tid,))
    result=[_industry_profile_view(conn,row,member) for row in rows]; conn.close(); return result

@app.get('/api/industry-profiles/{profile_id}/history')
def industry_profile_history(profile_id:int,request:Request):
    require(request,'read'); require_salus_component_authority(request,'Industry profile history'); _industry_profile_record(request,profile_id); conn=db(); result=[dict(r) for r in conn.execute('SELECT id,profile_id,version_no,event_type,summary,changed_by,changed_by_role,created_at FROM industry_profile_events WHERE tenant_id=? AND profile_id=? ORDER BY version_no',(tenant_id(request),profile_id))]; conn.close(); return result

@app.post('/api/industry-profiles')
def create_industry_profile(p:IndustryProfileIn,request:Request):
    require(request,'write'); require_ops_authority(request); conn=db(); key=f'IND-{uuid.uuid4().hex[:12].upper()}'; profile_id=_insert_industry_profile(conn,p,request,key,1); conn.commit(); row=conn.execute('SELECT * FROM industry_profiles WHERE id=?',(profile_id,)).fetchone(); result=_industry_profile_view(conn,row,False); conn.close(); return result

@app.post('/api/industry-profiles/{profile_id}/revise')
def revise_industry_profile(profile_id:int,p:IndustryProfileIn,request:Request):
    require(request,'write'); require_ops_authority(request); source=_industry_profile_record(request,profile_id)
    if source['status'] not in {'Published','Retired','Superseded'}: raise HTTPException(409,'Only a published or terminal industry profile version can be revised.')
    conn=db(); existing=conn.execute("SELECT id FROM industry_profiles WHERE tenant_id=? AND profile_key=? AND status IN ('Draft','In Review','Reviewed','Approved')",(tenant_id(request),source['profile_key'])).fetchone()
    if existing: conn.close(); raise HTTPException(409,'This industry profile already has an unreleased revision.')
    version=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM industry_profiles WHERE tenant_id=? AND profile_key=?',(tenant_id(request),source['profile_key'])).fetchone()['n']; new_id=_insert_industry_profile(conn,p,request,source['profile_key'],version,profile_id); conn.commit(); row=conn.execute('SELECT * FROM industry_profiles WHERE id=?',(new_id,)).fetchone(); result=_industry_profile_view(conn,row,False); conn.close(); return result

@app.post('/api/industry-profiles/{profile_id}/transition')
def transition_industry_profile(profile_id:int,p:IndustryProfileTransitionIn,request:Request):
    require(request,'write'); require_ops_authority(request); source=_industry_profile_record(request,profile_id); who=actor(request); ts=now(); conn=db(); updates={}
    if p.action=='Submit':
        if source['status']!='Draft': conn.close(); raise HTTPException(409,'Only a Draft profile can be submitted.')
        target='In Review'; updates={'submitted_by':who,'submitted_at':ts}
    elif p.action=='Review':
        if source['status']!='In Review': conn.close(); raise HTTPException(409,'Only an In Review profile can be reviewed.')
        if who==source['last_material_editor']: conn.close(); raise HTTPException(409,'The material editor cannot review this profile version.')
        target='Reviewed'; updates={'reviewed_by':who,'reviewed_at':ts,'review_reason':p.reason.strip()}
    elif p.action=='Approve':
        if source['status']!='Reviewed': conn.close(); raise HTTPException(409,'Only a Reviewed profile can be approved.')
        if who in {source['last_material_editor'],source['reviewed_by']}: conn.close(); raise HTTPException(409,'Approval requires authority independent from the material editor and reviewer.')
        target='Approved'; updates={'approved_by':who,'approved_at':ts,'approval_reason':p.reason.strip()}
    elif p.action=='Publish':
        if source['status']!='Approved': conn.close(); raise HTTPException(409,'Only an Approved profile can be published.')
        if who==source['last_material_editor']: conn.close(); raise HTTPException(409,'The material editor cannot publish this profile version.')
        previous=conn.execute("SELECT * FROM industry_profiles WHERE tenant_id=? AND profile_key=? AND status='Published' AND id<>?",(source['tenant_id'],source['profile_key'],profile_id)).fetchone()
        if previous:
            conn.execute("UPDATE industry_profiles SET status='Superseded',updated_at=? WHERE id=?",(ts,previous['id'])); replaced=conn.execute('SELECT * FROM industry_profiles WHERE id=?',(previous['id'],)).fetchone(); _industry_event(conn,replaced,'Superseded',f'Superseded by profile version #{profile_id}',request)
        target='Published'; updates={'published_by':who,'published_at':ts,'publish_reason':p.reason.strip()}
    else:
        if source['status']!='Published': conn.close(); raise HTTPException(409,'Only a Published profile can be retired.')
        if who==source['last_material_editor']: conn.close(); raise HTTPException(409,'The material editor cannot retire this profile version.')
        target='Retired'; updates={'retired_by':who,'retired_at':ts,'retirement_reason':p.reason.strip()}
    updates.update({'status':target,'updated_at':ts}); conn.execute('UPDATE industry_profiles SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',tuple(updates.values())+(profile_id,)); row=conn.execute('SELECT * FROM industry_profiles WHERE id=?',(profile_id,)).fetchone(); _industry_event(conn,row,target,p.reason.strip(),request); audit(conn,'INDUSTRY_PROFILE_TRANSITION','industry_profile',profile_id,f'{source["status"]} -> {target}: {p.reason}',who); conn.commit(); result=_industry_profile_view(conn,row,False); conn.close(); return result

@app.get('/api/industry-configurations')
def list_industry_configurations(request:Request):
    require(request,'read'); member=protected_member_request(request); conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM tenant_industry_configurations WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]; conn.close()
    if member: return [{k:r[k] for k in ('id','profile_id','profile_key_snapshot','profile_version_snapshot','profile_name_snapshot','industry_code_snapshot','member_summary_snapshot','status','selected_at')} for r in rows if r['status']=='Active']
    for row in rows:
        try: row['defaults_snapshot']=json.loads(row.pop('defaults_snapshot_json') or '[]')
        except Exception: row['defaults_snapshot']=[]
    return rows

@app.post('/api/industry-configurations')
def select_industry_configuration(p:IndustryConfigurationIn,request:Request):
    require(request,'write'); require_ops_authority(request); profile=_industry_profile_record(request,p.profile_id)
    if profile['status']!='Published': raise HTTPException(409,'Only a published industry profile may be selected for a tenant.')
    conn=db(); items=_industry_items(conn,p.profile_id); defaults=_industry_defaults(items); who=actor(request); ts=now(); existing=conn.execute('SELECT id,status FROM tenant_industry_configurations WHERE tenant_id=? AND profile_id=?',(tenant_id(request),p.profile_id)).fetchone()
    conn.execute("UPDATE tenant_industry_configurations SET status='Inactive',deactivated_by=?,deactivated_at=?,deactivation_reason='Replaced by a newly selected profile version' WHERE tenant_id=? AND profile_key_snapshot=? AND status='Active'",(who,ts,tenant_id(request),profile['profile_key']))
    if existing: conn.execute("UPDATE tenant_industry_configurations SET profile_key_snapshot=?,profile_version_snapshot=?,profile_name_snapshot=?,industry_code_snapshot=?,member_summary_snapshot=?,defaults_snapshot_json=?,status='Active',selected_by=?,selected_at=?,deactivated_by='',deactivated_at='',deactivation_reason='' WHERE id=?",(profile['profile_key'],profile['version_no'],profile['name'],profile['industry_code'],profile['member_summary'],defaults,who,ts,existing['id'])); config_id=existing['id']
    else:
        cur=conn.execute("INSERT INTO tenant_industry_configurations(tenant_id,profile_id,profile_key_snapshot,profile_version_snapshot,profile_name_snapshot,industry_code_snapshot,member_summary_snapshot,defaults_snapshot_json,status,selected_by,selected_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(tenant_id(request),p.profile_id,profile['profile_key'],profile['version_no'],profile['name'],profile['industry_code'],profile['member_summary'],defaults,'Active',who,ts)); config_id=cur.lastrowid
    audit(conn,'INDUSTRY_PROFILE_SELECTED','tenant_industry_configuration',config_id,f'profile={profile["profile_key"]}; version={profile["version_no"]}',who); conn.commit(); result=dict(conn.execute('SELECT * FROM tenant_industry_configurations WHERE id=?',(config_id,)).fetchone()); conn.close(); return result

@app.post('/api/industry-configurations/{configuration_id}/deactivate')
def deactivate_industry_configuration(configuration_id:int,p:IndustryConfigurationDeactivateIn,request:Request):
    require(request,'write'); require_ops_authority(request); tid=tenant_id(request); conn=db(); row=conn.execute('SELECT * FROM tenant_industry_configurations WHERE id=?',(configuration_id,)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Industry configuration not found')
    if int(row['tenant_id'])!=tid: conn.close(); security_event(request,'INDUSTRY_CONFIGURATION_TENANT_BOUNDARY_VIOLATION','High',f'configuration_id={configuration_id}'); raise HTTPException(403,'Industry configuration tenant boundary violation')
    if row['status']!='Active': conn.close(); raise HTTPException(409,'Industry configuration is already inactive.')
    who=actor(request); ts=now(); conn.execute("UPDATE tenant_industry_configurations SET status='Inactive',deactivated_by=?,deactivated_at=?,deactivation_reason=? WHERE id=?",(who,ts,p.reason.strip(),configuration_id)); audit(conn,'INDUSTRY_PROFILE_DEACTIVATED','tenant_industry_configuration',configuration_id,p.reason.strip(),who); conn.commit(); result=dict(conn.execute('SELECT * FROM tenant_industry_configurations WHERE id=?',(configuration_id,)).fetchone()); conn.close(); return result

def _selected_industry_profile(request:Request,profile_id:int):
    profile=_industry_profile_record(request,profile_id); conn=db(); config=conn.execute("SELECT * FROM tenant_industry_configurations WHERE tenant_id=? AND profile_id=? AND status='Active'",(tenant_id(request),profile_id)).fetchone(); items=_industry_items(conn,profile_id); conn.close()
    if not config: raise HTTPException(409,'The industry profile must be actively selected for this tenant before it can be applied.')
    if profile['status'] not in {'Published','Superseded'}: raise HTTPException(409,'Only a selected published profile version can be applied.')
    return profile,dict(config),items

def _ops_catalog_record(request:Request,service_id:int):
    conn=db(); row=conn.execute('SELECT * FROM ops_service_catalog WHERE id=?',(service_id,)).fetchone(); conn.close()
    if not row: raise HTTPException(404,'SalOPS service not found')
    if int(row['tenant_id'])!=tenant_id(request):
        security_event(request,'SALOPS_CATALOG_TENANT_BOUNDARY_VIOLATION','High',f'service_id={service_id}')
        raise HTTPException(403,'SalOPS service tenant boundary violation')
    return dict(row)

def _ops_catalog_event(conn,row,event_type:str,summary:str,request:Request):
    version=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM ops_catalog_events WHERE tenant_id=? AND service_id=?',(row['tenant_id'],row['id'])).fetchone()['n']
    snapshot=json.dumps(dict(row),sort_keys=True,separators=(',',':'),default=str)
    conn.execute('INSERT INTO ops_catalog_events(tenant_id,service_id,version_no,event_type,summary,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(row['tenant_id'],row['id'],version,event_type,summary,snapshot,actor(request),role(request),now()))

def _ops_catalog_view(conn,row,member:bool):
    item=dict(row); pillar=conn.execute('SELECT pillar_code,name,description FROM ops_service_pillars WHERE id=?',(item['pillar_id'],)).fetchone()
    item['pillar_code']=pillar['pillar_code']; item['pillar_name']=pillar['name']; item['pillar_description']=pillar['description']
    if member:
        allowed={'id','service_key','version_no','name','member_description','default_deliverables','authorization_requirements','status','published_at','pillar_code','pillar_name','pillar_description','industry_profile_id','industry_profile_key_snapshot','industry_profile_version_snapshot','industry_profile_name_snapshot'}
        item={key:value for key,value in item.items() if key in allowed}
    return item

@app.get('/api/salops/catalog/pillars')
def list_ops_service_pillars(request:Request):
    require(request,'read'); conn=db(); rows=[dict(r) for r in conn.execute("SELECT id,pillar_code,name,description,sort_order,status FROM ops_service_pillars WHERE tenant_id=? AND status='Active' ORDER BY sort_order",(tenant_id(request),))]; conn.close(); return rows

@app.get('/api/salops/catalog/services')
def list_ops_catalog_services(request:Request):
    require(request,'read'); tid=tenant_id(request); member=protected_member_request(request); conn=db()
    if member: rows=conn.execute("SELECT * FROM ops_service_catalog WHERE tenant_id=? AND status='Published' AND member_visible=1 ORDER BY pillar_id,name,version_no DESC",(tid,))
    else: rows=conn.execute('SELECT * FROM ops_service_catalog WHERE tenant_id=? ORDER BY pillar_id,service_key,version_no DESC',(tid,))
    result=[_ops_catalog_view(conn,row,member) for row in rows]; conn.close(); return result

@app.get('/api/salops/catalog/services/{service_id}/history')
def ops_catalog_history(service_id:int,request:Request):
    require(request,'read'); require_salus_component_authority(request,'SalOPS catalog history'); _ops_catalog_record(request,service_id); conn=db(); rows=[dict(r) for r in conn.execute('SELECT id,service_id,version_no,event_type,summary,changed_by,changed_by_role,created_at FROM ops_catalog_events WHERE tenant_id=? AND service_id=? ORDER BY version_no',(tenant_id(request),service_id))]; conn.close(); return rows

def _ops_pillar(conn,tid:int,code:str):
    row=conn.execute("SELECT * FROM ops_service_pillars WHERE tenant_id=? AND pillar_code=? AND status='Active'",(tid,code)).fetchone()
    if not row: raise HTTPException(422,'Active SalOPS service pillar not found')
    return row

def _insert_ops_service(conn,p:OpsCatalogServiceIn,request:Request,service_key:str,version_no:int,supersedes_id=None):
    tid=tenant_id(request); who=actor(request); ts=now(); pillar=_ops_pillar(conn,tid,p.pillar_code)
    profile=None; defaults='{}'
    if p.industry_profile_id is not None:
        profile,_,items=_selected_industry_profile(request,p.industry_profile_id); defaults=_industry_defaults(items)
    cur=conn.execute('''INSERT INTO ops_service_catalog(tenant_id,pillar_id,service_key,version_no,supersedes_id,name,member_description,internal_scope,default_deliverables,readiness_inputs,authorization_requirements,industry_profile_id,industry_profile_key_snapshot,industry_profile_version_snapshot,industry_profile_name_snapshot,industry_defaults_snapshot_json,member_visible,status,created_by,created_at,last_material_editor,last_material_edit_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,pillar['id'],service_key,version_no,supersedes_id,p.name.strip(),p.member_description.strip(),p.internal_scope.strip(),p.default_deliverables.strip(),p.readiness_inputs.strip(),p.authorization_requirements.strip(),profile['id'] if profile else None,profile['profile_key'] if profile else '',profile['version_no'] if profile else None,profile['name'] if profile else '',defaults,1 if p.member_visible else 0,'Draft',who,ts,who,ts,ts)); sid=cur.lastrowid
    row=conn.execute('SELECT * FROM ops_service_catalog WHERE id=?',(sid,)).fetchone(); _ops_catalog_event(conn,row,'Draft Created',f'service_key={service_key}; version={version_no}',request); audit(conn,'SALOPS_CATALOG_DRAFT','ops_service_catalog',sid,f'service_key={service_key}; version={version_no}',who); return sid

@app.post('/api/salops/catalog/services')
def create_ops_catalog_service(p:OpsCatalogServiceIn,request:Request):
    require(request,'write'); require_ops_authority(request); conn=db(); key=f'SVC-{uuid.uuid4().hex[:12].upper()}'; sid=_insert_ops_service(conn,p,request,key,1); conn.commit(); row=conn.execute('SELECT * FROM ops_service_catalog WHERE id=?',(sid,)).fetchone(); result=_ops_catalog_view(conn,row,False); conn.close(); return result

@app.post('/api/salops/catalog/services/{service_id}/revise')
def revise_ops_catalog_service(service_id:int,p:OpsCatalogServiceIn,request:Request):
    require(request,'write'); require_ops_authority(request); source=_ops_catalog_record(request,service_id)
    if source['status'] not in {'Published','Retired','Superseded'}: raise HTTPException(409,'Only a published or terminal service version can be revised.')
    conn=db(); existing=conn.execute("SELECT id FROM ops_service_catalog WHERE tenant_id=? AND service_key=? AND status IN ('Draft','In Review','Reviewed','Approved')",(tenant_id(request),source['service_key'])).fetchone()
    if existing: conn.close(); raise HTTPException(409,'This service already has an unreleased revision.')
    next_version=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM ops_service_catalog WHERE tenant_id=? AND service_key=?',(tenant_id(request),source['service_key'])).fetchone()['n']; sid=_insert_ops_service(conn,p,request,source['service_key'],next_version,service_id); conn.commit(); row=conn.execute('SELECT * FROM ops_service_catalog WHERE id=?',(sid,)).fetchone(); result=_ops_catalog_view(conn,row,False); conn.close(); return result

@app.post('/api/salops/catalog/services/{service_id}/transition')
def transition_ops_catalog_service(service_id:int,p:OpsCatalogTransitionIn,request:Request):
    require(request,'write'); require_ops_authority(request); source=_ops_catalog_record(request,service_id); who=actor(request); ts=now(); conn=db(); updates={}; target=''
    if p.action=='Submit':
        if source['status']!='Draft': conn.close(); raise HTTPException(409,'Only a Draft service can be submitted.')
        target='In Review'; updates={'submitted_by':who,'submitted_at':ts}
    elif p.action=='Review':
        if source['status']!='In Review': conn.close(); raise HTTPException(409,'Only an In Review service can be reviewed.')
        if who==source['last_material_editor']: conn.close(); raise HTTPException(409,'The material editor cannot review this service version.')
        target='Reviewed'; updates={'reviewed_by':who,'reviewed_at':ts,'review_reason':p.reason.strip()}
    elif p.action=='Approve':
        if source['status']!='Reviewed': conn.close(); raise HTTPException(409,'Only a Reviewed service can be approved.')
        if who in {source['last_material_editor'],source['reviewed_by']}: conn.close(); raise HTTPException(409,'Approval requires an authority independent from the material editor and reviewer.')
        target='Approved'; updates={'approved_by':who,'approved_at':ts,'approval_reason':p.reason.strip()}
    elif p.action=='Publish':
        if source['status']!='Approved': conn.close(); raise HTTPException(409,'Only an Approved service can be published.')
        if who==source['last_material_editor']: conn.close(); raise HTTPException(409,'The material editor cannot publish this service version.')
        previous=conn.execute("SELECT * FROM ops_service_catalog WHERE tenant_id=? AND service_key=? AND status='Published' AND id<>?",(source['tenant_id'],source['service_key'],service_id)).fetchone()
        if previous:
            conn.execute("UPDATE ops_service_catalog SET status='Superseded',updated_at=? WHERE id=?",(ts,previous['id'])); replaced=conn.execute('SELECT * FROM ops_service_catalog WHERE id=?',(previous['id'],)).fetchone(); _ops_catalog_event(conn,replaced,'Superseded',f'Superseded by service version #{service_id}',request)
        target='Published'; updates={'published_by':who,'published_at':ts,'publish_reason':p.reason.strip()}
    else:
        if source['status']!='Published': conn.close(); raise HTTPException(409,'Only a Published service can be retired.')
        if who==source['last_material_editor']: conn.close(); raise HTTPException(409,'The material editor cannot retire this service version.')
        target='Retired'; updates={'retired_by':who,'retired_at':ts,'retirement_reason':p.reason.strip()}
    updates.update({'status':target,'updated_at':ts}); conn.execute('UPDATE ops_service_catalog SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',tuple(updates.values())+(service_id,)); row=conn.execute('SELECT * FROM ops_service_catalog WHERE id=?',(service_id,)).fetchone(); _ops_catalog_event(conn,row,target,p.reason.strip(),request); audit(conn,'SALOPS_CATALOG_TRANSITION','ops_service_catalog',service_id,f'{source["status"]} -> {target}: {p.reason}',who); conn.commit(); result=_ops_catalog_view(conn,row,False); conn.close(); return result

def _expert_record(request:Request,profile_id:int):
    conn=db(); row=conn.execute('SELECT * FROM expert_profiles WHERE id=?',(profile_id,)).fetchone(); conn.close()
    if not row: raise HTTPException(404,'Expert profile not found')
    if int(row['tenant_id'])!=tenant_id(request):
        security_event(request,'EXPERT_TENANT_BOUNDARY_VIOLATION','High',f'profile_id={profile_id}')
        raise HTTPException(403,'Expert profile tenant boundary violation')
    return dict(row)

def _expert_event(conn,record_type:str,row,event_type:str,summary:str,request:Request):
    version=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM expert_events WHERE tenant_id=? AND record_type=? AND record_id=?',(row['tenant_id'],record_type,row['id'])).fetchone()['n']
    snapshot=json.dumps(dict(row),sort_keys=True,separators=(',',':'),default=str)
    conn.execute('INSERT INTO expert_events(tenant_id,record_type,record_id,version_no,event_type,summary,snapshot_json,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(row['tenant_id'],record_type,row['id'],version,event_type,summary,snapshot,actor(request),role(request),now()))

def _expert_date(value:str,label:str):
    text=str(value or '').strip()
    try: return datetime.strptime(text,'%Y-%m-%d').strftime('%Y-%m-%d')
    except ValueError: raise HTTPException(422,f'{label} must be YYYY-MM-DD.')

@app.get('/api/salops/experts')
def list_expert_profiles(request:Request):
    require(request,'read'); require_salus_component_authority(request,'Expert profiles'); conn=db(); rows=[]
    for row in conn.execute('SELECT * FROM expert_profiles WHERE tenant_id=? ORDER BY member_display_name,id',(tenant_id(request),)):
        item=dict(row); item['credentials']=[dict(r) for r in conn.execute('SELECT * FROM expert_credentials WHERE tenant_id=? AND profile_id=? ORDER BY id',(tenant_id(request),row['id']))]; item['availability']=[dict(r) for r in conn.execute('SELECT * FROM expert_availability WHERE tenant_id=? AND profile_id=? ORDER BY available_from,id',(tenant_id(request),row['id']))]; rows.append(item)
    conn.close(); return rows

@app.post('/api/salops/experts')
def create_expert_profile(p:ExpertProfileIn,request:Request):
    require(request,'write'); require_ops_authority(request); tid=tenant_id(request); who=actor(request); ts=now(); conn=db()
    try:
        cur=conn.execute('''INSERT INTO expert_profiles(tenant_id,profile_key,expert_actor,member_display_name,member_role_title,member_biography,member_contact_summary,internal_biography,disciplines,jurisdictions,regions,status,created_by,created_at,last_material_editor,last_material_edit_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,f'EXP-{uuid.uuid4().hex[:12].upper()}',p.expert_actor.strip(),p.member_display_name.strip(),p.member_role_title.strip(),p.member_biography.strip(),p.member_contact_summary.strip(),p.internal_biography.strip(),p.disciplines.strip(),p.jurisdictions.strip(),p.regions.strip(),'Draft',who,ts,who,ts,ts)); profile_id=cur.lastrowid
    except Exception as exc:
        conn.rollback(); conn.close()
        if 'UNIQUE' in str(exc).upper() or 'DUPLICATE' in str(exc).upper(): raise HTTPException(409,'An expert profile already exists for this actor.')
        raise
    row=conn.execute('SELECT * FROM expert_profiles WHERE id=?',(profile_id,)).fetchone(); _expert_event(conn,'expert_profile',row,'Draft Created','Expert profile drafted',request); audit(conn,'EXPERT_PROFILE_CREATED','expert_profile',profile_id,p.expert_actor.strip(),who); conn.commit(); result=dict(row); conn.close(); return result

@app.post('/api/salops/experts/{profile_id}/transition')
def transition_expert_profile(profile_id:int,p:ExpertProfileTransitionIn,request:Request):
    require(request,'write'); require_ops_authority(request); row=_expert_record(request,profile_id); who=actor(request); ts=now(); conn=db()
    if p.action=='Activate':
        if row['status']!='Draft': conn.close(); raise HTTPException(409,'Only a Draft expert profile can be activated.')
        if who in {row['expert_actor'],row['last_material_editor']}: conn.close(); raise HTTPException(409,'Activation requires authority independent from the expert and material editor.')
        target='Active'; updates={'activated_by':who,'activated_at':ts,'activation_reason':p.reason.strip()}
    else:
        if row['status']!='Active': conn.close(); raise HTTPException(409,'Only an Active expert profile can be deactivated.')
        if who==row['expert_actor']: conn.close(); raise HTTPException(409,'An expert cannot deactivate their own governed profile.')
        active_assignment=conn.execute("SELECT id FROM ops_engagement_assignments WHERE tenant_id=? AND profile_id=? AND status IN ('Proposed','Accepted') LIMIT 1",(row['tenant_id'],profile_id)).fetchone()
        if active_assignment: conn.close(); raise HTTPException(409,'Release all proposed or accepted assignments before deactivating this profile.')
        target='Inactive'; updates={'deactivated_by':who,'deactivated_at':ts,'deactivation_reason':p.reason.strip()}
    updates.update({'status':target,'updated_at':ts}); conn.execute('UPDATE expert_profiles SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',tuple(updates.values())+(profile_id,)); current=conn.execute('SELECT * FROM expert_profiles WHERE id=?',(profile_id,)).fetchone(); _expert_event(conn,'expert_profile',current,target,p.reason.strip(),request); audit(conn,'EXPERT_PROFILE_TRANSITION','expert_profile',profile_id,f'{row["status"]} -> {target}: {p.reason}',who); conn.commit(); result=dict(current); conn.close(); return result

@app.post('/api/salops/experts/{profile_id}/credentials')
def create_expert_credential(profile_id:int,p:ExpertCredentialIn,request:Request):
    require(request,'write'); require_ops_authority(request); profile=_expert_record(request,profile_id); effective=_expert_date(p.effective_on,'Effective date'); expires=_expert_date(p.expires_on,'Expiry date') if p.expires_on else ''
    if expires and expires<effective: raise HTTPException(422,'Expiry date cannot precede effective date.')
    if p.evidence_id:
        conn=db(); evidence=conn.execute('SELECT e.*,a.tenant_id FROM evidence e JOIN assessments a ON a.id=e.assessment_id WHERE e.id=?',(p.evidence_id,)).fetchone(); conn.close()
        if evidence and int(evidence['tenant_id'])!=tenant_id(request):
            security_event(request,'EXPERT_TENANT_BOUNDARY_VIOLATION','High',f'credential evidence_id={p.evidence_id}')
            raise HTTPException(403,'Credential evidence tenant boundary violation')
        if not evidence: raise HTTPException(422,'Credential evidence is unavailable in this tenant.')
        assessment_row_for_request(request,evidence['assessment_id'])
    who=actor(request); ts=now(); conn=db(); cur=conn.execute('''INSERT INTO expert_credentials(tenant_id,profile_id,credential_type,issuer,jurisdiction,effective_on,expires_on,evidence_id,status,entered_by,entered_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(tenant_id(request),profile_id,p.credential_type.strip(),p.issuer.strip(),p.jurisdiction.strip(),effective,expires,p.evidence_id,'Unverified',who,ts,ts)); cid=cur.lastrowid; row=conn.execute('SELECT * FROM expert_credentials WHERE id=?',(cid,)).fetchone(); _expert_event(conn,'expert_credential',row,'Recorded','Credential recorded as unverified',request); audit(conn,'EXPERT_CREDENTIAL_CREATED','expert_credential',cid,f'profile={profile_id}; type={p.credential_type}',who); conn.commit(); result=dict(row); conn.close(); return result

@app.post('/api/salops/credentials/{credential_id}/transition')
def transition_expert_credential(credential_id:int,p:ExpertCredentialTransitionIn,request:Request):
    require(request,'write'); require_ops_authority(request); tid=tenant_id(request); who=actor(request); ts=now(); conn=db(); row=conn.execute('SELECT c.*,p.expert_actor FROM expert_credentials c JOIN expert_profiles p ON p.id=c.profile_id WHERE c.id=? AND c.tenant_id=?',(credential_id,tid)).fetchone()
    if not row:
        outside=conn.execute('SELECT tenant_id FROM expert_credentials WHERE id=?',(credential_id,)).fetchone(); conn.close()
        if outside: security_event(request,'EXPERT_TENANT_BOUNDARY_VIOLATION','High',f'credential_id={credential_id}'); raise HTTPException(403,'Expert credential tenant boundary violation')
        raise HTTPException(404,'Expert credential not found')
    if p.action=='Verify':
        if row['status']!='Unverified': conn.close(); raise HTTPException(409,'Only an Unverified credential can be verified.')
        if who in {row['expert_actor'],row['entered_by']}: conn.close(); raise HTTPException(409,'Credential verification must be independent from the expert and recorder.')
        if row['evidence_id']:
            evidence=conn.execute('SELECT verification_status,lifecycle_status,valid_until FROM evidence WHERE id=?',(row['evidence_id'],)).fetchone()
            if not evidence or evidence['verification_status']!='Verified' or evidence['lifecycle_status']!='Current' or (evidence['valid_until'] and evidence['valid_until']<ts[:10]): conn.close(); raise HTTPException(409,'Credential evidence must be verified and current.')
        target='Verified'; updates={'verified_by':who,'verified_at':ts,'verification_reason':p.reason.strip()}
    else:
        if row['status'] not in {'Unverified','Verified'}: conn.close(); raise HTTPException(409,'This credential is already terminal.')
        if who==row['expert_actor']: conn.close(); raise HTTPException(409,'An expert cannot withdraw their own governed credential.')
        active_assignment=conn.execute("SELECT id FROM ops_engagement_assignments WHERE tenant_id=? AND profile_id=? AND status IN ('Proposed','Accepted') LIMIT 1",(tid,row['profile_id'])).fetchone()
        if active_assignment: conn.close(); raise HTTPException(409,'Release all proposed or accepted assignments before withdrawing this credential.')
        target='Withdrawn'; updates={'withdrawn_by':who,'withdrawn_at':ts,'withdrawal_reason':p.reason.strip()}
    updates.update({'status':target,'updated_at':ts}); conn.execute('UPDATE expert_credentials SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',tuple(updates.values())+(credential_id,)); current=conn.execute('SELECT * FROM expert_credentials WHERE id=?',(credential_id,)).fetchone(); _expert_event(conn,'expert_credential',current,target,p.reason.strip(),request); audit(conn,'EXPERT_CREDENTIAL_TRANSITION','expert_credential',credential_id,f'{row["status"]} -> {target}: {p.reason}',who); conn.commit(); result=dict(current); conn.close(); return result

@app.post('/api/salops/experts/{profile_id}/availability')
def create_expert_availability(profile_id:int,p:ExpertAvailabilityIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'Expert availability'); _expert_record(request,profile_id); start=_ops_time(p.available_from,'Available from'); end=_ops_time(p.available_until,'Available until')
    if end<=start: raise HTTPException(422,'Availability end must be after start.')
    who=actor(request); ts=now(); conn=db(); cur=conn.execute('INSERT INTO expert_availability(tenant_id,profile_id,available_from,available_until,region,status,recorded_by,recorded_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(tenant_id(request),profile_id,start,end,p.region.strip(),'Available',who,ts,ts)); aid=cur.lastrowid; row=conn.execute('SELECT * FROM expert_availability WHERE id=?',(aid,)).fetchone(); _expert_event(conn,'expert_availability',row,'Availability Recorded','Availability window recorded',request); audit(conn,'EXPERT_AVAILABILITY_CREATED','expert_availability',aid,f'profile={profile_id}',who); conn.commit(); result=dict(row); conn.close(); return result

@app.get('/api/salops/engagements/{engagement_id}/conflicts')
def list_expert_conflicts(engagement_id:int,request:Request):
    require(request,'read'); require_salus_component_authority(request,'Expert conflicts'); _ops_engagement(request,engagement_id); conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM expert_conflicts WHERE tenant_id=? AND engagement_id=? ORDER BY id',(tenant_id(request),engagement_id))]; conn.close(); return rows

@app.post('/api/salops/engagements/{engagement_id}/conflicts')
def create_expert_conflict(engagement_id:int,p:ExpertConflictIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'Expert conflicts'); engagement=_ops_engagement(request,engagement_id); _expert_record(request,p.profile_id); who=actor(request); ts=now(); conn=db()
    try: cur=conn.execute('INSERT INTO expert_conflicts(tenant_id,assessment_id,profile_id,engagement_id,disclosure,status,disclosed_by,disclosed_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(tenant_id(request),engagement['assessment_id'],p.profile_id,engagement_id,p.disclosure.strip(),'Pending',who,ts,ts)); cid=cur.lastrowid
    except Exception as exc:
        conn.rollback(); conn.close()
        if 'UNIQUE' in str(exc).upper() or 'DUPLICATE' in str(exc).upper(): raise HTTPException(409,'A conflict disclosure already exists for this expert and engagement.')
        raise
    row=conn.execute('SELECT * FROM expert_conflicts WHERE id=?',(cid,)).fetchone(); _expert_event(conn,'expert_conflict',row,'Disclosed',p.disclosure.strip(),request); audit(conn,'EXPERT_CONFLICT_CREATED','expert_conflict',cid,f'engagement={engagement_id}; profile={p.profile_id}',who); conn.commit(); result=dict(row); conn.close(); return result

@app.post('/api/salops/conflicts/{conflict_id}/review')
def review_expert_conflict(conflict_id:int,p:ExpertConflictReviewIn,request:Request):
    require(request,'write'); require_ops_authority(request); tid=tenant_id(request); who=actor(request); ts=now(); conn=db(); row=conn.execute('SELECT c.*,p.expert_actor FROM expert_conflicts c JOIN expert_profiles p ON p.id=c.profile_id WHERE c.id=? AND c.tenant_id=?',(conflict_id,tid)).fetchone()
    if not row:
        outside=conn.execute('SELECT tenant_id FROM expert_conflicts WHERE id=?',(conflict_id,)).fetchone(); conn.close()
        if outside: security_event(request,'EXPERT_TENANT_BOUNDARY_VIOLATION','High',f'conflict_id={conflict_id}'); raise HTTPException(403,'Expert conflict tenant boundary violation')
        raise HTTPException(404,'Expert conflict disclosure not found')
    if row['status']!='Pending': conn.close(); raise HTTPException(409,'Only a Pending conflict disclosure can be reviewed.')
    if who in {row['expert_actor'],row['disclosed_by']}: conn.close(); raise HTTPException(409,'Conflict review must be independent from the expert and discloser.')
    conn.execute('UPDATE expert_conflicts SET status=?,reviewed_by=?,reviewed_at=?,review_reason=?,updated_at=? WHERE id=?',(p.decision,who,ts,p.reason.strip(),ts,conflict_id)); current=conn.execute('SELECT * FROM expert_conflicts WHERE id=?',(conflict_id,)).fetchone(); _expert_event(conn,'expert_conflict',current,p.decision,p.reason.strip(),request); audit(conn,'EXPERT_CONFLICT_REVIEW','expert_conflict',conflict_id,f'{p.decision}: {p.reason}',who); conn.commit(); result=dict(current); conn.close(); return result

@app.get('/api/salops/engagements/{engagement_id}/experts')
def list_engagement_experts(engagement_id:int,request:Request):
    require(request,'read'); _ops_engagement(request,engagement_id); tid=tenant_id(request); conn=db()
    if protected_member_request(request):
        rows=[dict(r) for r in conn.execute("SELECT id,engagement_id,assignment_role,member_display_name_snapshot,member_role_title_snapshot,member_biography_snapshot,member_contact_summary_snapshot,status,accepted_at FROM ops_engagement_assignments WHERE tenant_id=? AND engagement_id=? AND status='Accepted' AND member_visible=1 ORDER BY id",(tid,engagement_id))]
    else: rows=[dict(r) for r in conn.execute('SELECT * FROM ops_engagement_assignments WHERE tenant_id=? AND engagement_id=? ORDER BY id',(tid,engagement_id))]
    conn.close(); return rows

@app.post('/api/salops/engagements/{engagement_id}/experts')
def propose_engagement_expert(engagement_id:int,p:ExpertAssignmentIn,request:Request):
    require(request,'write'); require_ops_authority(request); engagement=_ops_engagement(request,engagement_id); profile=_expert_record(request,p.profile_id); who=actor(request); tid=tenant_id(request)
    if engagement['status'] not in {'Planning','Mobilizing','Active'}: raise HTTPException(409,'Experts can be assigned only to a planning, mobilizing, or active engagement.')
    if profile['status']!='Active': raise HTTPException(409,'Only an Active expert profile can be assigned.')
    if who==profile['expert_actor']: raise HTTPException(409,'An expert cannot authorize their own assignment.')
    today=now()[:10]; conn=db(); credentials=[dict(r) for r in conn.execute("SELECT * FROM expert_credentials WHERE tenant_id=? AND profile_id=? AND status='Verified' AND effective_on<=? AND (expires_on='' OR expires_on>=?) ORDER BY id",(tid,p.profile_id,today,today))]
    if not credentials: conn.close(); raise HTTPException(409,'Assignment requires a current independently verified credential.')
    availability=conn.execute("SELECT id FROM expert_availability WHERE tenant_id=? AND profile_id=? AND status='Available' AND available_from<=? AND available_until>=? LIMIT 1",(tid,p.profile_id,engagement['planned_start'],engagement['planned_end'])).fetchone()
    if not availability: conn.close(); raise HTTPException(409,'Assignment requires an availability window covering the engagement operating period.')
    conflict=conn.execute("SELECT * FROM expert_conflicts WHERE id=? AND tenant_id=? AND profile_id=? AND engagement_id=? AND status='Cleared'",(p.conflict_id,tid,p.profile_id,engagement_id)).fetchone()
    if not conflict:
        outside=conn.execute('SELECT tenant_id,profile_id,engagement_id FROM expert_conflicts WHERE id=?',(p.conflict_id,)).fetchone(); conn.close()
        if outside and (int(outside['tenant_id'])!=tid or int(outside['profile_id'])!=p.profile_id or int(outside['engagement_id'])!=engagement_id):
            security_event(request,'EXPERT_ASSIGNMENT_SCOPE_VIOLATION','High',f'conflict_id={p.conflict_id}; engagement_id={engagement_id}')
            raise HTTPException(403,'Expert assignment scope violation')
        raise HTTPException(409,'Assignment requires an independently cleared conflict disclosure for this engagement.')
    if conflict['reviewed_by'] in {profile['expert_actor'],who}: conn.close(); raise HTTPException(409,'Conflict review and assignment authority must remain independent.')
    qualification=json.dumps([{'credential_type':c['credential_type'],'issuer':c['issuer'],'jurisdiction':c['jurisdiction'],'effective_on':c['effective_on'],'expires_on':c['expires_on'],'verified_by':c['verified_by'],'verified_at':c['verified_at']} for c in credentials],sort_keys=True,separators=(',',':'))
    ts=now()
    try:
        cur=conn.execute('''INSERT INTO ops_engagement_assignments(tenant_id,engagement_id,assessment_id,profile_id,conflict_id,assignment_role,member_display_name_snapshot,member_role_title_snapshot,member_biography_snapshot,member_contact_summary_snapshot,qualification_snapshot,member_visible,status,proposed_by,proposed_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,engagement_id,engagement['assessment_id'],p.profile_id,p.conflict_id,p.assignment_role.strip(),profile['member_display_name'],profile['member_role_title'],profile['member_biography'],profile['member_contact_summary'],qualification,1 if p.member_visible else 0,'Proposed',who,ts,ts)); assignment_id=cur.lastrowid
    except Exception as exc:
        conn.rollback(); conn.close()
        if 'UNIQUE' in str(exc).upper() or 'DUPLICATE' in str(exc).upper(): raise HTTPException(409,'This expert already has an active assignment to the engagement.')
        raise
    row=conn.execute('SELECT * FROM ops_engagement_assignments WHERE id=?',(assignment_id,)).fetchone(); _expert_event(conn,'expert_assignment',row,'Proposed',f'engagement={engagement_id}; role={p.assignment_role}',request); audit(conn,'EXPERT_ASSIGNMENT_PROPOSED','expert_assignment',assignment_id,f'engagement={engagement_id}; profile={p.profile_id}',who); conn.commit(); result=dict(row); conn.close(); return result

@app.post('/api/salops/expert-assignments/{assignment_id}/transition')
def transition_engagement_expert(assignment_id:int,p:ExpertAssignmentTransitionIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'Expert assignments'); tid=tenant_id(request); who=actor(request); ts=now(); conn=db(); row=conn.execute('SELECT a.*,p.expert_actor FROM ops_engagement_assignments a JOIN expert_profiles p ON p.id=a.profile_id WHERE a.id=? AND a.tenant_id=?',(assignment_id,tid)).fetchone()
    if not row:
        outside=conn.execute('SELECT tenant_id FROM ops_engagement_assignments WHERE id=?',(assignment_id,)).fetchone(); conn.close()
        if outside: security_event(request,'EXPERT_TENANT_BOUNDARY_VIOLATION','High',f'assignment_id={assignment_id}'); raise HTTPException(403,'Expert assignment tenant boundary violation')
        raise HTTPException(404,'Expert assignment not found')
    assessment_row_for_request(request,row['assessment_id'])
    if p.action=='Accept':
        if row['status']!='Proposed': conn.close(); raise HTTPException(409,'Only a Proposed assignment can be accepted.')
        if who!=row['expert_actor']: conn.close(); raise HTTPException(403,'Only the assigned expert may accept this assignment.')
        target='Accepted'; updates={'accepted_by':who,'accepted_at':ts,'acceptance_reason':p.reason.strip()}
    else:
        require_ops_authority(request)
        if row['status'] not in {'Proposed','Accepted'}: conn.close(); raise HTTPException(409,'This assignment is already terminal.')
        if who==row['expert_actor']: conn.close(); raise HTTPException(409,'Assignment release requires operational authority independent from the expert.')
        target='Released'; updates={'released_by':who,'released_at':ts,'release_reason':p.reason.strip()}
    updates.update({'status':target,'updated_at':ts}); conn.execute('UPDATE ops_engagement_assignments SET '+','.join(f'{k}=?' for k in updates)+' WHERE id=?',tuple(updates.values())+(assignment_id,)); current=conn.execute('SELECT * FROM ops_engagement_assignments WHERE id=?',(assignment_id,)).fetchone(); _expert_event(conn,'expert_assignment',current,target,p.reason.strip(),request); audit(conn,'EXPERT_ASSIGNMENT_TRANSITION','expert_assignment',assignment_id,f'{row["status"]} -> {target}: {p.reason}',who); conn.commit(); result=dict(current); conn.close(); return result

@app.get('/api/salops/requests')
def list_ops_requests(request:Request):
    require(request,'read'); conn=db()
    if protected_member_request(request):
        rows=[dict(r) for r in conn.execute('SELECT id,assessment_id,source_type,source_id,service_catalog_id,service_key_snapshot,service_version_snapshot,service_name_snapshot,service_member_description_snapshot,service_deliverables_snapshot,title,priority,status,result_summary,completed_at,updated_at FROM ops_requests WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]
    else:
        rows=[dict(r) for r in conn.execute('SELECT * FROM ops_requests WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]
    conn.close(); return rows

@app.post('/api/salops/requests')
def create_ops_request(p:OpsRequestIn,request:Request):
    require(request,'write'); tid=tenant_id(request); who=actor(request)
    if p.assessment_id is not None: assessment_row_for_request(request,p.assessment_id)
    service=None
    if p.service_catalog_id is not None:
        service=_ops_catalog_record(request,p.service_catalog_id)
        if service['status']!='Published' or (protected_member_request(request) and not service['member_visible']): raise HTTPException(409,'Only an active published member-visible service may be requested.')
    ts=now(); conn=db(); cur=conn.execute('''INSERT INTO ops_requests(tenant_id,assessment_id,source_type,source_id,service_catalog_id,service_key_snapshot,service_version_snapshot,service_name_snapshot,service_member_description_snapshot,service_deliverables_snapshot,title,description,priority,status,requested_by,requested_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,p.assessment_id,'Service Catalog' if service else 'Manual',None,service['id'] if service else None,service['service_key'] if service else '',service['version_no'] if service else None,service['name'] if service else '',service['member_description'] if service else '',service['default_deliverables'] if service else '',p.title,p.description,p.priority,'Requested',who,ts,ts)); oid=cur.lastrowid; audit(conn,'SALOPS_REQUEST','ops_request',oid,f'{p.title}; service={service["service_key"] if service else "manual"}',who); conn.commit(); row=dict(conn.execute('SELECT * FROM ops_requests WHERE id=?',(oid,)).fetchone()); conn.close(); return row

@app.post('/api/salthira/improvements/{improvement_id}/send-to-salops')
def send_improvement_to_salops(improvement_id:int,request:Request):
    require(request,'decide'); who=actor(request); tid=tenant_id(request); conn=db(); improvement=conn.execute('SELECT * FROM improvements WHERE id=?',(improvement_id,)).fetchone()
    if not improvement: conn.close(); raise HTTPException(404,'Improvement not found')
    assessment_row_for_request(request,improvement['assessment_id']); decision=conn.execute("SELECT * FROM decisions WHERE improvement_id=? AND decision_type IN ('Approve','Approve with Conditions') ORDER BY id DESC LIMIT 1",(improvement_id,)).fetchone()
    if not decision: conn.close(); raise HTTPException(409,'A governed approving decision is required before SalOPS handoff.')
    existing=conn.execute("SELECT * FROM ops_requests WHERE tenant_id=? AND source_type='SalTHIRA Improvement' AND source_id=?",(tid,improvement_id)).fetchone()
    if existing: conn.close(); return dict(existing)
    ts=now(); priority='Urgent' if float(improvement['priority_score'] or 0)>=75 else 'Priority'; cur=conn.execute('INSERT INTO ops_requests(tenant_id,assessment_id,source_type,source_id,title,description,priority,status,requested_by,requested_at,authorized_by,authorized_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,improvement['assessment_id'],'SalTHIRA Improvement',improvement_id,improvement['title'],improvement['description'],priority,'Authorized',who,ts,decision['authority'],decision['created_at'],ts)); oid=cur.lastrowid; audit(conn,'SALTHIRA_TO_SALOPS','improvement',improvement_id,f'ops_request={oid}; decision={decision["id"]}',who); audit(conn,'CREATE','ops_request',oid,f'Created from approved SalTHIRA improvement #{improvement_id}',who); conn.commit(); result=dict(conn.execute('SELECT * FROM ops_requests WHERE id=?',(oid,)).fetchone()); conn.close(); return result

@app.post('/api/salops/requests/{request_id}/decision')
def decide_ops_request(request_id:int,p:OpsRequestDecisionIn,request:Request):
    require_protected_member_authority(request,'salops_request_decision'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute("SELECT * FROM ops_requests WHERE id=? AND tenant_id=? AND status='Requested'",(request_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Requested operation not found')
    ts=now(); conn.execute('UPDATE ops_requests SET status=?,authorized_by=?,authorized_at=?,assigned_to=?,description=description||?,updated_at=? WHERE id=?',(p.decision,who,ts,p.assigned_to,f'\nAuthority basis: {p.reason}',ts,request_id)); audit(conn,'SALOPS_DECISION','ops_request',request_id,f'{p.decision}: {p.reason}',who); conn.commit(); result=dict(conn.execute('SELECT * FROM ops_requests WHERE id=?',(request_id,)).fetchone()); conn.close(); return result

@app.post('/api/salops/requests/{request_id}/complete')
def complete_ops_request(request_id:int,p:OpsResultIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalOPS'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute("SELECT * FROM ops_requests WHERE id=? AND tenant_id=? AND status IN ('Authorized','In Progress')",(request_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Active authorized operation not found')
    ts=now(); conn.execute("UPDATE ops_requests SET status='Completed',result_summary=?,completed_by=?,completed_at=?,updated_at=? WHERE id=?",(p.result_summary,who,ts,ts,request_id)); audit(conn,'SALOPS_COMPLETE','ops_request',request_id,p.result_summary[:1000],who)
    trigger_id=None
    if row['assessment_id']:
        cur=conn.execute("INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(row['assessment_id'],'SalOPS','Operational Result',f"Operational result available for assessment review: {row['title']}",'Moderate','ops_request',request_id,'Open','','','',ts,ts)); trigger_id=cur.lastrowid; audit(conn,'SALOPS_TO_SALTHIRA','ops_request',request_id,f'reassessment_trigger={trigger_id}',who)
    conn.commit(); result=dict(conn.execute('SELECT * FROM ops_requests WHERE id=?',(request_id,)).fetchone()); conn.close(); return {'operation':result,'reassessment_trigger_id':trigger_id}

def _ops_time(value:str,label:str):
    text=str(value or '').strip()
    try:
        parsed=datetime.fromisoformat(text.replace('Z','+00:00'))
    except ValueError:
        raise HTTPException(422,f'{label} must be an ISO 8601 date or timestamp.')
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def _ops_engagement(request:Request,engagement_id:int):
    conn=db(); row=conn.execute('SELECT * FROM ops_engagements WHERE id=? AND tenant_id=?',(engagement_id,tenant_id(request))).fetchone(); conn.close()
    if not row: raise HTTPException(404,'Operational engagement not found')
    assessment_row_for_request(request,row['assessment_id'])
    return dict(row)

@app.get('/api/salops/engagements')
def list_ops_engagements(request:Request):
    require(request,'read'); ids=accessible_assessment_ids(request)
    if not ids: return []
    marks=','.join('?'*len(ids)); params=(tenant_id(request),*ids); conn=db()
    if protected_member_request(request):
        sql=f'SELECT id,ops_request_id,assessment_id,title,service_type,planned_start,planned_end,member_status_summary,status,created_at,updated_at,closed_at FROM ops_engagements WHERE tenant_id=? AND assessment_id IN ({marks}) ORDER BY id DESC'
    else: sql=f'SELECT * FROM ops_engagements WHERE tenant_id=? AND assessment_id IN ({marks}) ORDER BY id DESC'
    rows=[dict(r) for r in conn.execute(sql,params)]
    for item in rows:
        counts={r['status']:r['c'] for r in conn.execute('SELECT status,COUNT(*) c FROM ops_engagement_readiness WHERE tenant_id=? AND engagement_id=? GROUP BY status',(tenant_id(request),item['id']))}
        item['readiness_summary']={'pending':counts.get('Pending',0),'complete':counts.get('Complete',0),'exceptions':counts.get('Exception',0),'total':sum(counts.values())}
    conn.close(); return rows

@app.post('/api/salops/requests/{request_id}/engagement')
def create_ops_engagement(request_id:int,p:OpsEngagementIn,request:Request):
    require(request,'write'); require_ops_authority(request); tid=tenant_id(request); who=actor(request); conn=db()
    source=conn.execute("SELECT * FROM ops_requests WHERE id=? AND tenant_id=? AND status='Authorized'",(request_id,tid)).fetchone()
    if not source: conn.close(); raise HTTPException(409,'An authorized SalOPS request is required to create an engagement.')
    if not source['assessment_id']: conn.close(); raise HTTPException(409,'The authorized request must be linked to an assessment before operational engagement.')
    assessment_row_for_request(request,source['assessment_id'])
    existing=conn.execute('SELECT id FROM ops_engagements WHERE tenant_id=? AND ops_request_id=?',(tid,request_id)).fetchone()
    if existing: conn.close(); raise HTTPException(409,'This authorized request already has an operational engagement.')
    start=_ops_time(p.planned_start,'Planned start'); end=_ops_time(p.planned_end,'Planned end')
    if end<=start: conn.close(); raise HTTPException(422,'Planned end must be after planned start.')
    service_type=source['service_name_snapshot'] or p.service_type
    ts=now(); cur=conn.execute('''INSERT INTO ops_engagements(tenant_id,ops_request_id,service_catalog_id,service_key_snapshot,service_version_snapshot,service_member_scope_snapshot,service_deliverables_snapshot,assessment_id,title,service_type,objective,location,planned_start,planned_end,operational_lead,communications_plan,member_status_summary,status,authorized_by,authorized_at,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,request_id,source['service_catalog_id'],source['service_key_snapshot'],source['service_version_snapshot'],source['service_member_description_snapshot'],source['service_deliverables_snapshot'],source['assessment_id'],source['title'],service_type,p.objective,p.location,start,end,p.operational_lead,p.communications_plan,p.member_status_summary,'Planning',source['authorized_by'],source['authorized_at'],who,ts,who,ts)); eid=cur.lastrowid
    audit(conn,'CREATE','ops_engagement',eid,f'Created from authorized ops_request={request_id}',who); snapshot_entity(conn,'ops_engagements',eid,who,'Operational engagement created'); conn.commit(); row=dict(conn.execute('SELECT * FROM ops_engagements WHERE id=?',(eid,)).fetchone()); conn.close(); return row

@app.post('/api/salops/engagements/{engagement_id}/transition')
def transition_ops_engagement(engagement_id:int,p:OpsEngagementTransitionIn,request:Request):
    require(request,'write'); require_ops_authority(request); row=_ops_engagement(request,engagement_id); allowed={'Planning':'Mobilizing','Mobilizing':'Active','Active':'Demobilizing','Demobilizing':'Closed'}
    if allowed.get(row['status'])!=p.status: raise HTTPException(409,f'Engagement transition must follow Planning → Mobilizing → Active → Demobilizing → Closed; current status is {row["status"]}.')
    tid=tenant_id(request); who=actor(request); ts=now(); conn=db()
    if row.get('service_catalog_id') and p.status=='Mobilizing':
        readiness_count=conn.execute('SELECT COUNT(*) c FROM ops_engagement_readiness WHERE engagement_id=? AND tenant_id=?',(engagement_id,tid)).fetchone()['c']
        if not readiness_count: conn.close(); raise HTTPException(409,'Catalog-backed engagements require documented readiness requirements before mobilization.')
        active_profiles=conn.execute("SELECT COUNT(*) c FROM expert_profiles WHERE tenant_id=? AND status='Active'",(tid,)).fetchone()['c']
        assignment_count=conn.execute("SELECT COUNT(*) c FROM ops_engagement_assignments WHERE engagement_id=? AND tenant_id=? AND status='Accepted'",(engagement_id,tid)).fetchone()['c']
        if active_profiles and not assignment_count: conn.close(); raise HTTPException(409,'Expert-enabled catalog engagements require at least one accepted qualified expert assignment before mobilization.')
    if row.get('service_catalog_id') and p.status=='Active':
        pending=conn.execute("SELECT COUNT(*) c FROM ops_engagement_readiness WHERE engagement_id=? AND tenant_id=? AND status='Pending'",(engagement_id,tid)).fetchone()['c']
        if pending: conn.close(); raise HTTPException(409,'Catalog-backed engagements cannot become Active while readiness requirements remain pending.')
    if p.status=='Closed':
        unresolved=conn.execute("SELECT COUNT(*) c FROM ops_tasks WHERE engagement_id=? AND tenant_id=? AND status NOT IN ('Completed','Cancelled')",(engagement_id,tid)).fetchone()['c']
        released=conn.execute("SELECT COUNT(*) c FROM ops_field_reports WHERE engagement_id=? AND tenant_id=? AND status='Released'",(engagement_id,tid)).fetchone()['c']
        if unresolved or not released: conn.close(); raise HTTPException(409,'Closure requires every task resolved and at least one released field report.')
    closed_by=who if p.status=='Closed' else ''; closed_at=ts if p.status=='Closed' else ''; closure=p.reason if p.status=='Closed' else ''
    conn.execute('UPDATE ops_engagements SET status=?,member_status_summary=?,updated_by=?,updated_at=?,closed_by=?,closed_at=?,closure_summary=? WHERE id=?',(p.status,p.member_status_summary,who,ts,closed_by,closed_at,closure,engagement_id))
    if p.status=='Active': conn.execute("UPDATE ops_requests SET status='In Progress',updated_at=? WHERE id=?",(ts,row['ops_request_id']))
    trigger_id=None
    if p.status=='Closed':
        conn.execute("UPDATE ops_requests SET status='Completed',result_summary=?,completed_by=?,completed_at=?,updated_at=? WHERE id=?",(p.reason,who,ts,ts,row['ops_request_id']))
        existing=conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='SalOPS' AND affected_record_type='ops_engagement' AND affected_record_id=?",(row['assessment_id'],engagement_id)).fetchone()
        if existing: trigger_id=existing['id']
        else:
            cur=conn.execute("INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(row['assessment_id'],'SalOPS','Operational Engagement Result',f"Operational engagement closed for assessment review: {row['title']}",'Moderate','ops_engagement',engagement_id,'Open','','','',ts,ts)); trigger_id=cur.lastrowid; audit(conn,'SALOPS_TO_SALTHIRA','ops_engagement',engagement_id,f'reassessment_trigger={trigger_id}',who); snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Created from closed operational engagement')
    audit(conn,'SALOPS_ENGAGEMENT_TRANSITION','ops_engagement',engagement_id,f'{row["status"]} -> {p.status}: {p.reason}',who); snapshot_entity(conn,'ops_engagements',engagement_id,who,f'{row["status"]} -> {p.status}'); conn.commit(); result=dict(conn.execute('SELECT * FROM ops_engagements WHERE id=?',(engagement_id,)).fetchone()); conn.close(); return {'engagement':result,'reassessment_trigger_id':trigger_id}

@app.get('/api/salops/engagements/{engagement_id}/readiness')
def list_ops_readiness(engagement_id:int,request:Request):
    require(request,'read'); _ops_engagement(request,engagement_id); tid=tenant_id(request); conn=db()
    if protected_member_request(request):
        rows=[dict(r) for r in conn.execute('SELECT id,engagement_id,label,member_summary,due_at,status,completed_at FROM ops_engagement_readiness WHERE tenant_id=? AND engagement_id=? AND member_visible=1 ORDER BY id',(tid,engagement_id))]
    else: rows=[dict(r) for r in conn.execute('SELECT * FROM ops_engagement_readiness WHERE tenant_id=? AND engagement_id=? ORDER BY id',(tid,engagement_id))]
    conn.close(); return rows

@app.post('/api/salops/engagements/{engagement_id}/readiness')
def create_ops_readiness(engagement_id:int,p:OpsReadinessIn,request:Request):
    require(request,'write'); require_ops_authority(request); engagement=_ops_engagement(request,engagement_id)
    if engagement['status'] not in {'Planning','Mobilizing'}: raise HTTPException(409,'Readiness requirements can be added only during planning or mobilization.')
    due=_ops_time(p.due_at,'Readiness due time') if p.due_at.strip() else ''; tid=tenant_id(request); who=actor(request); ts=now(); conn=db(); cur=conn.execute('''INSERT INTO ops_engagement_readiness(tenant_id,engagement_id,assessment_id,label,member_summary,internal_requirement,member_visible,due_at,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,engagement_id,engagement['assessment_id'],p.label.strip(),p.member_summary.strip(),p.internal_requirement.strip(),1 if p.member_visible else 0,due,'Pending',who,ts,ts)); rid=cur.lastrowid; audit(conn,'SALOPS_READINESS_CREATED','ops_engagement_readiness',rid,f'engagement={engagement_id}; label={p.label.strip()}',who); conn.commit(); row=dict(conn.execute('SELECT * FROM ops_engagement_readiness WHERE id=?',(rid,)).fetchone()); conn.close(); return row

@app.post('/api/salops/readiness/{readiness_id}/transition')
def transition_ops_readiness(readiness_id:int,p:OpsReadinessTransitionIn,request:Request):
    require(request,'write'); require_ops_authority(request); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute("SELECT * FROM ops_engagement_readiness WHERE id=? AND tenant_id=? AND status='Pending'",(readiness_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Pending engagement readiness requirement not found')
    assessment_row_for_request(request,row['assessment_id']); ts=now(); conn.execute('UPDATE ops_engagement_readiness SET status=?,completed_by=?,completed_at=?,completion_reason=?,updated_at=? WHERE id=?',(p.status,who,ts,p.reason.strip(),ts,readiness_id)); audit(conn,'SALOPS_READINESS_TRANSITION','ops_engagement_readiness',readiness_id,f'Pending -> {p.status}: {p.reason}',who); conn.commit(); result=dict(conn.execute('SELECT * FROM ops_engagement_readiness WHERE id=?',(readiness_id,)).fetchone()); conn.close(); return result

@app.get('/api/salops/engagements/{engagement_id}/tasks')
def list_ops_tasks(engagement_id:int,request:Request):
    require(request,'read'); require_salus_component_authority(request,'SalOPS'); _ops_engagement(request,engagement_id); conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM ops_tasks WHERE engagement_id=? AND tenant_id=? ORDER BY id',(engagement_id,tenant_id(request)))]; conn.close(); return rows

@app.post('/api/salops/engagements/{engagement_id}/tasks')
def create_ops_task(engagement_id:int,p:OpsTaskIn,request:Request):
    require(request,'write'); require_ops_authority(request); engagement=_ops_engagement(request,engagement_id)
    if engagement['status'] in ('Demobilizing','Closed'): raise HTTPException(409,'New tasks cannot be assigned during demobilization or after closure.')
    tid=tenant_id(request); who=actor(request); ts=now(); conn=db(); assigned_to=p.assigned_to
    if p.assignment_id:
        assignment=conn.execute("SELECT a.*,p.expert_actor FROM ops_engagement_assignments a JOIN expert_profiles p ON p.id=a.profile_id WHERE a.id=?",(p.assignment_id,)).fetchone()
        if assignment and (int(assignment['tenant_id'])!=tid or int(assignment['engagement_id'])!=engagement_id):
            conn.close(); security_event(request,'EXPERT_ASSIGNMENT_SCOPE_VIOLATION','High',f'assignment_id={p.assignment_id}; engagement_id={engagement_id}'); raise HTTPException(403,'Expert task assignment scope violation')
        if not assignment or assignment['status']!='Accepted': conn.close(); raise HTTPException(409,'Task assignment requires an accepted expert assignment for this engagement.')
        assigned_to=assignment['expert_actor']
    cur=conn.execute('INSERT INTO ops_tasks(tenant_id,engagement_id,assessment_id,assignment_id,title,instructions,assigned_to,priority,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tid,engagement_id,engagement['assessment_id'],p.assignment_id,p.title,p.instructions,assigned_to,p.priority,'Assigned',who,ts,ts)); task_id=cur.lastrowid; audit(conn,'CREATE','ops_task',task_id,f'engagement={engagement_id}; assigned_to={assigned_to}; assignment={p.assignment_id or "manual"}',who); snapshot_entity(conn,'ops_tasks',task_id,who,'Operational task assigned'); conn.commit(); row=dict(conn.execute('SELECT * FROM ops_tasks WHERE id=?',(task_id,)).fetchone()); conn.close(); return row

@app.post('/api/salops/tasks/{task_id}/transition')
def transition_ops_task(task_id:int,p:OpsTaskTransitionIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalOPS'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute('SELECT * FROM ops_tasks WHERE id=?',(task_id,)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Operational task not found')
    if int(row['tenant_id'])!=tid:
        conn.close(); security_event(request,'SALOPS_TASK_TENANT_BOUNDARY_VIOLATION','High',f'task_id={task_id}'); raise HTTPException(403,'Tenant boundary violation')
    if who!=row['assigned_to']:
        conn.close(); require_ops_authority(request); conn=db(); row=conn.execute('SELECT * FROM ops_tasks WHERE id=? AND tenant_id=?',(task_id,tid)).fetchone()
    assessment_row_for_request(request,row['assessment_id']); allowed={'Assigned':{'In Progress','Cancelled'},'In Progress':{'Completed','Cancelled'}}
    if p.status not in allowed.get(row['status'],set()): conn.close(); raise HTTPException(409,f'Task cannot transition from {row["status"]} to {p.status}.')
    if p.status=='Completed' and not p.result_summary.strip(): conn.close(); raise HTTPException(422,'A result summary is required to complete a task.')
    ts=now(); started_by=who if p.status=='In Progress' else row['started_by']; started_at=ts if p.status=='In Progress' else row['started_at']; terminal=p.status in ('Completed','Cancelled'); result=p.result_summary.strip() or p.reason
    conn.execute('UPDATE ops_tasks SET status=?,started_by=?,started_at=?,completed_by=?,completed_at=?,result_summary=?,updated_at=? WHERE id=?',(p.status,started_by,started_at,who if terminal else '',ts if terminal else '',result if terminal else row['result_summary'],ts,task_id)); audit(conn,'SALOPS_TASK_TRANSITION','ops_task',task_id,f'{row["status"]} -> {p.status}: {p.reason}',who); snapshot_entity(conn,'ops_tasks',task_id,who,f'{row["status"]} -> {p.status}'); conn.commit(); result_row=dict(conn.execute('SELECT * FROM ops_tasks WHERE id=?',(task_id,)).fetchone()); conn.close(); return result_row

@app.get('/api/salops/engagements/{engagement_id}/field-reports')
def list_ops_field_reports(engagement_id:int,request:Request):
    require(request,'read'); _ops_engagement(request,engagement_id); conn=db()
    if protected_member_request(request): rows=[dict(r) for r in conn.execute("SELECT id,engagement_id,assessment_id,report_type,occurred_at,member_summary,status,released_at FROM ops_field_reports WHERE engagement_id=? AND tenant_id=? AND status='Released' ORDER BY id DESC",(engagement_id,tenant_id(request)))]
    else: rows=[dict(r) for r in conn.execute('SELECT * FROM ops_field_reports WHERE engagement_id=? AND tenant_id=? ORDER BY id DESC',(engagement_id,tenant_id(request)))]
    conn.close(); return rows

@app.post('/api/salops/engagements/{engagement_id}/field-reports')
def create_ops_field_report(engagement_id:int,p:OpsFieldReportIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalOPS'); engagement=_ops_engagement(request,engagement_id)
    if engagement['status'] not in ('Active','Demobilizing'): raise HTTPException(409,'Field reports may be submitted only while an engagement is active or demobilizing.')
    tid=tenant_id(request); who=actor(request); occurred=_ops_time(p.occurred_at,'Occurrence time'); conn=db()
    if p.task_id is not None:
        task=conn.execute('SELECT id FROM ops_tasks WHERE id=? AND engagement_id=? AND tenant_id=?',(p.task_id,engagement_id,tid)).fetchone()
        if not task: conn.close(); raise HTTPException(422,'Field report task must belong to the same engagement.')
    ts=now(); cur=conn.execute('INSERT INTO ops_field_reports(tenant_id,engagement_id,assessment_id,task_id,report_type,occurred_at,member_summary,internal_details,status,submitted_by,submitted_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tid,engagement_id,engagement['assessment_id'],p.task_id,p.report_type,occurred,p.member_summary,p.internal_details,'Draft',who,ts,ts)); report_id=cur.lastrowid; audit(conn,'CREATE','ops_field_report',report_id,f'engagement={engagement_id}; type={p.report_type}',who); snapshot_entity(conn,'ops_field_reports',report_id,who,'Draft operational field report submitted'); conn.commit(); row=dict(conn.execute('SELECT * FROM ops_field_reports WHERE id=?',(report_id,)).fetchone()); conn.close(); return row

@app.post('/api/salops/field-reports/{report_id}/release')
def release_ops_field_report(report_id:int,p:OpsFieldReportReleaseIn,request:Request):
    require(request,'write'); require_ops_authority(request); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute("SELECT * FROM ops_field_reports WHERE id=? AND tenant_id=? AND status='Draft'",(report_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Draft operational field report not found')
    assessment_row_for_request(request,row['assessment_id']); ts=now(); conn.execute("UPDATE ops_field_reports SET status='Released',released_by=?,released_at=?,release_reason=?,updated_at=? WHERE id=?",(who,ts,p.reason,ts,report_id)); audit(conn,'SALOPS_FIELD_REPORT_RELEASE','ops_field_report',report_id,p.reason,who); snapshot_entity(conn,'ops_field_reports',report_id,who,'Member-facing field report released'); conn.commit(); result=dict(conn.execute('SELECT * FROM ops_field_reports WHERE id=?',(report_id,)).fetchone()); conn.close(); return result

def _money_cents(value:Decimal) -> int:
    return int((value * Decimal('100')).quantize(Decimal('1'),rounding=ROUND_HALF_UP))

def _money(cents:int) -> str:
    return f'{Decimal(int(cents))/Decimal(100):.2f}'

def _estimate_view(conn,row,include_internal:bool):
    item=dict(row); item['total_amount']=_money(item.pop('total_cents'))
    if include_internal:
        lines=[]
        for source in conn.execute('SELECT * FROM ops_estimate_lines WHERE estimate_id=? AND tenant_id=? ORDER BY id',(item['id'],item['tenant_id'])):
            line=dict(source); line['unit_rate']=_money(line.pop('unit_rate_cents')); line['line_total']=_money(line.pop('line_total_cents')); lines.append(line)
        item['lines']=lines
    else:
        allowed={'id','engagement_id','assessment_id','currency','member_summary','total_amount','status','created_at','submitted_at','decided_at'}
        item={key:value for key,value in item.items() if key in allowed}
    return item

@app.get('/api/salops/engagements/{engagement_id}/financials')
def get_ops_financials(engagement_id:int,request:Request):
    require(request,'read'); _ops_engagement(request,engagement_id); tid=tenant_id(request); conn=db(); member=protected_member_request(request)
    estimate_sql="SELECT * FROM ops_estimates WHERE engagement_id=? AND tenant_id=? AND status IN ('Submitted','Approved') ORDER BY id DESC" if member else 'SELECT * FROM ops_estimates WHERE engagement_id=? AND tenant_id=? ORDER BY id DESC'
    estimates=[_estimate_view(conn,row,not member) for row in conn.execute(estimate_sql,(engagement_id,tid))]
    approved=conn.execute("SELECT COALESCE(SUM(amount_cents),0) total FROM ops_expenses WHERE engagement_id=? AND tenant_id=? AND status='Approved' AND reimbursable=1 AND currency='USD'",(engagement_id,tid)).fetchone()['total']
    current=conn.execute("SELECT total_cents FROM ops_estimates WHERE engagement_id=? AND tenant_id=? AND status='Approved' ORDER BY decided_at DESC,id DESC LIMIT 1",(engagement_id,tid)).fetchone()
    estimated=int(current['total_cents']) if current else 0
    result={'engagement_id':engagement_id,'currency':'USD','approved_estimate_total':_money(estimated),'approved_actual_total':_money(approved),'remaining_estimate':_money(estimated-int(approved)),'estimates':estimates}
    if member:
        result['approved_actual_count']=conn.execute("SELECT COUNT(*) c FROM ops_expenses WHERE engagement_id=? AND tenant_id=? AND status='Approved' AND reimbursable=1 AND currency='USD'",(engagement_id,tid)).fetchone()['c']
    else:
        expenses=[]
        for source in conn.execute('SELECT * FROM ops_expenses WHERE engagement_id=? AND tenant_id=? ORDER BY id DESC',(engagement_id,tid)):
            expense=dict(source); expense['amount']=_money(expense.pop('amount_cents')); expense['reimbursable']=bool(expense['reimbursable']); expenses.append(expense)
        result['expenses']=expenses
    conn.close(); return result

@app.post('/api/salops/engagements/{engagement_id}/estimates')
def create_ops_estimate(engagement_id:int,p:OpsEstimateIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalOPS'); engagement=_ops_engagement(request,engagement_id)
    if engagement['status']=='Closed': raise HTTPException(409,'Estimates cannot be created after engagement closure.')
    tid=tenant_id(request); who=actor(request); ts=now(); calculated=[]; total=0
    for line in p.lines:
        rate=_money_cents(line.unit_rate); line_total=_money_cents(line.quantity*line.unit_rate); total+=line_total
        if total>10_000_000_000: raise HTTPException(422,'Estimate total exceeds the governed limit.')
        calculated.append((line,rate,line_total))
    conn=db(); cur=conn.execute('INSERT INTO ops_estimates(tenant_id,engagement_id,assessment_id,currency,member_summary,internal_basis,total_cents,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,engagement_id,engagement['assessment_id'],p.currency,p.member_summary,p.internal_basis,total,'Draft',who,ts,ts)); estimate_id=cur.lastrowid
    for line,rate,line_total in calculated:
        conn.execute('INSERT INTO ops_estimate_lines(tenant_id,estimate_id,engagement_id,assessment_id,category,description,quantity,unit,unit_rate_cents,line_total_cents,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tid,estimate_id,engagement_id,engagement['assessment_id'],line.category,line.description,format(line.quantity,'f'),line.unit,rate,line_total,who,ts))
    audit(conn,'SALOPS_ESTIMATE_CREATE','ops_estimate',estimate_id,f'engagement={engagement_id}; lines={len(calculated)}; total_cents={total}',who); snapshot_entity(conn,'ops_estimates',estimate_id,who,'Operational estimate created from server-calculated lines'); conn.commit(); row=conn.execute('SELECT * FROM ops_estimates WHERE id=?',(estimate_id,)).fetchone(); result=_estimate_view(conn,row,True); conn.close(); return result

@app.post('/api/salops/estimates/{estimate_id}/transition')
def transition_ops_estimate(estimate_id:int,p:OpsFinancialTransitionIn,request:Request):
    tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute('SELECT * FROM ops_estimates WHERE id=? AND tenant_id=?',(estimate_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Operational estimate not found')
    assessment_row_for_request(request,row['assessment_id']); allowed={'Draft':{'Submitted'},'Submitted':{'Approved','Rejected'}}
    if p.status not in allowed.get(row['status'],set()): conn.close(); raise HTTPException(409,f'Estimate cannot transition from {row["status"]} to {p.status}.')
    if p.status=='Submitted':
        require(request,'write'); require_salus_component_authority(request,'SalOPS')
    else:
        require(request,'decide')
        if role(request)!='Client Executive': require_ops_authority(request)
        if row['submitted_by']==who: conn.close(); raise HTTPException(409,'Estimate approval requires an actor other than the submitter.')
    ts=now(); submitted_by=who if p.status=='Submitted' else row['submitted_by']; submitted_at=ts if p.status=='Submitted' else row['submitted_at']; terminal=p.status in ('Approved','Rejected')
    conn.execute('UPDATE ops_estimates SET status=?,submitted_by=?,submitted_at=?,decided_by=?,decided_at=?,decision_reason=?,updated_at=? WHERE id=?',(p.status,submitted_by,submitted_at,who if terminal else '',ts if terminal else '',p.reason if terminal else '',ts,estimate_id)); audit(conn,'SALOPS_ESTIMATE_TRANSITION','ops_estimate',estimate_id,f'{row["status"]} -> {p.status}: {p.reason}',who); snapshot_entity(conn,'ops_estimates',estimate_id,who,f'{row["status"]} -> {p.status}'); conn.commit(); result=_estimate_view(conn,conn.execute('SELECT * FROM ops_estimates WHERE id=?',(estimate_id,)).fetchone(),not protected_member_request(request)); conn.close(); return result

@app.post('/api/salops/engagements/{engagement_id}/expenses')
def create_ops_expense(engagement_id:int,p:OpsExpenseIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalOPS'); engagement=_ops_engagement(request,engagement_id)
    if engagement['status'] not in ('Mobilizing','Active','Demobilizing'): raise HTTPException(409,'Expenses may be recorded only while an engagement is mobilizing, active, or demobilizing.')
    try: incurred=datetime.fromisoformat(p.incurred_on.replace('Z','+00:00')).date().isoformat()
    except ValueError: raise HTTPException(422,'Incurred date must be an ISO 8601 date or timestamp.')
    tid=tenant_id(request); conn=db()
    if p.task_id is not None and not conn.execute('SELECT id FROM ops_tasks WHERE id=? AND engagement_id=? AND tenant_id=?',(p.task_id,engagement_id,tid)).fetchone(): conn.close(); raise HTTPException(422,'Expense task must belong to the same engagement.')
    if p.evidence_id is not None and not conn.execute('SELECT id FROM evidence WHERE id=? AND assessment_id=?',(p.evidence_id,engagement['assessment_id'])).fetchone(): conn.close(); raise HTTPException(422,'Expense evidence must belong to the engagement assessment.')
    who=actor(request); ts=now(); cents=_money_cents(p.amount); cur=conn.execute('INSERT INTO ops_expenses(tenant_id,engagement_id,assessment_id,task_id,evidence_id,category,description,member_description,vendor,incurred_on,amount_cents,currency,reimbursable,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,engagement_id,engagement['assessment_id'],p.task_id,p.evidence_id,p.category,p.description,p.member_description,p.vendor,incurred,cents,p.currency,1 if p.reimbursable else 0,'Draft',who,ts,ts)); expense_id=cur.lastrowid; audit(conn,'SALOPS_EXPENSE_CREATE','ops_expense',expense_id,f'engagement={engagement_id}; amount_cents={cents}; reimbursable={p.reimbursable}',who); snapshot_entity(conn,'ops_expenses',expense_id,who,'Operational expense created'); conn.commit(); result=dict(conn.execute('SELECT * FROM ops_expenses WHERE id=?',(expense_id,)).fetchone()); result['amount']=_money(result.pop('amount_cents')); result['reimbursable']=bool(result['reimbursable']); conn.close(); return result

@app.post('/api/salops/expenses/{expense_id}/transition')
def transition_ops_expense(expense_id:int,p:OpsFinancialTransitionIn,request:Request):
    require(request,'write'); require_salus_component_authority(request,'SalOPS'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute('SELECT * FROM ops_expenses WHERE id=? AND tenant_id=?',(expense_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Operational expense not found')
    assessment_row_for_request(request,row['assessment_id']); allowed={'Draft':{'Submitted'},'Submitted':{'Approved','Rejected'}}
    if p.status not in allowed.get(row['status'],set()): conn.close(); raise HTTPException(409,f'Expense cannot transition from {row["status"]} to {p.status}.')
    if p.status in ('Approved','Rejected'):
        require_ops_authority(request)
        if row['submitted_by']==who: conn.close(); raise HTTPException(409,'Expense approval requires an actor other than the submitter.')
    ts=now(); submitted_by=who if p.status=='Submitted' else row['submitted_by']; submitted_at=ts if p.status=='Submitted' else row['submitted_at']; terminal=p.status in ('Approved','Rejected')
    conn.execute('UPDATE ops_expenses SET status=?,submitted_by=?,submitted_at=?,decided_by=?,decided_at=?,decision_reason=?,updated_at=? WHERE id=?',(p.status,submitted_by,submitted_at,who if terminal else '',ts if terminal else '',p.reason if terminal else '',ts,expense_id)); audit(conn,'SALOPS_EXPENSE_TRANSITION','ops_expense',expense_id,f'{row["status"]} -> {p.status}: {p.reason}',who); snapshot_entity(conn,'ops_expenses',expense_id,who,f'{row["status"]} -> {p.status}'); conn.commit(); result=dict(conn.execute('SELECT * FROM ops_expenses WHERE id=?',(expense_id,)).fetchone()); result['amount']=_money(result.pop('amount_cents')); result['reimbursable']=bool(result['reimbursable']); conn.close(); return result

def _invoice_date(value:str,label:str) -> str:
    try: return datetime.fromisoformat(value.replace('Z','+00:00')).date().isoformat()
    except ValueError: raise HTTPException(422,f'{label} must be an ISO 8601 date or timestamp.')

def _invoice_view(row,member:bool):
    item=dict(row); item.pop('snapshot_json',None)
    for source,target in (('estimate_total_cents','estimate_total'),('approved_actual_total_cents','approved_actual_total'),('billable_total_cents','billable_total'),('variance_cents','variance')):
        item[target]=_money(item.pop(source))
    if member:
        allowed={'id','engagement_id','assessment_id','statement_number','billing_period_start','billing_period_end','service_summary','currency','estimate_total','approved_actual_total','billable_total','variance','snapshot_sha256','status','released_at'}
        item={key:value for key,value in item.items() if key in allowed}
    return item

def _verify_invoice_snapshot(row,request:Request,conn=None):
    actual=hashlib.sha256(row['snapshot_json'].encode('utf-8')).hexdigest()
    if not secrets.compare_digest(actual,row['snapshot_sha256']):
        if conn is not None: conn.close()
        security_event(request,'INVOICE_READY_INTEGRITY_FAILURE','High',f'statement_id={row["id"]}')
        raise HTTPException(409,'Invoice-ready statement failed integrity verification.')
    return actual

@app.get('/api/salops/engagements/{engagement_id}/invoice-statements')
def list_ops_invoice_statements(engagement_id:int,request:Request):
    require(request,'read'); _ops_engagement(request,engagement_id); tid=tenant_id(request); member=protected_member_request(request); conn=db()
    sql="SELECT * FROM ops_invoice_statements WHERE engagement_id=? AND tenant_id=? AND status='Released' ORDER BY id DESC" if member else 'SELECT * FROM ops_invoice_statements WHERE engagement_id=? AND tenant_id=? ORDER BY id DESC'
    rows=[_invoice_view(row,member) for row in conn.execute(sql,(engagement_id,tid))]; conn.close(); return rows

@app.post('/api/salops/engagements/{engagement_id}/invoice-statements')
def create_ops_invoice_statement(engagement_id:int,p:OpsInvoiceStatementIn,request:Request):
    require(request,'write'); require_ops_authority(request); engagement=_ops_engagement(request,engagement_id)
    if engagement['status']!='Closed': raise HTTPException(409,'Invoice-ready statements require a closed operational engagement.')
    start=_invoice_date(p.billing_period_start,'Billing period start'); end=_invoice_date(p.billing_period_end,'Billing period end')
    if end<start: raise HTTPException(422,'Billing period end must be on or after the start date.')
    tid=tenant_id(request); who=actor(request); conn=db()
    if conn.execute('SELECT id FROM ops_invoice_statements WHERE engagement_id=? AND tenant_id=?',(engagement_id,tid)).fetchone(): conn.close(); raise HTTPException(409,'This engagement already has an invoice-ready statement.')
    estimate=conn.execute("SELECT * FROM ops_estimates WHERE engagement_id=? AND tenant_id=? AND status='Approved' ORDER BY decided_at DESC,id DESC LIMIT 1",(engagement_id,tid)).fetchone()
    if not estimate: conn.close(); raise HTTPException(409,'An approved operational estimate is required.')
    unresolved=conn.execute("SELECT COUNT(*) c FROM ops_expenses WHERE engagement_id=? AND tenant_id=? AND reimbursable=1 AND status IN ('Draft','Submitted')",(engagement_id,tid)).fetchone()['c']
    if unresolved: conn.close(); raise HTTPException(409,'Every reimbursable expense must be approved or rejected before statement generation.')
    expenses=[dict(row) for row in conn.execute("SELECT * FROM ops_expenses WHERE engagement_id=? AND tenant_id=? AND reimbursable=1 AND status='Approved' AND currency='USD' ORDER BY incurred_on,id",(engagement_id,tid))]
    if not expenses: conn.close(); raise HTTPException(409,'At least one approved reimbursable expense is required.')
    actual=sum(int(row['amount_cents']) for row in expenses); estimated=int(estimate['total_cents']); variance=estimated-actual; ts=now(); pending=f'PENDING-{uuid.uuid4().hex}'
    cur=conn.execute('INSERT INTO ops_invoice_statements(tenant_id,engagement_id,assessment_id,statement_number,billing_period_start,billing_period_end,service_summary,currency,estimate_total_cents,approved_actual_total_cents,billable_total_cents,variance_cents,snapshot_json,snapshot_sha256,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,engagement_id,engagement['assessment_id'],pending,start,end,p.service_summary,'USD',estimated,actual,actual,variance,'','', 'Draft',who,ts,ts)); statement_id=cur.lastrowid; number=f'SIR-{tid:04d}-{statement_id:08d}'
    snapshot={'statement_type':'Invoice Ready - Not Issued','statement_number':number,'generated_at':ts,'billing_period':{'start':start,'end':end},'service_summary':p.service_summary,'currency':'USD','engagement':{'id':engagement_id,'title':engagement['title'],'service_type':engagement['service_type'],'planned_start':engagement['planned_start'],'planned_end':engagement['planned_end']},'totals':{'approved_estimate':_money(estimated),'approved_actual':_money(actual),'billable':_money(actual),'variance':_money(variance)},'lines':[{'line_number':index,'category':row['category'],'description':row['member_description'],'incurred_on':row['incurred_on'],'amount':_money(row['amount_cents'])} for index,row in enumerate(expenses,1)]}
    canonical=json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=False); digest=hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    conn.execute('UPDATE ops_invoice_statements SET statement_number=?,snapshot_json=?,snapshot_sha256=? WHERE id=?',(number,canonical,digest,statement_id)); audit(conn,'SALOPS_INVOICE_READY_CREATE','ops_invoice_statement',statement_id,f'engagement={engagement_id}; lines={len(expenses)}; billable_cents={actual}; sha256={digest}',who); snapshot_entity(conn,'ops_invoice_statements',statement_id,who,'Immutable invoice-ready statement generated'); conn.commit(); result=_invoice_view(conn.execute('SELECT * FROM ops_invoice_statements WHERE id=?',(statement_id,)).fetchone(),False); conn.close(); return result

@app.post('/api/salops/invoice-statements/{statement_id}/transition')
def transition_ops_invoice_statement(statement_id:int,p:OpsInvoiceTransitionIn,request:Request):
    require(request,'read'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute('SELECT * FROM ops_invoice_statements WHERE id=? AND tenant_id=?',(statement_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Invoice-ready statement not found')
    assessment_row_for_request(request,row['assessment_id']); _verify_invoice_snapshot(row,request,conn); expected={'Draft':'Reviewed','Reviewed':'Approved','Approved':'Released'}
    if expected.get(row['status'])!=p.status: conn.close(); raise HTTPException(409,f'Invoice-ready statement transition must follow Draft → Reviewed → Approved → Released; current status is {row["status"]}.')
    if p.status=='Reviewed':
        require(request,'write'); require_ops_authority(request)
        if row['created_by']==who: conn.close(); raise HTTPException(409,'Statement review requires an actor other than the creator.')
    elif p.status=='Approved':
        require(request,'decide')
        if role(request) not in {'System Administrator','Assessment Director'}: conn.close(); raise HTTPException(403,f'{role(request)} cannot approve an invoice-ready statement.')
        if who in {row['created_by'],row['reviewed_by']}: conn.close(); raise HTTPException(409,'Statement approval requires an actor independent of creation and review.')
    else:
        require(request,'decide')
        if who!=row['approved_by']: conn.close(); raise HTTPException(409,'The recorded statement approver must authorize release.')
    ts=now(); fields={'Reviewed':('reviewed_by','reviewed_at','review_reason'),'Approved':('approved_by','approved_at','approval_reason'),'Released':('released_by','released_at','release_reason')}[p.status]; conn.execute(f'UPDATE ops_invoice_statements SET status=?,{fields[0]}=?,{fields[1]}=?,{fields[2]}=?,updated_at=? WHERE id=?',(p.status,who,ts,p.reason,ts,statement_id)); audit(conn,'SALOPS_INVOICE_READY_TRANSITION','ops_invoice_statement',statement_id,f'{row["status"]} -> {p.status}: {p.reason}',who); snapshot_entity(conn,'ops_invoice_statements',statement_id,who,f'{row["status"]} -> {p.status}'); conn.commit(); result=_invoice_view(conn.execute('SELECT * FROM ops_invoice_statements WHERE id=?',(statement_id,)).fetchone(),protected_member_request(request)); conn.close(); return result

@app.get('/api/salops/invoice-statements/{statement_id}/snapshot')
def get_ops_invoice_statement_snapshot(statement_id:int,request:Request):
    require(request,'read'); conn=db(); row=conn.execute('SELECT * FROM ops_invoice_statements WHERE id=? AND tenant_id=?',(statement_id,tenant_id(request))).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Invoice-ready statement not found')
    assessment_row_for_request(request,row['assessment_id'])
    if protected_member_request(request) and row['status']!='Released': conn.close(); raise HTTPException(404,'Released invoice-ready statement not found')
    digest=_verify_invoice_snapshot(row,request,conn); payload=json.loads(row['snapshot_json']); conn.close(); response=JSONResponse(payload); response.headers['ETag']=f'"{digest}"'; response.headers['Content-Disposition']=f'inline; filename="{row["statement_number"]}.json"'; return response

@app.get('/api/dashboard')
def dashboard(request:Request):
    require(request,'read'); ids=accessible_assessment_ids(request)
    if ids:
        sweep_overdue_assessments(ids)
        sweep_overdue_decisions(ids)
        sweep_stale_evidence(ids)
        sweep_overdue_accepted_risks(ids)
        sweep_overdue_risk_overrides(ids)
    conn=db(); stats={}; stats['assessments']=len(ids)
    if not ids:
        for k in ['threats','scenarios','capabilities','evidence','gaps','improvements','decisions','high_gaps','pending_decisions','approved_investment','avg_capability_gap','avg_capability_attainment','open_reassessment_triggers','critical_reassessment_triggers','active_accepted_risks','overdue_accepted_risk_reviews','evidence_files','pending_scope_changes','revision_snapshots','pending_improvement_validations','validated_improvements','active_risk_overrides','stale_evidence']: stats[k]=0
        conn.close(); return {'stats':stats,'assessments':[],'tenant_id':tenant_id(request)}
    marks=','.join('?'*len(ids)); P=tuple(ids)
    for table in ['threats','scenarios','capabilities','evidence','gaps','improvements','decisions','accepted_risks','risk_overrides']:
        stats[table]=conn.execute(f'SELECT COUNT(*) c FROM {table} WHERE assessment_id IN ({marks})',P).fetchone()['c']
    stats['high_gaps']=conn.execute(f"SELECT COUNT(*) c FROM gaps WHERE assessment_id IN ({marks}) AND severity IN ('High','Critical') AND status!='Closed'",P).fetchone()['c']
    stats['pending_decisions']=conn.execute(f"SELECT COUNT(*) c FROM improvements WHERE assessment_id IN ({marks}) AND status IN ('Proposed','Under Review')",P).fetchone()['c']
    stats['approved_investment']=conn.execute(f'SELECT COALESCE(SUM(funding_authorized),0) s FROM decisions WHERE assessment_id IN ({marks})',P).fetchone()['s']
    capability_rows=[dict(r) for r in conn.execute(f'SELECT * FROM capabilities WHERE assessment_id IN ({marks})',P)]
    attainments=[capability_effectiveness(r['required_standard'],r['current_performance'],r.get('comparator','>='),r.get('measurement_type','Percentage')) for r in capability_rows]
    stats['avg_capability_attainment']=round(sum(attainments)/len(attainments),1) if attainments else 0.0
    stats['avg_capability_gap']=round(100-stats['avg_capability_attainment'],1) if attainments else 0.0
    stats['open_reassessment_triggers']=conn.execute(f"SELECT COUNT(*) c FROM reassessment_triggers WHERE assessment_id IN ({marks}) AND status='Open'",P).fetchone()['c']
    stats['critical_reassessment_triggers']=conn.execute(f"SELECT COUNT(*) c FROM reassessment_triggers WHERE assessment_id IN ({marks}) AND status='Open' AND severity='Critical'",P).fetchone()['c']
    stats['active_accepted_risks']=conn.execute(f"SELECT COUNT(*) c FROM accepted_risks WHERE assessment_id IN ({marks}) AND status IN ('Active','Under Review')",P).fetchone()['c']
    today=datetime.now(timezone.utc).date().isoformat()
    stats['overdue_accepted_risk_reviews']=conn.execute(f"SELECT COUNT(*) c FROM accepted_risks WHERE assessment_id IN ({marks}) AND status IN ('Active','Under Review') AND review_date<>'' AND review_date<?",P+(today,)).fetchone()['c']
    stats['evidence_files']=conn.execute(f'SELECT COUNT(*) c FROM evidence_attachments WHERE assessment_id IN ({marks})',P).fetchone()['c']
    stats['pending_scope_changes']=conn.execute(f"SELECT COUNT(*) c FROM scope_changes WHERE assessment_id IN ({marks}) AND decision='Pending'",P).fetchone()['c']
    stats['revision_snapshots']=conn.execute(f'SELECT COUNT(*) c FROM entity_versions WHERE assessment_id IN ({marks})',P).fetchone()['c']
    stats['pending_improvement_validations']=conn.execute(f"SELECT COUNT(*) c FROM improvements WHERE assessment_id IN ({marks}) AND status='Complete' AND validation_status='Pending'",P).fetchone()['c']
    stats['validated_improvements']=conn.execute(f"SELECT COUNT(*) c FROM improvements WHERE assessment_id IN ({marks}) AND status='Complete' AND validation_status IN ('Validated','Partially Validated')",P).fetchone()['c']
    stats['active_risk_overrides']=conn.execute(f"""SELECT COUNT(*) c FROM risk_overrides o
      LEFT JOIN evidence e ON e.id=o.evidence_id
      WHERE o.assessment_id IN ({marks}) AND o.status='Active' AND o.review_lifecycle_status='Current'
      AND (o.evidence_id IS NULL OR (e.verification_status='Verified' AND e.lifecycle_status='Current'))""",P).fetchone()['c']
    stats['stale_evidence']=conn.execute(f"SELECT COUNT(*) c FROM evidence WHERE assessment_id IN ({marks}) AND lifecycle_status='Stale'",P).fetchone()['c']
    latest=[dict(r) for r in conn.execute(f'SELECT * FROM assessments WHERE id IN ({marks}) ORDER BY updated_at DESC LIMIT 6',P)]
    if protected_member_request(request): latest=[_member_assessment_view(r) for r in latest]
    conn.close(); return {'stats':stats,'assessments':latest,'tenant_id':tenant_id(request)}

@app.get('/api/intake')
def list_governed_intake(request:Request,limit:int=20):
    require(request,'read'); tid=tenant_id(request); bounded=max(1,min(limit,100)); conn=db()
    rows=[dict(r) for r in conn.execute('SELECT record_key,record_type,title,details,source_context,status,created_by,created_at,version FROM governed_intake WHERE tenant_id=? ORDER BY created_at DESC,id DESC LIMIT ?',(tid,bounded))]
    counts=dict(conn.execute("SELECT COUNT(*) total,SUM(CASE WHEN record_type='Evidence Lead' AND status='Draft' THEN 1 ELSE 0 END) evidence_leads,SUM(CASE WHEN record_type='Discovery' AND status='Draft' THEN 1 ELSE 0 END) discoveries,SUM(CASE WHEN record_type='Decision Input' AND status='Draft' THEN 1 ELSE 0 END) decision_inputs FROM governed_intake WHERE tenant_id=?",(tid,)).fetchone())
    conn.close()
    return {'records':[{'id':r['record_key'],'recordType':r['record_type'],'title':r['title'],'details':r['details'],'sourceContext':r['source_context'],'status':r['status'],'createdByName':r['created_by'],'createdAt':r['created_at'],'version':r['version']} for r in rows],'metrics':{'total':int(counts.get('total') or 0),'evidenceLeads':int(counts.get('evidence_leads') or 0),'discoveries':int(counts.get('discoveries') or 0),'decisionInputs':int(counts.get('decision_inputs') or 0)}}

@app.post('/api/intake')
def create_governed_intake(p:GovernedIntakeIn,request:Request):
    require(request,'write'); tid=tenant_id(request); title=p.title.strip(); details=p.details.strip(); source=p.source_context.strip()
    if not title or not details or not source: raise HTTPException(422,'Type, title, details, and source context are required.')
    key=f'INT-{uuid.uuid4()}'; who=actor(request); ts=now(); conn=db()
    cur=conn.execute("INSERT INTO governed_intake(tenant_id,record_key,record_type,title,details,source_context,status,created_by,created_at,version) VALUES(?,?,?,?,?,?,'Draft',?,?,1)",(tid,key,p.record_type,title,details,source,who,ts)); iid=cur.lastrowid
    audit(conn,'CREATE','governed_intake',iid,f'{p.record_type} captured as governed Draft',who); conn.commit(); conn.close()
    return {'record':{'id':key,'recordType':p.record_type,'title':title,'details':details,'sourceContext':source,'status':'Draft','createdByName':who,'createdAt':ts,'version':1}}

@app.get('/api/{table}')
def list_table(table: str, request:Request, assessment_id: Optional[int]=None):
    require(request,'read'); allowed={'assessments','threats','scenarios','capabilities','evidence','gaps','improvements','decisions','accepted_risks','risk_overrides','reassessment_triggers','audit_log','entity_versions','scope_changes','workflow_events','evidence_attachments'}
    if table not in allowed: raise HTTPException(404)
    table=sql_table_name(table)
    ids=accessible_assessment_ids(request)
    if assessment_id is not None:
        assessment_row_for_request(request,assessment_id); ids=[assessment_id]
    if table=='evidence' and ids: sweep_stale_evidence(ids)
    if table=='accepted_risks' and ids: sweep_overdue_accepted_risks(ids)
    if table=='risk_overrides' and ids: sweep_overdue_risk_overrides(ids)
    if table=='assessments' and ids: sweep_overdue_assessments(ids)
    if table=='decisions' and ids: sweep_overdue_decisions(ids)
    conn=db()
    if table=='audit_log':
        rows=[dict(r) for r in conn.execute('SELECT * FROM audit_log WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]; conn.close(); return rows
    if not ids: conn.close(); return []
    marks=','.join('?'*len(ids)); P=tuple(ids)
    if table=='assessments':
        rows=[dict(r) for r in conn.execute(f'SELECT * FROM assessments WHERE id IN ({marks}) ORDER BY id DESC',P)]
        if protected_member_request(request): rows=[_member_assessment_view(r) for r in rows]
    else: rows=[dict(r) for r in conn.execute(f'SELECT * FROM {table} WHERE assessment_id IN ({marks}) ORDER BY id DESC',P)]
    if table=='capabilities': rows=[capability_summary(r) for r in rows]
    if table=='evidence': rows=[r for r in rows if SENSITIVITY_LEVELS.get(r.get('sensitivity','Standard'),1)<=clearance_level(request)]
    elif table=='evidence_attachments':
        allowed_evidence={r['id'] for r in conn.execute(f"SELECT id FROM evidence WHERE assessment_id IN ({marks}) AND CASE sensitivity WHEN 'Highly Sensitive' THEN 4 WHEN 'Sensitive' THEN 3 WHEN 'Restricted' THEN 2 ELSE 1 END <= ?",P+(clearance_level(request),))}
        rows=[r for r in rows if r['evidence_id'] in allowed_evidence]
    elif table=='entity_versions':
        filtered=[]
        for r in rows:
            if r.get('entity_type')=='evidence':
                try: sens=json.loads(r.get('snapshot_json') or '{}').get('sensitivity','Standard')
                except Exception: sens='Highly Sensitive'
                if SENSITIVITY_LEVELS.get(sens,4)>clearance_level(request): continue
            if protected_member_request(request) and r.get('entity_type')=='assessments':
                try:
                    snapshot=json.loads(r.get('snapshot_json') or '{}'); snapshot=_member_assessment_view(snapshot); r=dict(r); r['snapshot_json']=json.dumps(snapshot,sort_keys=True,separators=(',',':'),default=str)
                except Exception: continue
            filtered.append(r)
        rows=filtered
    conn.close(); return rows

@app.get('/api/trace/{assessment_id}')
def trace(assessment_id:int, request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id); sweep_stale_evidence([assessment_id]); sweep_overdue_risk_overrides([assessment_id]); conn=db()
    a=conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone()
    if not a: raise HTTPException(404)
    data={'assessment':_member_assessment_view(a) if protected_member_request(request) else dict(a),'threats':[]}
    for t in conn.execute('SELECT * FROM threats WHERE assessment_id=?',(assessment_id,)):
        td=dict(t); td['risk_raw']=td['likelihood']*td['vulnerability']*td['consequence']; td['scenarios']=[]
        td['risk_overrides']=[dict(r) for r in conn.execute('SELECT * FROM risk_overrides WHERE threat_id=? ORDER BY id DESC',(t['id'],))]
        active_record=next((r for r in td['risk_overrides'] if r['status']=='Active' and r.get('review_lifecycle_status','Current')=='Current'),None)
        active_evidence=conn.execute('SELECT * FROM evidence WHERE id=?',(active_record['evidence_id'],)).fetchone() if active_record and active_record.get('evidence_id') is not None else None
        td['active_risk_override']=active_record if active_record and (active_record.get('evidence_id') is None or evidence_is_effective(active_evidence)) else None
        td['active_risk_override_record']=active_record
        for s in conn.execute('SELECT * FROM scenarios WHERE threat_id=?',(t['id'],)):
            sd=dict(s); sd['capabilities']=[]
            for c in conn.execute('SELECT * FROM capabilities WHERE scenario_id=?',(s['id'],)):
                cd=capability_summary(c); cd['gap']=cd['performance_gap']
                cd['gaps']=[]
                for g in conn.execute('SELECT * FROM gaps WHERE capability_id=?',(c['id'],)):
                    gd=dict(g); gd['improvements']=[]
                    for i in conn.execute('SELECT * FROM improvements WHERE gap_id=?',(g['id'],)):
                        idd=dict(i); idd['decisions']=[]
                        for d in conn.execute('SELECT * FROM decisions WHERE improvement_id=?',(i['id'],)):
                            dd=dict(d); ar=conn.execute('SELECT * FROM accepted_risks WHERE decision_id=?',(d['id'],)).fetchone(); dd['accepted_risk']=dict(ar) if ar else None; idd['decisions'].append(dd)
                        gd['improvements'].append(idd)
                    cd['gaps'].append(gd)
                sd['capabilities'].append(cd)
            td['scenarios'].append(sd)
        data['threats'].append(td)
    conn.close(); return data

def insert_model_in_transaction(conn,table:str,payload:BaseModel,user_name:str='prototype-user',extra:dict|None=None):
    data=payload.model_dump()
    if extra: data.update(extra)
    ts=now(); data['created_at']=ts
    data['updated_at']=ts
    if table=='improvements':
        score,_=improvement_priority(data); data['priority_score']=score
    cols=','.join(data.keys()); qs=','.join('?'*len(data))
    cur=conn.execute(f'INSERT INTO {table}({cols}) VALUES({qs})',tuple(data.values()))
    audit_data=dict(data)
    if table=='assessments':
        for field in ('industry_defaults_snapshot_json','industry_profile_applied_by'): audit_data.pop(field,None)
    audit(conn,'CREATE',table[:-1] if table.endswith('s') else table,cur.lastrowid,json.dumps(audit_data,default=str)[:500],user_name)
    snapshot_entity(conn,table,cur.lastrowid,user_name,'Record created')
    return dict(conn.execute(f'SELECT * FROM {table} WHERE id=?',(cur.lastrowid,)).fetchone())

def insert_model(table:str, payload:BaseModel, user_name:str='prototype-user', extra:dict|None=None):
    conn=db()
    try:
        row=insert_model_in_transaction(conn,table,payload,user_name,extra)
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

@app.post('/api/assessments')
def create_assessment(p:AssessmentIn, request:Request):
    require(request,'write')
    try: validate_requested_package_path(p.requested_package_level,p.requested_scope_band,p.requested_access_variant)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    start_date=_normalize_date(p.start_date,'Assessment start date')
    target_completion=_normalize_date(p.target_completion,'Assessment target completion date')
    reassessment_date=_normalize_date(p.reassessment_date,'Assessment reassessment date')
    profile=None; defaults='{}'; applied_at=''
    if p.industry_profile_id is not None:
        profile,_,items=_selected_industry_profile(request,p.industry_profile_id); defaults=_industry_defaults(items); applied_at=now()
    result=insert_model('assessments',p,actor(request),extra={
        'tenant_id':tenant_id(request),
        'status':'Draft',
        'start_date':start_date,
        'target_completion':target_completion,
        'reassessment_date':reassessment_date,
        'reassessment_lifecycle_status':'Current',
        'reassessment_overdue_reason':'',
        'reassessment_overdue_at':'',
        'last_reassessment_review_at':'',
        'last_reassessment_review_by':'',
        'industry_profile_id':profile['id'] if profile else None,
        'industry_profile_key_snapshot':profile['profile_key'] if profile else '',
        'industry_profile_version_snapshot':profile['version_no'] if profile else None,
        'industry_profile_name_snapshot':profile['name'] if profile else '',
        'industry_member_summary_snapshot':profile['member_summary'] if profile else '',
        'industry_defaults_snapshot_json':defaults,
        'industry_profile_applied_by':actor(request) if profile else '',
        'industry_profile_applied_at':applied_at,
        'scope_locked':0,
        'version':1,
    })
    return _member_assessment_view(result) if protected_member_request(request) else result

@app.post('/api/assessments/{assessment_id}/package-agreements')
async def upload_package_agreement(assessment_id:int,request:Request,file:UploadFile=File(...)):
    require_package_commercial_candidate(); require(request,'decide')
    require_salus_component_authority(request,'Package agreement')
    if role(request) not in ('System Administrator','Assessment Director'):
        raise HTTPException(403,'An authorized Salus reviewer must register the agreement.')
    assessment_row_for_request(request,assessment_id)
    content=await file.read(5*1024*1024+1)
    if len(content)>5*1024*1024: raise HTTPException(413,'Agreement PDF exceeds 5 MB.')
    if not content.startswith(b'%PDF-'): raise HTTPException(422,'The agreement must be a PDF.')
    original=safe_filename(file.filename or 'package-agreement.pdf')
    if not original.lower().endswith('.pdf'): raise HTTPException(422,'The agreement filename must end in .pdf.')
    scan=scan_bytes(content,original)
    if not scan['ok'] or scan['status']!='Clean':
        security_event(request,'PACKAGE_AGREEMENT_REJECTED','High' if scan['status']=='Infected' else 'Medium',f'status={scan["status"]}')
        raise HTTPException(422 if scan['status']=='Infected' else 503,'The agreement could not pass the file security check.')
    tid=tenant_id(request); digest=hashlib.sha256(content).hexdigest(); conn=db()
    existing=conn.execute('SELECT * FROM package_agreement_artifacts WHERE tenant_id=? AND assessment_id=? AND content_sha256=?',(tid,assessment_id,digest)).fetchone()
    if existing:
        conn.close()
        if existing['scan_status']!='Clean':
            raise HTTPException(409,'The stored agreement has not passed the file security check.')
        return {k:existing[k] for k in ('id','assessment_id','original_name','content_sha256','size_bytes','uploaded_at')}
    stored=f'tenant-{tid}/assessment-{assessment_id}/package-agreements/{uuid.uuid4().hex}_{digest[:16]}.pdf'
    try:
        storage.put_bytes(stored,content)
        retention_until=(_iso_now_dt()+timedelta(days=RETENTION_DEFAULT_DAYS)).replace(microsecond=0).isoformat().replace('+00:00','Z') if RETENTION_DEFAULT_DAYS>0 else ''
        uploaded_at=now()
        cur=conn.execute('INSERT INTO package_agreement_artifacts(tenant_id,assessment_id,original_name,stored_name,content_sha256,size_bytes,scan_status,retention_until,legal_hold,uploaded_by,uploaded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,assessment_id,original,stored,digest,len(content),scan['status'],retention_until,0,actor(request),uploaded_at))
        audit(conn,'PACKAGE_AGREEMENT','assessment',assessment_id,f'artifact_id={cur.lastrowid}; sha256={digest}',actor(request)); conn.commit()
        return {'id':cur.lastrowid,'assessment_id':assessment_id,'original_name':original,'content_sha256':digest,'size_bytes':len(content),'uploaded_at':uploaded_at}
    except Exception as exc:
        conn.rollback()
        try: storage.delete(stored)
        except Exception: pass
        if isinstance(exc,HTTPException): raise
        error_id=secrets.token_hex(8); record_internal_failure('package agreement upload',error_id,exc)
        raise HTTPException(503,f'Agreement storage is unavailable. Reference: {error_id}') from exc
    finally:
        conn.close()

@app.get('/api/package-agreements/{artifact_id}/download')
def download_package_agreement(artifact_id:int,request:Request):
    require(request,'read')
    conn=db(); item=conn.execute('SELECT * FROM package_agreement_artifacts WHERE id=? AND tenant_id=?',(artifact_id,tenant_id(request))).fetchone()
    if not item: conn.close(); raise HTTPException(404,'Agreement not found.')
    assessment_row_for_request(request,item['assessment_id'])
    member=protected_member_request(request)
    if member and (role(request)!='Client Executive' or auth_context(request)['auth_mode'] not in ('session','oidc')):
        conn.close(); raise HTTPException(403,'Only the signed-in Member decision owner may retrieve this agreement.')
    quote=conn.execute('SELECT * FROM package_quote_versions WHERE tenant_id=? AND assessment_id=? AND agreement_artifact_id=? ORDER BY version_no DESC LIMIT 1',(tenant_id(request),item['assessment_id'],artifact_id)).fetchone()
    if member and not quote: conn.close(); raise HTTPException(404,'The agreement is not attached to a Member quote.')
    if quote:
        try:
            verified_package_quote(conn,quote,request)
            if quote['level']>1:
                current=conn.execute('SELECT * FROM assessments WHERE id=? AND tenant_id=?',
                    (item['assessment_id'],tenant_id(request))).fetchone()
                verified_quote_predecessor_link(conn,quote,request,current)
        except Exception: conn.close(); raise
    if item['scan_status']!='Clean':
        conn.close(); raise HTTPException(409,'The agreement has not passed the file security check.')
    conn.close()
    try: data=storage.get_bytes(item['stored_name'])
    except FileNotFoundError: raise HTTPException(404,'Stored agreement is missing.')
    except Exception as exc:
        security_event(request,'PACKAGE_AGREEMENT_READ_FAILURE','High',type(exc).__name__)
        raise HTTPException(503,'Agreement storage is unavailable.') from exc
    if hashlib.sha256(data).hexdigest()!=item['content_sha256']:
        security_event(request,'PACKAGE_AGREEMENT_HASH_MISMATCH','Critical',f'artifact_id={artifact_id}')
        raise HTTPException(409,'Agreement integrity verification failed.')
    conn=db()
    try:
        if member:
            ctx=auth_context(request)
            conn.execute('INSERT INTO package_agreement_downloads(tenant_id,assessment_id,quote_id,agreement_artifact_id,member_user_id,content_sha256,downloaded_at) VALUES(?,?,?,?,?,?,?)',(tenant_id(request),item['assessment_id'],quote['id'],artifact_id,ctx['user_id'],item['content_sha256'],now()))
        audit(conn,'PACKAGE_AGREEMENT_DOWNLOAD','assessment',item['assessment_id'],f'artifact_id={artifact_id}; sha256={item["content_sha256"]}',actor(request))
        conn.commit()
    finally:
        conn.close()
    return Response(content=data,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{safe_filename(item["original_name"])}"','X-Content-SHA256':item['content_sha256']})

@app.get('/api/assessments/{assessment_id}/package-quote')
def get_package_quote(assessment_id:int,request:Request):
    require(request,'read'); assessment=assessment_row_for_request(request,assessment_id)
    conn=db(); quote=conn.execute('SELECT * FROM package_quote_versions WHERE tenant_id=? AND assessment_id=? ORDER BY version_no DESC LIMIT 1',(tenant_id(request),assessment_id)).fetchone()
    if not quote: conn.close(); raise HTTPException(404,'No fixed package quote has been approved.')
    try:
        verified_package_quote(conn,quote,request)
        predecessor_valid=True
        if quote['level']>1:
            try: verified_quote_predecessor_link(conn,quote,request,assessment)
            except HTTPException: predecessor_valid=False
    except Exception: conn.close(); raise
    acceptance=conn.execute('SELECT * FROM package_acceptances WHERE tenant_id=? AND assessment_id=? AND quote_id=?',(tenant_id(request),assessment_id,quote['id'])).fetchone()
    signer_valid=True
    if acceptance:
        try: verified_member_authority_review(conn,quote,acceptance['member_user_id'])
        except HTTPException: signer_valid=False
    conn.close(); result=dict(quote)
    scope_matches=(bool(quote['assessment_scope_sha256'])
        and quote['assessment_version']==assessment['version']
        and quote['covered_operation']==assessment['covered_operation']
        and quote['exclusions']==assessment['exclusions']
        and quote['level']==assessment['requested_package_level']
        and quote['band']==assessment['requested_scope_band']
        and quote['variant']==assessment['requested_access_variant']
        and quote['assessment_scope_sha256']==assessment_scope_digest(assessment))
    if not predecessor_valid: result['status']='Predecessor changed — review required'
    elif acceptance and not signer_valid: result['status']='Signer proof changed — review required'
    elif acceptance and not quote['assessment_scope_sha256']: result['status']='Authorized terms — scope proof requires review'
    elif acceptance and not scope_matches: result['status']='Authorized original scope — amendment required'
    elif acceptance: result['status']='Authorized'
    elif not quote['assessment_scope_sha256']: result['status']='Scope proof missing — new quote required'
    elif not scope_matches: result['status']='Scope changed — new quote required'
    elif date.fromisoformat(quote['valid_until']) < datetime.now(timezone.utc).date(): result['status']='Expired — new quote required'
    else: result['status']='Quoted'
    result['accepted_at']=acceptance['accepted_at'] if acceptance else ''
    if protected_member_request(request):
        for key in ('access_eligibility_basis','approved_by','scope_basis'):
            result.pop(key,None)
    return result

@app.post('/api/assessments/{assessment_id}/advisor-package-handoff')
def claim_advisor_package_handoff(assessment_id:int,p:PackageHandoffClaimIn,request:Request):
    """Record a claimed prospect receipt; Salus has not approved its scope or authority."""
    require_package_commercial_candidate()
    require_protected_member_authority(request,'advisor_package_handoff')
    ctx=auth_context(request)
    if ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id'):
        raise HTTPException(403,'A signed-in Protected Member decision owner is required.')
    assessment_row_for_request(request,assessment_id)
    conn=db()
    try:
        handoff=conn.execute('SELECT * FROM advisor_package_handoffs WHERE claim_token_sha256=?',(_hash_token(p.claim_code),)).fetchone()
        if not handoff or handoff['status']!='Pending' or handoff['claim_expires_at']<=now():
            raise HTTPException(409,'This package handoff is unavailable or expired.')
        source=conn.execute('SELECT status,deleted_at FROM advisor_public_sessions WHERE session_key=?',(handoff['session_key'],)).fetchone()
        account=conn.execute('SELECT status,email_verified_at FROM advisor_public_accounts WHERE account_key=?',(handoff['account_key'],)).fetchone()
        submission=conn.execute('SELECT submission_key FROM advisor_public_submissions WHERE session_key=?',(handoff['session_key'],)).fetchone()
        snapshot=conn.execute('SELECT content_sha256 FROM advisor_public_scope_receipt_snapshots WHERE session_key=? AND revision_no=?',(handoff['session_key'],handoff['revision_no'])).fetchone()
        if (not source or source['status']!='Submitted' or source['deleted_at'] or not account
            or account['status']!='Active' or not account['email_verified_at'] or not submission
            or submission['submission_key']!=handoff['submission_key'] or not snapshot
            or snapshot['content_sha256']!=handoff['receipt_sha256']):
            raise HTTPException(409,'The consented receipt is no longer available for a package handoff.')
        other=conn.execute("SELECT 1 FROM advisor_package_handoffs WHERE submission_key=? AND status IN ('Claimed','Reviewed') LIMIT 1",(handoff['submission_key'],)).fetchone()
        if other: raise HTTPException(409,'This receipt has already been claimed for review.')
        claimed_at=now()
        updated=conn.execute("UPDATE advisor_package_handoffs SET status='Claimed',tenant_id=?,assessment_id=?,member_user_id=?,claimed_at=? WHERE handoff_key=? AND status='Pending'",(tenant_id(request),assessment_id,ctx['user_id'],claimed_at,handoff['handoff_key']))
        if updated.rowcount!=1:
            raise HTTPException(409,'This package handoff was already claimed.')
        audit(conn,'ADVISOR_PACKAGE_HANDOFF_CLAIM','assessment',assessment_id,f'handoff_key={handoff["handoff_key"]}; receipt_revision={handoff["revision_no"]}',actor(request))
        conn.commit()
        return {'handoff_key':handoff['handoff_key'],'status':'Awaiting Salus identity, authority and scope review','receipt_id':handoff['receipt_id'],'receipt_revision':handoff['revision_no']}
    finally:
        conn.close()

@app.get('/api/assessments/{assessment_id}/advisor-package-handoffs')
def list_advisor_package_handoffs_for_review(assessment_id:int,request:Request):
    """Show only tenant-scoped claimed receipts to authorized Salus reviewers."""
    require_package_commercial_candidate()
    require(request,'read'); require_salus_component_authority(request,'Advisor package handoff')
    if role(request) not in ('System Administrator','Assessment Director'):
        raise HTTPException(403,'An authorized Salus reviewer must inspect this handoff.')
    assessment_row_for_request(request,assessment_id)
    conn=db()
    try:
        rows=conn.execute('''SELECT handoff_key,status,receipt_id,revision_no,claimed_at,reviewed_at,
                            reviewed_assessment_version FROM advisor_package_handoffs
                            WHERE tenant_id=? AND assessment_id=? AND status IN ('Claimed','Reviewed')
                            ORDER BY claimed_at DESC LIMIT 100''',(tenant_id(request),assessment_id)).fetchall()
        return {'handoffs':[dict(row) for row in rows]}
    finally:
        conn.close()

@app.post('/api/assessments/{assessment_id}/advisor-package-handoff/{handoff_key}/review')
def review_advisor_package_handoff(assessment_id:int,handoff_key:str,p:PackageHandoffReviewIn,request:Request):
    """Record a Salus scope match for quote preparation, never contract authority."""
    require_package_commercial_candidate()
    require(request,'decide'); require_salus_component_authority(request,'Advisor package handoff')
    if role(request) not in ('System Administrator','Assessment Director'):
        raise HTTPException(403,'An authorized Salus reviewer must check the package handoff.')
    assessment=assessment_row_for_request(request,assessment_id)
    if int(assessment['version'])!=p.assessment_version:
        raise HTTPException(409,'The requested scope changed; review the current assessment before linking a receipt.')
    conn=db()
    try:
        handoff=conn.execute('SELECT * FROM advisor_package_handoffs WHERE handoff_key=? AND tenant_id=? AND assessment_id=?',
            (handoff_key,tenant_id(request),assessment_id)).fetchone()
        if not handoff or handoff['status']!='Claimed':
            raise HTTPException(409,'This receipt has not been claimed for Salus review.')
        source=conn.execute('''SELECT s.status,s.deleted_at,a.status account_status,a.email_verified_at,
                     aa.identifiable_retention_consent,aa.detailed_assessment_acknowledged,
                     b.submission_key,p.profile_sha256,p.profile_json,p.package_json
                 FROM advisor_public_sessions s
                 JOIN advisor_public_accounts a ON a.account_key=?
                 JOIN advisor_public_account_assessments aa ON aa.account_key=a.account_key AND aa.session_key=s.session_key
                 JOIN advisor_public_submissions b ON b.session_key=s.session_key
                 JOIN advisor_public_service_profiles p ON p.submission_key=b.submission_key
                 WHERE s.session_key=?''',(handoff['account_key'],handoff['session_key'])).fetchone()
        snapshot=conn.execute('''SELECT content_sha256 FROM advisor_public_scope_receipt_snapshots
            WHERE session_key=? AND revision_no=?''',(handoff['session_key'],handoff['revision_no'])).fetchone()
        latest=conn.execute('''SELECT MAX(revision_no) revision_no FROM advisor_public_report_identity_revisions
            WHERE session_key=?''',(handoff['session_key'],)).fetchone()
        member=conn.execute('SELECT tenant_id,role,status FROM users WHERE id=?',(handoff['member_user_id'],)).fetchone()
        if (not source or source['status']!='Submitted' or source['deleted_at'] or
            source['account_status']!='Active' or not source['email_verified_at'] or
            not source['identifiable_retention_consent'] or not source['detailed_assessment_acknowledged'] or
            source['submission_key']!=handoff['submission_key'] or
            source['profile_sha256']!=handoff['profile_sha256'] or
            hashlib.sha256(source['profile_json'].encode('utf-8')).hexdigest()!=source['profile_sha256'] or
            hashlib.sha256(source['package_json'].encode('utf-8')).hexdigest()!=handoff['package_sha256'] or
            not snapshot or
            snapshot['content_sha256']!=handoff['receipt_sha256'] or not latest or
            latest['revision_no']!=handoff['revision_no'] or not member or
            member['tenant_id']!=tenant_id(request) or member['role']!='Client Executive' or member['status']!='Active'):
            raise HTTPException(409,'The prospect consent, Member claim or exact receipt changed; request a new review.')
        source_receipt=str((json.loads(source['package_json']).get('scope_receipt') or {}).get('receipt_id') or '')
        if source_receipt!=handoff['receipt_id']:
            raise HTTPException(409,'The saved receipt identity changed; request a new review.')
        basis=json.dumps({
            'organization_match':p.organization_match_basis.strip(),
            'covered_boundary':p.covered_boundary_basis.strip(),
            'decision_role':p.decision_role_basis.strip(),
        },sort_keys=True,separators=(',',':'))
        reviewed_at=now()
        updated=conn.execute('''UPDATE advisor_package_handoffs
            SET status='Reviewed',reviewed_at=?,reviewed_by=?,review_basis=?,reviewed_assessment_version=?
            WHERE handoff_key=? AND status='Claimed' ''',
            (reviewed_at,actor(request),basis,p.assessment_version,handoff_key))
        if updated.rowcount!=1: raise HTTPException(409,'The handoff state changed during review.')
        audit(conn,'ADVISOR_PACKAGE_HANDOFF_REVIEW','assessment',assessment_id,
            f'handoff_key={handoff_key}; receipt_revision={handoff["revision_no"]}; assessment_version={p.assessment_version}',actor(request))
        conn.commit()
        return {'handoff_key':handoff_key,'status':'Reviewed for quote preparation only',
                'receipt_id':handoff['receipt_id'],'receipt_revision':handoff['revision_no'],
                'assessment_version':p.assessment_version,'reviewed_at':reviewed_at}
    finally:
        conn.close()

@app.get('/api/assessments/{assessment_id}/advisor-package-handoff/{handoff_key}/review-packet')
def advisor_package_handoff_review_packet(assessment_id:int,handoff_key:str,request:Request):
    require_package_commercial_candidate()
    require(request,'read'); require_salus_component_authority(request,'Advisor package handoff')
    if role(request) not in ('System Administrator','Assessment Director'):
        raise HTTPException(403,'An authorized Salus reviewer must inspect this handoff.')
    assessment=assessment_row_for_request(request,assessment_id)
    conn=db()
    try:
        handoff=conn.execute('SELECT * FROM advisor_package_handoffs WHERE handoff_key=? AND tenant_id=? AND assessment_id=?',
            (handoff_key,tenant_id(request),assessment_id)).fetchone()
        if not handoff or handoff['status'] not in ('Claimed','Reviewed'):
            raise HTTPException(404,'Handoff is unavailable for review.')
        source=conn.execute('''SELECT s.organization_name,p.package_json
            FROM advisor_public_submissions s
            JOIN advisor_public_service_profiles p ON p.submission_key=s.submission_key
            JOIN advisor_public_sessions a ON a.session_key=s.session_key
            WHERE s.session_key=? AND s.submission_key=? AND a.status='Submitted' AND a.deleted_at='' ''',
            (handoff['session_key'],handoff['submission_key'])).fetchone()
        if not source or hashlib.sha256(source['package_json'].encode('utf-8')).hexdigest()!=handoff['package_sha256']:
            raise HTTPException(409,'The prospect scope changed; a new review is required.')
        receipt=(json.loads(source['package_json']).get('scope_receipt') or {})
        if str(receipt.get('receipt_id') or '')!=handoff['receipt_id']:
            raise HTTPException(409,'The receipt identity changed; a new review is required.')
        return {
            'handoff_key':handoff_key,'status':handoff['status'],
            'prospect_receipt':{'id':handoff['receipt_id'],'revision':handoff['revision_no'],
                                'sha256':handoff['receipt_sha256'],
                                'organization':source['organization_name'],
                                'requested_boundary':receipt.get('requested_boundary',''),
                                'requested_location':receipt.get('requested_location',''),
                                'possible_path':receipt.get('possible_path','')},
            'member_request':{'assessment_id':assessment_id,'assessment_version':assessment['version'],
                              'organization':assessment['organization'],
                              'covered_operation':assessment['covered_operation'],
                              'exclusions':assessment['exclusions'],
                              'level':assessment['requested_package_level'],
                              'band':assessment['requested_scope_band']},
            'review_limit':'A matching name or receipt does not prove contracting authority or authorize a purchase.'
        }
    finally:
        conn.close()

@app.get('/api/assessments/{assessment_id}/advisor-package-handoff/{handoff_key}/receipt.pdf')
def advisor_package_handoff_review_receipt(assessment_id:int,handoff_key:str,request:Request):
    require_package_commercial_candidate()
    require(request,'read'); require_salus_component_authority(request,'Advisor package handoff')
    if role(request) not in ('System Administrator','Assessment Director'):
        raise HTTPException(403,'An authorized Salus reviewer must inspect this receipt.')
    assessment_row_for_request(request,assessment_id)
    conn=db()
    try:
        handoff=conn.execute('SELECT * FROM advisor_package_handoffs WHERE handoff_key=? AND tenant_id=? AND assessment_id=?',
            (handoff_key,tenant_id(request),assessment_id)).fetchone()
        if not handoff or handoff['status'] not in ('Claimed','Reviewed'):
            raise HTTPException(404,'Handoff is unavailable for review.')
        snapshot=conn.execute('''SELECT item_id,content_sha256,content_size
            FROM advisor_public_scope_receipt_snapshots WHERE session_key=? AND revision_no=?''',
            (handoff['session_key'],handoff['revision_no'])).fetchone()
        source=conn.execute('SELECT status,deleted_at FROM advisor_public_sessions WHERE session_key=?',
            (handoff['session_key'],)).fetchone()
        if not snapshot or snapshot['content_sha256']!=handoff['receipt_sha256'] or not source or source['status']!='Submitted' or source['deleted_at']:
            raise HTTPException(409,'The saved receipt is no longer available for review.')
        import public_protection_advisor as advisor
        try:
            content=advisor.read_member_pdf(str(snapshot['item_id']),str(snapshot['content_sha256']),int(snapshot['content_size']))
        except advisor.M365ReportError as exc:
            raise HTTPException(503,'The saved receipt could not be verified.') from exc
        download_name=safe_filename(f'Salus-Scope-Receipt-{handoff["receipt_id"]}-R{handoff["revision_no"]}.pdf')
        return Response(content=content,media_type='application/pdf',headers={
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Content-Disposition':f'attachment; filename="{download_name}"',
            'X-Content-SHA256':handoff['receipt_sha256']})
    finally:
        conn.close()

@app.post('/api/assessments/{assessment_id}/package-quote')
def approve_package_quote(assessment_id:int,p:PackageQuoteIn,request:Request):
    require_package_commercial_candidate()
    require(request,'decide'); require_salus_component_authority(request,'Package quote')
    if role(request) not in ('System Administrator','Assessment Director'):
        raise HTTPException(403,'An authorized Salus commercial reviewer must approve the quote.')
    assessment=assessment_row_for_request(request,assessment_id)
    if int(assessment['version'])!=p.assessment_version:
        raise HTTPException(409,'The assessment scope changed; review the current version before quoting.')
    if p.level>1 and not p.predecessor_qualification_id:
        raise HTTPException(409,'Level 2 and 3 quotes require an exact qualified prior package.')
    if p.level==1 and p.predecessor_qualification_id:
        raise HTTPException(422,'Level 1 is the first package and has no predecessor.')
    if not p.separate_services_excluded:
        raise HTTPException(422,'Separately proposed SalOPS services must be excluded from this package fee.')
    data=p.model_dump(); predecessor_id=data.pop('predecessor_qualification_id')
    data['covered_operation']=data['covered_operation'].strip()
    if data['source_receipt_id']:
        raise HTTPException(409,'Protection Advisor receipt linkage is not yet verified; leave the source receipt blank until the consented handoff is available.')
    try:
        _normalize_date(data['valid_until'],'Quote validity date',required=True)
        if data['start_date']: _normalize_date(data['start_date'],'Package start date',required=True)
        if data['delivery_date']: _normalize_date(data['delivery_date'],'Package delivery date',required=True)
        validate_quote(data,assessment)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    if data['covered_operation']!=assessment['covered_operation'] or data['exclusions'].strip()!=assessment['exclusions']:
        raise HTTPException(409,'The quoted operation and exclusions must match the recorded assessment boundary.')
    data['assessment_id']=assessment_id; data['tenant_id']=tenant_id(request)
    conn=db()
    try:
        agreement=conn.execute('SELECT * FROM package_agreement_artifacts WHERE id=? AND tenant_id=? AND assessment_id=?',(p.agreement_artifact_id,tenant_id(request),assessment_id)).fetchone()
        if not agreement or agreement['content_sha256'].lower()!=p.agreement_sha256.lower():
            raise HTTPException(409,'Register and verify the exact agreement PDF before quoting.')
        if agreement['scan_status']!='Clean':
            raise HTTPException(409,'The agreement has not passed the file security check.')
        try: agreement_bytes=storage.get_bytes(agreement['stored_name'])
        except Exception as exc: raise HTTPException(503,'The stored agreement is unavailable.') from exc
        if hashlib.sha256(agreement_bytes).hexdigest()!=agreement['content_sha256']:
            raise HTTPException(409,'The stored agreement failed integrity verification.')
        lock_package_assessment(conn,assessment_id)
        current=conn.execute('SELECT * FROM assessments WHERE id=? AND tenant_id=?',(assessment_id,tenant_id(request))).fetchone()
        if not current or current['version']!=p.assessment_version or current['covered_operation']!=data['covered_operation'] or current['exclusions']!=data['exclusions']:
            raise HTTPException(409,'The assessment scope changed while preparing this quote. Review the current boundary and agreement.')
        try: validate_quote(data,current)
        except ValueError as exc: raise HTTPException(409,'The requested package path changed while preparing this quote.') from exc
        predecessor=(verified_package_predecessor(conn,predecessor_id,request,current,p.level)
            if p.level>1 else None)
        data['assessment_scope_sha256']=assessment_scope_digest(current)
        accepted=conn.execute('SELECT id FROM package_acceptances WHERE tenant_id=? AND assessment_id=? LIMIT 1',(tenant_id(request),assessment_id)).fetchone()
        if accepted:
            raise HTTPException(409,'An authorized package cannot be requoted without a reviewed amendment workflow.')
        version=conn.execute('SELECT COALESCE(MAX(version_no),0)+1 n FROM package_quote_versions WHERE tenant_id=? AND assessment_id=?',(tenant_id(request),assessment_id)).fetchone()['n']
        data['version_no']=version
        digest=quote_digest(data)
        columns=list(data)+['content_sha256','approved_by','approved_at']
        integer_flags={'capacity_confirmed','access_eligibility_confirmed','separate_services_excluded'}
        values=[int(data[key]) if key in integer_flags else data[key] for key in data]
        values += [digest,actor(request),now()]
        cur=conn.execute(f"INSERT INTO package_quote_versions({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",values)
        if predecessor:
            link_record={'assessment_id':assessment_id,'quote_id':cur.lastrowid,
                'qualification_id':predecessor['id'],
                'qualification_sha256':predecessor['record_sha256']}
            link_digest=hashlib.sha256(json.dumps(link_record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            conn.execute('''INSERT INTO package_quote_predecessor_links
                (tenant_id,assessment_id,quote_id,qualification_id,qualification_sha256,record_sha256,linked_at)
                VALUES(?,?,?,?,?,?,?)''',(tenant_id(request),assessment_id,cur.lastrowid,
                predecessor['id'],predecessor['record_sha256'],link_digest,now()))
        audit(conn,'PACKAGE_QUOTE','assessment',assessment_id,f'quote_id={cur.lastrowid}; version={version}; sha256={digest}',actor(request))
        conn.commit(); row=dict(conn.execute('SELECT * FROM package_quote_versions WHERE id=?',(cur.lastrowid,)).fetchone())
        return row
    finally:
        conn.rollback()
        conn.close()

@app.post('/api/assessments/{assessment_id}/package-member-authority')
def review_package_member_authority(assessment_id:int,p:PackageMemberAuthorityReviewIn,request:Request):
    """Bind one Salus-reviewed Member signer to an exact quote."""
    require_package_commercial_candidate()
    require(request,'decide'); require_salus_component_authority(request,'Member signer review')
    ctx=auth_context(request)
    if (ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id')
            or role(request) not in ('System Administrator','Assessment Director')):
        raise HTTPException(403,'A named authorized Salus reviewer must verify Member signing authority.')
    assessment_row_for_request(request,assessment_id)
    conn=db()
    try:
        lock_package_assessment(conn,assessment_id)
        quote=conn.execute('SELECT * FROM package_quote_versions WHERE id=? AND tenant_id=? AND assessment_id=?',
            (p.quote_id,tenant_id(request),assessment_id)).fetchone()
        if not quote: raise HTTPException(404,'Package quote not found.')
        verified_package_quote(conn,quote,request)
        current=conn.execute('SELECT * FROM assessments WHERE id=? AND tenant_id=?',
            (assessment_id,tenant_id(request))).fetchone()
        latest=conn.execute('SELECT MAX(version_no) n FROM package_quote_versions WHERE tenant_id=? AND assessment_id=?',
            (tenant_id(request),assessment_id)).fetchone()['n']
        if (not current or quote['version_no']!=latest or quote['assessment_version']!=current['version']
                or quote['assessment_scope_sha256']!=assessment_scope_digest(current)):
            raise HTTPException(409,'Review the current quote and boundary before verifying a signer.')
        member=conn.execute('SELECT id FROM users WHERE id=? AND tenant_id=? AND role=? AND status=?',
            (p.member_user_id,tenant_id(request),'Client Executive','Active')).fetchone()
        if not member: raise HTTPException(409,'Select an active Client Executive in this Protected Member account.')
        basis=p.authority_basis.strip(); reference=p.evidence_reference.strip()
        if len(basis)<12 or len(reference)<8:
            raise HTTPException(422,'Record the authority basis and evidence reference.')
        prior=conn.execute('SELECT * FROM package_member_authority_reviews WHERE quote_id=?',
            (p.quote_id,)).fetchone()
        if prior:
            if (prior['record_sha256']==_member_authority_review_digest(prior)
                    and prior['member_user_id']==p.member_user_id
                    and prior['authority_basis']==basis and prior['evidence_reference']==reference):
                return {'id':prior['id'],'quote_id':p.quote_id,'record_sha256':prior['record_sha256'],
                    'status':'Signer reviewed','idempotent':True}
            raise HTTPException(409,'This quote already has a different signer review; issue a new quote version.')
        accepted=conn.execute('SELECT id FROM package_acceptances WHERE quote_id=?',(p.quote_id,)).fetchone()
        if accepted: raise HTTPException(409,'An accepted quote cannot receive a new signer review.')
        record={'tenant_id':tenant_id(request),'assessment_id':assessment_id,'quote_id':p.quote_id,
            'member_user_id':p.member_user_id,'authority_basis':basis,'evidence_reference':reference,
            'reviewed_by_user_id':ctx['user_id'],'reviewed_at':now()}
        digest=_member_authority_review_digest(record)
        cur=conn.execute('''INSERT INTO package_member_authority_reviews
            (tenant_id,assessment_id,quote_id,member_user_id,authority_basis,evidence_reference,
             reviewed_by_user_id,reviewed_at,record_sha256) VALUES(?,?,?,?,?,?,?,?,?)''',
            tuple(record.values())+(digest,))
        audit(conn,'PACKAGE_MEMBER_AUTHORITY','assessment',assessment_id,
            f'quote_id={p.quote_id}; signer_user_id={p.member_user_id}; review_sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'quote_id':p.quote_id,'record_sha256':digest,
            'status':'Signer reviewed','idempotent':False}
    finally:
        conn.rollback(); conn.close()

@app.post('/api/assessments/{assessment_id}/package-acceptance')
def accept_package_quote(assessment_id:int,p:PackageAcceptanceIn,request:Request):
    require_package_commercial_candidate()
    require_protected_member_authority(request,'package_acceptance')
    ctx=auth_context(request)
    if ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id'):
        raise HTTPException(403,'A verified Protected Member sign-in is required to accept a package quote.')
    assessment_row_for_request(request,assessment_id)
    conn=db()
    try:
        lock_package_assessment(conn,assessment_id)
        assessment=conn.execute('SELECT * FROM assessments WHERE id=? AND tenant_id=?',(assessment_id,tenant_id(request))).fetchone()
        if not assessment: raise HTTPException(404,'Assessment not found.')
        prior=conn.execute('SELECT * FROM package_acceptances WHERE tenant_id=? AND assessment_id=? AND idempotency_key=?',(tenant_id(request),assessment_id,p.idempotency_key)).fetchone()
        if prior:
            prior_quote=conn.execute('SELECT * FROM package_quote_versions WHERE id=? AND tenant_id=? AND assessment_id=?',(prior['quote_id'],tenant_id(request),assessment_id)).fetchone()
            if prior_quote:
                verified_package_quote(conn,prior_quote,request)
                if prior_quote['level']>1:
                    verified_quote_predecessor_link(conn,prior_quote,request,assessment)
            if (prior_quote and prior['quote_id']==p.quote_id and prior['quote_sha256']==p.quote_sha256
                and prior['agreement_sha256']==p.agreement_sha256.lower() and prior['member_user_id']==ctx['user_id']
                and prior['member_authority_basis']==p.member_authority_basis.strip()):
                verified_member_authority_review(conn,prior_quote,ctx['user_id'])
                return {'status':'Authorized','quote_id':p.quote_id,'accepted_at':prior['accepted_at'],'idempotent':True}
            raise HTTPException(409,'This acceptance key was already used for another decision.')
        quote=conn.execute('SELECT * FROM package_quote_versions WHERE id=? AND tenant_id=? AND assessment_id=?',(p.quote_id,tenant_id(request),assessment_id)).fetchone()
        if not quote: raise HTTPException(404,'Package quote not found.')
        verified_package_quote(conn,quote,request)
        verified_member_authority_review(conn,quote,ctx['user_id'])
        if quote['level']>1: verified_quote_predecessor_link(conn,quote,request,assessment)
        if quote['source_receipt_id']:
            raise HTTPException(409,'This quote has an unverified Protection Advisor receipt and cannot be accepted.')
        latest=conn.execute('SELECT MAX(version_no) n FROM package_quote_versions WHERE tenant_id=? AND assessment_id=?',(tenant_id(request),assessment_id)).fetchone()['n']
        if (quote['version_no']!=latest or quote['assessment_version']!=assessment['version']
            or quote['covered_operation']!=assessment['covered_operation']
            or quote['exclusions']!=assessment['exclusions']
            or quote['level']!=assessment['requested_package_level']
            or quote['band']!=assessment['requested_scope_band']
            or quote['variant']!=assessment['requested_access_variant']
            or not quote['assessment_scope_sha256']
            or quote['assessment_scope_sha256']!=assessment_scope_digest(assessment)):
            raise HTTPException(409,'This quote has been superseded by a changed scope or a newer quote.')
        if quote['content_sha256']!=p.quote_sha256 or quote['agreement_sha256'].lower()!=p.agreement_sha256.lower():
            raise HTTPException(409,'The quote or agreement version does not match the accepted copy.')
        if date.fromisoformat(quote['valid_until']) < datetime.now(timezone.utc).date():
            raise HTTPException(409,'This quote has expired; request a current written quote.')
        existing=conn.execute('SELECT id FROM package_acceptances WHERE quote_id=?',(p.quote_id,)).fetchone()
        if existing: raise HTTPException(409,'This quote was already accepted.')
        download=conn.execute('SELECT id FROM package_agreement_downloads WHERE tenant_id=? AND assessment_id=? AND quote_id=? AND agreement_artifact_id=? AND member_user_id=? AND content_sha256=? ORDER BY id DESC LIMIT 1',(tenant_id(request),assessment_id,p.quote_id,quote['agreement_artifact_id'],ctx['user_id'],quote['agreement_sha256'].lower())).fetchone()
        if not download: raise HTTPException(409,'Download the exact agreement PDF before accepting this quote.')
        ts=now(); cur=conn.execute('INSERT INTO package_acceptances(tenant_id,assessment_id,quote_id,quote_sha256,agreement_sha256,member_user_id,agreement_download_id,member_authority_basis,idempotency_key,accepted_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(tenant_id(request),assessment_id,p.quote_id,p.quote_sha256,p.agreement_sha256.lower(),ctx['user_id'],download['id'],p.member_authority_basis.strip(),p.idempotency_key,ts))
        audit(conn,'PACKAGE_ACCEPT','assessment',assessment_id,f'acceptance_id={cur.lastrowid}; quote_id={p.quote_id}; quote_sha256={p.quote_sha256}',actor(request))
        conn.commit()
        return {'status':'Authorized','quote_id':p.quote_id,'accepted_at':ts,'idempotent':False}
    finally:
        conn.rollback()
        conn.close()

def authorized_package_intake(conn,assessment_id:int,request:Request):
    assessment=conn.execute('SELECT * FROM assessments WHERE id=? AND tenant_id=?',(assessment_id,tenant_id(request))).fetchone()
    accepted=conn.execute('''SELECT q.*,a.member_user_id accepted_member_user_id FROM package_acceptances a JOIN package_quote_versions q ON q.id=a.quote_id
        WHERE a.tenant_id=? AND a.assessment_id=? ORDER BY a.id DESC LIMIT 1''',(tenant_id(request),assessment_id)).fetchone()
    if not assessment or not accepted: raise HTTPException(409,'The package intake opens after an authorized agreement.')
    verified_package_quote(conn,accepted,request)
    verified_member_authority_review(conn,accepted,accepted['accepted_member_user_id'])
    if accepted['level']>1: verified_quote_predecessor_link(conn,accepted,request,assessment)
    if (not accepted['assessment_scope_sha256'] or accepted['assessment_scope_sha256']!=assessment_scope_digest(assessment)
        or accepted['assessment_version']!=assessment['version']):
        raise HTTPException(409,'The authorized scope changed; review the written package before requesting more records.')
    return accepted

@app.get('/api/assessments/{assessment_id}/package-intake')
def get_package_intake(assessment_id:int,request:Request):
    require_package_commercial_candidate(); require(request,'read'); assessment_row_for_request(request,assessment_id)
    if protected_member_request(request) and (role(request)!='Client Executive' or auth_context(request)['auth_mode'] not in ('session','oidc')):
        raise HTTPException(403,'A signed-in Protected Member decision owner is required.')
    conn=db()
    try:
        quote=authorized_package_intake(conn,assessment_id,request)
        rows=[dict(r) for r in conn.execute('''SELECT id,item_key,catalog_version,title,decision_use,requested_form,
            acceptable_equivalent,request_reason,status,requested_at,responded_at FROM package_intake_requests
            WHERE tenant_id=? AND assessment_id=? AND quote_id=? ORDER BY id''',(tenant_id(request),assessment_id,quote['id']))]
        uploads=[dict(r) for r in conn.execute('''SELECT id,intake_request_id,original_name,content_sha256,size_bytes,uploaded_at
            FROM package_intake_uploads WHERE tenant_id=? AND assessment_id=? AND quote_id=? ORDER BY id''',
            (tenant_id(request),assessment_id,quote['id']))]
        return {'quote_id':quote['id'],'catalog_version':PACKAGE_INTAKE_VERSION,'items':rows,
                'uploads':uploads,
                'catalog':package_intake_catalog() if role(request) in ('System Administrator','Assessment Director') else [],
                'notice':'Only selected items are requested. Do not upload personal directories, credentials, medical records or sensitive annexes. Ask Salus for separate protected handling when needed.'}
    finally: conn.close()

@app.post('/api/assessments/{assessment_id}/package-intake')
def select_package_intake(assessment_id:int,p:PackageIntakeSelectionIn,request:Request):
    require_package_commercial_candidate(); require(request,'decide'); require_salus_component_authority(request,'Package intake')
    if role(request) not in ('System Administrator','Assessment Director'):
        raise HTTPException(403,'Only an authorized Salus reviewer may tailor the records request.')
    assessment_row_for_request(request,assessment_id)
    keys=list(dict.fromkeys(p.item_keys))
    if len(keys)!=len(p.item_keys) or any(key not in PACKAGE_INTAKE_ITEMS for key in keys):
        raise HTTPException(422,'Select distinct items from the approved Level 1 records menu.')
    if len(p.request_reason.strip())<12:
        raise HTTPException(422,'State why these records are needed for the agreed decision.')
    conn=db()
    try:
        lock_package_assessment(conn,assessment_id)
        quote=authorized_package_intake(conn,assessment_id,request)
        for key in keys:
            title,purpose,requested,equivalent=PACKAGE_INTAKE_ITEMS[key]
            conn.execute('''INSERT INTO package_intake_requests
                (tenant_id,assessment_id,quote_id,item_key,catalog_version,title,decision_use,requested_form,acceptable_equivalent,request_reason,status,requested_by,requested_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,'Requested',?,?) ON CONFLICT(tenant_id,assessment_id,quote_id,item_key) DO NOTHING''',
                (tenant_id(request),assessment_id,quote['id'],key,PACKAGE_INTAKE_VERSION,title,purpose,requested,equivalent,p.request_reason.strip(),actor(request),now()))
        audit(conn,'PACKAGE_INTAKE_REQUEST','assessment',assessment_id,f'quote_id={quote["id"]}; keys={",".join(keys)}',actor(request))
        conn.commit()
        return {'quote_id':quote['id'],'requested_keys':keys,'status':'Requested'}
    finally:
        conn.rollback();conn.close()

@app.patch('/api/assessments/{assessment_id}/package-intake/{item_id}')
def respond_package_intake(assessment_id:int,item_id:int,p:PackageIntakeResponseIn,request:Request):
    require_package_commercial_candidate(); require_protected_member_authority(request,'package_intake_response')
    ctx=auth_context(request)
    if ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id'):
        raise HTTPException(403,'A signed-in Protected Member decision owner is required.')
    assessment_row_for_request(request,assessment_id)
    conn=db()
    try:
        lock_package_assessment(conn,assessment_id)
        quote=authorized_package_intake(conn,assessment_id,request)
        item=conn.execute('SELECT * FROM package_intake_requests WHERE id=? AND tenant_id=? AND assessment_id=? AND quote_id=?',(item_id,tenant_id(request),assessment_id,quote['id'])).fetchone()
        if not item: raise HTTPException(404,'Requested item not found in this package.')
        if conn.execute('SELECT 1 FROM package_intake_uploads WHERE tenant_id=? AND intake_request_id=? LIMIT 1',
            (tenant_id(request),item_id)).fetchone():
            raise HTTPException(409,'A file was already received for this item. Ask Salus to reconcile it before marking the item unavailable.')
        if item['status']!=p.status:
            conn.execute('UPDATE package_intake_requests SET status=?,response_user_id=?,responded_at=? WHERE id=?',(p.status,ctx['user_id'],now(),item_id))
            audit(conn,'PACKAGE_INTAKE_RESPONSE','assessment',assessment_id,f'item_id={item_id}; status={p.status}',actor(request))
            conn.commit()
        return {'item_id':item_id,'status':p.status}
    finally:
        conn.rollback();conn.close()

PACKAGE_INTAKE_ALLOWED_EXTENSIONS={'.pdf','.docx','.xlsx','.csv','.txt','.png','.jpg','.jpeg'}

@app.post('/api/assessments/{assessment_id}/package-intake/{item_id}/files')
async def upload_package_intake_file(assessment_id:int,item_id:int,request:Request,file:UploadFile=File(...)):
    require_package_commercial_candidate(); require_protected_member_authority(request,'package_intake_upload')
    ctx=auth_context(request)
    if ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id'):
        raise HTTPException(403,'A signed-in Protected Member decision owner is required.')
    assessment_row_for_request(request,assessment_id)
    original=safe_filename(file.filename or '')
    if Path(original).suffix.lower() not in PACKAGE_INTAKE_ALLOWED_EXTENSIONS:
        raise HTTPException(422,'Use a PDF, Office document, CSV, text file or image for this records request.')
    content=await file.read(MAX_ATTACHMENT_BYTES+1)
    if not content or len(content)>MAX_ATTACHMENT_BYTES:
        raise HTTPException(413,'The file must be nonempty and no larger than 25 MB.')
    scan=scan_bytes(content,original)
    if not scan['ok'] or scan['status']!='Clean':
        security_event(request,'PACKAGE_INTAKE_UPLOAD_REJECTED','High' if scan['status']=='Infected' else 'Medium',
            f'status={scan["status"]}')
        raise HTTPException(422 if scan['status']=='Infected' else 503,'The file could not pass the security check.')
    digest=hashlib.sha256(content).hexdigest(); tid=tenant_id(request); conn=db(); stored=''
    try:
        lock_package_assessment(conn,assessment_id)
        quote=authorized_package_intake(conn,assessment_id,request)
        item=conn.execute('''SELECT id,status FROM package_intake_requests
            WHERE id=? AND tenant_id=? AND assessment_id=? AND quote_id=?''',
            (item_id,tid,assessment_id,quote['id'])).fetchone()
        if not item: raise HTTPException(404,'This item was not requested for the authorized package.')
        if item['status'] in ('Not held','Not known','Prefer to discuss'):
            raise HTTPException(409,'Review this item with Salus before sending a file.')
        existing=conn.execute('''SELECT id,intake_request_id,original_name,content_sha256,size_bytes,scan_status,uploaded_at
            FROM package_intake_uploads WHERE tenant_id=? AND intake_request_id=? AND content_sha256=?''',
            (tid,item_id,digest)).fetchone()
        if existing:
            if existing['scan_status']!='Clean':
                raise HTTPException(409,'The stored file has not passed the security check.')
            return {key:existing[key] for key in
                ('id','intake_request_id','original_name','content_sha256','size_bytes','uploaded_at')}
        file_count=conn.execute('SELECT COUNT(*) AS n FROM package_intake_uploads WHERE tenant_id=? AND intake_request_id=?',
            (tid,item_id)).fetchone()['n']
        if file_count>=5:
            raise HTTPException(409,'This item has five files. Ask Salus to review before sending more.')
        stored=f'tenant-{tid}/assessment-{assessment_id}/package-intake/quote-{quote["id"]}/item-{item_id}/{uuid.uuid4().hex}_{digest[:16]}'
        storage.put_bytes(stored,content)
        retention_until=(_iso_now_dt()+timedelta(days=max(1,RETENTION_DEFAULT_DAYS))).replace(microsecond=0).isoformat().replace('+00:00','Z')
        uploaded_at=now()
        cur=conn.execute('''INSERT INTO package_intake_uploads
            (tenant_id,assessment_id,quote_id,intake_request_id,member_user_id,original_name,stored_name,
             content_sha256,size_bytes,scan_status,retention_until,legal_hold,uploaded_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (tid,assessment_id,quote['id'],item_id,ctx['user_id'],original,stored,digest,len(content),
             scan['status'],retention_until,0,uploaded_at))
        conn.execute('UPDATE package_intake_requests SET status=?,response_user_id=?,responded_at=? WHERE id=?',
            ('Provided',ctx['user_id'],uploaded_at,item_id))
        audit(conn,'PACKAGE_INTAKE_FILE','assessment',assessment_id,
            f'item_id={item_id}; file_id={cur.lastrowid}; sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'intake_request_id':item_id,'original_name':original,
                'content_sha256':digest,'size_bytes':len(content),'uploaded_at':uploaded_at}
    except Exception as exc:
        conn.rollback()
        if stored:
            try: storage.delete(stored)
            except Exception: pass
        if isinstance(exc,HTTPException): raise
        error_id=secrets.token_hex(8); record_internal_failure('package intake upload',error_id,exc)
        raise HTTPException(503,f'Package intake storage is unavailable. Reference: {error_id}') from exc
    finally: conn.close()

@app.get('/api/package-intake-files/{file_id}/download')
def download_package_intake_file(file_id:int,request:Request):
    require_package_commercial_candidate(); require(request,'read')
    conn=db()
    try:
        row=conn.execute('SELECT * FROM package_intake_uploads WHERE id=? AND tenant_id=?',
            (file_id,tenant_id(request))).fetchone()
        if not row: raise HTTPException(404,'Requested file not found.')
        assessment_row_for_request(request,row['assessment_id'])
        if protected_member_request(request):
            require_protected_member_authority(request,'package_intake_download')
            if auth_context(request)['auth_mode'] not in ('session','oidc'):
                raise HTTPException(403,'A signed-in Protected Member decision owner is required.')
        quote=authorized_package_intake(conn,row['assessment_id'],request)
        if row['quote_id']!=quote['id']:
            raise HTTPException(409,'This file belongs to a previous package scope.')
        if row['scan_status']!='Clean':
            raise HTTPException(409,'The file has not passed the security check.')
    finally: conn.close()
    try: data=storage.get_bytes(row['stored_name'])
    except FileNotFoundError: raise HTTPException(404,'Stored file is missing.')
    except Exception as exc:
        security_event(request,'PACKAGE_INTAKE_STORAGE_READ_FAILURE','High',type(exc).__name__)
        raise HTTPException(503,'Package intake storage is unavailable.') from exc
    if hashlib.sha256(data).hexdigest()!=row['content_sha256']:
        security_event(request,'PACKAGE_INTAKE_HASH_MISMATCH','Critical',f'file_id={file_id}')
        raise HTTPException(409,'File integrity verification failed.')
    conn=db()
    try:
        audit(conn,'PACKAGE_INTAKE_DOWNLOAD','assessment',row['assessment_id'],
            f'file_id={file_id}; sha256={row["content_sha256"]}',actor(request))
        conn.commit()
    finally: conn.close()
    return Response(content=data,media_type='application/octet-stream',headers={
        'Content-Disposition':f'attachment; filename="{safe_filename(row["original_name"])}"',
        'X-Content-SHA256':row['content_sha256'],'X-Content-Type-Options':'nosniff'})

@app.patch('/api/package-intake-files/{file_id}/retention')
def extend_package_intake_file_retention(file_id:int,p:PackageReportRetentionIn,request:Request):
    require_package_commercial_candidate(); require(request,'decide')
    if role(request) not in {'System Administrator','Assessment Director'}:
        raise HTTPException(403,'Package intake retention requires a Salus decision owner.')
    if p.retention_until is None and p.legal_hold is None:
        raise HTTPException(422,'Extend retention or place a legal hold.')
    new_until=None
    if p.retention_until is not None:
        try:
            parsed=datetime.fromisoformat(p.retention_until.replace('Z','+00:00'))
            if parsed.tzinfo is None: raise ValueError('Timezone required')
            if parsed.astimezone(timezone.utc)<=_iso_now_dt():
                raise HTTPException(422,'Extended retention must end in the future.')
            new_until=parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        except ValueError as exc: raise HTTPException(422,'Use an explicit UTC retention timestamp.') from exc
    conn=db()
    try:
        row=conn.execute('SELECT * FROM package_intake_uploads WHERE id=? AND tenant_id=?',
            (file_id,tenant_id(request))).fetchone()
        if not row: raise HTTPException(404,'Package intake file not found.')
        assessment_row_for_request(request,row['assessment_id'])
        require_package_report_assignment(request,row['assessment_id'])
        lock_package_assessment(conn,row['assessment_id'])
        if new_until and row['retention_until'] and new_until<row['retention_until']:
            raise HTTPException(409,'Package intake retention cannot be shortened through this route.')
        target_until=new_until or row['retention_until']
        target_hold=1 if p.legal_hold else row['legal_hold']
        if target_until!=row['retention_until'] or target_hold!=row['legal_hold']:
            conn.execute('UPDATE package_intake_uploads SET retention_until=?,legal_hold=? WHERE id=?',
                (target_until,target_hold,file_id))
            audit(conn,'PACKAGE_INTAKE_RETENTION','assessment',row['assessment_id'],
                f'file_id={file_id}; retention_until={target_until}; legal_hold={target_hold}; reason={p.reason.strip()}',actor(request))
            conn.commit()
        return {'id':file_id,'retention_until':target_until,'legal_hold':bool(target_hold),
            'notice':'This route cannot delete a file or clear a legal hold.'}
    finally: conn.close()

PACKAGE_REPORT_PRODUCTS={'SalINTEL','SalTHIRA','SalOPS','SalCAPA'}
PACKAGE_REPORT_DRAFT_ROLES={'System Administrator','Assessment Director','Lead Assessor'}
PACKAGE_REPORT_QA_KEYS=(
    'level_status_and_handoffs','evidence_and_provenance','uncertainty_and_contradictions',
    'protected_member_isolation','confidentiality_and_audience','approved_title_and_brand',
    'arial_headings_times_body','cover_blank_second_page_page_x_of_y','accessibility',
    'all_rendered_pages','docx_pdf_print_parity','method_and_template_version',
    'qualified_review_and_release_authority')
PACKAGE_REPORT_REVIEW_KEYS=('all_pages','native_word','accessibility','format_parity','member_isolation')

def require_package_report_assignment(request:Request,assessment_id:int):
    ctx=auth_context(request)
    if ctx['auth_mode'] not in ('session','oidc') or role(request)=='System Administrator': return
    conn=db()
    try:
        allowed=conn.execute('SELECT 1 FROM assessment_access WHERE user_id=? AND assessment_id=?',(ctx.get('user_id'),assessment_id)).fetchone()
    finally: conn.close()
    if not allowed: raise HTTPException(403,'An explicit assessment assignment is required for working reports.')

def check_package_docx(content:bytes):
    if len(content)>10*1024*1024: raise HTTPException(413,'Draft Word report exceeds 10 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names=set(archive.namelist())
            if not {'[Content_Types].xml','word/document.xml'}<=names or any('vbaproject.bin' in name.lower() for name in names):
                raise HTTPException(422,'The draft must be a macro-free Word .docx document.')
            if sum(item.file_size for item in archive.infolist())>150*1024*1024:
                raise HTTPException(413,'The draft Word report expands beyond the review limit.')
            if archive.testzip() is not None: raise HTTPException(422,'The draft Word report is damaged.')
    except (zipfile.BadZipFile, OSError) as exc:
        raise HTTPException(422,'The draft must be a valid Word .docx document.') from exc

def inspect_package_qa_archive(content:bytes,report_sha256:str):
    """Bind a rendered PDF and page log to a draft; do not qualify the review."""
    from pypdf import PdfReader
    if len(content)>50*1024*1024: raise HTTPException(413,'Report QA archive exceeds 50 MB.')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos=archive.infolist()
            if len(infos)!=2 or {item.filename for item in infos}!={'manifest.json','rendered.pdf'}:
                raise HTTPException(422,'Report QA archive must contain only manifest.json and rendered.pdf.')
            if any(item.file_size>50*1024*1024 for item in infos) or sum(item.file_size for item in infos)>60*1024*1024:
                raise HTTPException(413,'Report QA archive expands beyond its review limit.')
            if archive.testzip() is not None: raise HTTPException(422,'Report QA archive is damaged.')
            manifest_bytes=archive.read('manifest.json');pdf=archive.read('rendered.pdf')
    except (zipfile.BadZipFile,OSError,RuntimeError) as exc:
        raise HTTPException(422,'Report QA archive is not a readable ZIP file.') from exc
    if len(manifest_bytes)>250_000 or not pdf.startswith(b'%PDF-'):
        raise HTTPException(422,'Report QA manifest or PDF is invalid.')
    try:
        manifest=json.loads(manifest_bytes)
        if not isinstance(manifest,dict) or set(manifest)!={
                'report_sha256','pdf_sha256','renderer','pages','native_word','accessibility','parity','notes'}:
            raise ValueError('manifest fields')
        if manifest['report_sha256']!=report_sha256 or manifest['pdf_sha256']!=hashlib.sha256(pdf).hexdigest():
            raise ValueError('source or PDF hash')
        if (not isinstance(manifest['renderer'],str) or not 3<=len(manifest['renderer'].strip())<=120
                or not isinstance(manifest['notes'],str) or len(manifest['notes'])>4000):
            raise ValueError('renderer or notes')
        if any(manifest[key] not in ('Pending','Checked') for key in ('native_word','accessibility','parity')):
            raise ValueError('review states')
        reader=PdfReader(io.BytesIO(pdf),strict=True)
        count=len(reader.pages)
        if not 3<=count<=1000 or not isinstance(manifest['pages'],list) or len(manifest['pages'])!=count:
            raise ValueError('page count')
        for number,(item,page) in enumerate(zip(manifest['pages'],reader.pages),1):
            if (not isinstance(item,dict) or set(item)!={'page','checked_full_size','note'}
                    or type(item['page']) is not int or item['page']!=number
                    or type(item['checked_full_size']) is not bool or not isinstance(item['note'],str)
                    or len(item['note'])>500):
                raise ValueError('page inspection log')
            text_content=page.extract_text() or ''
            if number==2 and text_content.strip(): raise ValueError('second page is not blank')
            if number!=2 and not re.search(rf'page\s+{number}\s+of\s+{count}',text_content,re.IGNORECASE):
                raise ValueError('page count footer')
    except (ValueError,KeyError,TypeError,AttributeError,IndexError) as exc:
        raise HTTPException(422,'Report QA evidence does not match the exact Word file, PDF pages or page log.') from exc
    except Exception as exc:
        raise HTTPException(422,'Report QA PDF could not be inspected.') from exc
    return json.dumps(manifest,sort_keys=True,separators=(',',':')),pdf

@app.get('/api/assessments/{assessment_id}/package-reports')
def list_package_product_reports(assessment_id:int,request:Request):
    require_package_commercial_candidate();require(request,'read'); assessment_row_for_request(request,assessment_id)
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES: raise HTTPException(403,'Working reports are restricted to assigned Salus report owners.')
    require_package_report_assignment(request,assessment_id)
    conn=db()
    try:
        rows=[dict(row) for row in conn.execute('''SELECT id,quote_id,product,report_identity,display_title,version_no,
          assessment_scope_sha256,method_version,template_version,original_name,content_sha256,size_bytes,
          status,retention_until,legal_hold,disposition_status,created_by,created_at,supersedes_id FROM package_product_report_versions
          WHERE tenant_id=? AND assessment_id=? ORDER BY product,version_no''',(tenant_id(request),assessment_id))]
        return {'reports':rows,'notice':'Draft registration is not qualified review, issue, or predecessor proof.'}
    finally: conn.close()

@app.get('/api/assessments/{assessment_id}/package-release-readiness')
def package_release_readiness(assessment_id:int,request:Request):
    """Show exact draft gates; this endpoint never authorizes report issue."""
    require_package_commercial_candidate();require(request,'read')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES:
        raise HTTPException(403,'Package release review is restricted to Salus report owners.')
    assessment_row_for_request(request,assessment_id)
    require_package_report_assignment(request,assessment_id)
    conn=db()
    try:
        quote=authorized_package_intake(conn,assessment_id,request)
        tid=tenant_id(request);reports={};blockers=[]
        for product in ('SalINTEL','SalTHIRA','SalOPS','SalCAPA'):
            row=conn.execute('''SELECT * FROM package_product_report_versions WHERE tenant_id=? AND assessment_id=?
                AND product=? ORDER BY version_no DESC LIMIT 1''',(tid,assessment_id,product)).fetchone()
            if not row:
                blockers.append(f'{product}: a working Word report is missing.')
                continue
            reports[product]=row
            if (row['quote_id']!=quote['id'] or row['assessment_scope_sha256']!=quote['assessment_scope_sha256']):
                blockers.append(f'{product}: the report belongs to an older package boundary.')
            try: saved=storage.get_bytes(row['stored_name'])
            except Exception:
                blockers.append(f'{product}: the saved Word file is unavailable.')
            else:
                if hashlib.sha256(saved).hexdigest()!=row['content_sha256']:
                    security_event(request,'PACKAGE_PREFLIGHT_HASH_MISMATCH','High',f'report_id={row["id"]}')
                    blockers.append(f'{product}: the saved Word file failed its integrity check.')
            matrix=conn.execute('''SELECT matrix_status,content_sha256,checks_json,summary,record_sha256 FROM package_report_conformance
                WHERE tenant_id=? AND report_id=? ORDER BY id DESC LIMIT 1''',(tid,row['id'])).fetchone()
            if not matrix or matrix['content_sha256']!=row['content_sha256']:
                blockers.append(f'{product}: the exact-version Charter check is missing.')
            else:
                try:
                    checks=json.loads(matrix['checks_json'])
                    expected=hashlib.sha256(json.dumps({'report_id':row['id'],
                        'content_sha256':matrix['content_sha256'],'checks':checks,
                        'summary':matrix['summary']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    expected_status='Open' if any(item['status']=='Pending' for item in checks.values()) else 'Marked'
                    valid=(set(checks)==set(PACKAGE_REPORT_QA_KEYS) and expected==matrix['record_sha256']
                        and expected_status==matrix['matrix_status'])
                except (ValueError,TypeError,KeyError,AttributeError): valid=False
                if not valid:
                    blockers.append(f'{product}: the saved Charter check failed its integrity check.')
                elif matrix['matrix_status']!='Marked':
                    blockers.append(f'{product}: the Charter check still has pending items.')
            qa=conn.execute('''SELECT * FROM package_report_qa_evidence WHERE tenant_id=? AND report_id=?
                ORDER BY id DESC LIMIT 1''',(tid,row['id'])).fetchone()
            if not qa or qa['content_sha256']!=row['content_sha256']:
                blockers.append(f'{product}: exact-version rendered QA evidence is missing.')
            else:
                try:
                    manifest=json.loads(qa['manifest_json'])
                    canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'))
                    valid=(manifest.get('report_sha256')==row['content_sha256']
                        and hashlib.sha256(canonical.encode()).hexdigest()==qa['manifest_sha256']
                        and qa['status']=='Submitted')
                    if valid:
                        archive=storage.get_bytes(qa['stored_name'])
                        valid=hashlib.sha256(archive).hexdigest()==qa['archive_sha256']
                except Exception:
                    valid=False
                if not valid:
                    blockers.append(f'{product}: rendered QA evidence failed its integrity check.')
                elif (any(not page.get('checked_full_size') for page in manifest.get('pages',[]))
                        or any(manifest.get(key)!='Checked' for key in ('native_word','accessibility','parity'))):
                    blockers.append(f'{product}: rendered page, accessibility or format parity review is pending.')
                review=conn.execute('''SELECT * FROM package_report_qa_reviews WHERE tenant_id=?
                    AND report_id=? AND evidence_id=? ORDER BY id DESC LIMIT 1''',(tid,row['id'],qa['id'])).fetchone()
                if not review:
                    blockers.append(f'{product}: independent exact-version QA review is missing.')
                else:
                    try:
                        review_checks=json.loads(review['checks_json'])
                        review_record={key:review[key] for key in ('report_id','evidence_id','content_sha256',
                            'archive_sha256','decision','qualification_basis','review_note','reviewer_user_id')}
                        review_record['checks']=review_checks
                        valid_review=(review['content_sha256']==row['content_sha256']
                            and review['archive_sha256']==qa['archive_sha256']
                            and review['reviewer_user_id']!=qa['submitted_user_id']
                            and set(review_checks)==set(PACKAGE_REPORT_REVIEW_KEYS)
                            and hashlib.sha256(json.dumps(review_record,sort_keys=True,separators=(',',':')).encode()).hexdigest()==review['record_sha256'])
                    except (ValueError,TypeError,KeyError,AttributeError): valid_review=False
                    if not valid_review:
                        blockers.append(f'{product}: the independent QA review failed its integrity check.')
                    elif review['decision']!='Reviewed' or not all(review_checks.values()):
                        blockers.append(f'{product}: independent QA returned the report for correction.')
        capa=reports.get('SalCAPA')
        if capa:
            comparison=conn.execute('''SELECT * FROM package_report_reconciliations
                WHERE tenant_id=? AND salcapa_report_id=? ORDER BY id DESC LIMIT 1''',(tid,capa['id'])).fetchone()
            if not comparison or comparison['salcapa_sha256']!=capa['content_sha256']:
                blockers.append('SalCAPA: comparison with the other three current reports is missing.')
            else:
                source_ids={product:(reports[product]['id'] if product in reports else None)
                    for product in ('SalINTEL','SalTHIRA','SalOPS')}
                try: recorded=json.loads(comparison['sources_json'])
                except (ValueError,TypeError): recorded={}
                if not isinstance(recorded,dict) or any(
                        not isinstance(recorded.get(product),dict)
                        or recorded[product].get('report_id')!=source_ids[product] for product in source_ids):
                    blockers.append('SalCAPA: the comparison refers to an older source report.')
                expected_digest=hashlib.sha256(json.dumps({'salcapa_report_id':capa['id'],
                    'salcapa_sha256':comparison['salcapa_sha256'],'sources':recorded,
                    'summary':comparison['summary']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
                if expected_digest!=comparison['record_sha256']:
                    blockers.append('SalCAPA: the saved comparison failed its integrity check.')
                if comparison['comparison_status']!='Compared':
                    blockers.append('SalCAPA: a source difference remains unresolved.')
        technical_blockers=list(blockers)
        blockers.extend((
            'Independent qualified review and exact rendered/accessibility evidence are not recorded as approved.',
            'Controlled report issue and authorized recipient delivery proof have not been accepted in production.',
            'A qualified predecessor decision for a later package is not implemented.',
        ))
        return {'status':'Blocked','reports':[{ 'product':product,'report_id':row['id'],
            'version_no':row['version_no'],'content_sha256':row['content_sha256'],'status':row['status']}
            for product,row in reports.items()], 'blockers':blockers,'technical_blockers':technical_blockers,
            'notice':'This is an internal checklist. It does not approve, issue or deliver a report.'}
    finally: conn.close()

@app.post('/api/assessments/{assessment_id}/package-issues')
def issue_package_reports(assessment_id:int,p:PackageReportIssueIn,request:Request):
    require_package_commercial_candidate();require(request,'decide')
    ctx=auth_context(request)
    if (role(request) not in ('System Administrator','Assessment Director')
            or ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id')):
        raise HTTPException(403,'A named Salus report issuing authority is required.')
    if set(p.report_ids)!=PACKAGE_REPORT_PRODUCTS or any(type(value) is not int or value<1 for value in p.report_ids.values()):
        raise HTTPException(422,'Name the four exact product report IDs for this issue.')
    assessment_row_for_request(request,assessment_id)
    require_package_report_assignment(request,assessment_id)
    tid=tenant_id(request);conn=db()
    try:
        lock_package_assessment(conn,assessment_id)
        quote=authorized_package_intake(conn,assessment_id,request)
        acceptance=conn.execute('''SELECT * FROM package_acceptances WHERE tenant_id=? AND assessment_id=?
            AND quote_id=? ORDER BY id DESC LIMIT 1''',(tid,assessment_id,quote['id'])).fetchone()
        if not acceptance or acceptance['member_user_id']!=p.recipient_user_id:
            raise HTTPException(409,'The issue recipient must be the signed package decision owner.')
        recipient=conn.execute('SELECT status,role FROM users WHERE id=? AND tenant_id=?',
            (p.recipient_user_id,tid)).fetchone()
        if not recipient or recipient['status']!='Active' or recipient['role']!='Client Executive':
            raise HTTPException(409,'The approved Protected Member recipient is not active.')
        readiness=package_release_readiness(assessment_id,request)
        if readiness['technical_blockers']:
            raise HTTPException(409,'Exact report release checks remain open: '+'; '.join(readiness['technical_blockers']))
        reports={};snapshots={}
        for product in ('SalINTEL','SalTHIRA','SalOPS','SalCAPA'):
            row=conn.execute('''SELECT * FROM package_product_report_versions WHERE tenant_id=?
                AND assessment_id=? AND product=? ORDER BY version_no DESC LIMIT 1''',
                (tid,assessment_id,product)).fetchone()
            if (not row or row['id']!=p.report_ids[product] or row['quote_id']!=quote['id']
                    or row['assessment_scope_sha256']!=quote['assessment_scope_sha256']
                    or row['status'] not in ('Draft','Issued')):
                raise HTTPException(409,f'{product}: the exact current report or package boundary changed.')
            conformance=conn.execute('''SELECT * FROM package_report_conformance WHERE tenant_id=?
                AND report_id=? ORDER BY id DESC LIMIT 1''',(tid,row['id'])).fetchone()
            qa=conn.execute('''SELECT * FROM package_report_qa_evidence WHERE tenant_id=?
                AND report_id=? ORDER BY id DESC LIMIT 1''',(tid,row['id'])).fetchone()
            review=conn.execute('''SELECT * FROM package_report_qa_reviews WHERE tenant_id=?
                AND report_id=? AND evidence_id=? ORDER BY id DESC LIMIT 1''',
                (tid,row['id'],qa['id'] if qa else 0)).fetchone()
            if not conformance or not qa or not review or review['decision']!='Reviewed':
                raise HTTPException(409,f'{product}: exact conformance or independent review is missing.')
            checks=json.loads(conformance['checks_json'])
            if checks['qualified_review_and_release_authority']['status']!='Met':
                raise HTTPException(409,f'{product}: qualified release authority is not marked met.')
            manifest=json.loads(qa['manifest_json'])
            snapshots[product]={'report_id':row['id'],'version_no':row['version_no'],
                'content_sha256':row['content_sha256'],'pdf_sha256':manifest['pdf_sha256'],
                'conformance_id':conformance['id'],'qa_evidence_id':qa['id'],'qa_review_id':review['id']}
            reports[product]=row
        comparison=conn.execute('''SELECT * FROM package_report_reconciliations WHERE tenant_id=?
            AND salcapa_report_id=? ORDER BY id DESC LIMIT 1''',(tid,reports['SalCAPA']['id'])).fetchone()
        if not comparison or comparison['comparison_status']!='Compared':
            raise HTTPException(409,'The four-report source comparison is not complete.')
        record={'assessment_id':assessment_id,'quote_id':quote['id'],
            'assessment_scope_sha256':quote['assessment_scope_sha256'],
            'recipient_user_id':p.recipient_user_id,'reports':snapshots,
            'comparison_id':comparison['id'],'issue_basis':p.issue_basis.strip(),
            'issued_by_user_id':ctx['user_id']}
        digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        prior=conn.execute('''SELECT id FROM package_report_issue_packets WHERE tenant_id=?
            AND assessment_id=? AND record_sha256=?''',(tid,assessment_id,digest)).fetchone()
        if prior: return {'id':prior['id'],'status':'Issued','record_sha256':digest,'idempotent':True}
        if any(row['status']!='Draft' for row in reports.values()):
            raise HTTPException(409,'An issued report cannot be silently reissued under a changed packet.')
        previous=conn.execute('''SELECT id FROM package_report_issue_packets WHERE tenant_id=?
            AND assessment_id=? ORDER BY id DESC LIMIT 1''',(tid,assessment_id)).fetchone()
        cur=conn.execute('''INSERT INTO package_report_issue_packets
            (tenant_id,assessment_id,quote_id,assessment_scope_sha256,recipient_user_id,
             reports_json,comparison_id,issue_basis,record_sha256,issued_by_user_id,issued_at,supersedes_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,assessment_id,quote['id'],
             quote['assessment_scope_sha256'],p.recipient_user_id,
             json.dumps(snapshots,sort_keys=True,separators=(',',':')),comparison['id'],
             record['issue_basis'],digest,ctx['user_id'],now(),previous['id'] if previous else None))
        for row in reports.values():
            conn.execute("UPDATE package_product_report_versions SET status='Issued' WHERE id=? AND status='Draft'",(row['id'],))
        audit(conn,'PACKAGE_REPORT_ISSUE','assessment',assessment_id,
            f'issue_id={cur.lastrowid}; quote_id={quote["id"]}; sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'status':'Issued','record_sha256':digest,'idempotent':False,
            'notice':'The four exact reports are issued to the named recipient; download proof is recorded separately.'}
    finally:
        conn.rollback();conn.close()

def verified_package_issue_record(row):
    try:
        reports=json.loads(row['reports_json'])
        record={'assessment_id':row['assessment_id'],'quote_id':row['quote_id'],
            'assessment_scope_sha256':row['assessment_scope_sha256'],
            'recipient_user_id':row['recipient_user_id'],'reports':reports,
            'comparison_id':row['comparison_id'],'issue_basis':row['issue_basis'],
            'issued_by_user_id':row['issued_by_user_id']}
        digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest!=row['record_sha256'] or set(reports)!=PACKAGE_REPORT_PRODUCTS:
            raise ValueError('issue digest or report set')
    except (ValueError,TypeError,KeyError,AttributeError) as exc:
        raise HTTPException(409,'The issued package failed integrity verification.') from exc
    return reports

def verified_package_issue(conn,issue_id:int,request:Request):
    row=conn.execute('SELECT * FROM package_report_issue_packets WHERE id=? AND tenant_id=?',
        (issue_id,tenant_id(request))).fetchone()
    if not row: raise HTTPException(404,'Issued package not found.')
    ctx=auth_context(request)
    if (role(request)!='Client Executive' or ctx['auth_mode'] not in ('session','oidc')
            or ctx.get('user_id')!=row['recipient_user_id']):
        raise HTTPException(403,'This issued package is restricted to its named Protected Member recipient.')
    assessment_row_for_request(request,row['assessment_id'])
    return row,verified_package_issue_record(row)

@app.get('/api/assessments/{assessment_id}/package-issues')
def list_member_package_issues(assessment_id:int,request:Request):
    require_package_commercial_candidate();require(request,'read')
    ctx=auth_context(request)
    if role(request)!='Client Executive' or ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id'):
        raise HTTPException(403,'A signed-in Protected Member recipient is required.')
    assessment_row_for_request(request,assessment_id)
    conn=db()
    try:
        rows=conn.execute('''SELECT id FROM package_report_issue_packets WHERE tenant_id=?
            AND assessment_id=? AND recipient_user_id=? ORDER BY id''',
            (tenant_id(request),assessment_id,ctx['user_id'])).fetchall()
        result=[]
        for item in rows:
            issue,reports=verified_package_issue(conn,item['id'],request)
            acknowledgment=conn.execute('''SELECT acknowledged_at FROM package_report_issue_acknowledgments
                WHERE tenant_id=? AND issue_id=? AND recipient_user_id=?''',
                (tenant_id(request),issue['id'],ctx['user_id'])).fetchone()
            result.append({'id':issue['id'],'issued_at':issue['issued_at'],
                'acknowledged_at':acknowledgment['acknowledged_at'] if acknowledgment else None,
                'reports':{product:{'report_id':value['report_id'],'version_no':value['version_no']}
                    for product,value in reports.items()}})
        return {'issues':result,'notice':'Download the exact issued documents for your authorized package.'}
    finally: conn.close()

@app.get('/api/package-issues/{issue_id}/reports/{product}.{format}')
def download_issued_package_report(issue_id:int,product:str,format:str,request:Request):
    require_package_commercial_candidate();require(request,'read')
    if product not in PACKAGE_REPORT_PRODUCTS or format not in ('docx','pdf'):
        raise HTTPException(404,'Unknown issued report format.')
    conn=db()
    try:
        issue,reports=verified_package_issue(conn,issue_id,request)
        snapshot=reports[product]
        report=conn.execute('SELECT * FROM package_product_report_versions WHERE id=? AND tenant_id=?',
            (snapshot['report_id'],tenant_id(request))).fetchone()
        if (not report or report['assessment_id']!=issue['assessment_id']
                or report['quote_id']!=issue['quote_id'] or report['product']!=product
                or report['status']!='Issued' or report['content_sha256']!=snapshot['content_sha256']):
            raise HTTPException(409,'The issued report no longer matches its release record.')
        try:
            if format=='docx':
                content=storage.get_bytes(report['stored_name']);expected=snapshot['content_sha256']
            else:
                evidence=conn.execute('SELECT * FROM package_report_qa_evidence WHERE id=? AND tenant_id=?',
                    (snapshot['qa_evidence_id'],tenant_id(request))).fetchone()
                if not evidence or evidence['report_id']!=report['id'] or evidence['archive_sha256']=='':
                    raise HTTPException(409,'The issued PDF evidence is missing.')
                archive=storage.get_bytes(evidence['stored_name'])
                if hashlib.sha256(archive).hexdigest()!=evidence['archive_sha256']:
                    raise HTTPException(409,'The issued PDF archive failed integrity verification.')
                with zipfile.ZipFile(io.BytesIO(archive)) as z: content=z.read('rendered.pdf')
                expected=snapshot['pdf_sha256']
        except HTTPException: raise
        except Exception as exc: raise HTTPException(503,'The issued report is unavailable.') from exc
        if hashlib.sha256(content).hexdigest()!=expected:
            security_event(request,'PACKAGE_ISSUED_REPORT_HASH_MISMATCH','High',f'issue_id={issue_id}; product={product}')
            raise HTTPException(409,'The issued report failed integrity verification.')
        conn.execute('''INSERT INTO package_report_issue_deliveries
            (tenant_id,assessment_id,issue_id,report_id,product,format,content_sha256,
             recipient_user_id,downloaded_at) VALUES(?,?,?,?,?,?,?,?,?)''',
            (tenant_id(request),issue['assessment_id'],issue_id,report['id'],product,format,
             expected,issue['recipient_user_id'],now()))
        audit(conn,'PACKAGE_REPORT_DOWNLOAD','assessment',issue['assessment_id'],
            f'issue_id={issue_id}; report_id={report["id"]}; format={format}; sha256={expected}',actor(request))
        conn.commit()
        media=('application/pdf' if format=='pdf' else
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        filename=safe_filename(report['display_title'])+'.'+format
        return Response(content=content,media_type=media,headers={
            'Content-Disposition':f'attachment; filename="{filename}"',
            'X-Content-SHA256':expected,'Cache-Control':'no-store'})
    finally:
        conn.rollback();conn.close()

@app.post('/api/package-issues/{issue_id}/acknowledgment')
def acknowledge_issued_package(issue_id:int,p:PackageReportAcknowledgmentIn,request:Request):
    require_package_commercial_candidate()
    require_protected_member_authority(request,'package_report_acknowledgment')
    ctx=auth_context(request)
    if ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id'):
        raise HTTPException(403,'A signed-in Protected Member recipient is required.')
    conn=db()
    try:
        issue,reports=verified_package_issue(conn,issue_id,request)
        lock_package_assessment(conn,issue['assessment_id'])
        issue,reports=verified_package_issue(conn,issue_id,request)
        if p.issue_sha256!=issue['record_sha256']:
            raise HTTPException(409,'The issued package version changed. Review its current documents.')
        note=p.acknowledgment_note.strip()
        if len(note)<20:
            raise HTTPException(422,'Give a meaningful receipt and limitations acknowledgment.')
        record={'issue_id':issue_id,'issue_sha256':p.issue_sha256,
            'recipient_user_id':ctx['user_id'],'acknowledgment_note':note,
            'idempotency_key':p.idempotency_key}
        digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        prior=conn.execute('''SELECT * FROM package_report_issue_acknowledgments
            WHERE tenant_id=? AND (issue_id=? OR idempotency_key=?)''',
            (tenant_id(request),issue_id,p.idempotency_key)).fetchone()
        if prior:
            if (prior['issue_id']==issue_id and prior['recipient_user_id']==ctx['user_id']
                    and prior['record_sha256']==digest):
                return {'id':prior['id'],'status':'Acknowledged','record_sha256':digest,
                    'acknowledged_at':prior['acknowledged_at'],'idempotent':True}
            raise HTTPException(409,'This issue or acknowledgment key already has another decision.')
        downloads=conn.execute('''SELECT product,format,report_id,content_sha256
            FROM package_report_issue_deliveries WHERE tenant_id=? AND issue_id=?
            AND recipient_user_id=?''',(tenant_id(request),issue_id,ctx['user_id'])).fetchall()
        downloaded=set()
        for item in downloads:
            snapshot=reports.get(item['product'])
            if (snapshot and item['report_id']==snapshot['report_id']
                    and item['content_sha256']==snapshot['content_sha256' if item['format']=='docx' else 'pdf_sha256']):
                downloaded.add(item['product'])
        missing=PACKAGE_REPORT_PRODUCTS-downloaded
        if missing:
            raise HTTPException(409,'Download each of the four exact issued reports before acknowledging receipt: '+', '.join(sorted(missing)))
        ts=now()
        cur=conn.execute('''INSERT INTO package_report_issue_acknowledgments
            (tenant_id,assessment_id,issue_id,issue_sha256,recipient_user_id,
             acknowledgment_note,idempotency_key,record_sha256,acknowledged_at)
            VALUES(?,?,?,?,?,?,?,?,?)''',(tenant_id(request),issue['assessment_id'],issue_id,
             p.issue_sha256,ctx['user_id'],note,p.idempotency_key,digest,ts))
        audit(conn,'PACKAGE_REPORT_ACKNOWLEDGMENT','assessment',issue['assessment_id'],
            f'issue_id={issue_id}; acknowledgment_id={cur.lastrowid}; sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'status':'Acknowledged','record_sha256':digest,
            'acknowledged_at':ts,'idempotent':False,
            'notice':'Your receipt and review of the stated report limitations are recorded. This does not accept risk or authorize further services.'}
    finally:
        conn.rollback();conn.close()

@app.post('/api/assessments/{assessment_id}/package-predecessor-qualifications')
def qualify_package_predecessor(assessment_id:int,p:PackagePredecessorQualificationIn,request:Request):
    require_package_commercial_candidate();require(request,'decide')
    ctx=auth_context(request)
    if (role(request) not in ('System Administrator','Assessment Director')
            or ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id')):
        raise HTTPException(403,'A named Salus qualification reviewer is required.')
    assessment_row_for_request(request,assessment_id)
    require_package_report_assignment(request,assessment_id)
    conn=db();tid=tenant_id(request)
    try:
        lock_package_assessment(conn,assessment_id)
        issue=conn.execute('''SELECT * FROM package_report_issue_packets WHERE tenant_id=?
            AND assessment_id=? ORDER BY id DESC LIMIT 1''',(tid,assessment_id)).fetchone()
        if not issue or issue['record_sha256']!=p.issue_sha256:
            raise HTTPException(409,'Qualify only the latest exact four-report issue.')
        reports=verified_package_issue_record(issue)
        if issue['issued_by_user_id']==ctx['user_id']:
            raise HTTPException(403,'The issue authority cannot independently qualify the same package.')
        acknowledgment=conn.execute('''SELECT * FROM package_report_issue_acknowledgments
            WHERE id=? AND tenant_id=? AND issue_id=?''',(p.acknowledgment_id,tid,issue['id'])).fetchone()
        if not acknowledgment or acknowledgment['recipient_user_id']!=issue['recipient_user_id']:
            raise HTTPException(409,'The named Member receipt acknowledgment is missing.')
        acknowledgment_record={key:acknowledgment[key] for key in
            ('issue_id','issue_sha256','recipient_user_id','acknowledgment_note','idempotency_key')}
        acknowledgment_digest=hashlib.sha256(json.dumps(acknowledgment_record,
            sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if (acknowledgment['issue_sha256']!=issue['record_sha256']
                or acknowledgment_digest!=acknowledgment['record_sha256']):
            raise HTTPException(409,'The Member acknowledgment failed integrity verification.')
        quote=conn.execute('SELECT * FROM package_quote_versions WHERE id=? AND tenant_id=?',
            (issue['quote_id'],tid)).fetchone()
        if not quote or quote['assessment_id']!=assessment_id:
            raise HTTPException(409,'The predecessor quote is unavailable.')
        verified_package_quote(conn,quote,request)
        if (quote['assessment_scope_sha256']!=issue['assessment_scope_sha256']
                or quote['level'] not in (1,2)):
            raise HTTPException(409,'Only an exact issued Level 1 or Level 2 package can qualify its successor.')
        for product,snapshot in reports.items():
            report=conn.execute('''SELECT * FROM package_product_report_versions
                WHERE tenant_id=? AND assessment_id=? AND product=? ORDER BY version_no DESC LIMIT 1''',
                (tid,assessment_id,product)).fetchone()
            if (not report or report['id']!=snapshot['report_id'] or report['status']!='Issued'
                    or report['quote_id']!=quote['id']
                    or report['content_sha256']!=snapshot['content_sha256']):
                raise HTTPException(409,f'{product}: a later or changed report prevents predecessor qualification.')
        basis=p.qualification_basis.strip();limitations=p.limitations_disposition.strip()
        if len(basis)<40 or len(limitations)<40:
            raise HTTPException(422,'Record the independent qualification basis and unresolved limitations.')
        record={'assessment_id':assessment_id,'issue_id':issue['id'],
            'issue_sha256':issue['record_sha256'],'acknowledgment_id':acknowledgment['id'],
            'acknowledgment_sha256':acknowledgment['record_sha256'],'quote_id':quote['id'],
            'level':quote['level'],'band':quote['band'],
            'covered_operation':quote['covered_operation'],'exclusions':quote['exclusions'],
            'assessment_scope_sha256':quote['assessment_scope_sha256'],
            'qualification_basis':basis,'limitations_disposition':limitations,
            'reviewer_user_id':ctx['user_id']}
        digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        prior=conn.execute('''SELECT * FROM package_predecessor_qualifications
            WHERE tenant_id=? AND issue_id=?''',(tid,issue['id'])).fetchone()
        if prior:
            if prior['record_sha256']==digest:
                return {'id':prior['id'],'status':'Qualified','record_sha256':digest,
                    'qualified_at':prior['qualified_at'],'idempotent':True}
            raise HTTPException(409,'This issued package already has a different qualification decision.')
        ts=now();fields=['tenant_id']+list(record)+['record_sha256','qualified_at']
        values=[tid]+list(record.values())+[digest,ts]
        cur=conn.execute(f"INSERT INTO package_predecessor_qualifications({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",values)
        audit(conn,'PACKAGE_PREDECESSOR_QUALIFY','assessment',assessment_id,
            f'qualification_id={cur.lastrowid}; issue_id={issue["id"]}; sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'status':'Qualified','record_sha256':digest,
            'qualified_at':ts,'idempotent':False,
            'notice':'This records a predecessor review. A later quote still needs an exact-scope prerequisite check and separate authorization.'}
    finally:
        conn.rollback();conn.close()

@app.post('/api/assessments/{assessment_id}/package-reports/{product}/draft')
async def register_package_product_draft(assessment_id:int,product:str,request:Request,
        file:UploadFile=File(...),method_version:str=Form(...),template_version:str=Form(...)):
    require_package_commercial_candidate();require(request,'write');require_salus_component_authority(request,'Package report')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES:
        raise HTTPException(403,'A Salus report owner must register a working report.')
    if product not in PACKAGE_REPORT_PRODUCTS: raise HTTPException(404,'Unknown package report product.')
    assessment_row_for_request(request,assessment_id)
    require_package_report_assignment(request,assessment_id)
    method_version=method_version.strip();template_version=template_version.strip()
    if not method_version or not template_version or len(method_version)>120 or len(template_version)>120:
        raise HTTPException(422,'Name the exact method and template versions for this working draft.')
    original=safe_filename(file.filename or '')
    if not original.lower().endswith('.docx'): raise HTTPException(422,'A working package report must be a Word .docx file.')
    content=await file.read(10*1024*1024+1)
    check_package_docx(content)
    scan=scan_bytes(content,original)
    if not scan['ok'] or scan['status']!='Clean':
        raise HTTPException(422 if scan['status']=='Infected' else 503,'The draft Word report could not pass the file security check.')
    digest=hashlib.sha256(content).hexdigest();tid=tenant_id(request);conn=db();stored=''
    try:
        lock_package_assessment(conn,assessment_id)
        quote=authorized_package_intake(conn,assessment_id,request)
        existing=conn.execute('''SELECT * FROM package_product_report_versions WHERE tenant_id=? AND assessment_id=?
            AND quote_id=? AND product=? AND content_sha256=? AND method_version=? AND template_version=?''',
            (tid,assessment_id,quote['id'],product,digest,method_version,template_version)).fetchone()
        if existing:
            return {key:existing[key] for key in ('id','product','report_identity','display_title','version_no','content_sha256','status')}
        previous=conn.execute('''SELECT id,version_no FROM package_product_report_versions WHERE tenant_id=? AND assessment_id=?
            AND product=? ORDER BY version_no DESC LIMIT 1''',(tid,assessment_id,product)).fetchone()
        version=previous['version_no']+1 if previous else 1
        identity=f'PKG-{assessment_id}-{product}'
        assessment=conn.execute('SELECT organization FROM assessments WHERE id=? AND tenant_id=?',(assessment_id,tid)).fetchone()
        suffix=f' Level {quote["level"]}{quote["band"]}'
        if quote['level']==1 and quote['band']=='A': suffix+=f' {quote["variant"]}'
        display_title=f'{assessment["organization"]} - {product}{suffix}'
        stored=f'tenant-{tid}/assessment-{assessment_id}/package-reports/{product}/{uuid.uuid4().hex}_{digest[:16]}.docx'
        storage.put_bytes(stored,content)
        retention_until=(_iso_now_dt()+timedelta(days=max(1,RETENTION_DEFAULT_DAYS))).replace(microsecond=0).isoformat().replace('+00:00','Z')
        cur=conn.execute('''INSERT INTO package_product_report_versions
            (tenant_id,assessment_id,quote_id,product,report_identity,display_title,version_no,assessment_scope_sha256,
             method_version,template_version,original_name,stored_name,content_sha256,size_bytes,status,retention_until,legal_hold,disposition_status,created_by,created_at,supersedes_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,'Draft',?,0,'Active',?,?,?)''',
            (tid,assessment_id,quote['id'],product,identity,display_title,version,quote['assessment_scope_sha256'],
             method_version,template_version,original,stored,digest,len(content),retention_until,actor(request),now(),previous['id'] if previous else None))
        audit(conn,'PACKAGE_REPORT_DRAFT','assessment',assessment_id,f'product={product}; version={version}; sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'product':product,'report_identity':identity,'display_title':display_title,'version_no':version,'content_sha256':digest,'status':'Draft'}
    except Exception as exc:
        conn.rollback()
        if stored:
            try: storage.delete(stored)
            except Exception: pass
        if isinstance(exc,HTTPException): raise
        error_id=secrets.token_hex(8);record_internal_failure('package report draft',error_id,exc)
        raise HTTPException(503,f'Working report storage is unavailable. Reference: {error_id}') from exc
    finally: conn.close()

@app.get('/api/package-reports/{report_id}/draft.docx')
def download_package_product_draft(report_id:int,request:Request):
    require_package_commercial_candidate();require(request,'read')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES: raise HTTPException(403,'Working reports are restricted to assigned Salus report owners.')
    conn=db()
    try:
        row=conn.execute('SELECT * FROM package_product_report_versions WHERE id=? AND tenant_id=?',(report_id,tenant_id(request))).fetchone()
    finally: conn.close()
    if not row: raise HTTPException(404,'Working report not found.')
    assessment_row_for_request(request,row['assessment_id']);require_package_report_assignment(request,row['assessment_id'])
    try: content=storage.get_bytes(row['stored_name'])
    except Exception as exc: raise HTTPException(503,'Working report storage is unavailable.') from exc
    if hashlib.sha256(content).hexdigest()!=row['content_sha256']:
        security_event(request,'PACKAGE_REPORT_DRAFT_HASH_MISMATCH','High',f'report_id={report_id}')
        raise HTTPException(409,'Working report integrity verification failed.')
    return Response(content=content,media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        headers={'Content-Disposition':f'attachment; filename="{safe_filename(row["original_name"])}"',
                 'X-Content-SHA256':row['content_sha256'],'Cache-Control':'no-store'})

@app.get('/api/package-reports/{report_id}/conformance')
def list_package_report_conformance(report_id:int,request:Request):
    require_package_commercial_candidate();require(request,'read')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES: raise HTTPException(403,'Working report conformance is restricted to Salus report owners.')
    conn=db()
    try:
        report=conn.execute('SELECT assessment_id FROM package_product_report_versions WHERE id=? AND tenant_id=?',
            (report_id,tenant_id(request))).fetchone()
        if not report: raise HTTPException(404,'Working report not found.')
        assessment_row_for_request(request,report['assessment_id'])
        require_package_report_assignment(request,report['assessment_id'])
        rows=[dict(row) for row in conn.execute('SELECT * FROM package_report_conformance WHERE tenant_id=? AND report_id=? ORDER BY id',
            (tenant_id(request),report_id))]
        for row in rows: row['checks']=json.loads(row.pop('checks_json'))
        return {'records':rows,'required_checks':PACKAGE_REPORT_QA_KEYS,
            'notice':'A recorded matrix does not approve, issue or qualify a package report.'}
    finally: conn.close()

@app.get('/api/package-reports/{report_id}/qa-evidence')
def list_package_report_qa_evidence(report_id:int,request:Request):
    require_package_commercial_candidate();require(request,'read')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES:
        raise HTTPException(403,'Report QA evidence is restricted to assigned Salus report owners.')
    conn=db()
    try:
        report=conn.execute('SELECT assessment_id FROM package_product_report_versions WHERE id=? AND tenant_id=?',
            (report_id,tenant_id(request))).fetchone()
        if not report: raise HTTPException(404,'Working report not found.')
        assessment_row_for_request(request,report['assessment_id'])
        require_package_report_assignment(request,report['assessment_id'])
        rows=[dict(row) for row in conn.execute('''SELECT id,report_id,content_sha256,archive_sha256,
            archive_size_bytes,manifest_json,manifest_sha256,status,retention_until,legal_hold,submitted_by,submitted_at
            FROM package_report_qa_evidence WHERE tenant_id=? AND report_id=? ORDER BY id''',
            (tenant_id(request),report_id))]
        for row in rows: row['manifest']=json.loads(row.pop('manifest_json'))
        return {'records':rows,'notice':'Submitted QA evidence is not independent review or release approval.'}
    finally: conn.close()

@app.post('/api/package-reports/{report_id}/qa-evidence')
async def submit_package_report_qa_evidence(report_id:int,request:Request,file:UploadFile=File(...)):
    require_package_commercial_candidate();require(request,'write');require_salus_component_authority(request,'Package report QA')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES:
        raise HTTPException(403,'A Salus report owner must submit QA evidence.')
    original=safe_filename(file.filename or '')
    if not original.lower().endswith('.zip'): raise HTTPException(422,'Report QA evidence must be a ZIP archive.')
    content=await file.read(50*1024*1024+1)
    if len(content)>50*1024*1024: raise HTTPException(413,'Report QA archive exceeds 50 MB.')
    tid=tenant_id(request);conn=db();stored=''
    try:
        report=conn.execute('SELECT * FROM package_product_report_versions WHERE id=? AND tenant_id=?',(report_id,tid)).fetchone()
        if not report: raise HTTPException(404,'Working report not found.')
        assessment_row_for_request(request,report['assessment_id'])
        require_package_report_assignment(request,report['assessment_id'])
        lock_package_assessment(conn,report['assessment_id'])
        quote=authorized_package_intake(conn,report['assessment_id'],request)
        latest=conn.execute('''SELECT id FROM package_product_report_versions WHERE tenant_id=? AND assessment_id=?
            AND product=? ORDER BY version_no DESC LIMIT 1''',(tid,report['assessment_id'],report['product'])).fetchone()
        if (report['status']!='Draft' or latest['id']!=report_id or report['quote_id']!=quote['id']
                or report['assessment_scope_sha256']!=quote['assessment_scope_sha256']):
            raise HTTPException(409,'QA evidence must name the current working report and authorized package.')
        try: word=storage.get_bytes(report['stored_name'])
        except Exception as exc: raise HTTPException(503,'Working report storage is unavailable.') from exc
        if hashlib.sha256(word).hexdigest()!=report['content_sha256']:
            raise HTTPException(409,'The working Word report failed integrity verification.')
        manifest_json,pdf=inspect_package_qa_archive(content,report['content_sha256'])
        for name,data in ((original,content),('rendered.pdf',pdf)):
            scan=scan_bytes(data,name)
            if not scan['ok'] or scan['status']!='Clean':
                raise HTTPException(422 if scan['status']=='Infected' else 503,'Report QA evidence could not pass the file security check.')
        digest=hashlib.sha256(content).hexdigest()
        prior=conn.execute('SELECT id,status FROM package_report_qa_evidence WHERE tenant_id=? AND report_id=? AND archive_sha256=?',
            (tid,report_id,digest)).fetchone()
        if prior: return {'id':prior['id'],'status':prior['status'],'archive_sha256':digest,'idempotent':True}
        stored=f'tenant-{tid}/assessment-{report["assessment_id"]}/package-report-qa/{report_id}/{uuid.uuid4().hex}_{digest[:16]}.zip'
        storage.put_bytes(stored,content)
        retention_until=(_iso_now_dt()+timedelta(days=max(1,RETENTION_DEFAULT_DAYS))).replace(microsecond=0).isoformat().replace('+00:00','Z')
        cur=conn.execute('''INSERT INTO package_report_qa_evidence
            (tenant_id,assessment_id,report_id,content_sha256,stored_name,archive_sha256,archive_size_bytes,
             manifest_json,manifest_sha256,status,retention_until,legal_hold,submitted_by,submitted_user_id,submitted_at)
            VALUES(?,?,?,?,?,?,?,?,?,'Submitted',?,0,?,?,?)''',
            (tid,report['assessment_id'],report_id,report['content_sha256'],stored,digest,len(content),
             manifest_json,hashlib.sha256(manifest_json.encode()).hexdigest(),retention_until,actor(request),
             auth_context(request).get('user_id'),now()))
        audit(conn,'PACKAGE_REPORT_QA_SUBMISSION','assessment',report['assessment_id'],
            f'report_id={report_id}; archive_sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'status':'Submitted','archive_sha256':digest,'idempotent':False,
            'notice':'Archive integrity was screened. Independent QA and issue authority remain open.'}
    except Exception as exc:
        conn.rollback()
        if stored:
            try: storage.delete(stored)
            except Exception: pass
        if isinstance(exc,HTTPException): raise
        error_id=secrets.token_hex(8);record_internal_failure('package report QA evidence',error_id,exc)
        raise HTTPException(503,f'Report QA evidence storage is unavailable. Reference: {error_id}') from exc
    finally: conn.close()

@app.get('/api/package-report-qa/{evidence_id}/archive.zip')
def download_package_report_qa_evidence(evidence_id:int,request:Request):
    require_package_commercial_candidate();require(request,'read')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES:
        raise HTTPException(403,'Report QA evidence is restricted to assigned Salus report owners.')
    conn=db()
    try: row=conn.execute('SELECT * FROM package_report_qa_evidence WHERE id=? AND tenant_id=?',
        (evidence_id,tenant_id(request))).fetchone()
    finally: conn.close()
    if not row: raise HTTPException(404,'Report QA evidence not found.')
    assessment_row_for_request(request,row['assessment_id'])
    require_package_report_assignment(request,row['assessment_id'])
    try: content=storage.get_bytes(row['stored_name'])
    except Exception as exc: raise HTTPException(503,'Report QA evidence storage is unavailable.') from exc
    if hashlib.sha256(content).hexdigest()!=row['archive_sha256']:
        security_event(request,'PACKAGE_REPORT_QA_HASH_MISMATCH','High',f'evidence_id={evidence_id}')
        raise HTTPException(409,'Report QA archive integrity verification failed.')
    return Response(content=content,media_type='application/zip',headers={
        'Content-Disposition':f'attachment; filename="package-report-qa-{evidence_id}.zip"',
        'X-Content-SHA256':row['archive_sha256'],'Cache-Control':'no-store'})

@app.get('/api/package-reports/{report_id}/qa-reviews')
def list_package_report_qa_reviews(report_id:int,request:Request):
    require_package_commercial_candidate();require(request,'read')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES:
        raise HTTPException(403,'Report QA reviews are restricted to assigned Salus report owners.')
    conn=db()
    try:
        report=conn.execute('SELECT assessment_id FROM package_product_report_versions WHERE id=? AND tenant_id=?',
            (report_id,tenant_id(request))).fetchone()
        if not report: raise HTTPException(404,'Working report not found.')
        assessment_row_for_request(request,report['assessment_id'])
        require_package_report_assignment(request,report['assessment_id'])
        rows=[dict(row) for row in conn.execute('''SELECT id,report_id,evidence_id,content_sha256,
            archive_sha256,decision,checks_json,qualification_basis,review_note,record_sha256,
            reviewer_user_id,reviewer_at FROM package_report_qa_reviews
            WHERE tenant_id=? AND report_id=? ORDER BY id''',(tenant_id(request),report_id))]
        for row in rows: row['checks']=json.loads(row.pop('checks_json'))
        return {'records':rows,'notice':'A review record does not issue or deliver a report.'}
    finally: conn.close()

@app.post('/api/package-reports/{report_id}/qa-reviews')
def record_package_report_qa_review(report_id:int,p:PackageReportQaReviewIn,request:Request):
    require_package_commercial_candidate();require(request,'decide')
    ctx=auth_context(request)
    if (role(request) not in ('System Administrator','Assessment Director')
            or ctx['auth_mode'] not in ('session','oidc') or not ctx.get('user_id')):
        raise HTTPException(403,'An authenticated Salus review decision owner is required.')
    if set(p.checks)!=set(PACKAGE_REPORT_REVIEW_KEYS) or any(type(value) is not bool for value in p.checks.values()):
        raise HTTPException(422,'Record each required report review check as true or false.')
    if p.decision=='Reviewed' and not all(p.checks.values()):
        raise HTTPException(422,'Return the report when a review check remains incomplete.')
    tid=tenant_id(request);conn=db()
    try:
        report=conn.execute('SELECT * FROM package_product_report_versions WHERE id=? AND tenant_id=?',(report_id,tid)).fetchone()
        if not report: raise HTTPException(404,'Working report not found.')
        assessment_row_for_request(request,report['assessment_id'])
        require_package_report_assignment(request,report['assessment_id'])
        lock_package_assessment(conn,report['assessment_id'])
        quote=authorized_package_intake(conn,report['assessment_id'],request)
        latest=conn.execute('''SELECT id FROM package_product_report_versions WHERE tenant_id=? AND assessment_id=?
            AND product=? ORDER BY version_no DESC LIMIT 1''',(tid,report['assessment_id'],report['product'])).fetchone()
        if (report['status']!='Draft' or latest['id']!=report_id or report['quote_id']!=quote['id']
                or report['assessment_scope_sha256']!=quote['assessment_scope_sha256']):
            raise HTTPException(409,'The review must name the current authorized working report.')
        evidence=conn.execute('''SELECT * FROM package_report_qa_evidence WHERE id=? AND tenant_id=?
            AND report_id=?''',(p.evidence_id,tid,report_id)).fetchone()
        if not evidence or evidence['content_sha256']!=report['content_sha256']:
            raise HTTPException(409,'The review must name QA evidence for this exact Word version.')
        newest=conn.execute('''SELECT id FROM package_report_qa_evidence WHERE tenant_id=? AND report_id=?
            ORDER BY id DESC LIMIT 1''',(tid,report_id)).fetchone()
        if newest['id']!=p.evidence_id:
            raise HTTPException(409,'The review must use the current QA archive for this report.')
        if not evidence['submitted_user_id'] or evidence['submitted_user_id']==ctx['user_id']:
            raise HTTPException(409,'Independent review requires a different authenticated evidence submitter.')
        try:
            word=storage.get_bytes(report['stored_name'])
            archive=storage.get_bytes(evidence['stored_name'])
        except Exception as exc: raise HTTPException(503,'Exact report review evidence is unavailable.') from exc
        if (hashlib.sha256(word).hexdigest()!=report['content_sha256']
                or hashlib.sha256(archive).hexdigest()!=evidence['archive_sha256']):
            raise HTTPException(409,'Exact report review evidence failed integrity verification.')
        manifest_json,_=inspect_package_qa_archive(archive,report['content_sha256'])
        if hashlib.sha256(manifest_json.encode()).hexdigest()!=evidence['manifest_sha256']:
            raise HTTPException(409,'The report QA manifest failed integrity verification.')
        manifest=json.loads(manifest_json)
        if p.decision=='Reviewed' and (not all(page['checked_full_size'] for page in manifest['pages'])
                or any(manifest[key]!='Checked' for key in ('native_word','accessibility','parity'))):
            raise HTTPException(409,'The QA archive still records pending page or format checks.')
        checks={key:p.checks[key] for key in PACKAGE_REPORT_REVIEW_KEYS}
        record={'report_id':report_id,'evidence_id':p.evidence_id,'content_sha256':report['content_sha256'],
            'archive_sha256':evidence['archive_sha256'],'decision':p.decision,'checks':checks,
            'qualification_basis':p.qualification_basis.strip(),'review_note':p.review_note.strip(),
            'reviewer_user_id':ctx['user_id']}
        digest=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        prior=conn.execute('SELECT id FROM package_report_qa_reviews WHERE tenant_id=? AND evidence_id=? AND record_sha256=?',
            (tid,p.evidence_id,digest)).fetchone()
        if prior: return {'id':prior['id'],'decision':p.decision,'record_sha256':digest,'idempotent':True}
        cur=conn.execute('''INSERT INTO package_report_qa_reviews
            (tenant_id,assessment_id,report_id,evidence_id,content_sha256,archive_sha256,decision,
             checks_json,qualification_basis,review_note,record_sha256,reviewer_user_id,reviewer_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,report['assessment_id'],report_id,p.evidence_id,
             report['content_sha256'],evidence['archive_sha256'],p.decision,
             json.dumps(checks,sort_keys=True,separators=(',',':')),record['qualification_basis'],
             record['review_note'],digest,ctx['user_id'],now()))
        audit(conn,'PACKAGE_REPORT_QA_REVIEW','assessment',report['assessment_id'],
            f'report_id={report_id}; evidence_id={p.evidence_id}; decision={p.decision}; sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'decision':p.decision,'record_sha256':digest,'idempotent':False,
            'notice':'This review record does not issue, deliver or qualify a later package.'}
    finally:
        conn.rollback();conn.close()

@app.patch('/api/package-reports/{report_id}/retention')
def extend_package_report_retention(report_id:int,p:PackageReportRetentionIn,request:Request):
    require_package_commercial_candidate();require(request,'decide')
    if role(request) not in {'System Administrator','Assessment Director'}:
        raise HTTPException(403,'Package report retention requires a Salus decision owner.')
    if p.retention_until is None and p.legal_hold is None:
        raise HTTPException(422,'Extend retention or place a legal hold.')
    new_until=None
    if p.retention_until is not None:
        try:
            parsed=datetime.fromisoformat(p.retention_until.replace('Z','+00:00'))
            if parsed.tzinfo is None: raise ValueError('Timezone required')
            if parsed.astimezone(timezone.utc)<=_iso_now_dt():
                raise HTTPException(422,'Extended retention must end in the future.')
            new_until=parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        except ValueError as exc: raise HTTPException(422,'Use an explicit UTC retention timestamp.') from exc
    conn=db()
    try:
        row=conn.execute('SELECT * FROM package_product_report_versions WHERE id=? AND tenant_id=?',
            (report_id,tenant_id(request))).fetchone()
        if not row: raise HTTPException(404,'Working report not found.')
        assessment_row_for_request(request,row['assessment_id'])
        require_package_report_assignment(request,row['assessment_id'])
        lock_package_assessment(conn,row['assessment_id'])
        if new_until and row['retention_until'] and new_until<row['retention_until']:
            raise HTTPException(409,'Working report retention cannot be shortened through this route.')
        target_until=new_until or row['retention_until']
        target_hold=1 if p.legal_hold else row['legal_hold']
        if target_until!=row['retention_until'] or target_hold!=row['legal_hold']:
            conn.execute('UPDATE package_product_report_versions SET retention_until=?,legal_hold=? WHERE id=?',
                (target_until,target_hold,report_id))
            audit(conn,'PACKAGE_REPORT_RETENTION','assessment',row['assessment_id'],
                f'report_id={report_id}; retention_until={target_until}; legal_hold={target_hold}; reason={p.reason.strip()}',actor(request))
            conn.commit()
        return {'id':report_id,'retention_until':target_until,'legal_hold':bool(target_hold),
            'notice':'This route cannot delete a report or clear a legal hold.'}
    finally: conn.close()

@app.post('/api/package-reports/{report_id}/conformance')
def record_package_report_conformance(report_id:int,p:PackageReportConformanceIn,request:Request):
    require_package_commercial_candidate();require(request,'write')
    if role(request) not in {'System Administrator','Assessment Director'}:
        raise HTTPException(403,'A Salus report reviewer must record the conformance matrix.')
    if set(p.checks)!=set(PACKAGE_REPORT_QA_KEYS):
        raise HTTPException(422,'The report conformance matrix requires every current Charter check.')
    for key,item in p.checks.items():
        if set(item)!={'status','reason'} or item['status'] not in ('Met','Pending','Not applicable') or not 8<=len(item['reason'].strip())<=2000:
            raise HTTPException(422,f'{key} needs a valid status and a specific evidence, gate or applicability reason.')
    conn=db()
    try:
        row=conn.execute('SELECT * FROM package_product_report_versions WHERE id=? AND tenant_id=?',
            (report_id,tenant_id(request))).fetchone()
        if not row: raise HTTPException(404,'Working report not found.')
        assessment_row_for_request(request,row['assessment_id'])
        require_package_report_assignment(request,row['assessment_id'])
        lock_package_assessment(conn,row['assessment_id'])
        quote=authorized_package_intake(conn,row['assessment_id'],request)
        if quote['id']!=row['quote_id'] or quote['assessment_scope_sha256']!=row['assessment_scope_sha256']:
            raise HTTPException(409,'The working report belongs to a changed package boundary.')
        if p.content_sha256!=row['content_sha256'] or row['status']!='Draft':
            raise HTTPException(409,'The conformance record must bind to the exact named working document.')
        try: content=storage.get_bytes(row['stored_name'])
        except Exception as exc: raise HTTPException(503,'Working report storage is unavailable.') from exc
        if hashlib.sha256(content).hexdigest()!=row['content_sha256']:
            security_event(request,'PACKAGE_REPORT_QA_HASH_MISMATCH','High',f'report_id={report_id}')
            raise HTTPException(409,'Working report integrity verification failed.')
        checks_json=json.dumps({key:p.checks[key] for key in PACKAGE_REPORT_QA_KEYS},sort_keys=True,separators=(',',':'))
        summary=p.summary.strip()
        record_sha=hashlib.sha256(json.dumps({'report_id':report_id,'content_sha256':p.content_sha256,
            'checks':json.loads(checks_json),'summary':summary},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        prior=conn.execute('SELECT * FROM package_report_conformance WHERE record_sha256=? AND tenant_id=?',
            (record_sha,tenant_id(request))).fetchone()
        if prior: return {'id':prior['id'],'matrix_status':prior['matrix_status'],'record_sha256':record_sha,'idempotent':True}
        matrix_status='Open' if any(item['status']=='Pending' for item in p.checks.values()) else 'Marked'
        cur=conn.execute('''INSERT INTO package_report_conformance
            (tenant_id,assessment_id,report_id,content_sha256,checks_json,summary,matrix_status,record_sha256,recorded_by,recorded_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',(tenant_id(request),row['assessment_id'],report_id,p.content_sha256,
            checks_json,summary,matrix_status,record_sha,actor(request),now()))
        audit(conn,'PACKAGE_REPORT_CONFORMANCE','assessment',row['assessment_id'],
            f'report_id={report_id}; matrix={matrix_status}; sha256={record_sha}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'matrix_status':matrix_status,'record_sha256':record_sha,'idempotent':False,
            'notice':'This record does not approve, issue or qualify the report.'}
    finally: conn.close()

@app.get('/api/package-reports/{report_id}/source-reconciliation')
def list_package_report_reconciliation(report_id:int,request:Request):
    require_package_commercial_candidate();require(request,'read')
    if role(request) not in PACKAGE_REPORT_DRAFT_ROLES:
        raise HTTPException(403,'Working report reconciliation is restricted to Salus report owners.')
    conn=db()
    try:
        report=conn.execute('SELECT assessment_id,product FROM package_product_report_versions WHERE id=? AND tenant_id=?',
            (report_id,tenant_id(request))).fetchone()
        if not report or report['product']!='SalCAPA': raise HTTPException(404,'Working SalCAPA report not found.')
        assessment_row_for_request(request,report['assessment_id'])
        require_package_report_assignment(request,report['assessment_id'])
        rows=[dict(row) for row in conn.execute('SELECT * FROM package_report_reconciliations WHERE tenant_id=? AND salcapa_report_id=? ORDER BY id',
            (tenant_id(request),report_id))]
        for row in rows: row['sources']=json.loads(row.pop('sources_json'))
        return {'records':rows,'notice':'A source comparison is not qualified review, issue or predecessor proof.'}
    finally: conn.close()

@app.post('/api/package-reports/{report_id}/source-reconciliation')
def record_package_report_reconciliation(report_id:int,p:PackageReportReconciliationIn,request:Request):
    require_package_commercial_candidate();require(request,'write')
    if role(request) not in {'System Administrator','Assessment Director'}:
        raise HTTPException(403,'A Salus report reviewer must record the source comparison.')
    if set(p.sources)!={'SalINTEL','SalTHIRA','SalOPS'}:
        raise HTTPException(422,'Compare SalCAPA with each of its three exact source reports.')
    tid=tenant_id(request);conn=db()
    try:
        report=conn.execute('SELECT * FROM package_product_report_versions WHERE id=? AND tenant_id=?',
            (report_id,tid)).fetchone()
        if not report or report['product']!='SalCAPA': raise HTTPException(404,'Working SalCAPA report not found.')
        assessment_row_for_request(request,report['assessment_id'])
        require_package_report_assignment(request,report['assessment_id'])
        lock_package_assessment(conn,report['assessment_id'])
        quote=authorized_package_intake(conn,report['assessment_id'],request)
        if (quote['id']!=report['quote_id'] or quote['assessment_scope_sha256']!=report['assessment_scope_sha256']
                or report['status']!='Draft' or p.salcapa_sha256!=report['content_sha256']):
            raise HTTPException(409,'The SalCAPA document or authorized package boundary changed.')
        selected={'SalCAPA':report}
        for product in ('SalINTEL','SalTHIRA','SalOPS'):
            source=conn.execute('''SELECT * FROM package_product_report_versions WHERE tenant_id=? AND assessment_id=?
                AND product=? ORDER BY version_no DESC LIMIT 1''',(tid,report['assessment_id'],product)).fetchone()
            supplied=p.sources[product]
            if (not source or source['id']!=supplied.report_id or source['content_sha256']!=supplied.content_sha256
                    or source['quote_id']!=quote['id'] or source['assessment_scope_sha256']!=report['assessment_scope_sha256']
                    or source['status']!='Draft'):
                raise HTTPException(409,f'The current {product} source version or package boundary changed.')
            selected[product]=source
        latest_capa=conn.execute('''SELECT id FROM package_product_report_versions WHERE tenant_id=? AND assessment_id=?
            AND product='SalCAPA' ORDER BY version_no DESC LIMIT 1''',(tid,report['assessment_id'])).fetchone()
        if latest_capa['id']!=report_id: raise HTTPException(409,'Compare the current SalCAPA version.')
        for product,item in selected.items():
            try: content=storage.get_bytes(item['stored_name'])
            except Exception as exc: raise HTTPException(503,'Working report storage is unavailable.') from exc
            if hashlib.sha256(content).hexdigest()!=item['content_sha256']:
                security_event(request,'PACKAGE_RECONCILIATION_HASH_MISMATCH','High',f'report_id={item["id"]}')
                raise HTTPException(409,f'{product} document integrity verification failed.')
        sources={product:p.sources[product].model_dump() for product in ('SalINTEL','SalTHIRA','SalOPS')}
        summary=p.summary.strip()
        comparison_status='Open' if any(item['alignment']=='Unresolved' for item in sources.values()) else 'Compared'
        digest=hashlib.sha256(json.dumps({'salcapa_report_id':report_id,'salcapa_sha256':p.salcapa_sha256,
            'sources':sources,'summary':summary},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        prior=conn.execute('SELECT id,comparison_status FROM package_report_reconciliations WHERE tenant_id=? AND record_sha256=?',
            (tid,digest)).fetchone()
        if prior: return {'id':prior['id'],'comparison_status':prior['comparison_status'],'record_sha256':digest,'idempotent':True}
        cur=conn.execute('''INSERT INTO package_report_reconciliations
            (tenant_id,assessment_id,quote_id,salcapa_report_id,salcapa_sha256,sources_json,summary,comparison_status,record_sha256,recorded_by,recorded_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(tid,report['assessment_id'],quote['id'],report_id,p.salcapa_sha256,
            json.dumps(sources,sort_keys=True,separators=(',',':')),summary,comparison_status,digest,actor(request),now()))
        audit(conn,'PACKAGE_REPORT_SOURCE_RECONCILIATION','assessment',report['assessment_id'],
            f'salcapa_report_id={report_id}; comparison={comparison_status}; sha256={digest}',actor(request))
        conn.commit()
        return {'id':cur.lastrowid,'comparison_status':comparison_status,'record_sha256':digest,'idempotent':False,
            'notice':'This comparison does not approve or issue any report.'}
    finally: conn.close()

@app.post('/api/assessments/{assessment_id}/reassessment-review')
def review_assessment_reassessment(assessment_id:int,p:AssessmentReassessmentReviewIn,request:Request):
    require(request,'decide'); assessment_row_for_request(request,assessment_id); next_date=_normalize_date(p.next_reassessment_date,'Next assessment reassessment date',required=True); outcome=(p.review_outcome or '').strip()
    if not outcome: raise HTTPException(422,'Assessment reassessment review requires a documented outcome.')
    if datetime.strptime(next_date,'%Y-%m-%d').date()<=datetime.now(timezone.utc).date(): raise HTTPException(422,'Next assessment reassessment date must be in the future.')
    sweep_overdue_assessments([assessment_id]); conn=db(); assessment=conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone(); who=actor(request); ts=now(); trigger_ids=[r['id'] for r in conn.execute("SELECT id FROM reassessment_triggers WHERE source='Assessment Lifecycle' AND affected_record_type='assessment' AND affected_record_id=? AND status!='Resolved'",(assessment_id,))]
    conn.execute("UPDATE assessments SET reassessment_date=?,reassessment_lifecycle_status='Current',reassessment_overdue_reason='',reassessment_overdue_at='',last_reassessment_review_at=?,last_reassessment_review_by=?,updated_at=? WHERE id=?",(next_date,ts,who,ts,assessment_id)); resolution=f'Assessment reassessment reviewed and renewed through {next_date}: {outcome}'
    conn.execute("UPDATE reassessment_triggers SET status='Resolved',resolution=?,updated_at=? WHERE source='Assessment Lifecycle' AND affected_record_type='assessment' AND affected_record_id=? AND status!='Resolved'",(resolution,ts,assessment_id))
    for trigger_id in trigger_ids: snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Assessment overdue trigger resolved after controlled review')
    audit(conn,'ASSESSMENT_REASSESSMENT_REVIEW','assessment',assessment_id,resolution,who); snapshot_entity(conn,'assessments',assessment_id,who,'Controlled assessment reassessment review'); conn.commit(); row=dict(conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone()); conn.close(); return row
@app.post('/api/threats')
def create_threat(p:ThreatIn, request:Request):
    require(request,'write'); assessment_row_for_request(request,p.assessment_id); return insert_model('threats',p,actor(request),extra={'status':'Active'})
@app.post('/api/scenarios')
def create_scenario(p:ScenarioIn, request:Request):
    require(request,'write'); assessment_row_for_request(request,p.assessment_id); validate_relationship_payload('scenarios',p.assessment_id,p.model_dump()); return insert_model('scenarios',p,actor(request))
@app.post('/api/capabilities')
def create_capability(p:CapabilityIn, request:Request):
    require(request,'write'); assessment_row_for_request(request,p.assessment_id); validate_relationship_payload('capabilities',p.assessment_id,p.model_dump())
    validate_capability_measurement(p.measurement_type,p.comparator,p.required_standard,p.current_performance)
    last_validated=_normalize_date(p.last_validated,'Capability last-validated date')
    next_validation=_normalize_date(p.next_validation,'Capability next-validation date')
    return insert_model('capabilities',p,actor(request),extra={'last_validated':last_validated,'next_validation':next_validation})
@app.post('/api/evidence')
def create_evidence(p:EvidenceIn, request:Request):
    require(request,'write'); assessment_row_for_request(request,p.assessment_id); require_sensitivity(request,p.sensitivity); validate_relationship_payload('evidence',p.assessment_id,p.model_dump())
    sweep_stale_evidence([p.assessment_id])
    evidence_date=_normalize_date(p.evidence_date,'Evidence date')
    valid_until=_normalize_date(p.valid_until,'Evidence valid-until date')
    row=insert_model('evidence',p,actor(request),extra={'evidence_date':evidence_date,'valid_until':valid_until,'lifecycle_status':'Current','stale_reason':'','stale_at':'','last_lifecycle_review_at':'','last_lifecycle_review_by':''})
    sweep_stale_evidence([p.assessment_id])
    conn=db(); refreshed=dict(conn.execute('SELECT * FROM evidence WHERE id=?',(row['id'],)).fetchone()); conn.close(); return refreshed

@app.post('/api/evidence/{evidence_id}/lifecycle-review')
def review_evidence_lifecycle(evidence_id:int,p:EvidenceLifecycleReviewIn,request:Request):
    require(request,'write'); valid_until=_normalize_date(p.valid_until,'New evidence valid-until date',required=True); note=(p.review_note or '').strip()
    if not note: raise HTTPException(422,'Evidence lifecycle review requires a documented review note.')
    expiry=datetime.strptime(valid_until,'%Y-%m-%d').date(); today=datetime.now(timezone.utc).date()
    if expiry<today: raise HTTPException(422,'A lifecycle review cannot restore evidence with a validity date already in the past.')
    conn=db(); ev=conn.execute('SELECT * FROM evidence WHERE id=?',(evidence_id,)).fetchone()
    if not ev: conn.close(); raise HTTPException(404,'Evidence not found')
    assessment_row_for_request(request,ev['assessment_id']); require_sensitivity(request,ev['sensitivity']); who=actor(request); ts=now()
    trigger_ids=[r['id'] for r in conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Evidence Lifecycle' AND trigger_type='Evidence Stale' AND affected_record_type='evidence' AND affected_record_id=? AND status!='Resolved'",(ev['assessment_id'],evidence_id))]
    conn.execute("UPDATE evidence SET valid_until=?,lifecycle_status='Current',stale_reason='',stale_at='',last_lifecycle_review_at=?,last_lifecycle_review_by=?,updated_at=? WHERE id=?",(valid_until,ts,who,ts,evidence_id))
    resolution=f'Evidence lifecycle reviewed and restored to Current through {valid_until}: {note}'
    conn.execute("UPDATE reassessment_triggers SET status='Resolved',resolution=?,updated_at=? WHERE assessment_id=? AND source='Evidence Lifecycle' AND trigger_type='Evidence Stale' AND affected_record_type='evidence' AND affected_record_id=? AND status!='Resolved'",(resolution,ts,ev['assessment_id'],evidence_id))
    for tid in trigger_ids: snapshot_entity(conn,'reassessment_triggers',tid,who,'Stale-evidence trigger resolved after lifecycle review')
    audit(conn,'EVIDENCE_LIFECYCLE_REVIEW','evidence',evidence_id,resolution,who); snapshot_entity(conn,'evidence',evidence_id,who,'Controlled evidence lifecycle review')
    conn.commit(); row=dict(conn.execute('SELECT * FROM evidence WHERE id=?',(evidence_id,)).fetchone()); conn.close(); return row
@app.post('/api/gaps')
def create_gap(p:GapIn, request:Request):
    require(request,'write'); assessment_row_for_request(request,p.assessment_id); validate_relationship_payload('gaps',p.assessment_id,p.model_dump()); return insert_model('gaps',p,actor(request),extra={'status':'Open'})

@app.post('/api/gaps/{gap_id}/transition')
def transition_gap(gap_id:int,p:GapTransitionIn,request:Request):
    require(request,'write'); conn=db(); gap=conn.execute('SELECT * FROM gaps WHERE id=?',(gap_id,)).fetchone()
    if not gap: conn.close(); raise HTTPException(404,'Gap not found')
    assessment_row_for_request(request,gap['assessment_id']); current=str(gap['status']); target=p.status
    allowed={
        'Open':{'Under Review','Mitigating','Closed'},
        'Under Review':{'Open','Mitigating','Closed'},
        'Mitigating':{'Open','Under Review','Closed'},
        'Closed':{'Open'},
    }
    if target==current: conn.close(); raise HTTPException(409,'Gap is already in the requested lifecycle state.')
    if target not in allowed.get(current,set()): conn.close(); raise HTTPException(409,f'Gap lifecycle transition from {current} to {target} is not permitted.')
    who=actor(request); ts=now(); conn.execute('UPDATE gaps SET status=?,updated_at=? WHERE id=?',(target,ts,gap_id))
    detail=f'{current} -> {target}: {p.reason}'; audit(conn,'GAP_TRANSITION','gap',gap_id,detail,who); snapshot_entity(conn,'gaps',gap_id,who,'Controlled gap lifecycle transition')
    conn.commit(); row=dict(conn.execute('SELECT * FROM gaps WHERE id=?',(gap_id,)).fetchone()); conn.close(); return row

@app.post('/api/improvements')
def create_improvement(p:ImprovementIn, request:Request):
    require(request,'write'); assessment_row_for_request(request,p.assessment_id); validate_relationship_payload('improvements',p.assessment_id,p.model_dump()); return insert_model('improvements',p,actor(request),extra={'status':'Proposed','validation_status':'Pending','validation_evidence_id':None,'validation_outcome':'','validated_effectiveness_percent':0,'validated_by':'','validated_at':''})

def _open_improvement_completion_trigger(conn,improvement,who):
    existing=conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Completed Improvement' AND trigger_type='Capability Validation' AND affected_record_type='improvement' AND affected_record_id=? AND status!='Resolved' ORDER BY id DESC LIMIT 1",(improvement['assessment_id'],improvement['id'])).fetchone()
    if existing: return int(existing['id'])
    ts=now(); cur=conn.execute('''INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(improvement['assessment_id'],'Completed Improvement','Capability Validation',f'Improvement completed: {improvement["title"]}. Validate capability performance and recalculate residual risk.','High','improvement',improvement['id'],'Open',improvement['owner'],'','',ts,ts))
    trigger_id=cur.lastrowid; audit(conn,'CREATE','reassessment_trigger',trigger_id,'Automatically created after controlled improvement completion',who); snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Automatic capability validation trigger'); return trigger_id

@app.post('/api/improvements/{improvement_id}/transition')
def transition_improvement(improvement_id:int,p:ImprovementTransitionIn,request:Request):
    require(request,'write'); conn=db(); imp=conn.execute('SELECT * FROM improvements WHERE id=?',(improvement_id,)).fetchone()
    if not imp: conn.close(); raise HTTPException(404,'Improvement not found')
    assessment_row_for_request(request,imp['assessment_id']); current=str(imp['status']); target=p.status
    allowed={
        'Proposed':{'Under Review','Deferred','Rejected'},
        'Under Review':{'Proposed','Approved','Deferred','Rejected'},
        'Approved':{'In Progress','Deferred'},
        'In Progress':{'Complete','Deferred'},
        'Deferred':{'Under Review','Approved','In Progress','Rejected'},
        'Rejected':{'Under Review'},
        'Complete':set(),
    }
    if target==current: conn.close(); raise HTTPException(409,'Improvement is already in the requested lifecycle state.')
    if target not in allowed.get(current,set()): conn.close(); raise HTTPException(409,f'Improvement lifecycle transition from {current} to {target} is not permitted.')
    who=actor(request); ts=now(); conn.execute('UPDATE improvements SET status=?,updated_at=? WHERE id=?',(target,ts,improvement_id))
    detail=f'{current} -> {target}: {p.reason}'; audit(conn,'IMPROVEMENT_TRANSITION','improvement',improvement_id,detail,who); snapshot_entity(conn,'improvements',improvement_id,who,'Controlled improvement lifecycle transition')
    if target=='Complete':
        refreshed=conn.execute('SELECT * FROM improvements WHERE id=?',(improvement_id,)).fetchone(); _open_improvement_completion_trigger(conn,refreshed,who)
    conn.commit(); row=dict(conn.execute('SELECT * FROM improvements WHERE id=?',(improvement_id,)).fetchone()); conn.close(); return row

@app.post('/api/improvements/{improvement_id}/validate')
def validate_improvement(improvement_id:int,p:ImprovementValidationIn,request:Request):
    require(request,'write'); conn=db(); imp=conn.execute('SELECT * FROM improvements WHERE id=?',(improvement_id,)).fetchone()
    if not imp: conn.close(); raise HTTPException(404,'Improvement not found')
    aid=int(imp['assessment_id']); conn.close(); assessment_row_for_request(request,aid); sweep_stale_evidence([aid])
    conn=db(); imp=conn.execute('SELECT * FROM improvements WHERE id=?',(improvement_id,)).fetchone()
    if imp['status']!='Complete': conn.close(); raise HTTPException(409,'Improvement must be Complete before validation can be recorded.')
    status=(p.validation_status or '').strip()
    if status not in {'Validated','Partially Validated','Failed'}: conn.close(); raise HTTPException(422,'Validation status must be Validated, Partially Validated, or Failed.')
    outcome=(p.validation_outcome or '').strip()
    if not outcome: conn.close(); raise HTTPException(422,'Validation requires a documented outcome.')
    effect=float(p.validated_effectiveness_percent)
    if not 0 <= effect <= 100: conn.close(); raise HTTPException(422,'Validated effectiveness must be between 0 and 100.')
    if status=='Failed' and effect!=0: conn.close(); raise HTTPException(422,'Failed validation must record 0% validated effectiveness.')
    if status=='Validated' and effect<=0: conn.close(); raise HTTPException(422,'Validated improvement must record effectiveness greater than 0%.')
    if status=='Partially Validated' and not 0 < effect < 100: conn.close(); raise HTTPException(422,'Partially Validated effectiveness must be greater than 0% and less than 100%.')
    ev=conn.execute('SELECT * FROM evidence WHERE id=?',(p.evidence_id,)).fetchone()
    if not ev or int(ev['assessment_id'])!=int(imp['assessment_id']): conn.close(); raise HTTPException(422,'Validation evidence must belong to the same assessment.')
    require_sensitivity(request,ev['sensitivity'])
    if not evidence_is_effective(ev): conn.close(); raise HTTPException(409,'Improvement validation requires evidence that is Verified and lifecycle Current (not expired or stale).')
    ts=now(); who=actor(request)
    resolved_trigger_ids=[r['id'] for r in conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND affected_record_type='improvement' AND affected_record_id=? AND status!='Resolved'",(imp['assessment_id'],improvement_id))]
    conn.execute('''UPDATE improvements SET validation_status=?,validation_evidence_id=?,validation_outcome=?,validated_effectiveness_percent=?,validated_by=?,validated_at=?,updated_at=? WHERE id=?''',(status,p.evidence_id,outcome,effect,who,ts,ts,improvement_id))
    conn.execute("UPDATE reassessment_triggers SET status='Resolved',resolution=?,updated_at=? WHERE assessment_id=? AND affected_record_type='improvement' AND affected_record_id=? AND status!='Resolved'",(f'{status}: {outcome}',ts,imp['assessment_id'],improvement_id))
    for trigger_id in resolved_trigger_ids: snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Improvement validation trigger resolved')
    if status=='Failed':
        cur=conn.execute('''INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,affected_record_type,affected_record_id,status,assigned_to,due_date,resolution,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(imp['assessment_id'],'Improvement Validation','Corrective Action Required',f'Validation failed for improvement: {imp["title"]}. {outcome}','High','improvement',improvement_id,'Open',imp['owner'],'','',ts,ts))
        audit(conn,'CREATE','reassessment_trigger',cur.lastrowid,'Created after failed improvement validation',who)
        snapshot_entity(conn,'reassessment_triggers',cur.lastrowid,who,'Corrective action trigger after failed validation')
    audit(conn,'VALIDATE','improvement',improvement_id,f'{status}; evidence_id={p.evidence_id}; effectiveness={effect}%; {outcome}',who)
    snapshot_entity(conn,'improvements',improvement_id,who,'Controlled improvement validation')
    conn.commit(); row=dict(conn.execute('SELECT * FROM improvements WHERE id=?',(improvement_id,)).fetchone()); conn.close(); return row

@app.post('/api/decisions')
def create_decision(p:DecisionIn, request:Request):
    require_protected_member_authority(request,'executive_decision'); assessment_row_for_request(request,p.assessment_id)
    review_date=_normalize_date(p.review_date,'Executive decision review date')
    target_completion=_normalize_date(p.target_completion,'Executive decision target completion date')
    if review_date and datetime.strptime(review_date,'%Y-%m-%d').date()<=datetime.now(timezone.utc).date(): raise HTTPException(422,'Executive decision review date must be in the future.')
    if p.decision_type=='Accept Risk':
        if not review_date: raise HTTPException(422,'Accept Risk decisions require a future review date.')
        if not p.expected_residual_risk: raise HTTPException(422,'Accept Risk decisions require an explicit residual exposure statement.')
        if not p.implementation_owner: raise HTTPException(422,'Accept Risk decisions require an accountable risk owner.')
        if not p.conditions: raise HTTPException(422,'Accept Risk decisions require a documented reconsideration trigger.')
    conn=db()
    try:
        validate_entity_relationships(conn,'decisions',p.assessment_id,p.model_dump())
        who=actor(request)
        row=insert_model_in_transaction(conn,'decisions',p,who,extra={'authority':who,'target_completion':target_completion,'review_date':review_date,'review_lifecycle_status':'Current','review_overdue_reason':'','review_overdue_at':'','last_review_at':'','last_review_by':''})
        improvement=conn.execute('SELECT * FROM improvements WHERE id=?',(p.improvement_id,)).fetchone() if p.improvement_id else None
        if improvement:
            decision_status={
                'Approve':'Approved','Approve with Conditions':'Approved','Modify':'Under Review',
                'Defer':'Deferred','Reject':'Rejected','Transfer Risk':'Deferred',
                'Accept Risk':'Deferred','Continue Monitoring':'Deferred',
            }.get(p.decision_type)
            if improvement['status']!='Complete' and decision_status and improvement['status']!=decision_status:
                conn.execute('UPDATE improvements SET status=?, updated_at=? WHERE id=?',(decision_status,now(),p.improvement_id))
                audit(conn,'IMPROVEMENT_DECISION_TRANSITION','improvement',p.improvement_id,f'{improvement["status"]} -> {decision_status}; executive decision #{row["id"]}: {p.decision_type}',who)
                snapshot_entity(conn,'improvements',p.improvement_id,who,'Lifecycle state set by executive decision')
        if p.decision_type=='Accept Risk':
            gap_id=int(improvement['gap_id']) if improvement and improvement['gap_id'] is not None else None
            title=(str(improvement['title']).strip() if improvement else '') or f'Accepted Risk — Decision #{row["id"]}'
            ts=now()
            cur=conn.execute('''INSERT INTO accepted_risks(assessment_id,decision_id,improvement_id,gap_id,title,risk_statement,authority,residual_exposure,acceptance_date,review_date,reconsideration_trigger,owner,status,closure_basis,review_lifecycle_status,review_overdue_reason,review_overdue_at,last_review_at,last_review_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(p.assessment_id,row['id'],p.improvement_id,gap_id,title,p.rationale,who,p.expected_residual_risk,ts[:10],review_date,p.conditions,p.implementation_owner,'Active','','Current','','','','',ts,ts))
            accepted_id=cur.lastrowid
            audit(conn,'CREATE','accepted_risk',accepted_id,f'Accepted risk created atomically from executive decision #{row["id"]}',who)
            snapshot_entity(conn,'accepted_risks',accepted_id,who,'Accepted risk created atomically from executive decision')
        conn.commit()
        return row
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

@app.post('/api/decisions/{decision_id}/review')
def review_executive_decision(decision_id:int,p:DecisionReviewIn,request:Request):
    require_protected_member_authority(request,'executive_decision_review'); next_review=_normalize_date(p.next_review_date,'Next executive decision review date',required=True); outcome=(p.review_outcome or '').strip()
    if not outcome: raise HTTPException(422,'Executive decision review requires a documented outcome.')
    if datetime.strptime(next_review,'%Y-%m-%d').date()<=datetime.now(timezone.utc).date(): raise HTTPException(422,'Next executive decision review date must be in the future.')
    conn=db(); decision=conn.execute('SELECT * FROM decisions WHERE id=?',(decision_id,)).fetchone(); conn.close()
    if not decision: raise HTTPException(404)
    assessment_row_for_request(request,decision['assessment_id']); sweep_overdue_decisions([decision['assessment_id']])
    conn=db(); who=actor(request); ts=now(); trigger_ids=[r['id'] for r in conn.execute("SELECT id FROM reassessment_triggers WHERE source='Decision Lifecycle' AND affected_record_type='decision' AND affected_record_id=? AND status!='Resolved'",(decision_id,))]
    conn.execute("UPDATE decisions SET review_date=?,review_lifecycle_status='Current',review_overdue_reason='',review_overdue_at='',last_review_at=?,last_review_by=?,updated_at=? WHERE id=?",(next_review,ts,who,ts,decision_id)); resolution=f'Executive decision reviewed and renewed through {next_review}: {outcome}'
    conn.execute("UPDATE reassessment_triggers SET status='Resolved',resolution=?,updated_at=? WHERE source='Decision Lifecycle' AND affected_record_type='decision' AND affected_record_id=? AND status!='Resolved'",(resolution,ts,decision_id))
    for trigger_id in trigger_ids: snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Decision overdue trigger resolved after controlled review')
    audit(conn,'DECISION_REVIEW','decision',decision_id,resolution,who); snapshot_entity(conn,'decisions',decision_id,who,'Controlled executive decision review'); conn.commit(); row=dict(conn.execute('SELECT * FROM decisions WHERE id=?',(decision_id,)).fetchone()); conn.close(); return row

@app.post('/api/accepted-risks/{risk_id}/review')
def review_accepted_risk(risk_id:int,p:AcceptedRiskReviewIn,request:Request):
    require_protected_member_authority(request,'accepted_risk_review'); next_review=_normalize_date(p.next_review_date,'Next accepted-risk review date',required=True); outcome=(p.review_outcome or '').strip()
    if not outcome: raise HTTPException(422,'Accepted-risk review requires a documented outcome.')
    if datetime.strptime(next_review,'%Y-%m-%d').date()<=datetime.now(timezone.utc).date(): raise HTTPException(422,'Next accepted-risk review date must be in the future.')
    conn=db(); risk=conn.execute('SELECT * FROM accepted_risks WHERE id=?',(risk_id,)).fetchone()
    if not risk: conn.close(); raise HTTPException(404,'Accepted risk not found.')
    aid=int(risk['assessment_id']); conn.close(); assessment_row_for_request(request,aid); sweep_overdue_accepted_risks([aid])
    conn=db(); risk=conn.execute('SELECT * FROM accepted_risks WHERE id=?',(risk_id,)).fetchone()
    if risk['status'] not in ('Active','Under Review'): conn.close(); raise HTTPException(409,'Only Active or Under Review accepted risks can be reviewed and renewed.')
    who=actor(request); ts=now()
    trigger_ids=[r['id'] for r in conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Accepted Risk Lifecycle' AND trigger_type='Accepted Risk Review Overdue' AND affected_record_type='accepted_risk' AND affected_record_id=? AND status!='Resolved'",(aid,risk_id))]
    conn.execute("UPDATE accepted_risks SET status='Active',review_date=?,review_lifecycle_status='Current',review_overdue_reason='',review_overdue_at='',last_review_at=?,last_review_by=?,updated_at=? WHERE id=?",(next_review,ts,who,ts,risk_id))
    resolution=f'Accepted risk reviewed and renewed through {next_review}: {outcome}'
    conn.execute("UPDATE reassessment_triggers SET status='Resolved',resolution=?,updated_at=? WHERE assessment_id=? AND source='Accepted Risk Lifecycle' AND trigger_type='Accepted Risk Review Overdue' AND affected_record_type='accepted_risk' AND affected_record_id=? AND status!='Resolved'",(resolution,ts,aid,risk_id))
    for trigger_id in trigger_ids: snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Accepted-risk overdue trigger resolved after controlled review')
    audit(conn,'ACCEPTED_RISK_REVIEW','accepted_risk',risk_id,resolution,who); snapshot_entity(conn,'accepted_risks',risk_id,who,'Controlled accepted-risk review')
    conn.commit(); row=dict(conn.execute('SELECT * FROM accepted_risks WHERE id=?',(risk_id,)).fetchone()); conn.close(); return row

@app.post('/api/accepted-risks/{risk_id}/transition')
def transition_accepted_risk(risk_id:int,p:AcceptedRiskTransitionIn,request:Request):
    require_protected_member_authority(request,'accepted_risk_transition')
    conn=db(); risk=conn.execute('SELECT * FROM accepted_risks WHERE id=?',(risk_id,)).fetchone(); conn.close()
    if not risk: raise HTTPException(404,'Accepted risk not found.')
    aid=int(risk['assessment_id']); assessment_row_for_request(request,aid); sweep_overdue_accepted_risks([aid])
    conn=db()
    try:
        risk=conn.execute('SELECT * FROM accepted_risks WHERE id=?',(risk_id,)).fetchone()
        current=str(risk['status']); target=p.status
        if current==target: raise HTTPException(409,'Accepted risk is already in the requested state.')
        if current in ('Closed','Superseded'): raise HTTPException(409,'Closed or Superseded accepted risks are terminal and cannot be reopened.')
        allowed={'Active':{'Under Review','Closed','Superseded'},'Under Review':{'Closed','Superseded'}}
        if target not in allowed.get(current,set()): raise HTTPException(409,f'Accepted risk cannot transition from {current} to {target}.')
        who=actor(request); ts=now(); closure_basis=p.reason if target in ('Closed','Superseded') else str(risk['closure_basis'] or '')
        conn.execute('UPDATE accepted_risks SET status=?,closure_basis=?,updated_at=? WHERE id=?',(target,closure_basis,ts,risk_id))
        if target in ('Closed','Superseded'):
            resolution=f'Accepted risk {target.lower()}: {p.reason}'
            trigger_ids=[r['id'] for r in conn.execute("SELECT id FROM reassessment_triggers WHERE assessment_id=? AND source='Accepted Risk Lifecycle' AND affected_record_type='accepted_risk' AND affected_record_id=? AND status!='Resolved'",(aid,risk_id))]
            conn.execute("UPDATE reassessment_triggers SET status='Resolved',resolution=?,updated_at=? WHERE assessment_id=? AND source='Accepted Risk Lifecycle' AND affected_record_type='accepted_risk' AND affected_record_id=? AND status!='Resolved'",(resolution,ts,aid,risk_id))
            for trigger_id in trigger_ids: snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Accepted-risk lifecycle trigger resolved by terminal transition')
        detail=f'{current} -> {target}: {p.reason}'
        audit(conn,'ACCEPTED_RISK_TRANSITION','accepted_risk',risk_id,detail,who); snapshot_entity(conn,'accepted_risks',risk_id,who,'Controlled accepted-risk status transition')
        conn.commit(); return dict(conn.execute('SELECT * FROM accepted_risks WHERE id=?',(risk_id,)).fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _risk_row_for_threat(assessment_id:int, threat_id:int):
    row=next((r for r in risk_summary(assessment_id) if int(r['threat_id'])==int(threat_id)),None)
    if not row: raise HTTPException(404,'Threat / hazard not found in risk model.')
    return row

@app.post('/api/risk-overrides')
def create_risk_override(p:RiskOverrideIn, request:Request):
    require(request,'decide'); assessment_row_for_request(request,p.assessment_id); sweep_stale_evidence([p.assessment_id])
    if not 0 <= float(p.assigned_score) <= 100: raise HTTPException(422,'Assigned risk score must be between 0 and 100.')
    if not p.reason.strip(): raise HTTPException(422,'Professional risk override requires a documented reason.')
    review_date=_normalize_date(p.review_date,'Professional risk override review date') or (datetime.now(timezone.utc).date()+timedelta(days=90)).isoformat()
    if datetime.strptime(review_date,'%Y-%m-%d').date()<=datetime.now(timezone.utc).date(): raise HTTPException(422,'Professional risk override review date must be in the future.')
    conn=db()
    try:
        validate_entity_relationships(conn,'risk_overrides',p.assessment_id,p.model_dump())
        if p.evidence_id is not None:
            ev=conn.execute('SELECT * FROM evidence WHERE id=?',(p.evidence_id,)).fetchone()
            if not ev: raise HTTPException(422,'Supporting evidence does not exist.')
            require_sensitivity(request,ev['sensitivity'])
            if not evidence_is_effective(ev): raise HTTPException(409,'Professional risk override evidence must be Verified and lifecycle Current (not expired or stale).')
        current=_risk_row_for_threat(p.assessment_id,p.threat_id)
        previous=conn.execute("SELECT * FROM risk_overrides WHERE assessment_id=? AND threat_id=? AND status='Active' ORDER BY id DESC LIMIT 1",(p.assessment_id,p.threat_id)).fetchone()
        ts=now(); who=actor(request)
        if previous:
            conn.execute("UPDATE risk_overrides SET status='Superseded',updated_at=? WHERE id=?",(ts,previous['id']))
            audit(conn,'SUPERSEDE','risk_override',previous['id'],f'Superseded by new professional judgment for threat #{p.threat_id}',who)
            snapshot_entity(conn,'risk_overrides',previous['id'],who,'Risk override superseded')
        cur=conn.execute('''INSERT INTO risk_overrides(assessment_id,threat_id,calculated_score,calculated_band,assigned_score,assigned_band,reason,evidence_id,authority,review_date,review_lifecycle_status,review_overdue_reason,review_overdue_at,last_review_at,last_review_by,status,supersedes_id,withdrawn_reason,created_by,created_at,withdrawn_by,withdrawn_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(p.assessment_id,p.threat_id,current['current_score'],current['current_band'],float(p.assigned_score),risk_band(float(p.assigned_score)),p.reason.strip(),p.evidence_id,who,review_date,'Current','','','','','Active',previous['id'] if previous else None,'',who,ts,'','',ts))
        oid=cur.lastrowid
        audit(conn,'CREATE','risk_override',oid,f"Calculated {current['current_band']} {current['current_score']} -> assigned {risk_band(float(p.assigned_score))} {float(p.assigned_score):.1f}; authority={who}",who)
        snapshot_entity(conn,'risk_overrides',oid,who,'Professional risk override recorded')
        conn.commit(); return dict(conn.execute('SELECT * FROM risk_overrides WHERE id=?',(oid,)).fetchone())
    finally:
        conn.close()

@app.post('/api/risk-overrides/{override_id}/withdraw')
def withdraw_risk_override(override_id:int,p:RiskOverrideWithdrawIn,request:Request):
    require(request,'decide')
    reason=(p.reason or '').strip()
    if not reason: raise HTTPException(422,'Withdrawing a professional risk override requires a documented reason.')
    conn=db()
    try:
        row=conn.execute('SELECT * FROM risk_overrides WHERE id=?',(override_id,)).fetchone()
        if not row: raise HTTPException(404,'Risk override not found.')
        assessment_row_for_request(request,row['assessment_id'])
        if row['status']!='Active': raise HTTPException(409,'Only the active professional risk override can be withdrawn.')
        ts=now(); who=actor(request)
        conn.execute("UPDATE risk_overrides SET status='Withdrawn',withdrawn_reason=?,withdrawn_by=?,withdrawn_at=?,updated_at=? WHERE id=?",(reason,who,ts,ts,override_id))
        conn.execute("UPDATE reassessment_triggers SET status='Resolved',resolution=?,updated_at=? WHERE source='Risk Override Lifecycle' AND affected_record_type='risk_override' AND affected_record_id=? AND status!='Resolved'",(f'Override withdrawn: {reason}',ts,override_id))
        audit(conn,'WITHDRAW','risk_override',override_id,reason,who)
        snapshot_entity(conn,'risk_overrides',override_id,who,'Professional risk override withdrawn')
        conn.commit(); return dict(conn.execute('SELECT * FROM risk_overrides WHERE id=?',(override_id,)).fetchone())
    finally:
        conn.close()

@app.post('/api/risk-overrides/{override_id}/review')
def review_risk_override(override_id:int,p:RiskOverrideReviewIn,request:Request):
    require(request,'decide'); next_review=_normalize_date(p.next_review_date,'Next professional risk override review date',required=True); outcome=(p.review_outcome or '').strip()
    if not outcome: raise HTTPException(422,'Professional risk override review requires a documented outcome.')
    if datetime.strptime(next_review,'%Y-%m-%d').date()<=datetime.now(timezone.utc).date(): raise HTTPException(422,'Next professional risk override review date must be in the future.')
    conn=db(); override=conn.execute('SELECT * FROM risk_overrides WHERE id=?',(override_id,)).fetchone()
    if not override: conn.close(); raise HTTPException(404,'Risk override not found.')
    aid=int(override['assessment_id']); conn.close(); assessment_row_for_request(request,aid); sweep_overdue_risk_overrides([aid]); conn=db(); override=conn.execute('SELECT * FROM risk_overrides WHERE id=?',(override_id,)).fetchone()
    if override['status']!='Active': conn.close(); raise HTTPException(409,'Only an Active professional risk override can be reviewed and renewed.')
    if override['evidence_id'] is not None:
        supporting=conn.execute('SELECT * FROM evidence WHERE id=?',(override['evidence_id'],)).fetchone()
        if not supporting or not evidence_is_effective(supporting):
            conn.close(); raise HTTPException(409,'Professional risk override review cannot renew assigned risk while its supporting evidence is stale, expired, missing, or not Verified.')
        require_sensitivity(request,supporting['sensitivity'])
    who=actor(request); ts=now(); trigger_ids=[r['id'] for r in conn.execute("SELECT id FROM reassessment_triggers WHERE source='Risk Override Lifecycle' AND affected_record_type='risk_override' AND affected_record_id=? AND status!='Resolved'",(override_id,))]
    conn.execute("UPDATE risk_overrides SET review_date=?,review_lifecycle_status='Current',review_overdue_reason='',review_overdue_at='',last_review_at=?,last_review_by=?,updated_at=? WHERE id=?",(next_review,ts,who,ts,override_id)); resolution=f'Professional risk override reviewed and renewed through {next_review}: {outcome}'
    conn.execute("UPDATE reassessment_triggers SET status='Resolved',resolution=?,updated_at=? WHERE source='Risk Override Lifecycle' AND affected_record_type='risk_override' AND affected_record_id=? AND status!='Resolved'",(resolution,ts,override_id))
    for trigger_id in trigger_ids: snapshot_entity(conn,'reassessment_triggers',trigger_id,who,'Risk-override overdue trigger resolved after controlled review')
    audit(conn,'RISK_OVERRIDE_REVIEW','risk_override',override_id,resolution,who); snapshot_entity(conn,'risk_overrides',override_id,who,'Controlled professional risk-override review'); conn.commit(); row=dict(conn.execute('SELECT * FROM risk_overrides WHERE id=?',(override_id,)).fetchone()); conn.close(); return row

@app.post('/api/reassessment_triggers')
def create_trigger(p:TriggerIn, request: Request):
    require(request,'write'); assessment_row_for_request(request,p.assessment_id); validate_relationship_payload('reassessment_triggers',p.assessment_id,p.model_dump())
    return insert_model('reassessment_triggers',p,actor(request))

@app.get('/api/system/access')
def access(request: Request):
    ctx=auth_context(request); r=ctx['role']; return {'user':ctx['user'],'role':r,'tenant_id':ctx['tenant_id'],'auth_mode':AUTH_MODE,'clearance':ctx.get('clearance','Standard'),'permissions':sorted(ROLE_PERMISSIONS.get(r,{'read'})),'roles':list(ROLE_PERMISSIONS.keys())}

def risk_summary(assessment_id:int):
    conn=db()
    threats=[dict(x) for x in conn.execute('SELECT * FROM threats WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    scenarios=[dict(x) for x in conn.execute('SELECT * FROM scenarios WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    caps=[dict(x) for x in conn.execute('SELECT * FROM capabilities WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    imps=[dict(x) for x in conn.execute('SELECT * FROM improvements WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    decisions=[dict(x) for x in conn.execute('SELECT * FROM decisions WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    latest_decisions={}
    for d in decisions:
        if d['improvement_id']: latest_decisions[d['improvement_id']]=d
    approved_ids={iid for iid,d in latest_decisions.items() if d['decision_type'] in ('Approve','Approve with Conditions')}
    evidence_rows=[dict(r) for r in conn.execute('SELECT * FROM evidence WHERE assessment_id=?',(assessment_id,))]
    verified_evidence_ids={r['id'] for r in evidence_rows if evidence_is_effective(r)}
    gaps=[dict(x) for x in conn.execute('SELECT * FROM gaps WHERE assessment_id=?',(assessment_id,))]
    overrides=[dict(x) for x in conn.execute('SELECT * FROM risk_overrides WHERE assessment_id=? ORDER BY id',(assessment_id,))]
    active_override_records={}
    for o in overrides:
        if o['status']=='Active' and o.get('review_lifecycle_status','Current')=='Current': active_override_records[o['threat_id']]=o
    out=[]
    weights_row=conn.execute('SELECT * FROM assessment_weights WHERE assessment_id=?',(assessment_id,)).fetchone()
    weights=dict(weights_row) if weights_row else {'life_safety':1,'mission':1,'operations':1,'financial':1,'legal_regulatory':1,'reputation':1,'recovery':1,'risk_methodology_version':RISK_METHODOLOGY_VERSION}
    methodology=weights.get('risk_methodology_version') or RISK_METHODOLOGY_VERSION
    dims=['life_safety','mission','operations','financial','legal_regulatory','reputation','recovery']
    for t in threats:
        tscens=[x for x in scenarios if x['threat_id']==t['id']]
        scenario_consequences=[]
        for sc in tscens:
            denom=sum(float(weights.get(d,1)) for d in dims) or 1
            scenario_consequences.append(sum(float(sc[d])*float(weights.get(d,1)) for d in dims)/denom)
        modeled_consequence=(sum(scenario_consequences)/len(scenario_consequences)) if scenario_consequences else float(t['consequence'])
        inherent=round(float(t['likelihood'])*float(t['vulnerability'])*modeled_consequence/125*100,1)
        tcaps=[]
        for sc in tscens: tcaps.extend([c for c in caps if c['scenario_id']==sc['id']])
        effs=[capability_effectiveness(c['required_standard'],c['current_performance'],c['comparator'],c['measurement_type']) for c in tcaps]
        eff=round(sum(effs)/len(effs),1) if effs else 0.0
        # Current risk credits demonstrated capability only. Executive approval and implementation status never reduce current risk.
        current=round(inherent*max(.25,1-(eff/100*.75)),1)
        capids={c['id'] for c in tcaps}; gapids={g['id'] for g in gaps if g['capability_id'] in capids}
        approved=[i for i in imps if i['gap_id'] in gapids and i['id'] in approved_ids]
        if approved:
            forecast_strength=sum(clamp(float(i['consequence_reduction']),1,5)/5 for i in approved)/len(approved)
            validated_strength=sum((clamp(float(i['consequence_reduction']),1,5)/5)*(clamp(float(i.get('validated_effectiveness_percent') or 0),0,100)/100) if i['status']=='Complete' and i.get('validation_status') in ('Validated','Partially Validated') and i.get('validation_evidence_id') in verified_evidence_ids else 0 for i in approved)/len(approved)
        else:
            forecast_strength=validated_strength=0.0
        forecast_reduction=min(.45,forecast_strength*.45)
        validated_reduction=min(forecast_reduction,validated_strength*.45)
        predicted=round(current*(1-forecast_reduction),1)
        validated=round(current*(1-validated_reduction),1)
        validated_improvements=sum(1 for i in approved if i['status']=='Complete' and i.get('validation_status') in ('Validated','Partially Validated') and i.get('validation_evidence_id') in verified_evidence_ids)
        override_record=active_override_records.get(t['id'])
        override_evidence=next((e for e in evidence_rows if override_record and override_record.get('evidence_id')==e['id']),None)
        evidence_current=(evidence_is_effective(override_evidence) if override_record and override_record.get('evidence_id') is not None else None)
        override_applicable=bool(override_record and (override_record.get('evidence_id') is None or evidence_current))
        unavailable_reason=''
        if override_record and not override_applicable:
            unavailable_reason='Supporting evidence is stale, expired, missing, or not Verified; calculated risk remains authoritative.'
        override=override_record if override_applicable else None
        out.append({'threat_id':t['id'],'name':t['name'],'inherent_score':inherent,'inherent_band':risk_band(inherent),'capability_effectiveness':eff,'current_score':current,'current_band':risk_band(current),'approved_improvements':len(approved),'validated_improvements':validated_improvements,'predicted_residual_score':predicted,'predicted_residual_band':risk_band(predicted),'validated_residual_score':validated,'validated_residual_band':risk_band(validated),'estimated_residual_score':predicted,'estimated_residual_band':risk_band(predicted),'estimated_residual_state':'Predicted - not validated','forecast_reduction_percent':round(forecast_reduction*100,1),'validated_reduction_percent':round(validated_reduction*100,1),'confidence':t['confidence'],'trend':t['trend'],'modeled_consequence':round(modeled_consequence,2),'risk_methodology_version':methodology,'professional_override':override,'professional_override_record':override_record,'professional_override_applicable':override_applicable,'professional_override_unavailable_reason':unavailable_reason,'professional_override_evidence_current':evidence_current,'assigned_risk_score':override['assigned_score'] if override else None,'assigned_risk_band':override['assigned_band'] if override else None})
    conn.close(); return out

@app.get('/api/risk/{assessment_id}')
def risk_route(assessment_id:int, request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id); sweep_stale_evidence([assessment_id]); sweep_overdue_risk_overrides([assessment_id]); return risk_summary(assessment_id)

def priorities(assessment_id:int):
    conn=db(); rows=[]
    for r in conn.execute('SELECT i.*, g.severity gap_severity, g.description gap_description FROM improvements i JOIN gaps g ON g.id=i.gap_id WHERE i.assessment_id=?',(assessment_id,)):
        i=dict(r); score,factors=improvement_priority(i); i['priority_score']=score; i['factors']=factors; rows.append(i)
    conn.close(); return sorted(rows,key=lambda x:x['priority_score'],reverse=True)

@app.get('/api/priorities/{assessment_id}')
def priorities_route(assessment_id:int, request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id); return priorities(assessment_id)

@app.get('/api/weights/{assessment_id}')
def get_weights(assessment_id:int, request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id); conn=db(); r=conn.execute('SELECT * FROM assessment_weights WHERE assessment_id=?',(assessment_id,)).fetchone(); conn.close()
    return dict(r) if r else {'assessment_id':assessment_id,'life_safety':1,'mission':1,'operations':1,'financial':1,'legal_regulatory':1,'reputation':1,'recovery':1,'risk_methodology_version':RISK_METHODOLOGY_VERSION}

@app.put('/api/weights/{assessment_id}')
def set_weights(assessment_id:int,p:WeightIn,request:Request):
    require(request,'write'); assessment_row_for_request(request,assessment_id); d=p.model_dump(); conn=db()
    conn.execute('''INSERT INTO assessment_weights(assessment_id,life_safety,mission,operations,financial,legal_regulatory,reputation,recovery) VALUES(?,?,?,?,?,?,?,?)
    ON CONFLICT(assessment_id) DO UPDATE SET life_safety=excluded.life_safety,mission=excluded.mission,operations=excluded.operations,financial=excluded.financial,legal_regulatory=excluded.legal_regulatory,reputation=excluded.reputation,recovery=excluded.recovery''',(assessment_id,d['life_safety'],d['mission'],d['operations'],d['financial'],d['legal_regulatory'],d['reputation'],d['recovery']))
    audit(conn,'UPDATE','assessment_weights',assessment_id,'Consequence weights updated',actor(request)); conn.commit(); conn.close(); return {'ok':True}

@app.post('/api/assessments/{assessment_id}/lock-scope')
def lock_scope(assessment_id:int, request:Request):
    require(request,'write'); assessment_row_for_request(request,assessment_id)
    conn=db(); r=conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone()
    if not r: raise HTTPException(404)
    conn.execute('UPDATE assessments SET scope_locked=1, updated_at=? WHERE id=?',(now(),assessment_id)); audit(conn,'LOCK_SCOPE','assessment',assessment_id,'Scope locked',actor(request)); snapshot_entity(conn,'assessments',assessment_id,actor(request),'Scope locked'); conn.commit(); conn.close(); return {'ok':True}

@app.post('/api/scope-changes')
def create_scope_change(p:ScopeChangeIn, request:Request):
    require(request,'write'); assessment_row_for_request(request,p.assessment_id); conn=db()
    a=conn.execute('SELECT * FROM assessments WHERE id=?',(p.assessment_id,)).fetchone()
    if not a: conn.close(); raise HTTPException(404)
    d=p.model_dump(); d.update({'requested_by':actor(request),'decision':'Pending','approved_by':'','created_at':now(),'decided_at':''})
    cols=','.join(d.keys()); qs=','.join('?'*len(d)); cur=conn.execute(f'INSERT INTO scope_changes({cols}) VALUES({qs})',tuple(d.values()))
    audit(conn,'CREATE','scope_change',cur.lastrowid,p.reason,actor(request)); conn.commit(); row=dict(conn.execute('SELECT * FROM scope_changes WHERE id=?',(cur.lastrowid,)).fetchone()); conn.close(); return row

@app.post('/api/scope-changes/{change_id}/decision')
def decide_scope_change(change_id:int,p:ScopeDecisionIn,request:Request):
    require_protected_member_authority(request,'scope_change_decision')
    if p.decision not in ('Approved','Rejected'): raise HTTPException(400,'Decision must be Approved or Rejected')
    conn=db(); ch=conn.execute('SELECT * FROM scope_changes WHERE id=?',(change_id,)).fetchone()
    if not ch: conn.close(); raise HTTPException(404)
    assessment_row_for_request(request,ch['assessment_id'])
    if ch['decision']!='Pending': conn.close(); raise HTTPException(409,'Scope change already decided')
    if p.decision=='Approved':
        a=conn.execute('SELECT * FROM assessments WHERE id=?',(ch['assessment_id'],)).fetchone()
        updates={}
        for col in ('purpose','mission','scope','exclusions'):
            v=ch['new_'+col]
            if v is not None: updates[col]=v
        updates['version']=int(a['version'])+1; updates['updated_at']=now(); updates['scope_locked']=1
        sets=','.join(f'{k}=?' for k in updates)
        conn.execute(f'UPDATE assessments SET {sets} WHERE id=?',list(updates.values())+[ch['assessment_id']])
        snapshot_entity(conn,'assessments',ch['assessment_id'],actor(request),f'Approved scope change #{change_id}')
        audit(conn,'VERSION','assessment',ch['assessment_id'],f'Assessment version incremented for scope change #{change_id}',actor(request))
    conn.execute('UPDATE scope_changes SET decision=?,approved_by=?,decided_at=? WHERE id=?',(p.decision,actor(request),now(),change_id))
    audit(conn,'DECIDE','scope_change',change_id,f'{p.decision}: {p.reason}',actor(request)); conn.commit(); row=dict(conn.execute('SELECT * FROM scope_changes WHERE id=?',(change_id,)).fetchone()); conn.close(); return row

@app.post('/api/assessments/{assessment_id}/transition')
def transition_assessment(assessment_id:int,p:WorkflowTransitionIn,request:Request):
    require(request,'write'); assessment_row_for_request(request,assessment_id); conn=db(); a=conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone()
    if not a: conn.close(); raise HTTPException(404)
    current=a['status']; target=p.to_status
    if target not in WORKFLOW_STATES: conn.close(); raise HTTPException(400,'Unknown workflow status')
    ci=WORKFLOW_STATES.index(current) if current in WORKFLOW_STATES else 0; ti=WORKFLOW_STATES.index(target)
    admin_override=role(request) in ('System Administrator','Assessment Director') and bool(p.reason.strip())
    if abs(ti-ci)!=1 and not admin_override:
        conn.close(); raise HTTPException(409,'Workflow transitions must move one stage at a time. Assessment Directors and System Administrators may override with a documented reason.')
    conn.execute('UPDATE assessments SET status=?,updated_at=? WHERE id=?',(target,now(),assessment_id))
    conn.execute('INSERT INTO workflow_events(assessment_id,from_status,to_status,reason,changed_by,created_at) VALUES(?,?,?,?,?,?)',(assessment_id,current,target,p.reason,actor(request),now()))
    audit(conn,'TRANSITION','assessment',assessment_id,f'{current} -> {target}. {p.reason}',actor(request)); snapshot_entity(conn,'assessments',assessment_id,actor(request),f'Workflow transition {current} -> {target}')
    conn.commit(); conn.close(); return {'ok':True,'from_status':current,'to_status':target}

@app.get('/api/versions/{entity_type}/{entity_id}')
def versions(entity_type:str,entity_id:int,request:Request):
    require(request,'read')
    if entity_type not in VERSIONED_TABLES: raise HTTPException(404)
    if protected_member_request(request) and entity_type in {'ops_engagements','ops_tasks','ops_field_reports','ops_estimates','ops_expenses','ops_invoice_statements'}: raise HTTPException(403,'Internal SalOPS version snapshots are restricted to authorized Salus personnel.')
    conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM entity_versions WHERE entity_type=? AND entity_id=? ORDER BY version_no DESC',(entity_type,entity_id))]
    if rows: assessment_row_for_request(request,rows[0]['assessment_id'])
    conn.close(); return rows

@app.post('/api/evidence/{evidence_id}/attachments')
async def upload_evidence_attachment(evidence_id:int, request:Request, file:UploadFile=File(...)):
    require(request,'write'); conn=db(); ev=conn.execute('SELECT * FROM evidence WHERE id=?',(evidence_id,)).fetchone()
    if not ev: conn.close(); raise HTTPException(404)
    assessment_row_for_request(request,ev['assessment_id']); require_sensitivity(request,ev['sensitivity'])
    content=await file.read(MAX_ATTACHMENT_BYTES+1)
    if len(content)>MAX_ATTACHMENT_BYTES: conn.close(); raise HTTPException(413,'Attachment exceeds 25 MB limit')
    original=safe_filename(file.filename or 'attachment'); scan=scan_bytes(content,original)
    if not scan['ok']:
        conn.close(); security_event(request,'UPLOAD_REJECTED','High' if scan['status']=='Infected' else 'Medium',f'{original}: {scan["status"]} {scan["detail"]}')
        status=422 if scan['status']=='Infected' else 503
        raise HTTPException(status,f'Upload rejected: {scan["status"]}')
    digest=hashlib.sha256(content).hexdigest(); tid=tenant_id(request)
    stored=f'tenant-{tid}/assessment-{ev["assessment_id"]}/evidence-{evidence_id}/{digest[:16]}_{original}'
    try: storage.put_bytes(stored,content)
    except Exception as exc: conn.close(); security_event(request,'STORAGE_WRITE_FAILURE','High',type(exc).__name__); raise HTTPException(503,'Evidence storage unavailable')
    retention_until=(_iso_now_dt()+timedelta(days=RETENTION_DEFAULT_DAYS)).replace(microsecond=0).isoformat().replace('+00:00','Z') if RETENTION_DEFAULT_DAYS>0 else ''
    cur=conn.execute('INSERT INTO evidence_attachments(evidence_id,assessment_id,original_name,stored_name,content_type,size_bytes,sha256,uploaded_by,scan_status,scan_detail,scanned_at,retention_until,legal_hold,disposition_status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(evidence_id,ev['assessment_id'],original,stored,file.content_type or 'application/octet-stream',len(content),digest,actor(request),scan['status'],scan['detail'][:1000],now(),retention_until,0,'Active',now()))
    audit(conn,'ATTACH','evidence',evidence_id,f'{original} sha256={digest} scan={scan["status"]}',actor(request)); conn.commit(); row=dict(conn.execute('SELECT * FROM evidence_attachments WHERE id=?',(cur.lastrowid,)).fetchone()); conn.close(); return row

@app.get('/api/evidence-attachments/{attachment_id}/download')
def download_evidence_attachment(attachment_id:int, request:Request):
    require(request,'read'); conn=db(); r=conn.execute('SELECT * FROM evidence_attachments WHERE id=?',(attachment_id,)).fetchone()
    if not r: conn.close(); raise HTTPException(404)
    assessment_row_for_request(request,r['assessment_id']); ev=conn.execute('SELECT sensitivity FROM evidence WHERE id=?',(r['evidence_id'],)).fetchone(); require_sensitivity(request,ev['sensitivity'] if ev else 'Standard'); conn.close()
    try: data=storage.get_bytes(r['stored_name'])
    except FileNotFoundError: raise HTTPException(404,'Stored attachment missing')
    except Exception as exc: security_event(request,'STORAGE_READ_FAILURE','High',type(exc).__name__); raise HTTPException(503,'Evidence storage unavailable')
    if hashlib.sha256(data).hexdigest()!=r['sha256']:
        security_event(request,'EVIDENCE_HASH_MISMATCH','Critical',f'attachment_id={attachment_id}'); raise HTTPException(409,'Evidence integrity verification failed')
    conn=db(); audit(conn,'DOWNLOAD','evidence',r['evidence_id'],f'Attachment {r["original_name"]} downloaded and hash verified',actor(request)); conn.commit(); conn.close()
    headers={'Content-Disposition':f'attachment; filename="{safe_filename(r["original_name"])}"','X-Content-SHA256':r['sha256']}
    return Response(content=data,media_type=r['content_type'],headers=headers)

@app.patch('/api/evidence-attachments/{attachment_id}/governance')
def update_attachment_governance(attachment_id:int,p:AttachmentGovernanceIn,request:Request):
    require(request,'decide'); conn=db(); r=conn.execute('SELECT * FROM evidence_attachments WHERE id=?',(attachment_id,)).fetchone()
    if not r: conn.close(); raise HTTPException(404)
    assessment_row_for_request(request,r['assessment_id']); ev=conn.execute('SELECT sensitivity FROM evidence WHERE id=?',(r['evidence_id'],)).fetchone(); require_sensitivity(request,ev['sensitivity'] if ev else 'Standard')
    changes={}
    if p.retention_until is not None: changes['retention_until']=p.retention_until
    if p.legal_hold is not None: changes['legal_hold']=1 if p.legal_hold else 0
    if p.disposition_status is not None: changes['disposition_status']=p.disposition_status
    if changes:
        sets=','.join(f'{k}=?' for k in changes); conn.execute(f'UPDATE evidence_attachments SET {sets} WHERE id=?',list(changes.values())+[attachment_id]); audit(conn,'EVIDENCE_GOVERNANCE','evidence',r['evidence_id'],json.dumps(changes),actor(request)); conn.commit()
    row=dict(conn.execute('SELECT * FROM evidence_attachments WHERE id=?',(attachment_id,)).fetchone()); conn.close(); return row

@app.delete('/api/evidence-attachments/{attachment_id}')
def delete_evidence_attachment(attachment_id:int,request:Request):
    require(request,'write'); conn=db(); r=conn.execute('SELECT * FROM evidence_attachments WHERE id=?',(attachment_id,)).fetchone()
    if not r: conn.close(); raise HTTPException(404)
    assessment_row_for_request(request,r['assessment_id']); ev=conn.execute('SELECT sensitivity FROM evidence WHERE id=?',(r['evidence_id'],)).fetchone(); require_sensitivity(request,ev['sensitivity'] if ev else 'Standard')
    if int(r['legal_hold'] or 0): conn.close(); raise HTTPException(409,'Attachment is under legal hold and cannot be deleted')
    if retention_active(r['retention_until']): conn.close(); raise HTTPException(409,'Attachment retention period has not expired')
    try: storage.delete(r['stored_name'])
    except Exception as exc: conn.close(); error_id=uuid.uuid4().hex; record_internal_failure('evidence storage delete',error_id,exc); raise HTTPException(503,f'Evidence storage unavailable. Reference: {error_id}')
    conn.execute('DELETE FROM evidence_attachments WHERE id=?',(attachment_id,)); audit(conn,'DELETE_ATTACHMENT','evidence',r['evidence_id'],f'{r["original_name"]} deleted after governance checks',actor(request)); conn.commit(); conn.close(); return {'deleted':attachment_id}

def _report_snapshot(assessment_id:int):
    return json.dumps(executive_package(assessment_id),sort_keys=True,separators=(',',':'),default=str)

def _verified_report_snapshot(row,request:Request):
    snapshot=row['snapshot_json']; actual=hashlib.sha256(snapshot.encode('utf-8')).hexdigest()
    if actual!=row['snapshot_sha256']:
        security_event(request,'REPORT_INTEGRITY_FAILURE','High',f'report_id={row["id"]}')
        raise HTTPException(409,'Report snapshot failed integrity verification')
    payload=json.loads(snapshot)
    if protected_member_request(request) and payload.get('assessment'):
        payload['assessment']=_member_assessment_view(payload['assessment'])
    return payload,actual

def _latest_released_report_snapshot(assessment_id:int,request:Request):
    assessment_row_for_request(request,assessment_id); conn=db()
    row=conn.execute("SELECT * FROM report_versions WHERE tenant_id=? AND assessment_id=? AND status='Released' ORDER BY released_at DESC,id DESC LIMIT 1",(tenant_id(request),assessment_id)).fetchone()
    conn.close()
    if not row: raise HTTPException(404,'Released report not found')
    payload,actual=_verified_report_snapshot(row,request)
    return payload,actual,dict(row)

@app.get('/api/reports/{assessment_id}')
def list_report_versions(assessment_id:int,request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id)
    if protected_member_request(request):
        query="SELECT id,assessment_id,assessment_version,report_type,status,snapshot_sha256,created_by,created_at,reviewed_by,reviewed_at,approved_by,approved_at,released_by,released_at,transition_reason FROM report_versions WHERE tenant_id=? AND assessment_id=? AND status='Released' ORDER BY id DESC"
    else:
        query='SELECT id,assessment_id,assessment_version,report_type,status,snapshot_sha256,created_by,created_at,reviewed_by,reviewed_at,approved_by,approved_at,released_by,released_at,transition_reason FROM report_versions WHERE tenant_id=? AND assessment_id=? ORDER BY id DESC'
    conn=db(); rows=[dict(r) for r in conn.execute(query,(tenant_id(request),assessment_id))]; conn.close(); return rows

@app.post('/api/reports/{assessment_id}')
def create_report_version(assessment_id:int,request:Request,p:ReportCreateIn=ReportCreateIn()):
    require(request,'write'); require_salus_component_authority(request,'SalCAPA reporting'); a=assessment_row_for_request(request,assessment_id)
    snapshot=_report_snapshot(assessment_id); digest=hashlib.sha256(snapshot.encode('utf-8')).hexdigest(); who=actor(request); ts=now(); conn=db()
    cur=conn.execute('INSERT INTO report_versions(tenant_id,assessment_id,assessment_version,report_type,status,snapshot_json,snapshot_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(tenant_id(request),assessment_id,a['version'],'Executive','Draft',snapshot,digest,who,ts))
    rid=cur.lastrowid; audit(conn,'CREATE','report_version',rid,f'Immutable Executive report snapshot sha256={digest}; assessment_version={a["version"]}',who); conn.commit(); row=dict(conn.execute('SELECT * FROM report_versions WHERE id=?',(rid,)).fetchone()); conn.close(); return row

@app.post('/api/reports/versions/{report_id}/transition')
def transition_report_version(report_id:int,p:ReportTransitionIn,request:Request):
    require(request,'read'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute('SELECT * FROM report_versions WHERE id=? AND tenant_id=?',(report_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Report version not found')
    assessment_row_for_request(request,row['assessment_id']); allowed={'Draft':'Reviewed','Reviewed':'Approved','Approved':'Released'}
    if allowed.get(row['status'])!=p.status: conn.close(); raise HTTPException(409,f'Report transition must follow Draft → Reviewed → Approved → Released; current status is {row["status"]}.')
    transition_roles={'Reviewed':{'Assessment Director','Lead Assessor'},'Approved':{'System Administrator','Assessment Director','Client Executive'},'Released':{'System Administrator','Assessment Director'}}
    if role(request) not in transition_roles[p.status]: conn.close(); raise HTTPException(403,f'{role(request)} cannot record the {p.status} report authority gate.')
    if p.status=='Released':
        from salcapa_m365_reports import publish_member_safe_report, readiness as m365_report_readiness
        if m365_report_readiness()['configured']:
            try:
                publish_member_safe_report(dict(row),_member_assessment_view)
            except Exception as exc:
                error_id=secrets.token_hex(8); record_internal_failure('m365_report_publish',error_id,exc); conn.close()
                raise HTTPException(503,f'Governed Microsoft 365 report storage is unavailable. Reference: {error_id}') from exc
    ts=now(); field={'Reviewed':'reviewed','Approved':'approved','Released':'released'}[p.status]
    conn.execute(f'UPDATE report_versions SET status=?,{field}_by=?,{field}_at=?,transition_reason=? WHERE id=?',(p.status,who,ts,p.reason,report_id)); audit(conn,'REPORT_TRANSITION','report_version',report_id,f'{row["status"]} -> {p.status}: {p.reason}',who); conn.commit(); result=dict(conn.execute('SELECT * FROM report_versions WHERE id=?',(report_id,)).fetchone()); conn.close(); return result

@app.get('/api/reports/versions/{report_id}/snapshot')
def report_version_snapshot(report_id:int,request:Request):
    require(request,'read'); conn=db(); row=conn.execute('SELECT * FROM report_versions WHERE id=? AND tenant_id=?',(report_id,tenant_id(request))).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Report version not found')
    assessment_row_for_request(request,row['assessment_id'])
    if protected_member_request(request) and row['status']!='Released': conn.close(); raise HTTPException(404,'Released report not found')
    conn.close(); payload,actual=_verified_report_snapshot(row,request)
    response=JSONResponse(payload); response.headers['ETag']=f'"{actual}"'; response.headers['X-Salus-Report-Status']=row['status']; return response

@app.get('/api/audit/assessments/{assessment_id}')
def assessment_audit_history(assessment_id:int,request:Request,limit:int=500):
    require(request,'read'); assessment_row_for_request(request,assessment_id); conn=db(); lim=max(1,min(limit,1000))
    versions=[dict(r) for r in conn.execute('SELECT * FROM entity_versions WHERE assessment_id=? ORDER BY id DESC LIMIT ?',(assessment_id,lim))]
    governed={(str(v['entity_type']).rstrip('s'),int(v['entity_id'])) for v in versions}; governed.add(('assessment',assessment_id))
    governed.update(('report_version',int(r['id'])) for r in conn.execute('SELECT id FROM report_versions WHERE assessment_id=?',(assessment_id,)))
    tenant_audit=[dict(r) for r in conn.execute('SELECT * FROM audit_log WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]
    audits=[r for r in tenant_audit if r['entity_id'] is not None and (str(r['entity_type']).rstrip('s'),int(r['entity_id'])) in governed][:lim]
    if protected_member_request(request):
        audits=[{**r,'detail':'Governed activity recorded.'} for r in audits]
        versions=[{k:v for k,v in row.items() if k!='snapshot_json'} for row in versions]
    conn.close(); return {'assessment_id':assessment_id,'audit':audits,'versions':versions}

@app.post('/api/admin/restore-requests')
def create_restore_request(p:RestoreRequestIn,request:Request):
    require(request,'admin'); tid=tenant_id(request); who=actor(request); conn=db(); backup=conn.execute('SELECT * FROM backup_history WHERE id=? AND tenant_id=?',(p.backup_id,tid)).fetchone()
    if not backup: conn.close(); raise HTTPException(404,'Backup not found')
    validation=conn.execute("SELECT * FROM dr_validations WHERE backup_id=? AND tenant_id=? AND status='Passed' ORDER BY id DESC LIMIT 1",(p.backup_id,tid)).fetchone()
    if not validation: conn.close(); raise HTTPException(409,'A passed restore-readiness validation is required before a restore request can be created.')
    cur=conn.execute('INSERT INTO restore_requests(tenant_id,backup_id,scope,reason,status,requested_by,requested_at,validation_id) VALUES(?,?,?,?,?,?,?,?)',(tid,p.backup_id,p.scope,p.reason,'Pending',who,now(),validation['id'])); rid=cur.lastrowid; audit(conn,'RESTORE_REQUEST','restore_request',rid,f'backup_id={p.backup_id}; scope={p.scope}; reason={p.reason}',who); conn.commit(); row=dict(conn.execute('SELECT * FROM restore_requests WHERE id=?',(rid,)).fetchone()); conn.close(); security_event(request,'RESTORE_REQUESTED','Medium',f'restore_request_id={rid}; backup_id={p.backup_id}'); return row

@app.post('/api/admin/restore-requests/{restore_request_id}/decision')
def decide_restore_request(restore_request_id:int,p:RestoreDecisionIn,request:Request):
    require(request,'admin'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute("SELECT * FROM restore_requests WHERE id=? AND tenant_id=? AND status='Pending'",(restore_request_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Pending restore request not found')
    if row['requested_by']==who: conn.close(); raise HTTPException(409,'The restore requester cannot authorize or reject the same request.')
    conn.execute('UPDATE restore_requests SET status=?,authorized_by=?,authorized_at=?,decision_reason=? WHERE id=?',(p.decision,who,now(),p.reason,restore_request_id)); audit(conn,'RESTORE_DECISION','restore_request',restore_request_id,f'{p.decision}: {p.reason}',who); conn.commit(); result=dict(conn.execute('SELECT * FROM restore_requests WHERE id=?',(restore_request_id,)).fetchone()); conn.close(); security_event(request,'RESTORE_AUTHORIZED' if p.decision=='Authorized' else 'RESTORE_REJECTED','High',f'restore_request_id={restore_request_id}'); return result

@app.get('/api/admin/restore-requests')
def list_restore_requests(request:Request):
    require(request,'admin'); conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM restore_requests WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]; conn.close(); return rows

@app.get('/api/report/{assessment_id}/executive.csv')
def executive_csv(assessment_id:int,request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id)
    released=None
    if protected_member_request(request): package,digest,released=_latest_released_report_snapshot(assessment_id,request)
    else: package=executive_package(assessment_id)
    out=io.StringIO(); w=csv.writer(out)
    a=package['assessment']; w.writerow(['SalCAPA Protective Readiness Executive Briefing']); w.writerow(['Assessment',a['name']]); w.writerow(['Organization',a['organization']]); w.writerow(['Status',a['status']]); w.writerow(['Version',a['version']]); w.writerow(['Mission',a['mission']]); w.writerow(['Methodology note','SalTHIRA applies a Salus-specific methodology informed by recognized THIRA principles; Salus does not claim ownership of the public THIRA framework.']); w.writerow([])
    w.writerow(['Risk Outlook']); w.writerow(['Threat / Hazard','Inherent','Current','Professional Assigned Risk','Predicted Residual','Validated Residual','Validated Improvements','Methodology','Confidence','Trend'])
    for r in package['risk']: w.writerow([r['name'],f"{r['inherent_band']} {r['inherent_score']}",f"{r['current_band']} {r['current_score']}",(f"{r['assigned_risk_band']} {r['assigned_risk_score']}" if r.get('professional_override') else ''),f"{r['predicted_residual_band']} {r['predicted_residual_score']}",f"{r['validated_residual_band']} {r['validated_residual_score']}",r['validated_improvements'],r['risk_methodology_version'],r['confidence'],r['trend']])
    w.writerow([]); w.writerow(['Capability Performance']); w.writerow(['Capability','Measure','Comparator','Required','Current','Unit','Attainment','Status','Confidence'])
    for c in package['capability_performance']: w.writerow([c['name'],c['measurement_type'],c['comparator'],c['required_standard'],c['current_performance'],c['measurement_unit'],f"{c['attainment_percent']}%",c['target_status'],c['confidence']])
    w.writerow([]); w.writerow(['Top Improvement Priorities']); w.writerow(['Priority Score','Improvement','Status','Initial Cost','Owner'])
    for r in package['priorities'][:10]: w.writerow([r['priority_score'],r['title'],r['status'],r['initial_cost'],r['owner']])
    w.writerow([]); w.writerow(['Executive Decisions']); w.writerow(['Decision','Authority','Funding Authorized','Rationale','Review Date'])
    for d in package['decisions']: w.writerow([d['decision_type'],d['authority'],d['funding_authorized'],d['rationale'],d['review_date']])
    w.writerow([]); w.writerow(['Evidence Lifecycle']); w.writerow(['Evidence','Verification','Lifecycle','Valid Until','Stale Reason','Last Lifecycle Review','Reviewed By'])
    for e in package['evidence']: w.writerow([e['title'],e['verification_status'],e.get('lifecycle_status','Current'),e.get('valid_until',''),e.get('stale_reason',''),e.get('last_lifecycle_review_at',''),e.get('last_lifecycle_review_by','')])
    w.writerow([]); w.writerow(['Accepted Risk Register']); w.writerow(['Status','Risk','Authority','Residual Exposure','Owner','Review Date','Reconsideration Trigger'])
    for r in package['accepted_risks']: w.writerow([r['status'],r['title'],r['authority'],r['residual_exposure'],r['owner'],r['review_date'],r['reconsideration_trigger']])
    w.writerow([]); w.writerow(['Professional Risk Override Register']); w.writerow(['Status','Threat ID','Calculated','Assigned','Authority','Reason','Evidence ID','Review Date','Created At','Withdrawn Reason'])
    for r in package['risk_overrides']: w.writerow([r['status'],r['threat_id'],f"{r['calculated_band']} {r['calculated_score']}",f"{r['assigned_band']} {r['assigned_score']}",r['authority'],r['reason'],r['evidence_id'] or '',r['review_date'],r['created_at'],r['withdrawn_reason']])
    response=PlainTextResponse(out.getvalue(),media_type='text/csv; charset=utf-8'); response.headers['Content-Disposition']=f'attachment; filename=salcapa-protective-readiness-{assessment_id}.csv'
    if released: response.headers['ETag']=f'"{digest}"'; response.headers['X-Salus-Report-Status']='Released'
    return response

@app.get('/api/report/{assessment_id}/executive.html')
def executive_html(assessment_id:int,request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id)
    released=None
    if protected_member_request(request): p,digest,released=_latest_released_report_snapshot(assessment_id,request)
    else: p=executive_package(assessment_id)
    a=p['assessment']; prepared_at=released['released_at'] if released else now()
    risk_rows=''.join(f"<tr><td>{html.escape(str(r['name']))}</td><td>{html.escape(str(r['inherent_band']))} {r['inherent_score']}</td><td>{html.escape(str(r['current_band']))} {r['current_score']}</td><td>{(html.escape(str(r['assigned_risk_band']))+' '+str(r['assigned_risk_score'])) if r.get('professional_override') else ''}</td><td>{html.escape(str(r['predicted_residual_band']))} {r['predicted_residual_score']}</td><td>{html.escape(str(r['validated_residual_band']))} {r['validated_residual_score']}</td><td>{r['validated_improvements']}</td><td>{html.escape(str(r['confidence']))}</td></tr>" for r in p['risk'])
    capability_rows=''.join(f"<tr><td>{html.escape(str(c['name']))}</td><td>{html.escape(str(c['measurement_type']))}</td><td>{html.escape(str(c['comparator']))} {c['required_standard']} {html.escape(str(c['measurement_unit']))}</td><td>{c['current_performance']} {html.escape(str(c['measurement_unit']))}</td><td>{c['attainment_percent']}%</td><td>{html.escape(str(c['target_status']))}</td></tr>" for c in p['capability_performance'])
    priority_rows=''.join(f"<tr><td>{r['priority_score']}</td><td>{html.escape(str(r['title']))}</td><td>{html.escape(str(r['status']))}</td><td>${float(r['initial_cost'] or 0):,.0f}</td></tr>" for r in p['priorities'][:10])
    decision_rows=''.join(f"<tr><td>{html.escape(str(d['decision_type']))}</td><td>{html.escape(str(d['authority']))}</td><td>${float(d['funding_authorized'] or 0):,.0f}</td><td>{html.escape(str(d['rationale']))}</td></tr>" for d in p['decisions'])
    accepted_rows=''.join(f"<tr><td>{html.escape(str(r['status']))}</td><td>{html.escape(str(r['title']))}</td><td>{html.escape(str(r['authority']))}</td><td>{html.escape(str(r['residual_exposure']))}</td><td>{html.escape(str(r['review_date']))}</td></tr>" for r in p['accepted_risks'])
    override_rows=''.join(f"<tr><td>{html.escape(str(r['status']))}</td><td>{r['threat_id']}</td><td>{html.escape(str(r['calculated_band']))} {r['calculated_score']}</td><td>{html.escape(str(r['assigned_band']))} {r['assigned_score']}</td><td>{html.escape(str(r['authority']))}</td><td>{html.escape(str(r['reason']))}</td><td>{html.escape(str(r['review_date']))}</td></tr>" for r in p['risk_overrides'])
    evidence_rows=''.join(f"<tr><td>{html.escape(str(e['title']))}</td><td>{html.escape(str(e['verification_status']))}</td><td>{html.escape(str(e.get('lifecycle_status','Current')))}</td><td>{html.escape(str(e.get('valid_until','')))}</td><td>{html.escape(str(e.get('stale_reason','')))}</td></tr>" for e in p['evidence'])
    body=f'''<!doctype html><html><head><meta charset="utf-8"><title>SalCAPA Protective Readiness Executive Briefing</title><style>body{{font-family:Arial,sans-serif;margin:36px;color:#111}}h1{{margin-bottom:0}}.meta{{color:#555}}table{{width:100%;border-collapse:collapse;margin:16px 0 28px}}th,td{{border:1px solid #bbb;padding:8px;text-align:left;vertical-align:top}}th{{background:#eee}}@media print{{button{{display:none}}}}</style></head><body><button onclick="window.print()">Print / Save PDF</button><h1>SalCAPA Protective Readiness Executive Briefing</h1><p class="meta">Prepared {html.escape(str(prepared_at))}</p><h2>{html.escape(str(a['name']))}</h2><p>{html.escape(str(a['organization']))} · {html.escape(str(a['assessment_type']))} · {html.escape(str(a['status']))} · Version {a['version']}</p><p><strong>Mission:</strong> {html.escape(str(a['mission']))}</p><p><strong>Purpose:</strong> {html.escape(str(a['purpose']))}</p><p><strong>Methodology note:</strong> SalTHIRA applies a Salus-specific methodology informed by recognized THIRA principles; Salus does not claim ownership of the public THIRA framework.</p><h2>Risk Outlook</h2><table><tr><th>Threat / Hazard</th><th>Inherent</th><th>Current</th><th>Professional Assigned Risk</th><th>Predicted Residual</th><th>Validated Residual</th><th>Validated Improvements</th><th>Confidence</th></tr>{risk_rows}</table><h2>Professional Risk Override Register</h2><table><tr><th>Status</th><th>Threat ID</th><th>Calculated</th><th>Assigned</th><th>Authority</th><th>Reason</th><th>Review Date</th></tr>{override_rows}</table><h2>Evidence Lifecycle</h2><table><tr><th>Evidence</th><th>Verification</th><th>Lifecycle</th><th>Valid Until</th><th>Stale Reason</th></tr>{evidence_rows}</table><h2>Capability Performance</h2><table><tr><th>Capability</th><th>Measure</th><th>Target</th><th>Current</th><th>Attainment</th><th>Status</th></tr>{capability_rows}</table><h2>Top Improvement Priorities</h2><table><tr><th>Priority</th><th>Improvement</th><th>Status</th><th>Initial Cost</th></tr>{priority_rows}</table><h2>Executive Decisions</h2><table><tr><th>Decision</th><th>Authority</th><th>Funding</th><th>Rationale</th></tr>{decision_rows}</table><h2>Accepted Risk Register</h2><table><tr><th>Status</th><th>Risk</th><th>Authority</th><th>Residual Exposure</th><th>Review Date</th></tr>{accepted_rows}</table><p class="meta">Decision-support output. Professional judgment and authoritative source records remain controlling.</p></body></html>'''
    response=HTMLResponse(body)
    if released: response.headers['ETag']=f'"{digest}"'; response.headers['X-Salus-Report-Status']='Released'
    return response

@app.get('/api/export/{assessment_id}')
def export_assessment(assessment_id:int, request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id)
    released=None
    if protected_member_request(request): package,digest,released=_latest_released_report_snapshot(assessment_id,request)
    else: package=executive_package(assessment_id)
    response=JSONResponse(package); response.headers['Content-Disposition']=f'attachment; filename="salus-thira-assessment-{assessment_id}.json"'
    if released: response.headers['ETag']=f'"{digest}"'; response.headers['X-Salus-Report-Status']='Released'
    return response

@app.put('/api/{table}/{entity_id}')
def update_entity(table:str,entity_id:int,payload:dict[str,Any],request:Request):
    require(request,'decide' if table=='accepted_risks' else 'write')
    allowed={'assessments','threats','scenarios','capabilities','evidence','gaps','improvements','accepted_risks','reassessment_triggers'}
    if table not in allowed: raise HTTPException(404)
    table=sql_table_name(table)
    if table=='assessments': assessment_row_for_request(request,entity_id)
    conn=db()
    if table=='assessments': lock_package_assessment(conn,entity_id)
    old=conn.execute(f'SELECT * FROM {table} WHERE id=?',(entity_id,)).fetchone()
    if not old: conn.close(); raise HTTPException(404)
    aid=entity_assessment_id(table,old); assessment_row_for_request(request,aid)
    if table in CHILD_ASSESSMENT_TABLES and 'assessment_id' in payload:
        try: requested_assessment=int(payload['assessment_id'])
        except (TypeError,ValueError): conn.close(); raise HTTPException(422,'Assessment ID must be a valid integer.')
        if requested_assessment!=aid:
            conn.close(); raise HTTPException(409,'Assessment assignment is immutable. Create a new record in the correct assessment rather than moving a governed record across assessments.')
    relation_data=dict(old); relation_data.update(payload); relation_data['assessment_id']=aid
    validate_entity_relationships(conn,table,aid,relation_data)
    if table=='evidence':
        require_sensitivity(request,str(payload.get('sensitivity',old['sensitivity'])))
        governed_lifecycle={'valid_until','lifecycle_status','stale_reason','stale_at','last_lifecycle_review_at','last_lifecycle_review_by'}
        changed_governed=[k for k in governed_lifecycle if k in payload and str(payload.get(k) or '')!=str(old[k] or '')]
        if changed_governed:
            conn.close(); raise HTTPException(409,'Evidence lifecycle fields are controlled. Use the evidence lifecycle review action rather than editing validity or stale state directly.')
    if table=='capabilities':
        merged=dict(old); merged.update(payload)
        validate_capability_measurement(merged.get('measurement_type'),merged.get('comparator'),merged.get('required_standard'),merged.get('current_performance'))
    if table=='assessments':
        requested=dict(old); requested.update(payload)
        try:
            requested_level=int(requested['requested_package_level'])
            validate_requested_package_path(requested_level,requested['requested_scope_band'],requested['requested_access_variant'])
        except (ValueError,TypeError) as exc:
            conn.close(); raise HTTPException(422,str(exc)) from exc
        governed_reassessment={'reassessment_date','reassessment_lifecycle_status','reassessment_overdue_reason','reassessment_overdue_at','last_reassessment_review_at','last_reassessment_review_by'}
        if any(k in payload and str(payload.get(k) or '')!=str(old[k] or '') for k in governed_reassessment):
            conn.close(); raise HTTPException(409,'Assessment reassessment lifecycle fields are controlled. Use the assessment reassessment review action rather than editing review currency directly.')
        if 'status' in payload and str(payload['status'])!=str(old['status']):
            conn.close(); raise HTTPException(409,'Use the controlled workflow transition action to change assessment status.')
        protected={'organization','purpose','mission','scope','covered_operation','requested_package_level','requested_scope_band','requested_access_variant','exclusions'}
        if any(k in payload and str(payload[k])!=str(old[k]) for k in protected):
            quote_exists=conn.execute('SELECT 1 FROM package_quote_versions WHERE tenant_id=? AND assessment_id=? LIMIT 1',(old['tenant_id'],entity_id)).fetchone()
            if old['scope_locked'] or quote_exists:
                conn.close(); raise HTTPException(409,'This assessment has a locked scope or a package quote. Use an authorized scope/version change; start a new assessment if the covered operation or package path must change.')
    columns={r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
    immutable={'id','created_at'}
    if table in CHILD_ASSESSMENT_TABLES: immutable.add('assessment_id')
    if table=='accepted_risks': immutable|={'assessment_id','decision_id','improvement_id','gap_id','authority','acceptance_date'}
    if table=='accepted_risks':
        attempted_immutable=[k for k in immutable if k in payload and str(payload.get(k) or '')!=str(old[k] or '')]
        if attempted_immutable:
            conn.close(); raise HTTPException(409,f'Accepted-risk provenance is immutable: {", ".join(sorted(attempted_immutable))}.')
    server_controlled={'tenant_id','created_at','updated_at','version','version_no','changed_at','changed_by','change_reason','industry_profile_id','industry_profile_key_snapshot','industry_profile_version_snapshot','industry_profile_name_snapshot','industry_member_summary_snapshot','industry_defaults_snapshot_json','industry_profile_applied_by','industry_profile_applied_at'}
    attempted=server_controlled.intersection(payload)
    if attempted:
        conn.close(); raise HTTPException(409,f'Server-controlled fields cannot be edited: {", ".join(sorted(attempted))}.')
    data={k:v for k,v in payload.items() if k in columns and k not in immutable}
    if table=='accepted_risks':
        governed_review={'review_date','review_lifecycle_status','review_overdue_reason','review_overdue_at','last_review_at','last_review_by'}
        if any(k in payload and str(payload.get(k) or '')!=str(old[k] or '') for k in governed_review):
            conn.close(); raise HTTPException(409,'Accepted-risk review lifecycle fields are controlled. Use the accepted-risk review action rather than editing review currency directly.')
        if 'status' in payload or 'closure_basis' in payload:
            conn.close(); raise HTTPException(409,'Accepted-risk status and closure basis are controlled. Use the accepted-risk transition action.')
        allowed_accepted_fields=set(AcceptedRiskUpdate.model_fields)
        unsupported=set(data)-allowed_accepted_fields
        if unsupported:
            conn.close(); raise HTTPException(409,f'Accepted-risk fields are governed and cannot be edited here: {", ".join(sorted(unsupported))}.')
        candidate={k:payload[k] for k in allowed_accepted_fields if k in payload}
        try: data=AcceptedRiskUpdate.model_validate(candidate).model_dump(exclude_none=True)
        except ValidationError as exc: conn.close(); raise HTTPException(422,exc.errors(include_context=False))
    if table=='gaps':
        if 'status' in payload:
            conn.close(); raise HTTPException(409,'Use the controlled gap transition action to change lifecycle state.')
        allowed_gap_fields={'capability_id','gap_type','description','severity','root_cause','owner'}
        unsupported=set(data)-allowed_gap_fields
        if unsupported:
            conn.close(); raise HTTPException(409,f'Gap fields are governed and cannot be edited here: {", ".join(sorted(unsupported))}.')
        candidate=dict(old); candidate.update(data)
        try: validated=GapIn.model_validate({k:candidate[k] for k in GapIn.model_fields}).model_dump()
        except ValidationError as exc: conn.close(); raise HTTPException(422,exc.errors(include_context=False))
        data={k:validated[k] for k in allowed_gap_fields if k in data}
    if table=='improvements':
        governed={'status','priority_score','validation_status','validation_evidence_id','validation_outcome','validated_effectiveness_percent','validated_by','validated_at'}
        if any(k in payload for k in governed):
            conn.close(); raise HTTPException(409,'Improvement lifecycle, validation, and priority fields are controlled. Use the governed transition or validation action.')
        allowed_improvement_fields={'gap_id','title','description','initial_cost','recurring_cost','implementation_days','feasibility','consequence_reduction','mission_benefit','sustainability','compliance_impact','staffing_impact','expected_capability_gain','dependencies','owner'}
        unsupported=set(data)-allowed_improvement_fields
        if unsupported:
            conn.close(); raise HTTPException(409,f'Improvement fields are governed and cannot be edited here: {", ".join(sorted(unsupported))}.')
        candidate=dict(old); candidate.update(data)
        try: validated=ImprovementIn.model_validate({k:candidate[k] for k in ImprovementIn.model_fields}).model_dump()
        except ValidationError as exc: conn.close(); raise HTTPException(422,exc.errors(include_context=False))
        data={k:validated[k] for k in allowed_improvement_fields if k in data}
        merged=dict(old); merged.update(data); score,_=improvement_priority(merged); data['priority_score']=score
    if 'updated_at' in columns: data['updated_at']=now()
    if not data: conn.close(); return dict(old)
    assignments=','.join(f'{k}=?' for k in data); vals=list(data.values())+[entity_id]
    conn.execute(f'UPDATE {table} SET {assignments} WHERE id=?',vals)
    audit(conn,'UPDATE',table[:-1] if table.endswith('s') else table,entity_id,json.dumps({'before':dict(old),'changes':data},default=str)[:1000],actor(request))
    snapshot_entity(conn,table,entity_id,actor(request),'Record updated')
    conn.commit(); row=dict(conn.execute(f'SELECT * FROM {table} WHERE id=?',(entity_id,)).fetchone()); conn.close()
    if table=='evidence':
        sweep_stale_evidence([aid]); conn=db(); row=dict(conn.execute('SELECT * FROM evidence WHERE id=?',(entity_id,)).fetchone()); conn.close()
    return row

@app.delete('/api/{table}/{entity_id}')
def delete_entity(table:str,entity_id:int,request:Request):
    require(request,'write')
    allowed={'threats','scenarios','capabilities','evidence','gaps','improvements','reassessment_triggers'}
    if table not in allowed: raise HTTPException(404)
    table=sql_table_name(table)
    conn=db(); old=conn.execute(f'SELECT * FROM {table} WHERE id=?',(entity_id,)).fetchone();
    if not old: conn.close(); raise HTTPException(404)
    assessment_row_for_request(request,entity_assessment_id(table,old))
    if table=='evidence': require_sensitivity(request,old['sensitivity'])
    conn.execute(f'DELETE FROM {table} WHERE id=?',(entity_id,)); audit(conn,'DELETE',table[:-1],entity_id,'Deleted in prototype',actor(request)); conn.commit(); conn.close(); return {'ok':True}

# Register the governed generic-material capability only after all shared
# authorization, tenancy, audit, storage, and lifecycle helpers are defined.
from material_capability import register_material_capability
register_material_capability(app, globals())

# Register shared SalINTEL investigative domains after governed materials.
from salintel_domains import register_salintel_domain_capability
register_salintel_domain_capability(app, globals())


# Register the isolated public Protection Advisor prospect boundary.
from public_protection_advisor import register_public_protection_advisor
register_public_protection_advisor(app, globals())

# Register folder-selected Microsoft 365 intake and released-report storage.
from salcapa_m365_intake import register_m365_intake
register_m365_intake(app, globals())

from salcapa_m365_reports import register_m365_reports
register_m365_reports(app, globals())

from salcapa_knowledge_promotion import register_knowledge_promotion
register_knowledge_promotion(app, globals())
