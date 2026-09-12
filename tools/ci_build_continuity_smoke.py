#!/usr/bin/env python3
"""Deterministic checks for the governed SalCAPA build-continuity record."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "build-continuity.md"
RUNTIME = ROOT / "salcapa_runtime.py"

REQUIRED_KEYS = {
    "schema_version",
    "record_kind",
    "last_verified_at",
    "current_frozen_release",
    "current_frozen_commit",
    "active_development_branch",
    "active_roadmap_issue",
    "active_increment",
    "last_completed_release",
    "candidate_release",
    "validation_pr",
    "validation_gate_state",
    "genuine_blockers",
    "next_authorized_increment",
}


def front_matter(text: str) -> dict[str, str]:
    assert text.startswith("---\n"), "continuity record must begin with front matter"
    _, raw, _ = text.split("---", 2)
    values: dict[str, str] = {}
    for line in raw.strip().splitlines():
        key, separator, value = line.partition(":")
        assert separator and key.strip() and value.strip(), f"invalid continuity field: {line!r}"
        assert key.strip() not in values, f"duplicate continuity field: {key.strip()}"
        values[key.strip()] = value.strip()
    return values


def version_tuple(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"v?(\d+)\.(\d+)", value)
    assert match, f"invalid release version: {value}"
    return int(match.group(1)), int(match.group(2))


def main() -> None:
    text = RECORD.read_text(encoding="utf-8")
    values = front_matter(text)
    assert set(values) == REQUIRED_KEYS, (REQUIRED_KEYS - set(values), set(values) - REQUIRED_KEYS)
    assert values["schema_version"] == "1"
    assert values["record_kind"] == "salcapa_build_continuity"
    assert values["active_development_branch"] == "development/salcapa-platform"
    assert values["active_roadmap_issue"].isdigit()
    assert re.fullmatch(r"[0-9a-f]{40}", values["current_frozen_commit"])
    assert re.fullmatch(
        r"\d{2} (January|February|March|April|May|June|July|August|September|October|November|December) "
        r"\d{4} \d{2}:\d{2} (CST|CDT)",
        values["last_verified_at"],
    ), values["last_verified_at"]
    assert values["validation_pr"] == "pending" or values["validation_pr"] == "none" \
        or values["validation_pr"].isdigit()
    assert values["validation_gate_state"] in {
        "local_verified_github_pending",
        "github_validation_running",
        "controlled_validation_in_progress",
        "all_required_gates_green",
    }

    runtime_text = RUNTIME.read_text(encoding="utf-8")
    match = re.search(r'^SALCAPA_RELEASE_VERSION\s*=\s*"(\d+\.\d+)"', runtime_text, re.MULTILINE)
    assert match, "runtime release version marker missing"
    runtime_version = version_tuple(match.group(1))
    frozen_version = version_tuple(values["current_frozen_release"])
    candidate_version = version_tuple(values["candidate_release"]) if values["candidate_release"] != "none" else None
    assert values["last_completed_release"] == values["current_frozen_release"]
    if candidate_version is None:
        assert runtime_version == frozen_version
        if values["validation_gate_state"] == "all_required_gates_green":
            assert values["validation_pr"] == "none"
        else:
            assert values["validation_pr"] == "pending" or values["validation_pr"].isdigit()
    else:
        assert candidate_version == runtime_version
        if candidate_version == frozen_version:
            release_marker = f"v{candidate_version[0]}{candidate_version[1]}"
            assert release_marker in values["active_increment"]
            assert values["active_increment"].endswith(
                ("_azure_demo_promotion", "_immutable_image_publication", "_application_promotion")
            )
            assert values["validation_pr"].isdigit()
            assert values["validation_gate_state"] in {
                "controlled_validation_in_progress",
                "all_required_gates_green",
            }
            if values["validation_gate_state"] == "controlled_validation_in_progress":
                assert values["genuine_blockers"] != "none"
        else:
            assert candidate_version[0] == frozen_version[0]
            assert candidate_version[1] == frozen_version[1] + 1

    required_phrases = (
        "GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records.",
        "conversation is not a build blocker",
        "close the controlled validation pull request without merge",
        "Human-First Communications and Human Trust & Comprehension doctrine",
        "Never place credentials, confidential Protected Member information",
    )
    lowered = text.lower()
    for phrase in required_phrases:
        assert phrase.lower() in lowered, phrase

    secret_assignment = re.compile(
        r"(?im)^\s*(password|passwd|token|api[_-]?key|client[_-]?secret|connection[_-]?string)\s*[:=]\s*\S+"
    )
    assert not secret_assignment.search(text), "continuity record contains a credential-like assignment"
    assert "-----BEGIN " not in text, "continuity record contains private key material"
    print("SalCAPA build continuity acceptance checks passed.")


if __name__ == "__main__":
    main()

