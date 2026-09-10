"""Governed material suggestions, duplicate review, and proposal-only handoffs.

This module prepares bounded review aids from already-authorized derived text.
It never qualifies intelligence, resolves identity, creates an authoritative
relationship, or changes disclosure, monitoring, scope, cost, or authority.
Cross-tenant comparison and silent record merging are prohibited.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import unicodedata
import uuid
from typing import Literal

import database as database_support

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator


PROCESSOR = "SalCAPA Governed Source Review"
PROCESSOR_VERSION = "1.0.0"
MAX_DERIVATIVE_CHARACTERS = 500_000
MAX_REFERENCES = 1_000
MAX_ALIASES_PER_REFERENCE = 20
MAX_ALIAS_CHARACTERS = 240
MAX_COMPARISON_CANDIDATES = 200
MAX_TOKENS = 50_000
SHINGLE_WIDTH = 5
NEAR_DUPLICATE_MINIMUM_BASIS_POINTS = 6_000
RULESET = {
    "reference_matching": "nfkc-casefold-boundary-v1",
    "date_time": "explicit-date-time-v1",
    "exact_duplicate": "sha256-v1",
    "near_duplicate": "token-shingle-jaccard-v1",
    "shingle_width": SHINGLE_WIDTH,
    "minimum_basis_points": NEAR_DUPLICATE_MINIMUM_BASIS_POINTS,
}
RULESET_HASH = hashlib.sha256(
    json.dumps(RULESET, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()

REFERENCE_TYPES = {"Person", "Organization", "Protected Member", "Facility", "Asset", "Event", "Location"}
ENTITY_REFERENCE_TYPES = {"Person", "Organization", "Protected Member", "Asset", "Event"}
LOCATION_REFERENCE_TYPES = {"Facility", "Location"}
REVIEW_STATES = {"Human Reviewed", "Corrected", "Rejected"}
DESTINATION_PRODUCTS = {"SalINTEL", "SalTHIRA", "SalCAPA", "SalOPS", "PROVE", "Personnel Assessment", "Facility Assessment", "Mission Map"}


class ReferenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_type: Literal["Person", "Organization", "Protected Member", "Facility", "Asset", "Event", "Location"]
    display_name: str = Field(min_length=1, max_length=240)
    aliases: list[str] = Field(default_factory=list, max_length=MAX_ALIASES_PER_REFERENCE)
    target_type: str = Field(default="", max_length=120)
    target_id: int = Field(default=0, ge=0)
    sensitivity: Literal["Standard", "Restricted", "Highly Restricted"] = "Restricted"

    @field_validator("display_name", "target_type")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            alias = value.strip()
            if not alias or len(alias) > MAX_ALIAS_CHARACTERS:
                raise ValueError("Reference aliases must contain 1 to 240 characters.")
            key = _normalized(alias)
            if len(key) < 3:
                raise ValueError("Reference aliases must contain at least three normalized characters.")
            if key not in seen:
                cleaned.append(alias)
                seen.add(key)
        return cleaned


class AnalyzeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=4000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A legitimate review purpose is required.")
        return value


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["Human Reviewed", "Corrected", "Rejected"]
    reason: str = Field(min_length=1, max_length=4000)
    corrected_value: str = Field(default="", max_length=1000)

    @field_validator("reason", "corrected_value")
    @classmethod
    def clean_values(cls, value: str) -> str:
        return value.strip()

    @field_validator("corrected_value")
    @classmethod
    def correction_is_bounded(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("A correction cannot contain null characters.")
        return value


class LinkProposalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination_product: Literal["SalINTEL", "SalTHIRA", "SalCAPA", "SalOPS", "PROVE", "Personnel Assessment", "Facility Assessment", "Mission Map"]
    destination_type: str = Field(min_length=1, max_length=120)
    destination_id: int = Field(default=0, ge=0)
    purpose: str = Field(min_length=1, max_length=4000)

    @field_validator("destination_type", "purpose")
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A non-empty value is required.")
        return value


SCHEMA = """
CREATE TABLE IF NOT EXISTS material_reference_terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  reference_key TEXT NOT NULL UNIQUE,
  reference_type TEXT NOT NULL,
  display_name TEXT NOT NULL,
  aliases_json TEXT NOT NULL DEFAULT '[]',
  target_type TEXT NOT NULL DEFAULT '',
  target_id INTEGER NOT NULL DEFAULT 0,
  sensitivity TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Active',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_material_reference_terms_scope
  ON material_reference_terms(tenant_id,status,reference_type,id);

