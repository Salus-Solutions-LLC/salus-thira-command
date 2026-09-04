from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, HTMLResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from typing import Optional, Any, Literal
from decimal import Decimal, ROUND_HALF_UP
import sqlite3, json, os, hashlib, re, secrets, zipfile, shutil, tempfile, csv, io, html, uuid, subprocess
import urllib.parse
import httpx, jwt
from pathlib import Path
from datetime import datetime, timedelta, timezone
from storage import build_storage, StorageError
from security_controls import scan_bytes, retention_active, AV_MODE, AV_REQUIRED
from secret_provider import secret, readiness as secret_readiness
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
RETENTION_DEFAULT_DAYS = int(os.getenv('SALUS_RETENTION_DEFAULT_DAYS','2555'))
OIDC_DISCOVERY_URL = os.getenv('SALUS_OIDC_DISCOVERY_URL','').strip()
OIDC_CLIENT_ID = os.getenv('SALUS_OIDC_CLIENT_ID','').strip()
OIDC_CLIENT_SECRET = secret('SALUS_OIDC_CLIENT_SECRET','').strip()
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

    CREATE TABLE IF NOT EXISTS assessments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      organization TEXT NOT NULL,
      assessment_type TEXT NOT NULL DEFAULT 'Enterprise',
      purpose TEXT NOT NULL DEFAULT '',
      mission TEXT NOT NULL DEFAULT '',
      scope TEXT NOT NULL DEFAULT '',
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
      scope_locked INTEGER NOT NULL DEFAULT 0,
      version INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
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
    CREATE TABLE IF NOT EXISTS ops_requests (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      assessment_id INTEGER,
      source_type TEXT NOT NULL,
      source_id INTEGER,
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
      UNIQUE(tenant_id,source_type,source_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ops_requests_scope ON ops_requests(tenant_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_engagements (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      ops_request_id INTEGER NOT NULL,
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
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
      UNIQUE(tenant_id,ops_request_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ops_engagements_scope ON ops_engagements(tenant_id,assessment_id,status,id);
    CREATE TABLE IF NOT EXISTS ops_tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      tenant_id INTEGER NOT NULL,
      engagement_id INTEGER NOT NULL,
      assessment_id INTEGER NOT NULL,
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
      FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
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
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('0.8.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('0.9.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.0.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.1.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.2.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.3.0',now()))
    conn.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(?,?) ON CONFLICT(version) DO NOTHING',('1.4.0',now()))

    # v0.6 tenant/bootstrap migration. Existing records are assigned to the default tenant.
    if conn.execute('SELECT COUNT(*) c FROM tenants').fetchone()['c'] == 0:
        conn.execute('INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)',('Salus Prototype','salus-prototype','Active',now()))
    default_tenant=conn.execute('SELECT id FROM tenants ORDER BY id LIMIT 1').fetchone()['id']
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
    exclusions: str = Field(default='', max_length=2000)
    executive_sponsor: str = Field(default='', max_length=160)
    assessment_director: str = Field(default='', max_length=160)
    lead_assessor: str = Field(default='', max_length=160)
    start_date: str = Field(default='', max_length=10)
    target_completion: str = Field(default='', max_length=10)
    reassessment_date: str = Field(default='', max_length=10)
    classification: Literal['Standard','Restricted','Sensitive','Highly Sensitive'] = 'Standard'

    @field_validator('name','organization')
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized=value.strip()
        if not normalized: raise ValueError('A non-empty value is required.')
        return normalized

    @field_validator('assessment_type','purpose','mission','scope','exclusions','executive_sponsor','assessment_director','lead_assessor')
    @classmethod
    def normalized_text(cls, value: str) -> str:
        return value.strip()

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

    @field_validator('authority','rationale')
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

    @field_validator('reason','authority')
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

class OpsRequestIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    assessment_id: Optional[int] = None
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

class OpsTaskIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=500)
    instructions: str = Field(min_length=1, max_length=12000)
    assigned_to: str = Field(min_length=1, max_length=500)
    priority: Literal['Routine','Priority','Urgent','Critical'] = 'Routine'

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

class AttachmentGovernanceIn(BaseModel):
    retention_until: Optional[str] = None
    legal_hold: Optional[bool] = None
    disposition_status: Optional[str] = None

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
def oidc_configured():
    return all([OIDC_DISCOVERY_URL,OIDC_CLIENT_ID,OIDC_CLIENT_SECRET])

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
    if ENVIRONMENT=='production':
        if AUTH_MODE not in ('session','oidc'): issues.append('Production requires session or OIDC authentication.')
        if not COOKIE_SECURE: issues.append('SALUS_COOKIE_SECURE=1 is required in production.')
        if STORAGE_BACKEND=='local': issues.append('Managed object storage is required for production; local evidence storage is not production-grade.')
        if not AV_REQUIRED: issues.append('SALUS_REQUIRE_AV=1 should be enabled for production evidence uploads.')
        if AUTH_MODE=='oidc' and not oidc_configured(): issues.append('OIDC mode is selected but provider configuration is incomplete.')
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
    return {'ready':not blocking,'version':APP_VERSION,'environment':ENVIRONMENT,'auth_mode':AUTH_MODE,'storage_backend':STORAGE_BACKEND,'av_mode':AV_MODE,'secret_provider':public_status(secret_status),'rate_limit':public_status(rate_status),'telemetry':public_status(telemetry_status),'runtime_database':public_status(runtime_db),'managed_database_target':public_status(managed_db),'issues':issues}

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
    table_map={'assessment':'assessments','threat':'threats','scenario':'scenarios','capability':'capabilities','evidence':'evidence','gap':'gaps','improvement':'improvements','decision':'decisions','accepted_risk':'accepted_risks','risk_override':'risk_overrides','reassessment_trigger':'reassessment_triggers','scope_change':'scope_changes','workflow_event':'workflow_events','backup_history':'backup_history','governed_intake':'governed_intake','report_version':'report_versions','restore_request':'restore_requests','intel_finding':'intel_findings','ops_request':'ops_requests','ops_engagement':'ops_engagements','ops_task':'ops_tasks','ops_field_report':'ops_field_reports','ops_estimate':'ops_estimates','ops_estimate_line':'ops_estimate_lines','ops_expense':'ops_expenses','ops_invoice_statement':'ops_invoice_statements'}
    table=table_map.get(entity_type,entity_type if entity_type in table_map.values() else '')
    try:
        if table in ('assessments','backup_history','governed_intake','report_versions','restore_requests','intel_findings','ops_requests','ops_engagements','ops_tasks','ops_field_reports','ops_estimates','ops_estimate_lines','ops_expenses','ops_invoice_statements'): r=conn.execute(f'SELECT tenant_id FROM {table} WHERE id=?',(entity_id,)).fetchone()
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
def system_mode(): return {'auth_mode':AUTH_MODE,'version':APP_VERSION,'db_backend':DB_BACKEND,'restore_enabled':ALLOW_RESTORE,'environment':ENVIRONMENT,'storage_backend':STORAGE_BACKEND,'av_mode':AV_MODE,'av_required':AV_REQUIRED,'oidc_configured':oidc_configured(),'rate_limit_backend':RATE_LIMITER.backend,'secret_backend':secret_readiness().get('backend'),'managed_db_target':managed_target_status().get('target')}

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
        tr=httpx.post(cfg['token_endpoint'],data={'grant_type':'authorization_code','code':code,'redirect_uri':oidc_redirect_uri(request),'client_id':OIDC_CLIENT_ID,'client_secret':OIDC_CLIENT_SECRET},timeout=15); tr.raise_for_status(); tokens=tr.json(); id_token=tokens.get('id_token','')
        if not id_token: raise RuntimeError('No ID token returned')
        signing_key=jwt.PyJWKClient(cfg['jwks_uri']).get_signing_key_from_jwt(id_token).key
        claims=jwt.decode(id_token,signing_key,algorithms=['RS256','RS384','RS512','ES256','ES384','ES512'],audience=OIDC_CLIENT_ID,issuer=cfg['issuer'])
        if claims.get('nonce')!=nonce: raise RuntimeError('OIDC nonce mismatch')
    except Exception as exc:
        security_event(request,'OIDC_TOKEN_FAILURE','High',type(exc).__name__); raise HTTPException(401,'OIDC token validation failed')
    subject=str(claims.get('sub') or ''); email=str(claims.get('email') or '').strip().lower(); display=str(claims.get('name') or claims.get('preferred_username') or email or subject)
    if not subject: raise HTTPException(401,'OIDC subject claim missing')
    conn=db(); user=conn.execute("SELECT * FROM users WHERE identity_provider=? AND external_subject=? AND status='Active'",(OIDC_PROVIDER_NAME,subject)).fetchone()
    if not user and email and claims.get('email_verified') is True:
        user=conn.execute("SELECT * FROM users WHERE lower(email)=? AND status='Active'",(email,)).fetchone()
        if user and not user['external_subject']:
            conn.execute('UPDATE users SET external_subject=?,identity_provider=?,updated_at=? WHERE id=?',(subject,OIDC_PROVIDER_NAME,now(),user['id'])); conn.commit(); user=conn.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
    if not user:
        if not OIDC_AUTO_PROVISION:
            conn.close(); security_event(request,'OIDC_USER_NOT_PROVISIONED','Medium',f'subject={subject} email={email}'); raise HTTPException(403,'User is not provisioned for Salus THIRA Command')
        tenant=conn.execute("SELECT * FROM tenants WHERE slug=? AND status='Active'",(OIDC_DEFAULT_TENANT_SLUG,)).fetchone()
        if not tenant: conn.close(); raise HTTPException(503,'OIDC default tenant is not configured')
        username=email or f'{OIDC_PROVIDER_NAME}-{subject[:40]}'
        cur=conn.execute('INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email,external_subject,identity_provider) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tenant['id'],username,display,'','Contributor','Standard','Active',now(),now(),email,subject,OIDC_PROVIDER_NAME)); conn.commit(); user=conn.execute('SELECT * FROM users WHERE id=?',(cur.lastrowid,)).fetchone()
    token=secrets.token_urlsafe(32); session_expires=(_iso_now_dt()+timedelta(hours=SESSION_HOURS)).replace(microsecond=0).isoformat().replace('+00:00','Z')
    conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',(user['id'],_hash_token(token),session_expires,now(),now())); conn.commit(); conn.close()
    security_event(request,'OIDC_LOGIN_SUCCESS','Info',f'user_id={user["id"]}',tenant=int(user['tenant_id']),user_name=display)
    response=RedirectResponse('/',status_code=302); response.set_cookie('salus_session',token,httponly=True,secure=COOKIE_SECURE,samesite='strict',max_age=SESSION_HOURS*3600,path='/'); response.delete_cookie('salus_oidc_state',path='/'); return response

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
    require(request,'admin'); tid=tenant_id(request); ts=datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'); name=f'salus-thira-tenant-{tid}-backup-{ts}.zip'; final=os.path.join(BACKUPS_DIR,name)
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
        for item in sorted(records.get('evidence_attachments',[]),key=lambda x:str(x.get('stored_name',''))):
            fn=str(item.get('stored_name','')).strip()
            if not fn: continue
            try: b=storage.get_bytes(fn)
            except Exception as exc:
                error_id=uuid.uuid4().hex; record_internal_failure('backup evidence read',error_id,exc)
                raise HTTPException(409,f'Backup cannot read an evidence object. Reference: {error_id}')
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
            assessment_count=len(records.get('assessments',[])); attachment_count=len(records.get('evidence_attachments',[]))
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
            conn=db(); old_keys=[r['stored_name'] for r in conn.execute('SELECT ea.stored_name FROM evidence_attachments ea JOIN assessments a ON a.id=ea.assessment_id WHERE a.tenant_id=?',(tid,))]; conn.close()
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

@app.get('/api/salcapa/workspace')
def get_salcapa_workspace(request:Request):
    require(request,'read'); return salcapa_workspace_contract(request)

@app.get('/api/salcapa/common-operating-picture')
def salcapa_common_operating_picture(request:Request):
    require(request,'read'); tid=tenant_id(request); ids=accessible_assessment_ids(request); conn=db()
    if ids:
        marks=','.join('?'*len(ids)); params=tuple(ids)
        open_triggers=[dict(r) for r in conn.execute(f"SELECT * FROM reassessment_triggers WHERE assessment_id IN ({marks}) AND status<>'Resolved' ORDER BY CASE severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 ELSE 3 END,id DESC LIMIT 10",params)]
        stale=conn.execute(f"SELECT COUNT(*) c FROM evidence WHERE assessment_id IN ({marks}) AND lifecycle_status='Stale'",params).fetchone()['c']
        active_risks=conn.execute(f"SELECT COUNT(*) c FROM accepted_risks WHERE assessment_id IN ({marks}) AND status IN ('Active','Under Review')",params).fetchone()['c']
    else: open_triggers=[]; stale=active_risks=0
    if protected_member_request(request):
        intel=[dict(r) for r in conn.execute("SELECT id,assessment_id,title,relevance,credibility,validation_status,operational_significance,status,qualified_at,updated_at FROM intel_findings WHERE tenant_id=? AND status IN ('Qualified','Sent to SalTHIRA') ORDER BY id DESC LIMIT 10",(tid,))]
        ops=[dict(r) for r in conn.execute("SELECT id,assessment_id,source_type,source_id,title,priority,status,result_summary,completed_at,updated_at FROM ops_requests WHERE tenant_id=? AND status IN ('Requested','Authorized','In Progress') ORDER BY id DESC LIMIT 10",(tid,))]
    else:
        intel=[dict(r) for r in conn.execute("SELECT * FROM intel_findings WHERE tenant_id=? AND status IN ('Qualified','Sent to SalTHIRA') ORDER BY id DESC LIMIT 10",(tid,))]
        ops=[dict(r) for r in conn.execute("SELECT * FROM ops_requests WHERE tenant_id=? AND status IN ('Requested','Authorized','In Progress') ORDER BY id DESC LIMIT 10",(tid,))]
    conn.close()
    return {'workspace':salcapa_workspace_contract(request),'metrics':{'qualified_intelligence':len(intel),'priority_actions':len(open_triggers),'active_operations':len(ops),'stale_evidence':stale,'active_accepted_risks':active_risks},'attention':{'intelligence':intel,'reassessment':open_triggers,'operations':ops}}

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

@app.get('/api/salops/requests')
def list_ops_requests(request:Request):
    require(request,'read'); conn=db()
    if protected_member_request(request):
        rows=[dict(r) for r in conn.execute('SELECT id,assessment_id,source_type,source_id,title,priority,status,result_summary,completed_at,updated_at FROM ops_requests WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]
    else:
        rows=[dict(r) for r in conn.execute('SELECT * FROM ops_requests WHERE tenant_id=? ORDER BY id DESC',(tenant_id(request),))]
    conn.close(); return rows

@app.post('/api/salops/requests')
def create_ops_request(p:OpsRequestIn,request:Request):
    require(request,'write'); tid=tenant_id(request); who=actor(request)
    if p.assessment_id is not None: assessment_row_for_request(request,p.assessment_id)
    ts=now(); conn=db(); cur=conn.execute('INSERT INTO ops_requests(tenant_id,assessment_id,source_type,source_id,title,description,priority,status,requested_by,requested_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,p.assessment_id,'Manual',None,p.title,p.description,p.priority,'Requested',who,ts,ts)); oid=cur.lastrowid; audit(conn,'SALOPS_REQUEST','ops_request',oid,p.title,who); conn.commit(); row=dict(conn.execute('SELECT * FROM ops_requests WHERE id=?',(oid,)).fetchone()); conn.close(); return row

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
    require(request,'decide'); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute("SELECT * FROM ops_requests WHERE id=? AND tenant_id=? AND status='Requested'",(request_id,tid)).fetchone()
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
    rows=[dict(r) for r in conn.execute(sql,params)]; conn.close(); return rows

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
    ts=now(); cur=conn.execute('INSERT INTO ops_engagements(tenant_id,ops_request_id,assessment_id,title,service_type,objective,location,planned_start,planned_end,operational_lead,communications_plan,member_status_summary,status,authorized_by,authorized_at,created_by,created_at,updated_by,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,request_id,source['assessment_id'],source['title'],p.service_type,p.objective,p.location,start,end,p.operational_lead,p.communications_plan,p.member_status_summary,'Planning',source['authorized_by'],source['authorized_at'],who,ts,who,ts)); eid=cur.lastrowid
    audit(conn,'CREATE','ops_engagement',eid,f'Created from authorized ops_request={request_id}',who); snapshot_entity(conn,'ops_engagements',eid,who,'Operational engagement created'); conn.commit(); row=dict(conn.execute('SELECT * FROM ops_engagements WHERE id=?',(eid,)).fetchone()); conn.close(); return row

@app.post('/api/salops/engagements/{engagement_id}/transition')
def transition_ops_engagement(engagement_id:int,p:OpsEngagementTransitionIn,request:Request):
    require(request,'write'); require_ops_authority(request); row=_ops_engagement(request,engagement_id); allowed={'Planning':'Mobilizing','Mobilizing':'Active','Active':'Demobilizing','Demobilizing':'Closed'}
    if allowed.get(row['status'])!=p.status: raise HTTPException(409,f'Engagement transition must follow Planning → Mobilizing → Active → Demobilizing → Closed; current status is {row["status"]}.')
    tid=tenant_id(request); who=actor(request); ts=now(); conn=db()
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

@app.get('/api/salops/engagements/{engagement_id}/tasks')
def list_ops_tasks(engagement_id:int,request:Request):
    require(request,'read'); require_salus_component_authority(request,'SalOPS'); _ops_engagement(request,engagement_id); conn=db(); rows=[dict(r) for r in conn.execute('SELECT * FROM ops_tasks WHERE engagement_id=? AND tenant_id=? ORDER BY id',(engagement_id,tenant_id(request)))]; conn.close(); return rows

@app.post('/api/salops/engagements/{engagement_id}/tasks')
def create_ops_task(engagement_id:int,p:OpsTaskIn,request:Request):
    require(request,'write'); require_ops_authority(request); engagement=_ops_engagement(request,engagement_id)
    if engagement['status'] in ('Demobilizing','Closed'): raise HTTPException(409,'New tasks cannot be assigned during demobilization or after closure.')
    tid=tenant_id(request); who=actor(request); ts=now(); conn=db(); cur=conn.execute('INSERT INTO ops_tasks(tenant_id,engagement_id,assessment_id,title,instructions,assigned_to,priority,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,engagement_id,engagement['assessment_id'],p.title,p.instructions,p.assigned_to,p.priority,'Assigned',who,ts,ts)); task_id=cur.lastrowid; audit(conn,'CREATE','ops_task',task_id,f'engagement={engagement_id}; assigned_to={p.assigned_to}',who); snapshot_entity(conn,'ops_tasks',task_id,who,'Operational task assigned'); conn.commit(); row=dict(conn.execute('SELECT * FROM ops_tasks WHERE id=?',(task_id,)).fetchone()); conn.close(); return row

@app.post('/api/salops/tasks/{task_id}/transition')
def transition_ops_task(task_id:int,p:OpsTaskTransitionIn,request:Request):
    require(request,'write'); require_ops_authority(request); tid=tenant_id(request); who=actor(request); conn=db(); row=conn.execute('SELECT * FROM ops_tasks WHERE id=? AND tenant_id=?',(task_id,tid)).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Operational task not found')
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
    if table=='assessments': rows=[dict(r) for r in conn.execute(f'SELECT * FROM assessments WHERE id IN ({marks}) ORDER BY id DESC',P)]
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
            filtered.append(r)
        rows=filtered
    conn.close(); return rows

@app.get('/api/trace/{assessment_id}')
def trace(assessment_id:int, request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id); sweep_stale_evidence([assessment_id]); sweep_overdue_risk_overrides([assessment_id]); conn=db()
    a=conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone()
    if not a: raise HTTPException(404)
    data={'assessment':dict(a),'threats':[]}
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
    audit(conn,'CREATE',table[:-1] if table.endswith('s') else table,cur.lastrowid,json.dumps(data,default=str)[:500],user_name)
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
    start_date=_normalize_date(p.start_date,'Assessment start date')
    target_completion=_normalize_date(p.target_completion,'Assessment target completion date')
    reassessment_date=_normalize_date(p.reassessment_date,'Assessment reassessment date')
    return insert_model('assessments',p,actor(request),extra={
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
        'scope_locked':0,
        'version':1,
    })

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
    require(request,'decide'); assessment_row_for_request(request,p.assessment_id)
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
        row=insert_model_in_transaction(conn,'decisions',p,who,extra={'target_completion':target_completion,'review_date':review_date,'review_lifecycle_status':'Current','review_overdue_reason':'','review_overdue_at':'','last_review_at':'','last_review_by':''})
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
            cur=conn.execute('''INSERT INTO accepted_risks(assessment_id,decision_id,improvement_id,gap_id,title,risk_statement,authority,residual_exposure,acceptance_date,review_date,reconsideration_trigger,owner,status,closure_basis,review_lifecycle_status,review_overdue_reason,review_overdue_at,last_review_at,last_review_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(p.assessment_id,row['id'],p.improvement_id,gap_id,title,p.rationale,p.authority,p.expected_residual_risk,ts[:10],review_date,p.conditions,p.implementation_owner,'Active','','Current','','','','',ts,ts))
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
    require(request,'decide'); next_review=_normalize_date(p.next_review_date,'Next executive decision review date',required=True); outcome=(p.review_outcome or '').strip()
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
    require(request,'decide'); next_review=_normalize_date(p.next_review_date,'Next accepted-risk review date',required=True); outcome=(p.review_outcome or '').strip()
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
    require(request,'decide')
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
    if not p.authority.strip(): raise HTTPException(422,'Professional risk override requires a named authority.')
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
        cur=conn.execute('''INSERT INTO risk_overrides(assessment_id,threat_id,calculated_score,calculated_band,assigned_score,assigned_band,reason,evidence_id,authority,review_date,review_lifecycle_status,review_overdue_reason,review_overdue_at,last_review_at,last_review_by,status,supersedes_id,withdrawn_reason,created_by,created_at,withdrawn_by,withdrawn_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(p.assessment_id,p.threat_id,current['current_score'],current['current_band'],float(p.assigned_score),risk_band(float(p.assigned_score)),p.reason.strip(),p.evidence_id,p.authority.strip(),review_date,'Current','','','','','Active',previous['id'] if previous else None,'',who,ts,'','',ts))
        oid=cur.lastrowid
        audit(conn,'CREATE','risk_override',oid,f"Calculated {current['current_band']} {current['current_score']} -> assigned {risk_band(float(p.assigned_score))} {float(p.assigned_score):.1f}; authority={p.authority.strip()}",who)
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
    require(request,'decide')
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

@app.get('/api/reports/{assessment_id}')
def list_report_versions(assessment_id:int,request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id)
    conn=db(); rows=[dict(r) for r in conn.execute('SELECT id,assessment_id,assessment_version,report_type,status,snapshot_sha256,created_by,created_at,reviewed_by,reviewed_at,approved_by,approved_at,released_by,released_at,transition_reason FROM report_versions WHERE tenant_id=? AND assessment_id=? ORDER BY id DESC',(tenant_id(request),assessment_id))]; conn.close(); return rows

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
    ts=now(); field={'Reviewed':'reviewed','Approved':'approved','Released':'released'}[p.status]
    conn.execute(f'UPDATE report_versions SET status=?,{field}_by=?,{field}_at=?,transition_reason=? WHERE id=?',(p.status,who,ts,p.reason,report_id)); audit(conn,'REPORT_TRANSITION','report_version',report_id,f'{row["status"]} -> {p.status}: {p.reason}',who); conn.commit(); result=dict(conn.execute('SELECT * FROM report_versions WHERE id=?',(report_id,)).fetchone()); conn.close(); return result

@app.get('/api/reports/versions/{report_id}/snapshot')
def report_version_snapshot(report_id:int,request:Request):
    require(request,'read'); conn=db(); row=conn.execute('SELECT * FROM report_versions WHERE id=? AND tenant_id=?',(report_id,tenant_id(request))).fetchone()
    if not row: conn.close(); raise HTTPException(404,'Report version not found')
    assessment_row_for_request(request,row['assessment_id']); snapshot=row['snapshot_json']; actual=hashlib.sha256(snapshot.encode('utf-8')).hexdigest()
    if actual!=row['snapshot_sha256']: conn.close(); security_event(request,'REPORT_INTEGRITY_FAILURE','High',f'report_id={report_id}'); raise HTTPException(409,'Report snapshot failed integrity verification')
    conn.close(); response=JSONResponse(json.loads(snapshot)); response.headers['ETag']=f'"{actual}"'; response.headers['X-Salus-Report-Status']=row['status']; return response

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
    require(request,'read'); assessment_row_for_request(request,assessment_id); package=executive_package(assessment_id); out=io.StringIO(); w=csv.writer(out)
    a=package['assessment']; w.writerow(['Salus THIRA Command Executive Summary']); w.writerow(['Assessment',a['name']]); w.writerow(['Organization',a['organization']]); w.writerow(['Status',a['status']]); w.writerow(['Version',a['version']]); w.writerow(['Mission',a['mission']]); w.writerow([])
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
    response=PlainTextResponse(out.getvalue(),media_type='text/csv; charset=utf-8'); response.headers['Content-Disposition']=f'attachment; filename=salus-thira-executive-{assessment_id}.csv'; return response

@app.get('/api/report/{assessment_id}/executive.html')
def executive_html(assessment_id:int,request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id); p=executive_package(assessment_id); a=p['assessment']
    risk_rows=''.join(f"<tr><td>{html.escape(str(r['name']))}</td><td>{html.escape(str(r['inherent_band']))} {r['inherent_score']}</td><td>{html.escape(str(r['current_band']))} {r['current_score']}</td><td>{(html.escape(str(r['assigned_risk_band']))+' '+str(r['assigned_risk_score'])) if r.get('professional_override') else ''}</td><td>{html.escape(str(r['predicted_residual_band']))} {r['predicted_residual_score']}</td><td>{html.escape(str(r['validated_residual_band']))} {r['validated_residual_score']}</td><td>{r['validated_improvements']}</td><td>{html.escape(str(r['confidence']))}</td></tr>" for r in p['risk'])
    capability_rows=''.join(f"<tr><td>{html.escape(str(c['name']))}</td><td>{html.escape(str(c['measurement_type']))}</td><td>{html.escape(str(c['comparator']))} {c['required_standard']} {html.escape(str(c['measurement_unit']))}</td><td>{c['current_performance']} {html.escape(str(c['measurement_unit']))}</td><td>{c['attainment_percent']}%</td><td>{html.escape(str(c['target_status']))}</td></tr>" for c in p['capability_performance'])
    priority_rows=''.join(f"<tr><td>{r['priority_score']}</td><td>{html.escape(str(r['title']))}</td><td>{html.escape(str(r['status']))}</td><td>${float(r['initial_cost'] or 0):,.0f}</td></tr>" for r in p['priorities'][:10])
    decision_rows=''.join(f"<tr><td>{html.escape(str(d['decision_type']))}</td><td>{html.escape(str(d['authority']))}</td><td>${float(d['funding_authorized'] or 0):,.0f}</td><td>{html.escape(str(d['rationale']))}</td></tr>" for d in p['decisions'])
    accepted_rows=''.join(f"<tr><td>{html.escape(str(r['status']))}</td><td>{html.escape(str(r['title']))}</td><td>{html.escape(str(r['authority']))}</td><td>{html.escape(str(r['residual_exposure']))}</td><td>{html.escape(str(r['review_date']))}</td></tr>" for r in p['accepted_risks'])
    override_rows=''.join(f"<tr><td>{html.escape(str(r['status']))}</td><td>{r['threat_id']}</td><td>{html.escape(str(r['calculated_band']))} {r['calculated_score']}</td><td>{html.escape(str(r['assigned_band']))} {r['assigned_score']}</td><td>{html.escape(str(r['authority']))}</td><td>{html.escape(str(r['reason']))}</td><td>{html.escape(str(r['review_date']))}</td></tr>" for r in p['risk_overrides'])
    evidence_rows=''.join(f"<tr><td>{html.escape(str(e['title']))}</td><td>{html.escape(str(e['verification_status']))}</td><td>{html.escape(str(e.get('lifecycle_status','Current')))}</td><td>{html.escape(str(e.get('valid_until','')))}</td><td>{html.escape(str(e.get('stale_reason','')))}</td></tr>" for e in p['evidence'])
    body=f'''<!doctype html><html><head><meta charset="utf-8"><title>Salus THIRA Executive Summary</title><style>body{{font-family:Arial,sans-serif;margin:36px;color:#111}}h1{{margin-bottom:0}}.meta{{color:#555}}table{{width:100%;border-collapse:collapse;margin:16px 0 28px}}th,td{{border:1px solid #bbb;padding:8px;text-align:left;vertical-align:top}}th{{background:#eee}}@media print{{button{{display:none}}}}</style></head><body><button onclick="window.print()">Print / Save PDF</button><h1>Salus THIRA Executive Summary</h1><p class="meta">Generated {html.escape(now())}</p><h2>{html.escape(str(a['name']))}</h2><p>{html.escape(str(a['organization']))} · {html.escape(str(a['assessment_type']))} · {html.escape(str(a['status']))} · Version {a['version']}</p><p><strong>Mission:</strong> {html.escape(str(a['mission']))}</p><p><strong>Purpose:</strong> {html.escape(str(a['purpose']))}</p><h2>Risk Outlook</h2><table><tr><th>Threat / Hazard</th><th>Inherent</th><th>Current</th><th>Professional Assigned Risk</th><th>Predicted Residual</th><th>Validated Residual</th><th>Validated Improvements</th><th>Confidence</th></tr>{risk_rows}</table><h2>Professional Risk Override Register</h2><table><tr><th>Status</th><th>Threat ID</th><th>Calculated</th><th>Assigned</th><th>Authority</th><th>Reason</th><th>Review Date</th></tr>{override_rows}</table><h2>Evidence Lifecycle</h2><table><tr><th>Evidence</th><th>Verification</th><th>Lifecycle</th><th>Valid Until</th><th>Stale Reason</th></tr>{evidence_rows}</table><h2>Capability Performance</h2><table><tr><th>Capability</th><th>Measure</th><th>Target</th><th>Current</th><th>Attainment</th><th>Status</th></tr>{capability_rows}</table><h2>Top Improvement Priorities</h2><table><tr><th>Priority</th><th>Improvement</th><th>Status</th><th>Initial Cost</th></tr>{priority_rows}</table><h2>Executive Decisions</h2><table><tr><th>Decision</th><th>Authority</th><th>Funding</th><th>Rationale</th></tr>{decision_rows}</table><h2>Accepted Risk Register</h2><table><tr><th>Status</th><th>Risk</th><th>Authority</th><th>Residual Exposure</th><th>Review Date</th></tr>{accepted_rows}</table><p class="meta">Decision-support output. Professional judgment and authoritative source records remain controlling.</p></body></html>'''
    return HTMLResponse(body)

@app.get('/api/export/{assessment_id}')
def export_assessment(assessment_id:int, request:Request):
    require(request,'read'); assessment_row_for_request(request,assessment_id); package=executive_package(assessment_id)
    response=JSONResponse(package); response.headers['Content-Disposition']=f'attachment; filename="salus-thira-assessment-{assessment_id}.json"'; return response

@app.put('/api/{table}/{entity_id}')
def update_entity(table:str,entity_id:int,payload:dict[str,Any],request:Request):
    require(request,'decide' if table=='accepted_risks' else 'write')
    allowed={'assessments','threats','scenarios','capabilities','evidence','gaps','improvements','accepted_risks','reassessment_triggers'}
    if table not in allowed: raise HTTPException(404)
    table=sql_table_name(table)
    conn=db(); old=conn.execute(f'SELECT * FROM {table} WHERE id=?',(entity_id,)).fetchone()
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
        governed_reassessment={'reassessment_date','reassessment_lifecycle_status','reassessment_overdue_reason','reassessment_overdue_at','last_reassessment_review_at','last_reassessment_review_by'}
        if any(k in payload and str(payload.get(k) or '')!=str(old[k] or '') for k in governed_reassessment):
            conn.close(); raise HTTPException(409,'Assessment reassessment lifecycle fields are controlled. Use the assessment reassessment review action rather than editing review currency directly.')
        if 'status' in payload and str(payload['status'])!=str(old['status']):
            conn.close(); raise HTTPException(409,'Use the controlled workflow transition action to change assessment status.')
        if old['scope_locked']:
            protected={'purpose','mission','scope','exclusions'}
            if any(k in payload and str(payload[k])!=str(old[k]) for k in protected):
                conn.close(); raise HTTPException(409,'Scope is locked. Create an authorized scope/version change rather than overwriting mission, purpose, scope, or exclusions.')
    columns={r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
    immutable={'id','created_at'}
    if table in CHILD_ASSESSMENT_TABLES: immutable.add('assessment_id')
    if table=='accepted_risks': immutable|={'assessment_id','decision_id','improvement_id','gap_id','authority','acceptance_date'}
    if table=='accepted_risks':
        attempted_immutable=[k for k in immutable if k in payload and str(payload.get(k) or '')!=str(old[k] or '')]
        if attempted_immutable:
            conn.close(); raise HTTPException(409,f'Accepted-risk provenance is immutable: {", ".join(sorted(attempted_immutable))}.')
    server_controlled={'tenant_id','created_at','updated_at','version','version_no','changed_at','changed_by','change_reason'}
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
