"""Candidate read-only Graph verification probe for one governed knowledge row.

This file is not activated. It must receive exact-source, cost, and one-time
activation review before running with the existing knowledge worker identity.
"""

from __future__ import annotations

import hashlib
import json
import re
import signal
from urllib.parse import quote, urlparse


SOURCE_SIZE = 103_344_128
PREFIX = "SALUS_DESTINATION_BRANCH_DIAGNOSTIC="
SAFE_ID = re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")
SAFE_SHA = re.compile(r"^[0-9a-f]{64}$")
OFFICE = (".docx", ".xlsx", ".pptx")


def names_for_hash(name: str, sha256: str) -> list[tuple[str, str]]:
    if not name or len(name) > 260 or not SAFE_SHA.fullmatch(sha256):
        raise ValueError("invalid private candidate metadata")
    stem, separator, extension = name.rpartition(".")
    if not stem:
        stem, separator, extension = name, "", ""
    suffix = f".{sha256[:24]}" + (f".{extension}" if separator else "")
    primary = stem[:max(1, 240 - len(suffix))] + suffix
    result = [("primary", primary)]
    if primary.lower().endswith(OFFICE):
        result.append(("original_fallback", f"{primary}.{sha256[:16]}.original.bin"))
    return result


def trusted_redirect(value: str) -> bool:
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and bool(parsed.hostname)
        and parsed.hostname.lower().endswith(".sharepoint.com")
    )


def read_verified(client, url: str, headers: dict[str, str], expected_hash: str,
                  expected_size: int) -> dict[str, object]:
    """Read one existing object into a streaming hash; emit no bytes or URL."""
    with client.stream("GET", url, headers=headers, timeout=120.0) as response:
        first_status = int(response.status_code)
        if first_status in {302, 303, 307, 308}:
            location = str(response.headers.get("Location", ""))
            if not trusted_redirect(location):
                return {"first_status": first_status, "final_status": 0,
                        "redirect_trusted": False}
        else:
            location = ""
            if first_status != 200:
                return {"first_status": first_status, "final_status": first_status}
            return hash_response(response, first_status, expected_hash, expected_size)
    with client.stream("GET", location, headers={"Accept": "application/octet-stream"},
                       timeout=120.0) as response:
        if response.status_code != 200:
            return {"first_status": first_status, "final_status": int(response.status_code),
                    "redirect_trusted": True}
        result = hash_response(response, first_status, expected_hash, expected_size)
        result["redirect_trusted"] = True
        return result


def hash_response(response, first_status: int, expected_hash: str,
                  expected_size: int) -> dict[str, object]:
    digest = hashlib.sha256()
    size = 0
    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
        size += len(chunk)
        if size > expected_size:
            return {"first_status": first_status, "final_status": 200,
                    "size_match": False, "hash_match": False}
        digest.update(chunk)
    return {"first_status": first_status, "final_status": 200,
            "size_match": size == expected_size,
            "hash_match": size == expected_size and digest.hexdigest() == expected_hash}


def inspect(writer, folder: str, name: str, sha256: str, size: int) -> dict[str, object]:
    folder_id = writer._resolve_folder(folder)
    if not SAFE_ID.fullmatch(folder_id):
        raise ValueError("invalid destination folder")
    observations: list[dict[str, object]] = []
    for label, candidate_name in names_for_hash(name, sha256):
        item_path = (
            f"https://graph.microsoft.com/v1.0/drives/{writer.destination.drive_id}"
            f"/items/{folder_id}:/{quote(candidate_name, safe='')}:"
        )
        metadata = writer.client.get(
            item_path, headers=writer._headers() | {"Accept": "application/json"},
            timeout=30.0,
        )
        observation: dict[str, object] = {"path_kind": label,
                                          "metadata_status": int(metadata.status_code)}
        if metadata.status_code == 200:
            item_id = str(metadata.json().get("id", ""))
            if not SAFE_ID.fullmatch(item_id):
                observation["item_identity_valid"] = False
            else:
                observation["item_identity_valid"] = True
                observation.update(read_verified(
                    writer.client,
                    f"https://graph.microsoft.com/v1.0/drives/{writer.destination.drive_id}"
                    f"/items/{item_id}/content",
                    writer._headers() | {"Accept": "application/octet-stream"},
                    sha256, size,
                ))
        observations.append(observation)
        if observation.get("hash_match") is True:
            break
    return {"candidate_count": 1, "observations": observations}


def main() -> None:
    signal.alarm(180)
    try:
        from database import backend_name, connect_database
        from salcapa_m365_intake import GovernedM365Config
        from salcapa_knowledge_promotion import (
            GraphKnowledgeWriter, KnowledgeDestinationConfig, TARGETS,
        )
        if backend_name() != "postgres":
            raise ValueError("governed database required")
        conn = connect_database()
        try:
            conn.execute("SET TRANSACTION READ ONLY")
            rows = conn.execute(
                "SELECT status,source_name,source_sha256,source_size,target_folder "
                "FROM m365_knowledge_candidates WHERE source_size=? LIMIT 2",
                (SOURCE_SIZE,),
            ).fetchall()
            if len(rows) != 1 or rows[0]["status"] != "Automatic Retry Required":
                raise ValueError("candidate identity or status changed")
            row = rows[0]
            name, sha256, size, folder = (
                str(row["source_name"]), str(row["source_sha256"]),
                int(row["source_size"]), str(row["target_folder"]),
            )
            if size != SOURCE_SIZE or folder not in TARGETS:
                raise ValueError("candidate route changed")
        finally:
            conn.rollback()
            conn.close()
        intake = GovernedM365Config.from_environment()
        destination = KnowledgeDestinationConfig.from_environment()
        writer = GraphKnowledgeWriter(intake, destination)
        result = inspect(writer, folder, name, sha256, size)
    except Exception:
        print(PREFIX + json.dumps({"probe_state": "unavailable"}), flush=True)
        raise SystemExit(2) from None
    print(PREFIX + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