CREATE TABLE IF NOT EXISTS material_suggestion_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  job_key TEXT NOT NULL UNIQUE,
  source_material_id INTEGER NOT NULL,
  derivative_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  purpose TEXT NOT NULL,
  processor TEXT NOT NULL,
  processor_version TEXT NOT NULL,
  ruleset_hash TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  requested_by_role TEXT NOT NULL,
  candidate_count INTEGER NOT NULL DEFAULT 0,
  comparison_count INTEGER NOT NULL DEFAULT 0,
  failure_code TEXT NOT NULL DEFAULT '',
  failure_detail TEXT NOT NULL DEFAULT '',
  started_at TEXT NOT NULL,
  completed_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
  FOREIGN KEY (derivative_id) REFERENCES material_derivatives(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_material_suggestion_jobs_scope
  ON material_suggestion_jobs(tenant_id,derivative_id,status,id);

CREATE TABLE IF NOT EXISTS material_suggestions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  suggestion_key TEXT NOT NULL UNIQUE,
  job_id INTEGER NOT NULL,
  source_material_id INTEGER NOT NULL,
  derivative_id INTEGER NOT NULL,
  suggestion_type TEXT NOT NULL,
  suggestion_subtype TEXT NOT NULL,
  source_text TEXT NOT NULL,
  context_text TEXT NOT NULL,
  start_offset INTEGER NOT NULL,
  end_offset INTEGER NOT NULL,
  proposed_value TEXT NOT NULL,
  alternatives_json TEXT NOT NULL DEFAULT '[]',
  reference_id INTEGER,
  method TEXT NOT NULL,
  rule_id TEXT NOT NULL,
  confidence_status TEXT NOT NULL,
  uncertainty_note TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  review_status TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_by_role TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  current_value TEXT NOT NULL DEFAULT '',
  supersedes_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (job_id) REFERENCES material_suggestion_jobs(id) ON DELETE RESTRICT,
  FOREIGN KEY (source_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
  FOREIGN KEY (derivative_id) REFERENCES material_derivatives(id) ON DELETE RESTRICT,
  FOREIGN KEY (reference_id) REFERENCES material_reference_terms(id) ON DELETE SET NULL,
  FOREIGN KEY (supersedes_id) REFERENCES material_suggestions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_material_suggestions_triage
  ON material_suggestions(tenant_id,review_status,suggestion_type,id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_material_suggestions_idempotent
  ON material_suggestions(job_id,suggestion_type,rule_id,start_offset,end_offset,proposed_value);

CREATE TABLE IF NOT EXISTS material_duplicate_suggestions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  comparison_key TEXT NOT NULL UNIQUE,
  job_id INTEGER NOT NULL,
  left_derivative_id INTEGER NOT NULL,
  right_derivative_id INTEGER NOT NULL,
  comparison_class TEXT NOT NULL,
  method TEXT NOT NULL,
  method_version TEXT NOT NULL,
  similarity_basis_points INTEGER NOT NULL DEFAULT 0,
  similarity_band TEXT NOT NULL,
  support_summary TEXT NOT NULL,
  difference_summary TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  confidence_status TEXT NOT NULL,
  uncertainty_note TEXT NOT NULL,
  review_status TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_by_role TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (job_id) REFERENCES material_suggestion_jobs(id) ON DELETE RESTRICT,
  FOREIGN KEY (left_derivative_id) REFERENCES material_derivatives(id) ON DELETE RESTRICT,
  FOREIGN KEY (right_derivative_id) REFERENCES material_derivatives(id) ON DELETE RESTRICT,
  UNIQUE(tenant_id,left_derivative_id,right_derivative_id,method,method_version)
);
CREATE INDEX IF NOT EXISTS idx_material_duplicate_suggestions_triage
  ON material_duplicate_suggestions(tenant_id,review_status,comparison_class,id);

CREATE TABLE IF NOT EXISTS material_suggestion_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  record_type TEXT NOT NULL,
  record_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  from_status TEXT NOT NULL DEFAULT '',
  to_status TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL,
  corrected_value TEXT NOT NULL DEFAULT '',
  changed_by TEXT NOT NULL,
  changed_by_role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_material_suggestion_events_record
  ON material_suggestion_events(tenant_id,record_type,record_id,id);

CREATE TABLE IF NOT EXISTS proposed_governed_links (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  proposal_key TEXT NOT NULL UNIQUE,
  suggestion_id INTEGER NOT NULL,
  destination_product TEXT NOT NULL,
  destination_type TEXT NOT NULL,
  destination_id INTEGER NOT NULL DEFAULT 0,
  purpose TEXT NOT NULL,
  status TEXT NOT NULL,
  sensitivity TEXT NOT NULL,
  proposed_by TEXT NOT NULL,
  proposed_by_role TEXT NOT NULL,
  proposed_at TEXT NOT NULL,
  reviewed_by TEXT NOT NULL DEFAULT '',
  reviewed_by_role TEXT NOT NULL DEFAULT '',
  reviewed_at TEXT NOT NULL DEFAULT '',
  review_reason TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (suggestion_id) REFERENCES material_suggestions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_proposed_governed_links_scope
  ON proposed_governed_links(tenant_id,status,destination_product,id);
"""


MONTHS = {
    name.casefold(): index for index, name in enumerate(
        ("", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
    ) if name
}
MONTH_PATTERN = "|".join(name.title() for name in MONTHS)
DATE_PATTERNS = (
    ("day-month-name-year", re.compile(rf"(?<!\w)(\d{{1,2}})\s+({MONTH_PATTERN})\s+(\d{{4}})(?!\w)", re.I)),
    ("month-name-day-year", re.compile(rf"(?<!\w)({MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})(?!\w)", re.I)),
    ("iso-date", re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")),
    ("numeric-date", re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?!\d)")),
)
TIME_PATTERN = re.compile(r"(?<!\d)([01]\d|2[0-3]):([0-5]\d)(?:\s*(Z|UTC|[+-]\d{2}:?\d{2}))?(?!\d)", re.I)
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _context(text: str, start: int, end: int, radius: int = 180) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return ("…" if left else "") + text[left:right] + ("…" if right < len(text) else "")


def _display_date(year: int, month: int, day: int) -> str | None:
    try:
        value = dt.date(year, month, day)
    except ValueError:
        return None
    return f"{value.day:02d} {value.strftime('%B')} {value.year:04d}"


def _date_time_candidates(text: str) -> list[dict]:
    records: list[dict] = []
    seen: set[tuple[int, int, str]] = set()
    for rule_id, pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0)
            alternatives: list[str] = []
            uncertainty = "The source wording is preserved; this proposed normalization does not establish an event date."
            proposed: str | None = None
            if rule_id == "day-month-name-year":
                proposed = _display_date(int(match.group(3)), MONTHS[match.group(2).casefold()], int(match.group(1)))
            elif rule_id == "month-name-day-year":
                proposed = _display_date(int(match.group(3)), MONTHS[match.group(1).casefold()], int(match.group(2)))
            elif rule_id == "iso-date":
                proposed = _display_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            else:
                first, second, year = map(int, match.groups())
                day_first = _display_date(year, second, first)
                month_first = _display_date(year, first, second)
                valid = list(dict.fromkeys(item for item in (day_first, month_first) if item))
                if len(valid) == 1:
                    proposed = valid[0]
                elif len(valid) > 1:
                    proposed = "Ambiguous numeric date"
                    alternatives = valid
                    uncertainty = "Numeric date order is ambiguous. Review the source context before selecting an interpretation."
            if not proposed:
                continue
            key = (match.start(), match.end(), "Date")
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "suggestion_type": "Date", "suggestion_subtype": rule_id,
                "source_text": raw, "context_text": _context(text, match.start(), match.end()),
                "start_offset": match.start(), "end_offset": match.end(),
                "proposed_value": proposed, "alternatives": alternatives,
                "method": "Explicit bounded date parsing", "rule_id": rule_id,
                "uncertainty_note": uncertainty,
            })
    for match in TIME_PATTERN.finditer(text):
        timezone = match.group(3) or ""
        proposed = f"{match.group(1)}:{match.group(2)}" + (f" {timezone.upper()}" if timezone else "")
        uncertainty = "The source time has no recorded timezone basis." if not timezone else "The source timezone marker is preserved; review the event context."
        records.append({
            "suggestion_type": "Time", "suggestion_subtype": "explicit-24-hour-time",
            "source_text": match.group(0), "context_text": _context(text, match.start(), match.end()),
            "start_offset": match.start(), "end_offset": match.end(),
            "proposed_value": proposed, "alternatives": [],
            "method": "Explicit bounded 24-hour time parsing", "rule_id": "explicit-24-hour-time",
            "uncertainty_note": uncertainty,
        })
    return sorted(records, key=lambda item: (item["start_offset"], item["end_offset"], item["suggestion_type"]))


def _reference_candidates(text: str, references: list[dict]) -> list[dict]:
    records: list[dict] = []
    seen: set[tuple[int, int, int]] = set()
    for reference in references:
        aliases = [reference["display_name"], *json.loads(reference["aliases_json"] or "[]")]
        for alias in aliases:
            normalized_alias = _normalized(alias)
            if len(normalized_alias) < 3:
                continue
            pattern = re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.I)
            for match in pattern.finditer(text):
                key = (match.start(), match.end(), int(reference["id"]))
                if key in seen:
                    continue
                seen.add(key)
                ref_type = reference["reference_type"]
                records.append({
                    "suggestion_type": "Location" if ref_type in LOCATION_REFERENCE_TYPES else "Entity",
                    "suggestion_subtype": ref_type,
                    "source_text": match.group(0), "context_text": _context(text, match.start(), match.end()),
                    "start_offset": match.start(), "end_offset": match.end(),
                    "proposed_value": reference["display_name"], "alternatives": [],
                    "reference_id": int(reference["id"]),
                    "method": "Authorized tenant reference comparison", "rule_id": "tenant-reference-boundary-v1",
                    "uncertainty_note": "A text match is a review aid. It does not establish identity, location, relationship, or source truth.",
                })
    return sorted(records, key=lambda item: (item["start_offset"], item["end_offset"], item["suggestion_subtype"]))


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(unicodedata.normalize("NFKC", text).casefold())[:MAX_TOKENS]


def _shingles(text: str) -> set[str]:
    tokens = _tokens(text)
    if len(tokens) < SHINGLE_WIDTH:
        return set()
    return {
        hashlib.sha256(" ".join(tokens[index:index + SHINGLE_WIDTH]).encode("utf-8")).hexdigest()
        for index in range(len(tokens) - SHINGLE_WIDTH + 1)
    }


def _comparison(left: dict, right: dict) -> dict | None:
    if left["source_sha256"] == right["source_sha256"]:
        return {
            "comparison_class": "Exact source-byte match", "method": "SHA-256 source comparison",
            "method_version": "sha256-v1", "similarity_basis_points": 10_000,
            "similarity_band": "Exact source-byte match",
            "support_summary": "The immutable source SHA-256 values are identical.",
            "difference_summary": "Custody, version, purpose, sensitivity, retention, authenticity, and applicability remain separate review questions.",
            "uncertainty_note": "An exact byte match does not establish authenticity, attribution, truth, independent collection, or common custody.",
        }
    if left["content_sha256"] == right["content_sha256"] and left["processor"] == right["processor"] and left["processor_version"] == right["processor_version"]:
        return {
            "comparison_class": "Exact derived-content match", "method": "SHA-256 derived-content comparison",
            "method_version": "sha256-v1", "similarity_basis_points": 10_000,
            "similarity_band": "Exact derived-content match",
            "support_summary": "The derived-content SHA-256 values and processor lineage are identical.",
            "difference_summary": "The original sources, custody, purpose, sensitivity, retention, and applicability remain independent.",
            "uncertainty_note": "An exact derived match does not establish source authenticity, attribution, truth, or common custody.",
        }
    left_set, right_set = _shingles(left["content_text"] or ""), _shingles(right["content_text"] or "")
    if not left_set or not right_set:
        return None
    union = left_set | right_set
    basis_points = round(len(left_set & right_set) * 10_000 / len(union))
    if basis_points < NEAR_DUPLICATE_MINIMUM_BASIS_POINTS:
        return None
    band = "Very substantial text overlap" if basis_points >= 9_000 else "Substantial text overlap" if basis_points >= 7_500 else "Potential text overlap"
    return {
        "comparison_class": "Near-duplicate text suggestion", "method": "Bounded hashed token-shingle comparison",
        "method_version": "token-shingle-jaccard-v1", "similarity_basis_points": basis_points,
        "similarity_band": band,
        "support_summary": f"{len(left_set & right_set)} bounded token shingles overlap within the authorized comparison.",
        "difference_summary": f"The review compared {len(left_set)} and {len(right_set)} bounded shingles; open both originals to review differences.",
        "uncertainty_note": "Text similarity is a review aid. It does not prove identity, authorship, custody, coordination, intent, relevance, or truth.",
    }


def register_salcapa_material_suggestions(fastapi_app, core: dict) -> None:
    db = core["db"]
    now = core["now"]
    actor = core["actor"]
    role = core["role"]
    tenant_id = core["tenant_id"]
    require = core["require"]
    require_sensitivity = core["require_sensitivity"]
    protected_member_request = core["protected_member_request"]
    require_salus_component_authority = core["require_salus_component_authority"]
    security_event = core["security_event"]
    clearance_level = core["clearance_level"]
    sensitivity_levels = core["SENSITIVITY_LEVELS"]

    conn = db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    tables = {
        "material_reference_terms", "material_suggestion_jobs", "material_suggestions",
        "material_duplicate_suggestions", "material_suggestion_events", "proposed_governed_links",
    }
    database_support.ID_TABLES.update(tables)
    if not getattr(fastapi_app.state, "salcapa_material_suggestions_backup_registered", False):
        base_collect = core["collect_tenant_records"]
        base_validate = core["validate_records"]
        base_replace = core["replace_tenant_records"]

        def collect_with_suggestions(conn, selected_tenant: int):
            records = base_collect(conn, selected_tenant)
            for table in sorted(tables):
                records[table] = [dict(row) for row in conn.execute(
                    f"SELECT * FROM {table} WHERE tenant_id=? ORDER BY id", (selected_tenant,)
                )]
            return records

        def validate_with_suggestions(records: dict, selected_tenant: int | None = None):
            errors = list(base_validate(records, selected_tenant))
            material_ids = {int(row["id"]) for row in records.get("materials", []) if row.get("id") is not None}
            derivative_ids = {int(row["id"]) for row in records.get("material_derivatives", []) if row.get("id") is not None}
            job_ids = {int(row["id"]) for row in records.get("material_suggestion_jobs", []) if row.get("id") is not None}
            suggestion_ids = {int(row["id"]) for row in records.get("material_suggestions", []) if row.get("id") is not None}
            reference_ids = {int(row["id"]) for row in records.get("material_reference_terms", []) if row.get("id") is not None}
            comparison_ids = {int(row["id"]) for row in records.get("material_duplicate_suggestions", []) if row.get("id") is not None}
            for table in tables:
                for row in records.get(table, []):
                    if selected_tenant is not None and int(row.get("tenant_id", -1)) != int(selected_tenant):
                        errors.append(f"{table} record {row.get('id')} crosses the tenant boundary")
            for row in records.get("material_reference_terms", []):
                try:
                    aliases = json.loads(row.get("aliases_json", "[]") or "[]")
                    if not isinstance(aliases, list) or not all(isinstance(item, str) for item in aliases):
                        raise ValueError
                except (TypeError, ValueError, json.JSONDecodeError):
                    errors.append(f"material reference {row.get('id')} has invalid aliases")
            for row in records.get("material_suggestion_jobs", []):
                if int(row.get("source_material_id", -1)) not in material_ids:
                    errors.append(f"material suggestion job {row.get('id')} has an invalid source")
                if int(row.get("derivative_id", -1)) not in derivative_ids:
                    errors.append(f"material suggestion job {row.get('id')} has an invalid derivative")
                if len(str(row.get("ruleset_hash", ""))) != 64:
                    errors.append(f"material suggestion job {row.get('id')} has an invalid ruleset hash")
            for row in records.get("material_suggestions", []):
                if int(row.get("job_id", -1)) not in job_ids or int(row.get("derivative_id", -1)) not in derivative_ids:
                    errors.append(f"material suggestion {row.get('id')} has invalid lineage")
                reference_id = row.get("reference_id")
                if reference_id is not None and int(reference_id) not in reference_ids:
                    errors.append(f"material suggestion {row.get('id')} has an invalid reference")
            for row in records.get("material_duplicate_suggestions", []):
                if int(row.get("job_id", -1)) not in job_ids:
                    errors.append(f"material duplicate suggestion {row.get('id')} has an invalid job")
                if int(row.get("left_derivative_id", -1)) not in derivative_ids or int(row.get("right_derivative_id", -1)) not in derivative_ids:
                    errors.append(f"material duplicate suggestion {row.get('id')} has invalid derivative lineage")
            for row in records.get("proposed_governed_links", []):
                if int(row.get("suggestion_id", -1)) not in suggestion_ids:
                    errors.append(f"proposed governed link {row.get('id')} has an invalid suggestion")
                if row.get("status") not in {"Awaiting Destination Review", "Accepted", "Rejected", "Withdrawn", "Superseded"}:
                    errors.append(f"proposed governed link {row.get('id')} has an invalid state")
            for row in records.get("material_suggestion_events", []):
                record_type = row.get("record_type")
                record_id = int(row.get("record_id", -1))
                if record_type == "Suggestion" and record_id not in suggestion_ids:
                    errors.append(f"material suggestion event {row.get('id')} has an invalid suggestion")
                elif record_type == "Comparison" and record_id not in comparison_ids:
                    errors.append(f"material suggestion event {row.get('id')} has an invalid comparison")
                elif record_type not in {"Suggestion", "Comparison"}:
                    errors.append(f"material suggestion event {row.get('id')} has an invalid record type")
            return errors

        def insert_row(conn, table: str, row: dict) -> None:
            allowed = {item["name"] for item in conn.execute(f"PRAGMA table_info({table})")}
            data = {key: value for key, value in row.items() if key in allowed}
            if data:
                conn.execute(
                    f"INSERT INTO {table}({','.join(data)}) VALUES({','.join('?' * len(data))})",
                    tuple(data.values()),
                )

        def replace_with_suggestions(conn, selected_tenant: int, records: dict):
            errors = validate_with_suggestions(records, selected_tenant)
            if errors:
                raise ValueError("; ".join(errors))
            for table in (
                "proposed_governed_links", "material_suggestion_events", "material_duplicate_suggestions",
                "material_suggestions", "material_suggestion_jobs", "material_reference_terms",
            ):
                conn.execute(f"DELETE FROM {table} WHERE tenant_id=?", (selected_tenant,))
            base_replace(conn, selected_tenant, records)
            for table in (
                "material_reference_terms", "material_suggestion_jobs", "material_suggestions",
                "material_duplicate_suggestions", "material_suggestion_events", "proposed_governed_links",
            ):
                for row in records.get(table, []):
                    insert_row(conn, table, row)
            database_support.reset_identity_sequences(conn, tables)

        core["collect_tenant_records"] = collect_with_suggestions
        core["validate_records"] = validate_with_suggestions
        core["replace_tenant_records"] = replace_with_suggestions
        fastapi_app.state.salcapa_material_suggestions_backup_registered = True

    def internal_request(request: Request, permission: str = "read") -> None:
        require(request, permission)
        if protected_member_request(request):
            raise HTTPException(403, "Source suggestions and duplicate review are restricted to authorized Salus personnel.")

    def audit(conn, request: Request, action: str, entity_type: str, entity_id: int, detail: str) -> None:
        conn.execute(
            "INSERT INTO audit_log(ts,user_name,action,entity_type,entity_id,detail,tenant_id) VALUES(?,?,?,?,?,?,?)",
            (now(), actor(request), action, entity_type, entity_id, detail[:2000], tenant_id(request)),
        )

    def visible_sensitivity(request: Request, sensitivity: str) -> bool:
        return sensitivity_levels.get(sensitivity or "Standard", 1) <= clearance_level(request)

    def max_sensitivity(*values: str) -> str:
        return max(values, key=lambda value: sensitivity_levels.get(value or "Standard", 1))

    def derivative_for_request(conn, derivative_id: int, request: Request):
        row = conn.execute(
            "SELECT d.*,m.sensitivity,m.disposition_status,m.title source_title,m.original_name "
            "FROM material_derivatives d JOIN materials m ON m.id=d.source_material_id WHERE d.id=?",
            (derivative_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Derived material not found")
        if int(row["tenant_id"]) != tenant_id(request):
            security_event(request, "MATERIAL_SUGGESTION_TENANT_BOUNDARY_VIOLATION", "High", f"derivative_id={derivative_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        return row

    def public_suggestion(row) -> dict:
        result = dict(row)
        result["alternatives"] = json.loads(result.pop("alternatives_json", "[]") or "[]")
        result["authority_note"] = (
            "This is a source-review aid. It does not establish identity, location, source truth, intelligence, a finding, a relationship, disclosure authority, or operational authority."
        )
        return result

    def public_comparison(row) -> dict:
        result = dict(row)
        result["authority_note"] = (
            "Similarity supports comparison only. It does not prove identity, authorship, custody, coordination, intent, relevance, or truth."
        )
        return result

    @fastapi_app.post("/api/material-suggestions/references")
    def add_reference(payload: ReferenceIn, request: Request):
        internal_request(request, "decide")
        require_salus_component_authority(request, "SalCAPA governed source references")
        require_sensitivity(request, payload.sensitivity)
        created = now()
        key = "MRF-" + uuid.uuid4().hex
        aliases = [item for item in payload.aliases if _normalized(item) != _normalized(payload.display_name)]
        conn = db()
        conn.execute(
            "INSERT INTO material_reference_terms(tenant_id,reference_key,reference_type,display_name,aliases_json,target_type,target_id,sensitivity,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), key, payload.reference_type, payload.display_name, json.dumps(aliases), payload.target_type, payload.target_id, payload.sensitivity, "Active", actor(request), created, created),
        )
        row = conn.execute("SELECT * FROM material_reference_terms WHERE reference_key=?", (key,)).fetchone()
        audit(conn, request, "MATERIAL_REFERENCE_REGISTERED", "material_reference", int(row["id"]), f"type={payload.reference_type}; target_type={payload.target_type}; target_id={payload.target_id}")
        conn.commit()
        result = dict(row)
        result["aliases"] = json.loads(result.pop("aliases_json"))
        conn.close()
        return result

    @fastapi_app.get("/api/material-suggestions/references")
    def list_references(request: Request):
        internal_request(request)
        conn = db()
        rows = conn.execute("SELECT * FROM material_reference_terms WHERE tenant_id=? AND status='Active' ORDER BY reference_type,display_name,id", (tenant_id(request),))
        results = []
        for row in rows:
            if visible_sensitivity(request, row["sensitivity"]):
                item = dict(row)
                item["aliases"] = json.loads(item.pop("aliases_json"))
                results.append(item)
        conn.close()
        return {"items": results, "scope_note": "Only active references authorized for this tenant and sensitivity clearance are shown."}

    @fastapi_app.post("/api/material-processing/derivatives/{derivative_id}/review-suggestions")
    def prepare_suggestions(derivative_id: int, payload: AnalyzeIn, request: Request):
        internal_request(request, "write")
        require_salus_component_authority(request, "SalCAPA source suggestion review")
        conn = db()
        derivative = derivative_for_request(conn, derivative_id, request)
        if derivative["disposition_status"] != "Active":
            conn.close()
            raise HTTPException(409, "Disposed source material cannot be analyzed")
        if derivative["review_status"] != "Human Reviewed":
            conn.close()
            raise HTTPException(409, "The derived representation must receive independent human review before suggestions are prepared")
        existing = conn.execute(
            "SELECT * FROM material_suggestion_jobs WHERE tenant_id=? AND derivative_id=? AND ruleset_hash=? AND status='Completed' ORDER BY id DESC LIMIT 1",
            (tenant_id(request), derivative_id, RULESET_HASH),
        ).fetchone()
        if existing:
            suggestions = [public_suggestion(row) for row in conn.execute("SELECT * FROM material_suggestions WHERE job_id=? ORDER BY id", (int(existing["id"]),))]
            comparisons = [public_comparison(row) for row in conn.execute("SELECT * FROM material_duplicate_suggestions WHERE job_id=? ORDER BY id", (int(existing["id"]),))]
            conn.close()
            return {"job": dict(existing), "suggestions": suggestions, "comparisons": comparisons, "idempotent_reuse": True}

        started = now()
        job_key = "MSJ-" + uuid.uuid4().hex
        conn.execute(
            "INSERT INTO material_suggestion_jobs(tenant_id,job_key,source_material_id,derivative_id,status,purpose,processor,processor_version,ruleset_hash,requested_by,requested_by_role,started_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), job_key, int(derivative["source_material_id"]), derivative_id, "Processing", payload.reason, PROCESSOR, PROCESSOR_VERSION, RULESET_HASH, actor(request), role(request), started, started, started),
        )
        job = conn.execute("SELECT * FROM material_suggestion_jobs WHERE job_key=?", (job_key,)).fetchone()
        audit(conn, request, "MATERIAL_SUGGESTION_REVIEW_STARTED", "material_suggestion_job", int(job["id"]), f"derivative_id={derivative_id}; ruleset_hash={RULESET_HASH}")
        conn.commit()
        try:
            text = (derivative["content_text"] or "")[:MAX_DERIVATIVE_CHARACTERS]
            references = [dict(row) for row in conn.execute(
                "SELECT * FROM material_reference_terms WHERE tenant_id=? AND status='Active' ORDER BY id LIMIT ?",
                (tenant_id(request), MAX_REFERENCES),
            ) if visible_sensitivity(request, row["sensitivity"])]
            candidates = _reference_candidates(text, references) + _date_time_candidates(text)
            candidates.sort(key=lambda item: (item["start_offset"], item["end_offset"], item["suggestion_type"], item["proposed_value"]))
            created = now()
            for item in candidates:
                reference_id = item.get("reference_id")
                reference = next((ref for ref in references if int(ref["id"]) == int(reference_id)), None) if reference_id else None
                sensitivity = max_sensitivity(derivative["sensitivity"], reference["sensitivity"] if reference else derivative["sensitivity"])
                conn.execute(
                    "INSERT INTO material_suggestions(tenant_id,suggestion_key,job_id,source_material_id,derivative_id,suggestion_type,suggestion_subtype,source_text,context_text,start_offset,end_offset,proposed_value,alternatives_json,reference_id,method,rule_id,confidence_status,uncertainty_note,sensitivity,review_status,current_value,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tenant_id(request), "MSG-" + uuid.uuid4().hex, int(job["id"]), int(derivative["source_material_id"]), derivative_id, item["suggestion_type"], item["suggestion_subtype"], item["source_text"], item["context_text"], item["start_offset"], item["end_offset"], item["proposed_value"], json.dumps(item["alternatives"]), reference_id, item["method"], item["rule_id"], "Derived — Unverified", item["uncertainty_note"], sensitivity, "Awaiting Human Review", item["proposed_value"], created, created),
                )
            others = [dict(row) for row in conn.execute(
                "SELECT d.*,m.sensitivity,m.title source_title FROM material_derivatives d JOIN materials m ON m.id=d.source_material_id WHERE d.tenant_id=? AND d.id<>? AND d.review_status='Human Reviewed' ORDER BY d.id DESC LIMIT ?",
                (tenant_id(request), derivative_id, MAX_COMPARISON_CANDIDATES),
            ) if visible_sensitivity(request, row["sensitivity"])]
            comparison_count = 0
            left = dict(derivative)
            for other in others:
                result = _comparison(left, other)
                if not result:
                    continue
                left_id, right_id = sorted((derivative_id, int(other["id"])))
                sensitivity = max_sensitivity(derivative["sensitivity"], other["sensitivity"])
                key_material = f"{tenant_id(request)}:{left_id}:{right_id}:{result['method']}:{result['method_version']}"
                comparison_key = "MDC-" + hashlib.sha256(key_material.encode("utf-8")).hexdigest()
                existing_comparison = conn.execute("SELECT id FROM material_duplicate_suggestions WHERE comparison_key=?", (comparison_key,)).fetchone()
                if existing_comparison:
                    continue
                conn.execute(
                    "INSERT INTO material_duplicate_suggestions(tenant_id,comparison_key,job_id,left_derivative_id,right_derivative_id,comparison_class,method,method_version,similarity_basis_points,similarity_band,support_summary,difference_summary,sensitivity,confidence_status,uncertainty_note,review_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tenant_id(request), comparison_key, int(job["id"]), left_id, right_id, result["comparison_class"], result["method"], result["method_version"], result["similarity_basis_points"], result["similarity_band"], result["support_summary"], result["difference_summary"], sensitivity, "Derived — Unverified", result["uncertainty_note"], "Awaiting Human Review", created, created),
                )
                comparison_count += 1
            conn.execute(
                "UPDATE material_suggestion_jobs SET status='Completed',candidate_count=?,comparison_count=?,completed_at=?,updated_at=? WHERE id=?",
                (len(candidates), comparison_count, created, created, int(job["id"])),
            )
            audit(conn, request, "MATERIAL_SUGGESTIONS_PREPARED", "material_suggestion_job", int(job["id"]), f"suggestions={len(candidates)}; comparisons={comparison_count}; no_authoritative_link=true")
            conn.commit()
            complete = conn.execute("SELECT * FROM material_suggestion_jobs WHERE id=?", (int(job["id"]),)).fetchone()
            suggestions = [public_suggestion(row) for row in conn.execute("SELECT * FROM material_suggestions WHERE job_id=? ORDER BY id", (int(job["id"]),))]
            comparisons = [public_comparison(row) for row in conn.execute("SELECT * FROM material_duplicate_suggestions WHERE job_id=? ORDER BY id", (int(job["id"]),))]
            conn.close()
            return {"job": dict(complete), "suggestions": suggestions, "comparisons": comparisons, "idempotent_reuse": False}
        except Exception as exc:
            failed = now()
            try:
                conn.rollback()
                conn.execute(
                    "UPDATE material_suggestion_jobs SET status='Failed',failure_code='SUGGESTION_PROCESSING_FAILED',failure_detail=?,completed_at=?,updated_at=? WHERE id=?",
                    ("Suggestions could not be prepared. The source and derivative remain unchanged for manual review.", failed, failed, int(job["id"])),
                )
                audit(conn, request, "MATERIAL_SUGGESTION_REVIEW_FAILED", "material_suggestion_job", int(job["id"]), f"failure_type={type(exc).__name__}")
                conn.commit()
            finally:
                conn.close()
            raise HTTPException(422, "Suggestions could not be prepared. The source and derivative remain unchanged for manual review.") from exc

    @fastapi_app.get("/api/material-suggestions/triage")
    def suggestion_triage(request: Request, limit: int = 200):
        internal_request(request)
        conn = db()
        suggestions = [public_suggestion(row) for row in conn.execute(
            "SELECT s.*,m.title source_title,m.original_name FROM material_suggestions s JOIN materials m ON m.id=s.source_material_id WHERE s.tenant_id=? ORDER BY CASE s.review_status WHEN 'Awaiting Human Review' THEN 0 ELSE 1 END,s.id DESC LIMIT ?",
            (tenant_id(request), max(1, min(limit, 500))),
        ) if visible_sensitivity(request, row["sensitivity"])]
        comparisons = [public_comparison(row) for row in conn.execute(
            "SELECT c.*,lm.title left_title,rm.title right_title FROM material_duplicate_suggestions c JOIN material_derivatives ld ON ld.id=c.left_derivative_id JOIN materials lm ON lm.id=ld.source_material_id JOIN material_derivatives rd ON rd.id=c.right_derivative_id JOIN materials rm ON rm.id=rd.source_material_id WHERE c.tenant_id=? ORDER BY CASE c.review_status WHEN 'Awaiting Human Review' THEN 0 ELSE 1 END,c.id DESC LIMIT ?",
            (tenant_id(request), max(1, min(limit, 500))),
        ) if visible_sensitivity(request, row["sensitivity"])]
        conn.close()
        return {
            "suggestions": suggestions, "comparisons": comparisons,
            "guidance": "Review proposed names, dates, places, and source similarities. These are source-review aids, not verified facts or authoritative relationships.",
        }

    def review_record(record_type: str, record_id: int, payload: ReviewIn, request: Request):
        internal_request(request, "decide")
        require_salus_component_authority(request, "SalCAPA source suggestion review")
        table = "material_suggestions" if record_type == "Suggestion" else "material_duplicate_suggestions"
        conn = db()
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, f"{record_type} not found")
        if int(row["tenant_id"]) != tenant_id(request):
            conn.close()
            security_event(request, "MATERIAL_SUGGESTION_REVIEW_BOUNDARY_VIOLATION", "High", f"record_type={record_type}; record_id={record_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, row["sensitivity"])
        if row["review_status"] != "Awaiting Human Review":
            conn.close()
            raise HTTPException(409, "This review aid already has a recorded review state")
        job = conn.execute("SELECT requested_by FROM material_suggestion_jobs WHERE id=?", (int(row["job_id"]),)).fetchone()
        if job and job["requested_by"] == actor(request):
            conn.close()
            raise HTTPException(409, "A different authorized person must review this source-review aid")
        if payload.status == "Corrected" and not payload.corrected_value:
            conn.close()
            raise HTTPException(422, "A corrected value is required when recording a correction")
        if payload.status != "Corrected" and payload.corrected_value:
            conn.close()
            raise HTTPException(422, "A corrected value is allowed only for a correction")
        reviewed = now()
        fields = "review_status=?,reviewed_by=?,reviewed_by_role=?,reviewed_at=?,updated_at=?"
        values: list = [payload.status, actor(request), role(request), reviewed, reviewed]
        if record_type == "Suggestion" and payload.status == "Corrected":
            fields += ",current_value=?"
            values.append(payload.corrected_value)
        values.append(record_id)
        conn.execute(f"UPDATE {table} SET {fields} WHERE id=?", tuple(values))
        conn.execute(
            "INSERT INTO material_suggestion_events(tenant_id,record_type,record_id,event_type,from_status,to_status,reason,corrected_value,changed_by,changed_by_role,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), record_type, record_id, "HUMAN_REVIEW_RECORDED", "Awaiting Human Review", payload.status, payload.reason, payload.corrected_value, actor(request), role(request), reviewed),
        )
        audit(conn, request, "MATERIAL_SOURCE_AID_REVIEWED", record_type.casefold(), record_id, f"status={payload.status}; does_not_establish_authority=true")
        conn.commit()
        updated = conn.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
        conn.close()
        return public_suggestion(updated) if record_type == "Suggestion" else public_comparison(updated)

    @fastapi_app.post("/api/material-suggestions/{suggestion_id}/review")
    def review_suggestion(suggestion_id: int, payload: ReviewIn, request: Request):
        return review_record("Suggestion", suggestion_id, payload, request)

    @fastapi_app.post("/api/material-suggestions/comparisons/{comparison_id}/review")
    def review_duplicate_suggestion(comparison_id: int, payload: ReviewIn, request: Request):
        if payload.status == "Corrected":
            raise HTTPException(422, "Duplicate comparisons may be reviewed or rejected; prepare a new comparison to change its technical result")
        return review_record("Comparison", comparison_id, payload, request)

    @fastapi_app.post("/api/material-suggestions/{suggestion_id}/governed-link-proposals")
    def propose_governed_link(suggestion_id: int, payload: LinkProposalIn, request: Request):
        internal_request(request, "decide")
        require_salus_component_authority(request, "SalCAPA governed link proposal")
        if payload.destination_product not in DESTINATION_PRODUCTS:
            raise HTTPException(422, "Unsupported destination product")
        conn = db()
        suggestion = conn.execute("SELECT * FROM material_suggestions WHERE id=?", (suggestion_id,)).fetchone()
        if not suggestion:
            conn.close()
            raise HTTPException(404, "Suggestion not found")
        if int(suggestion["tenant_id"]) != tenant_id(request):
            conn.close()
            security_event(request, "MATERIAL_LINK_PROPOSAL_BOUNDARY_VIOLATION", "High", f"suggestion_id={suggestion_id}")
            raise HTTPException(403, "Tenant boundary violation")
        require_sensitivity(request, suggestion["sensitivity"])
        if suggestion["review_status"] not in {"Human Reviewed", "Corrected"}:
            conn.close()
            raise HTTPException(409, "A source suggestion must receive human review before a governed link can be proposed")
        created = now()
        proposal_key = "MGL-" + uuid.uuid4().hex
        conn.execute(
            "INSERT INTO proposed_governed_links(tenant_id,proposal_key,suggestion_id,destination_product,destination_type,destination_id,purpose,status,sensitivity,proposed_by,proposed_by_role,proposed_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tenant_id(request), proposal_key, suggestion_id, payload.destination_product, payload.destination_type, payload.destination_id, payload.purpose, "Awaiting Destination Review", suggestion["sensitivity"], actor(request), role(request), created, created),
        )
        row = conn.execute("SELECT * FROM proposed_governed_links WHERE proposal_key=?", (proposal_key,)).fetchone()
        audit(conn, request, "GOVERNED_LINK_PROPOSED", "proposed_governed_link", int(row["id"]), f"destination={payload.destination_product}; destination_type={payload.destination_type}; destination_id={payload.destination_id}; no_destination_acceptance=true")
        conn.commit()
        result = dict(row)
        result["authority_note"] = "This proposal awaits the destination authority. It has not created or changed an authoritative relationship."
        conn.close()
        return result
