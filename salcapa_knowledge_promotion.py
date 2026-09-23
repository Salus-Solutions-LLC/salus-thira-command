"""Governed promotion from OneDrive pending classification to SharePoint knowledge."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from azure.identity import ManagedIdentityCredential
from pydantic import BaseModel, ConfigDict, Field, field_validator

import salcapa_audio_video_processing as full_processing
import salcapa_material_processing as material_processing

from salcapa_m365_intake import (
    ASSERTION_SCOPE,
    ASSERTION_TYPE,
    GRAPH_ROOT,
    GovernedM365Config,
    GovernedM365Intake,
    M365IntakeError,
)

PENDING_PREFIX = "10 Pending Classification/"
DECISIONS = {"Approved", "Deferred", "Duplicate", "Unsupported", "Sensitive", "Excluded"}
TARGETS = {
    "01 Salus Doctrine and Methodologies",
    "02 Service Capabilities",
    "03 Assessment Standards and Templates",
    "04 Approved Examples",
    "05 Research and Reference",
    "06 Policies and SOPs",
    "07 Training and Exercises",
    "08 Visual Media",
    "09 Historical Material",
    "99 Superseded and Retained",
}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")
_AUTO_ACTOR = "SalCAPA Policy Engine"
_EXCEPTION_MARKERS = {
    "attorney-client", "confidential", "draft", "employee", "export controlled",
    "legal hold", "medical record", "patient", "personnel", "privileged",
    "protected member", "restricted", "ssn",
}
_AUTO_TARGET_RULES = (
    ("06 Policies and SOPs", ("policy", "procedure", "sop")),
    ("01 Salus Doctrine and Methodologies", ("doctrine", "methodology")),
    ("03 Assessment Standards and Templates", ("checklist", "standard", "template")),
    ("07 Training and Exercises", ("exercise", "training")),
    ("08 Visual Media", ("image", "photo", "video")),
    ("09 Historical Material", ("archive", "historical")),
    ("04 Approved Examples", ("example", "sample")),
    ("02 Service Capabilities", ("capability", "service")),
    (
        "05 Research and Reference",
        ("analysis", "assessment", "intelligence", "reference", "report", "research", "strategic"),
    ),
)
_AUTO_PRODUCTS = {
    "01 Salus Doctrine and Methodologies": ["SalCAPA", "SalINTEL", "SalTHIRA", "SalOPS"],
    "02 Service Capabilities": ["SalCAPA", "SalOPS"],
    "03 Assessment Standards and Templates": ["SalCAPA", "SalINTEL", "SalTHIRA"],
    "04 Approved Examples": ["SalCAPA", "SalINTEL", "SalTHIRA", "SalOPS"],
    "05 Research and Reference": ["SalCAPA", "SalINTEL", "SalTHIRA"],
    "06 Policies and SOPs": ["SalCAPA", "SalOPS"],
    "07 Training and Exercises": ["SalCAPA", "SalOPS"],
    "08 Visual Media": ["SalCAPA", "SalINTEL", "SalTHIRA", "SalOPS"],
    "09 Historical Material": ["SalCAPA"],
}


def _extract_all_accessible_content(document) -> dict[str, Any]:
    """Extract every safely accessible component without blocking source ingestion."""
    content_type = str(
        getattr(document, "mime_type", "")
        or getattr(document, "content_type", "")
        or "application/octet-stream"
    )
    try:
        text, method, truncated, processor, processor_version = full_processing._decode_media(
            document.content, document.name, content_type
        )
        return {
            "status": "Complete",
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "method": method,
            "processor": processor,
            "processor_version": processor_version,
            "truncated": bool(truncated),
        }
    except material_processing.ProcessingFailure as exc:
        # The exact original is still promoted and retained. An inaccessible,
        # encrypted, damaged, capacity-limited, or not-yet-supported component
        # becomes an automatic retry obligation rather than an exception queue.
        return {
            "status": "Automatic Retry Required",
            "text": "",
            "text_sha256": hashlib.sha256(b"").hexdigest(),
            "method": "Exact original retained; automatic extraction retry required",
            "processor": "SalCAPA Full Knowledge Processor",
            "processor_version": "2.0.0",
            "truncated": False,
            "failure_code": str(exc.code)[:120],
            "failure_detail": str(exc.public_detail)[:1000],
        }


def _citation_metadata(document, extraction: dict[str, Any]) -> dict[str, Any]:
    """Create structured, hash-bound metadata suitable for later citations."""
    text = str(extraction.get("text", ""))
    source_properties: dict[str, str] = {}
    for field in (
        "title", "subject", "creator", "keywords", "description", "category",
        "created", "modified", "lastModifiedBy",
    ):
        match = re.search(rf"(?m)^{re.escape(field)}:\s*(.+?)\s*$", text)
        if match:
            source_properties[field] = match.group(1)[:1000]
    extension = os.path.splitext(document.name)[1].lower()
    locator_scheme = {
        ".pdf": "page",
        ".pptx": "slide and speaker-note section",
        ".xlsx": "worksheet and cell",
        ".docx": "document part, heading, paragraph, footnote, endnote, comment, header, and footer",
        ".csv": "row and column",
        ".tsv": "row and column",
    }.get(extension, "content section")
    author_values = []
    for value in (
        source_properties.get("creator", ""),
        str(getattr(document, "source_owner", "") or ""),
    ):
        if value and value not in author_values:
            author_values.append(value)
    source_sha256 = str(
        getattr(document, "sha256", "")
        or hashlib.sha256(document.content).hexdigest()
    )
    return {
        "citation_key": f"sha256:{source_sha256}",
        "document_title": source_properties.get("title", "") or os.path.splitext(document.name)[0],
        "authors": author_values,
        "source_created_at": source_properties.get("created", ""),
        "source_modified_at": source_properties.get("modified", "")
        or str(getattr(document, "last_modified", "") or ""),
        "source_last_modified_by": source_properties.get("lastModifiedBy", "")
        or str(getattr(document, "last_modified_by", "") or ""),
        "source_owner": str(getattr(document, "source_owner", "") or ""),
        "source_owner_id": str(getattr(document, "source_owner_id", "") or ""),
        "source_item_id": str(getattr(document, "item_id", "") or ""),
        "source_relative_path": str(getattr(document, "relative_path", "") or ""),
        "source_web_url": str(getattr(document, "web_url", "") or ""),
        "source_etag": str(getattr(document, "etag", "") or ""),
        "source_ctag": str(getattr(document, "ctag", "") or ""),
        "source_sha256": source_sha256,
        "source_mime_type": str(
            getattr(document, "mime_type", "")
            or getattr(document, "content_type", "")
            or "application/octet-stream"
        ),
        "locator_scheme": locator_scheme,
        "source_properties": source_properties,
        "metadata_verification": "Source-stored metadata retained as provenance; authorship is not independently verified by ingestion.",
    }


def refresh_archived_extraction(
    classification: dict[str, Any], document, expected_sha256: str
) -> tuple[dict[str, Any], str]:
    """Retry derived extraction without changing the original citation identity."""
    if document.sha256 != expected_sha256:
        return classification, "archived_source_hash_mismatch"
    refreshed = _extract_all_accessible_content(document)
    if refreshed["status"] != "Complete":
        return classification, "extraction_retry_required"
    updated = dict(classification)
    updated["extraction"] = refreshed
    updated["processing_flags"] = [
        flag for flag in classification.get("processing_flags", [])
        if flag != "Automatic Extraction Retry Required"
    ]
    return updated, ""


def automatic_classification(document, *, duplicate: bool) -> tuple[dict[str, Any], str]:
    """Classify every source automatically; conditions become metadata flags."""
    extraction = _extract_all_accessible_content(document)
    normalized = re.sub(r"[^a-z0-9]+", " ", document.name.lower()).strip()
    inspectable_text = extraction["text"].lower()
    if not inspectable_text:
        inspectable_text = document.content[:2_000_000].decode("utf-8", errors="ignore").lower()
    inspection_scope = normalized + " " + inspectable_text
    markers = [value for value in sorted(_EXCEPTION_MARKERS) if value in inspection_scope]
    filename_matches = [
        target
        for target, keywords in _AUTO_TARGET_RULES
        if any(keyword in normalized for keyword in keywords)
    ]
    content_matches = [
        target
        for target, keywords in _AUTO_TARGET_RULES
        if any(keyword in inspectable_text for keyword in keywords)
    ]
    matches = filename_matches or content_matches
    target = matches[0] if len(matches) == 1 else "05 Research and Reference"
    flags = []
    if duplicate:
        flags.append("Duplicate")
    if markers:
        flags.extend(["Sensitive", *[f"Sensitivity Marker: {value}" for value in markers]])
    if len(matches) > 1:
        flags.append("Multiple Classification Signals")
    if not matches:
        flags.append("Default Research Classification")
    if extraction["status"] != "Complete":
        flags.append("Automatic Extraction Retry Required")
    if extraction.get("truncated"):
        flags.append("Derived Text Truncated; Original Retained")
    return {
        "decision": "Approved",
        "target_folder": target,
        "knowledge_domain": "Enterprise Reference",
        "document_type": "Reference Material",
        "sensitivity": "Salus Internal",
        "rationale": (
            "Automatically processed under the approved no-exception knowledge-ingestion policy."
        ),
        "permit_products": _AUTO_PRODUCTS[target],
        "processing_flags": list(dict.fromkeys(flags)),
        "extraction": extraction,
        "citation_metadata": _citation_metadata(document, extraction),
        "automation": {
            "policy": "automatic-full-processing-v2",
            "classification_confidence": "high" if len(matches) == 1 else "bounded-default",
            "human_ingestion_approval_required": False,
            "exception_queue": False,
        },
    }, ""


class KnowledgePromotionError(RuntimeError):
    """Fail-closed error safe for internal workflow handling."""


@dataclass(frozen=True)
class KnowledgeDestinationConfig:
    drive_id: str
    root_folder_item_id: str
    processed_folder_item_id: str

    @classmethod
    def from_environment(cls) -> "KnowledgeDestinationConfig":
        return cls(
            drive_id=os.getenv("SALUS_M365_KNOWLEDGE_DRIVE_ID", "").strip(),
            root_folder_item_id=os.getenv("SALUS_M365_KNOWLEDGE_FOLDER_ITEM_ID", "").strip(),
            processed_folder_item_id=os.getenv(
                "SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID", ""
            ).strip(),
        )

    def validate(self) -> None:
        if (
            not _IDENTIFIER.fullmatch(self.drive_id)
            or not _IDENTIFIER.fullmatch(self.root_folder_item_id)
            or not _IDENTIFIER.fullmatch(self.processed_folder_item_id)
        ):
            raise KnowledgePromotionError("Knowledge destination or processed archive is incomplete or invalid")


class ClassificationCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    target_folder: str = ""
    knowledge_domain: str = Field(default="", max_length=120)
    document_type: str = Field(default="", max_length=120)
    sensitivity: str = Field(default="Salus Internal", max_length=80)
    rationale: str = Field(min_length=10, max_length=2000)
    permit_products: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, value: str) -> str:
        if value not in DECISIONS:
            raise ValueError("unsupported classification decision")
        return value

    @field_validator("target_folder")
    @classmethod
    def valid_target(cls, value: str) -> str:
        if value and value not in TARGETS:
            raise ValueError("unsupported knowledge destination")
        return value

    @field_validator("permit_products")
    @classmethod
    def valid_products(cls, values: list[str]) -> list[str]:
        allowed = {"ChatGPT", "SalCAPA", "SalINTEL", "SalTHIRA", "SalOPS"}
        if any(value not in allowed for value in values):
            raise ValueError("unsupported permitted product")
        return list(dict.fromkeys(values))


class GraphKnowledgeWriter:
    def __init__(self, intake_config, destination, *, credential=None, client=None):
        destination.validate()
        self.intake_config = intake_config
        self.destination = destination
        self.credential = credential or ManagedIdentityCredential(
            client_id=intake_config.managed_identity_client_id
        )
        self.client = client or httpx.Client(timeout=30.0, follow_redirects=False)
        self._token: tuple[str, int] | None = None

    def _headers(self) -> dict[str, str]:
        now = int(time.time())
        if not self._token or self._token[1] <= now + 60:
            assertion = self.credential.get_token(ASSERTION_SCOPE)
            response = self.client.post(
                f"https://login.microsoftonline.com/{self.intake_config.tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": self.intake_config.application_client_id,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                    "client_assertion_type": ASSERTION_TYPE,
                    "client_assertion": str(assertion.token),
                },
            )
            if response.status_code != 200 or not response.json().get("access_token"):
                raise KnowledgePromotionError("Microsoft 365 token exchange was rejected")
            self._token = (
                str(response.json()["access_token"]),
                now + min(int(response.json().get("expires_in", 300)), 3600),
            )
        return {"Authorization": f"Bearer {self._token[0]}"}

    def _resolve_folder(self, folder_name: str) -> str:
        response = self.client.get(
            f"{GRAPH_ROOT}/drives/{self.destination.drive_id}/items/"
            f"{self.destination.root_folder_item_id}/children",
            headers=self._headers() | {"Accept": "application/json"},
            params={"$select": "id,name,folder", "$top": "200"},
        )
        if response.status_code != 200:
            raise KnowledgePromotionError("Knowledge destination could not be read")
        matches = [
            row for row in response.json().get("value", [])
            if row.get("name") == folder_name and isinstance(row.get("folder"), dict)
        ]
        if len(matches) != 1 or not _IDENTIFIER.fullmatch(str(matches[0].get("id", ""))):
            raise KnowledgePromotionError("Approved knowledge folder was not uniquely resolved")
        return str(matches[0]["id"])

    def put_verified(self, folder_name: str, name: str, content: bytes, sha256: str) -> dict[str, Any]:
        # Keep the visible source title in candidate metadata while giving distinct
        # same-title documents separate destination paths.
        stem, separator, extension = name.rpartition(".")
        if not stem:
            stem, separator, extension = name, "", ""
        suffix = f".{sha256[:24]}" + (f".{extension}" if separator else "")
        unique_name = stem[:max(1, 240 - len(suffix))] + suffix
        return self._put_verified_once(folder_name, unique_name, content, sha256, office_fallback=True)

    def _put_verified_once(
        self, folder_name: str, name: str, content: bytes, sha256: str, *, office_fallback: bool
    ) -> dict[str, Any]:
        folder_id = self._resolve_folder(folder_name)
        safe_name = quote(name, safe="")
        response = self.client.put(
            f"{GRAPH_ROOT}/drives/{self.destination.drive_id}/items/{folder_id}:/{safe_name}:/content",
            headers=self._headers() | {"Content-Type": "application/octet-stream"},
            content=content,
        )
        if response.status_code not in {200, 201}:
            raise KnowledgePromotionError("Approved knowledge file could not be written")
        item = response.json()
        item_id = str(item.get("id", ""))
        if not _IDENTIFIER.fullmatch(item_id):
            raise KnowledgePromotionError("Knowledge destination identity was incomplete")
        verify = self.client.get(
            f"{GRAPH_ROOT}/drives/{self.destination.drive_id}/items/{item_id}/content",
            headers=self._headers() | {"Accept": "application/octet-stream"},
        )
        if verify.status_code in {302, 303, 307, 308}:
            location = str(verify.headers.get("Location", ""))
            parsed_location = urlparse(location)
            if (
                parsed_location.scheme != "https"
                or parsed_location.username is not None
                or parsed_location.password is not None
                or not (parsed_location.hostname or "").lower().endswith(".sharepoint.com")
            ):
                raise KnowledgePromotionError(
                    "Knowledge destination returned an untrusted verification location"
                )
            verify = self.client.get(
                location, headers={"Accept": "application/octet-stream"}
            )
        if verify.status_code != 200:
            raise KnowledgePromotionError("Knowledge destination verification failed")
        if hashlib.sha256(verify.content).hexdigest() != sha256:
            # SharePoint can rewrite Office package metadata after upload. Keep a
            # byte-exact, hash-bound original under an opaque extension while
            # leaving the Office rendering available for ordinary reading.
            if office_fallback and name.lower().endswith((".docx", ".xlsx", ".pptx")):
                original_name = f"{name}.{sha256[:16]}.original.bin"
                return self._put_verified_once(
                    folder_name, original_name, content, sha256, office_fallback=False
                )
            raise KnowledgePromotionError("Knowledge destination verification failed")
        web_url = str(item.get("webUrl", ""))
        parsed = urlparse(web_url)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".sharepoint.com"):
            raise KnowledgePromotionError("Knowledge destination returned an untrusted location")
        return {"item_id": item_id, "web_url": web_url, "etag": str(item.get("eTag", ""))[:512]}

    def archive_verified_source(
        self, item_id: str, etag: str, name: str, sha256: str
    ) -> dict[str, str]:
        url = f"{GRAPH_ROOT}/drives/{self.intake_config.drive_id}/items/{item_id}"
        headers = self._headers() | {
            "If-Match": etag,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {"parentReference": {"id": self.destination.processed_folder_item_id}}
        response = self.client.patch(url, headers=headers, json=body)
        archive_name = name
        if response.status_code == 409:
            # A sibling already has this name. Rename this same source item as
            # part of the move; never replace or delete the existing sibling.
            stem, separator, extension = name.rpartition(".")
            if not stem:
                stem, separator, extension = name, "", ""
            suffix = (
                f".{sha256[:16]}-{hashlib.sha256(item_id.encode()).hexdigest()[:12]}"
                + (f".{extension}" if separator else "")
            )
            archive_name = stem[:max(1, 240 - len(suffix))] + suffix
            response = self.client.patch(
                url, headers=headers, json=body | {"name": archive_name}
            )
        if response.status_code != 200:
            raise KnowledgePromotionError(
                f"Verified intake source could not be archived (HTTP {response.status_code}); source remains pending"
            )
        item = response.json()
        parent_id = str((item.get("parentReference") or {}).get("id", ""))
        if str(item.get("id", "")) != item_id or parent_id != self.destination.processed_folder_item_id:
            raise KnowledgePromotionError("Processed intake archive could not be verified")
        if archive_name != name and str(item.get("name", "")) != archive_name:
            raise KnowledgePromotionError("Processed intake archive rename could not be verified")
        web_url = str(item.get("webUrl", ""))
        parsed = urlparse(web_url)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".sharepoint.com"):
            raise KnowledgePromotionError("Processed intake archive returned an untrusted location")
        return {"item_id": item_id, "web_url": web_url, "etag": str(item.get("eTag", ""))[:512]}

_POSTGRES_SCHEMA_LOCK = threading.Lock()
_POSTGRES_SCHEMA_READY = False


def _init_tables(conn) -> None:
    global _POSTGRES_SCHEMA_READY
    if getattr(conn, "backend", "sqlite") == "postgres":
        with _POSTGRES_SCHEMA_LOCK:
            if _POSTGRES_SCHEMA_READY:
                return
            _create_tables(conn)
            conn.commit()
            _POSTGRES_SCHEMA_READY = True
        return
    _create_tables(conn)


def _create_tables(conn) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS m365_knowledge_candidates (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source_drive_id TEXT NOT NULL, source_item_id TEXT NOT NULL,
      source_name TEXT NOT NULL, source_relative_path TEXT NOT NULL,
      source_etag TEXT NOT NULL, source_sha256 TEXT NOT NULL,
      source_size INTEGER NOT NULL, source_modified_at TEXT NOT NULL,
      source_owner TEXT NOT NULL DEFAULT '', discovered_at TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'Pending Review',
      decision TEXT NOT NULL DEFAULT '', target_folder TEXT NOT NULL DEFAULT '',
      classification_json TEXT NOT NULL DEFAULT '{}', reviewed_by TEXT NOT NULL DEFAULT '',
      reviewed_at TEXT NOT NULL DEFAULT '', review_rationale TEXT NOT NULL DEFAULT '',
      destination_drive_id TEXT NOT NULL DEFAULT '', destination_item_id TEXT NOT NULL DEFAULT '',
      destination_web_url TEXT NOT NULL DEFAULT '', destination_etag TEXT NOT NULL DEFAULT '',
      promoted_at TEXT NOT NULL DEFAULT '', source_removed_at TEXT NOT NULL DEFAULT '',
      source_archived_at TEXT NOT NULL DEFAULT '', source_archive_item_id TEXT NOT NULL DEFAULT '',
      source_archive_web_url TEXT NOT NULL DEFAULT '', source_archive_etag TEXT NOT NULL DEFAULT '',
      UNIQUE(source_drive_id, source_item_id, source_etag)
    );
    DROP INDEX IF EXISTS idx_m365_knowledge_sha_destination;
    CREATE INDEX IF NOT EXISTS idx_m365_knowledge_sha_destination_lookup
      ON m365_knowledge_candidates(source_sha256, target_folder)
      WHERE status IN ('Promoted','Source Retained','Source Removed','Ingested and Verified');
    CREATE TABLE IF NOT EXISTS m365_knowledge_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER NOT NULL,
      event_type TEXT NOT NULL, actor TEXT NOT NULL, detail_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(candidate_id) REFERENCES m365_knowledge_candidates(id) ON DELETE CASCADE
    );
    """)


def register_knowledge_promotion(app, namespace: dict[str, Any]) -> None:
    Request = namespace["Request"]
    HTTPException = namespace["HTTPException"]
    db = namespace["db"]
    now = namespace["now"]
    auth_context = namespace["auth_context"]
    app.state.knowledge_processing = {
        "state": "registered",
        "last_discovered": 0,
        "last_promoted": 0,
        "last_retry_required": 0,
        "last_error_code": "",
        "last_retry_codes": [],
    }

    def promotion_retry_code(exc: KnowledgePromotionError) -> str:
        detail = str(exc)
        if "destination could not be read" in detail:
            return "destination_read_denied"
        if "folder was not uniquely resolved" in detail:
            return "destination_folder_unresolved"
        if "file could not be written" in detail:
            return "destination_write_denied"
        if "destination verification failed" in detail:
            return "destination_hash_verification_failed"
        if "source could not be archived" in detail:
            return "source_archive_denied"
        if "archive could not be verified" in detail:
            return "source_archive_verification_failed"
        return "promotion_error"

    def authority(request):
        context = auth_context(request)
        if context.get("role") not in {"System Administrator", "Reviewer", "Approver"}:
            raise HTTPException(403, "Knowledge-review authority is required")
        return context

    def actor(context):
        return str(context.get("username") or context.get("display_name") or "authorized-user")[:240]

    def process_pending(processor_actor: str) -> dict[str, int]:
        app.state.knowledge_processing = {
            "state": "running",
            "last_discovered": 0,
            "last_promoted": 0,
            "last_retry_required": 0,
            "last_error_code": "",
            "last_retry_codes": [],
        }
        try:
            intake_config = GovernedM365Config.from_environment()
            intake = GovernedM365Intake(intake_config)
            listed = intake.list_files(pending_only=True)
            pending_files = [
                row for row in listed
                if row["relative_path"].startswith(PENDING_PREFIX)
            ]
            conn = db()
            _init_tables(conn)
            prior = {
                (row["source_item_id"], row["source_etag"]): row
                for row in conn.execute(
                    "SELECT source_item_id,source_etag,status,reviewed_at "
                    "FROM m365_knowledge_candidates"
                ).fetchall()
            }
            # Job invocations do not share memory. Prioritize never-seen files,
            # then the oldest retry, so a stubborn file cannot stall the queue.
            pending_files.sort(key=lambda row: (
                1 if (row["id"], row["etag"]) in prior else 0,
                str(prior.get((row["id"], row["etag"]), {}).get("reviewed_at") or ""),
                row["relative_path"],
            ))
            files = pending_files[:20]
            listed_by_id = {row["id"]: row for row in listed}
            created = 0
            automatically_promoted = 0
            automatic_retry_required = 0
            retry_codes: set[str] = set()
            retry_pending_ids: set[int] = set()
            writer = None
            for row in files:
                try:
                    document = intake.read_listed_document(
                        row, access_classification="Salus Internal"
                    )
                except M365IntakeError:
                    automatic_retry_required += 1
                    retry_codes.add("source_changed_during_scan")
                    continue
                existing = conn.execute(
                    "SELECT id FROM m365_knowledge_candidates "
                    "WHERE source_drive_id=? AND source_item_id=? AND source_etag=?",
                    (intake_config.drive_id, document.item_id, document.etag),
                ).fetchone()
                if existing:
                    current = conn.execute(
                        "SELECT * FROM m365_knowledge_candidates WHERE id=?", (existing["id"],)
                    ).fetchone()
                    if current["status"] != "Automatic Retry Required":
                        continue
                    candidate_id = current["id"]
                else:
                    candidate_id = None
                duplicate = conn.execute(
                    "SELECT id FROM m365_knowledge_candidates WHERE source_sha256=? "
                    "AND status IN ('Promoted','Source Retained','Source Removed',"
                    "'Ingested and Verified')",
                    (document.sha256,),
                ).fetchone()
                classification, _ = automatic_classification(
                    document, duplicate=bool(duplicate)
                )
                extraction_complete = classification["extraction"]["status"] == "Complete"
                initial_status = "Approved for Promotion" if extraction_complete else "Automatic Retry Required"
                timestamp = now()
                if candidate_id is None:
                    cursor = conn.execute(
                        """INSERT INTO m365_knowledge_candidates
                        (source_drive_id,source_item_id,source_name,source_relative_path,source_etag,
                         source_sha256,source_size,source_modified_at,source_owner,discovered_at,status,
                         decision,target_folder,classification_json,reviewed_by,reviewed_at,
                         review_rationale)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
                        (
                            intake_config.drive_id,document.item_id,document.name,
                            document.relative_path,document.etag,document.sha256,document.size,
                            document.last_modified,document.source_owner,timestamp,initial_status,
                            "Approved",classification["target_folder"],
                            json.dumps(classification,sort_keys=True),_AUTO_ACTOR,timestamp,
                            classification["rationale"],
                        ),
                    )
                    inserted = cursor.fetchone()
                    if inserted is None:
                        raise KnowledgePromotionError(
                            "Automatic knowledge candidate identity was not returned"
                        )
                    candidate_id = inserted[0]
                    created += 1
                    conn.execute(
                        "INSERT INTO m365_knowledge_events"
                        "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                        (
                            candidate_id,"Captured",processor_actor,
                            json.dumps({"sha256":document.sha256,"etag":document.etag}),timestamp,
                        ),
                    )
                else:
                    conn.execute(
                        """UPDATE m365_knowledge_candidates SET status=?,decision='Approved',
                        target_folder=?,classification_json=?,reviewed_by=?,reviewed_at=?,
                        review_rationale=? WHERE id=?""",
                        (initial_status,classification["target_folder"],
                         json.dumps(classification,sort_keys=True),_AUTO_ACTOR,timestamp,
                         classification["rationale"],candidate_id),
                    )
                if not extraction_complete:
                    automatic_retry_required += 1
                    retry_pending_ids.add(candidate_id)
                    retry_codes.add("extraction_retry_required")
                    conn.execute(
                        "INSERT INTO m365_knowledge_events"
                        "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                        (candidate_id,"AutomaticExtractionRetryScheduled",_AUTO_ACTOR,
                         json.dumps(classification["extraction"],sort_keys=True),timestamp),
                    )
                conn.execute(
                    "INSERT INTO m365_knowledge_events"
                    "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                    (
                        candidate_id,"AutomaticallyClassified",_AUTO_ACTOR,
                        json.dumps(classification,sort_keys=True),timestamp,
                    ),
                )
                conn.commit()
                try:
                    if writer is None:
                        writer = GraphKnowledgeWriter(
                            intake_config,
                            KnowledgeDestinationConfig.from_environment(),
                        )
                    destination = writer.put_verified(
                        classification["target_folder"],
                        document.name,
                        document.content,
                        document.sha256,
                    )
                    archived = writer.archive_verified_source(
                        document.item_id, document.etag, document.name, document.sha256
                    )
                    completed_at = now()
                    conn.execute(
                        """UPDATE m365_knowledge_candidates
                        SET status='Ingested and Verified',destination_drive_id=?,
                        destination_item_id=?,destination_web_url=?,destination_etag=?,
                        promoted_at=?,source_archived_at=?,source_archive_item_id=?,
                        source_archive_web_url=?,source_archive_etag=? WHERE id=?""",
                        (
                            writer.destination.drive_id,destination["item_id"],
                            destination["web_url"],destination["etag"],completed_at,
                            completed_at,archived["item_id"],archived["web_url"],
                            archived["etag"],candidate_id,
                        ),
                    )
                    conn.execute(
                        "INSERT INTO m365_knowledge_events"
                        "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                        (
                            candidate_id,"AutomaticallyPromotedVerifiedAndArchived",
                            _AUTO_ACTOR,json.dumps({
                                "destination_item_id":destination["item_id"],
                                "source_archive_item_id":archived["item_id"],
                                "target_folder":classification["target_folder"],
                                "permit_products":classification["permit_products"],
                            },sort_keys=True),completed_at,
                        ),
                    )
                    automatically_promoted += 1
                except KnowledgePromotionError as exc:
                    automatic_retry_required += 1
                    retry_codes.add(promotion_retry_code(exc))
                    conn.execute(
                        "UPDATE m365_knowledge_candidates "
                        "SET status='Automatic Retry Required',review_rationale=? WHERE id=?",
                        (str(exc),candidate_id),
                    )
                    conn.execute(
                        "INSERT INTO m365_knowledge_events"
                        "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                        (
                            candidate_id,"AutomaticPromotionRetryScheduled",_AUTO_ACTOR,
                            json.dumps({"reason":str(exc)},sort_keys=True),now(),
                        ),
                    )
                conn.commit()
            if not pending_files:
                archived_listed = intake.list_files(processed_only=True)
                listed_by_id = {row["id"]: row for row in archived_listed}
            # Extraction obligations survive promotion. Retry against the exact
            # archived original on later scans, without moving or rewriting it.
            archived_retries = conn.execute(
                "SELECT id,source_sha256,source_archive_item_id,classification_json "
                "FROM m365_knowledge_candidates WHERE status='Ingested and Verified' "
                "AND source_archive_item_id IS NOT NULL"
            ).fetchall() if not pending_files else []
            for pending in archived_retries:
                classification = json.loads(pending["classification_json"] or "{}")
                if classification.get("extraction", {}).get("status") != "Automatic Retry Required":
                    continue
                if pending["id"] in retry_pending_ids:
                    continue
                try:
                    archived_row = listed_by_id.get(pending["source_archive_item_id"])
                    if archived_row is None:
                        raise M365IntakeError("Archived source is outside current intake listing")
                    archived_doc = intake.read_listed_document(
                        archived_row,
                        access_classification="Salus Internal",
                    )
                except M365IntakeError:
                    automatic_retry_required += 1
                    retry_codes.add("archived_source_read_unavailable")
                    continue
                classification, retry_code = refresh_archived_extraction(
                    classification, archived_doc, pending["source_sha256"]
                )
                if retry_code:
                    automatic_retry_required += 1
                    retry_codes.add(retry_code)
                    continue
                completed_at = now()
                conn.execute(
                    "UPDATE m365_knowledge_candidates SET classification_json=? WHERE id=?",
                    (json.dumps(classification, sort_keys=True), pending["id"]),
                )
                conn.execute(
                    "INSERT INTO m365_knowledge_events"
                    "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                    (pending["id"],"AutomaticArchivedExtractionCompleted",_AUTO_ACTOR,
                     json.dumps({"source_sha256":pending["source_sha256"]}),completed_at),
                )
                conn.commit()
            total = conn.execute(
                "SELECT COUNT(*) FROM m365_knowledge_candidates"
            ).fetchone()[0]
            conn.close()
            result = {
                "discovered": len(files),
                "created": created,
                "automatically_promoted": automatically_promoted,
                "automatic_retry_required": automatic_retry_required,
                "exception_review": 0,
                "candidate_count": total,
            }
            app.state.knowledge_processing = {
                "state": "completed",
                "last_discovered": len(files),
                "last_promoted": automatically_promoted,
                "last_retry_required": automatic_retry_required,
                "last_error_code": "promotion_retry_required" if automatic_retry_required else "",
                "last_retry_codes": sorted(retry_codes),
            }
            return result
        except M365IntakeError as exc:
            app.state.knowledge_processing = {
                "state": "failed",
                "last_discovered": 0,
                "last_promoted": 0,
                "last_retry_required": 0,
                "last_error_code": "m365_intake_unavailable",
                "last_retry_codes": [],
            }
            raise KnowledgePromotionError("Governed Microsoft 365 intake is unavailable") from exc

    app.state.process_knowledge_pending = process_pending

    def scan(request):
        context = authority(request)
        try:
            return process_pending(actor(context))
        except KnowledgePromotionError as exc:
            raise HTTPException(503, str(exc)) from exc

    scan.__annotations__["request"] = Request
    app.post("/api/integrations/m365/knowledge/scan", include_in_schema=False)(scan)

    def scheduled_scan_loop() -> None:
        interval = max(30, min(int(os.getenv("SALUS_KNOWLEDGE_SCAN_INTERVAL_SECONDS", "60")), 86400))
        while True:
            try:
                process_pending("SalCAPA Scheduled Knowledge Processor")
            except Exception as exc:
                current = dict(getattr(app.state, "knowledge_processing", {}) or {})
                current["state"] = "failed"
                current["last_error_code"] = (
                    "knowledge_promotion_error"
                    if isinstance(exc, KnowledgePromotionError)
                    else "unexpected_" + type(exc).__name__
                )
                app.state.knowledge_processing = current
                # The next bounded interval retries automatically. Detailed item
                # outcomes are recorded in the governed candidate/event tables.
                pass
            time.sleep(interval)

    @app.on_event("startup")
    def start_scheduled_knowledge_processing() -> None:
        required = (
            "SALUS_M365_INTAKE_DRIVE_ID", "SALUS_M365_INTAKE_FOLDER_ITEM_ID",
            "SALUS_M365_KNOWLEDGE_DRIVE_ID", "SALUS_M365_KNOWLEDGE_FOLDER_ITEM_ID",
            "SALUS_M365_PROCESSED_INTAKE_FOLDER_ITEM_ID",
        )
        if all(os.getenv(name, "").strip() for name in required):
            threading.Thread(
                target=scheduled_scan_loop,
                name="salcapa-knowledge-scan",
                daemon=True,
            ).start()

    def list_candidates(request):
        authority(request); conn = db(); _init_tables(conn)
        rows = [dict(row) for row in conn.execute("SELECT * FROM m365_knowledge_candidates ORDER BY id DESC").fetchall()]
        conn.close(); return {"items": rows, "count": len(rows)}

    list_candidates.__annotations__["request"] = Request
    app.get("/api/integrations/m365/knowledge/candidates", include_in_schema=False)(list_candidates)

    def classify(candidate_id: int, command: ClassificationCommand, request):
        context = authority(request); conn = db(); _init_tables(conn)
        row = conn.execute("SELECT * FROM m365_knowledge_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row: conn.close(); raise HTTPException(404, "Knowledge candidate was not found")
        if row["status"] not in {"Pending Review", "Duplicate Review", "Deferred"}:
            conn.close(); raise HTTPException(409, "Knowledge candidate is not reviewable")
        if command.decision == "Approved" and (not command.target_folder or not command.permit_products):
            conn.close(); raise HTTPException(422, "Approved knowledge requires a destination and permitted products")
        payload = command.model_dump()
        conn.execute(
            """UPDATE m365_knowledge_candidates SET status=?,decision=?,target_folder=?,
            classification_json=?,reviewed_by=?,reviewed_at=?,review_rationale=? WHERE id=?""",
            ("Approved for Promotion" if command.decision == "Approved" else command.decision,
             command.decision,command.target_folder,json.dumps(payload,sort_keys=True),actor(context),now(),command.rationale,candidate_id),
        )
        conn.execute(
            "INSERT INTO m365_knowledge_events(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
            (candidate_id,"Classified",actor(context),json.dumps(payload,sort_keys=True),now()),
        )
        conn.commit(); result = dict(conn.execute("SELECT * FROM m365_knowledge_candidates WHERE id=?",(candidate_id,)).fetchone()); conn.close(); return result

    classify.__annotations__["request"] = Request
    app.post("/api/integrations/m365/knowledge/candidates/{candidate_id}/classify", include_in_schema=False)(classify)

    def promote(candidate_id: int, request):
        context = authority(request); conn = db(); _init_tables(conn)
        row = conn.execute("SELECT * FROM m365_knowledge_candidates WHERE id=?",(candidate_id,)).fetchone()
        if not row: conn.close(); raise HTTPException(404, "Knowledge candidate was not found")
        if row["status"] != "Approved for Promotion": conn.close(); raise HTTPException(409, "The automatic processing record is not ready for promotion")
        intake_config = GovernedM365Config.from_environment(); intake = GovernedM365Intake(intake_config)
        document = intake.read_document(row["source_item_id"], access_classification="Salus Internal")
        if document.etag != row["source_etag"] or document.sha256 != row["source_sha256"]:
            conn.execute("UPDATE m365_knowledge_candidates SET status='Automatic Retry Required' WHERE id=?",(candidate_id,)); conn.commit(); conn.close()
            raise HTTPException(409, "The source changed and has been scheduled for automatic reprocessing")
        writer = GraphKnowledgeWriter(intake_config, KnowledgeDestinationConfig.from_environment())
        destination = writer.put_verified(
            row["target_folder"], document.name, document.content, document.sha256
        )
        archived = writer.archive_verified_source(document.item_id, document.etag, document.name, document.sha256)
        timestamp = now()
        conn.execute(
            """UPDATE m365_knowledge_candidates SET status='Ingested and Verified',
            destination_drive_id=?,destination_item_id=?,destination_web_url=?,destination_etag=?,
            promoted_at=?,source_archived_at=?,source_archive_item_id=?,source_archive_web_url=?,
            source_archive_etag=? WHERE id=?""",
            (writer.destination.drive_id,destination["item_id"],destination["web_url"],
             destination["etag"],timestamp,timestamp,archived["item_id"],archived["web_url"],
             archived["etag"],candidate_id),
        )
        conn.execute(
            "INSERT INTO m365_knowledge_events(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
            (candidate_id,"PromotedVerifiedAndArchived",actor(context),json.dumps({
                "destination_item_id": destination["item_id"],
                "source_archive_item_id": archived["item_id"],
                "source_archive_folder_item_id": writer.destination.processed_folder_item_id,
                "approved_by": row["reviewed_by"],
                "approved_at": row["reviewed_at"],
                "verified_and_archived_by": actor(context),
            },sort_keys=True),timestamp),
        )
        conn.commit(); result = dict(conn.execute("SELECT * FROM m365_knowledge_candidates WHERE id=?",(candidate_id,)).fetchone()); conn.close(); return result

    promote.__annotations__["request"] = Request
    app.post("/api/integrations/m365/knowledge/candidates/{candidate_id}/promote", include_in_schema=False)(promote)
