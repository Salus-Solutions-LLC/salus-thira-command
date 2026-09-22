#!/usr/bin/env python3
"""Deterministic checks for the governed Azure demonstration continuity record."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "demo-deployment-continuity.md"
BUILD_RECORD = ROOT / "docs" / "build-continuity.md"

REQUIRED_KEYS = {
    "schema_version",
    "record_kind",
    "last_verified_at",
    "environment",
    "deployed_release",
    "deployed_commit",
    "image_digest",
    "deployed_at",
    "deployment_workflow_run",
    "deployment_acceptance",
    "current_stable_release",
    "current_stable_commit",
    "promotion_candidate",
    "promotion_candidate_image_commit",
    "promotion_candidate_image_digest",
    "promotion_candidate_image_reference",
    "promotion_candidate_image_published_at",
    "promotion_candidate_image_workflow_run",
    "promotion_candidate_image_acceptance",
    "promotion_readiness",
    "fictional_member_seed_state",
    "critical_journey_acceptance",
    "rollback_baseline",
    "genuine_blocker",
}

DATE_TIME = re.compile(
    r"\d{2} (January|February|March|April|May|June|July|August|September|October|November|December) "
    r"\d{4} \d{2}:\d{2} (CST|CDT)"
)


def front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name} must begin with front matter"
    _, raw, _ = text.split("---", 2)
    values: dict[str, str] = {}
    for line in raw.strip().splitlines():
        key, separator, value = line.partition(":")
        assert separator and key.strip() and value.strip(), f"invalid field: {line!r}"
        assert key.strip() not in values, f"duplicate field: {key.strip()}"
        values[key.strip()] = value.strip()
    return values


def version(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"v(\d+)\.(\d+)", value)
    assert match, f"invalid release version: {value}"
    return int(match.group(1)), int(match.group(2))


def main() -> None:
    values = front_matter(RECORD)
    build = front_matter(BUILD_RECORD)

    assert set(values) == REQUIRED_KEYS, (REQUIRED_KEYS - set(values), set(values) - REQUIRED_KEYS)
    assert values["schema_version"] == "1"
    assert values["record_kind"] == "salcapa_demo_deployment_continuity"
    assert values["environment"] == "azure_development_demonstration"
    assert DATE_TIME.fullmatch(values["last_verified_at"])
    assert DATE_TIME.fullmatch(values["deployed_at"])
    assert re.fullmatch(r"[0-9a-f]{40}", values["deployed_commit"])
    assert re.fullmatch(r"[0-9a-f]{40}", values["current_stable_commit"])
    assert re.fullmatch(r"[0-9a-f]{40}", values["promotion_candidate_image_commit"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", values["image_digest"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", values["promotion_candidate_image_digest"])
    assert values["promotion_candidate_image_reference"].endswith(
        "@" + values["promotion_candidate_image_digest"]
    )
    assert values["deployment_workflow_run"].isdigit()
    assert values["promotion_candidate_image_workflow_run"].isdigit()
    assert DATE_TIME.fullmatch(values["promotion_candidate_image_published_at"])
    assert values["promotion_candidate_image_acceptance"] in {
        "immutable_image_published_not_deployed",
        "immutable_image_deployed_awaiting_live_acceptance",
        "immutable_image_deployed_and_accepted",
    }
    assert values["deployment_acceptance"] in {
        "live_runtime_readiness_accepted",
        "full_demonstration_acceptance",
    }
    assert values["promotion_readiness"] in {"not_ready", "preflight_ready", "deployed_awaiting_live_acceptance", "accepted"}
    assert values["fictional_member_seed_state"] in {
        "not_verified",
        "foundation_verified_not_deployed",
        "cross_functional_records_verified_not_deployed",
        "role_preflight_verified_not_deployed",
        "migration_recovery_rehearsal_verified_not_deployed",
        "candidate_image_boundary_verified_not_deployed",
        "v310_publication_contract_verified_not_deployed",
        "v310_image_published_not_deployed",
        "v311_image_published_not_deployed",
        "v312_image_published_not_deployed",
        "v313_image_published_not_deployed",
        "v313_deployed_awaiting_live_acceptance",
        "v312_deployed_awaiting_live_acceptance",
        "v311_live_copy_migration_accepted_not_deployed",
        "verified",
    }
    assert values["critical_journey_acceptance"] in {"not_verified", "verified"}

    assert version(values["current_stable_release"]) <= version(build["current_frozen_release"])
    if values["current_stable_release"] == build["current_frozen_release"]:
        assert values["current_stable_commit"] == build["current_frozen_commit"]
    else:
        frozen = version(build["current_frozen_release"])
        candidate = version(build["candidate_release"])
        abandoned_gap = (
            candidate == (frozen[0], frozen[1] + 2)
            and build["root_cause"] == (
                "v3.164_abandoned_before_image_publication_after_release_identity_mismatch"
            )
            and build["active_increment"] == "knowledge_promotion_v3165"
        )
        assert candidate in {frozen, (frozen[0], frozen[1] + 1)} or abandoned_gap
        if candidate != frozen and not abandoned_gap:
            assert "superseded" in build["genuine_blockers"]
            assert f"v{frozen[0]}{frozen[1]}" in build["last_completed_increment"]
        if abandoned_gap:
            assert build["validation_pr"] in {"pending", "none"} or build["validation_pr"].isdigit()
        else:
            assert build["validation_pr"].isdigit()
        assert build["genuine_blockers"] != "none"
    assert version(values["promotion_candidate"]) <= version(values["current_stable_release"])
    if values["promotion_candidate"] == values["current_stable_release"]:
        assert values["promotion_candidate_image_commit"] == values["current_stable_commit"]
    assert version(values["current_stable_release"]) >= version(values["deployed_release"])
    assert version(values["rollback_baseline"]) <= version(values["deployed_release"])

    if values["promotion_readiness"] == "accepted":
        assert values["deployed_release"] == values["current_stable_release"]
        assert values["promotion_candidate_image_acceptance"] == "immutable_image_deployed_and_accepted"
        assert values["fictional_member_seed_state"] == "verified"
        assert values["critical_journey_acceptance"] == "verified"
        assert values["genuine_blocker"] == "none"
    elif values["promotion_readiness"] == "preflight_ready":
        assert values["genuine_blocker"] != "none"
        assert values["deployed_release"] != values["promotion_candidate"]
    elif values["promotion_readiness"] == "deployed_awaiting_live_acceptance":
        assert values["deployed_release"] == values["promotion_candidate"]
        assert values["deployed_release"] == values["current_stable_release"]
        assert values["promotion_candidate_image_acceptance"] == "immutable_image_deployed_awaiting_live_acceptance"
        assert values["fictional_member_seed_state"] in {
            "v312_deployed_awaiting_live_acceptance",
            "v313_deployed_awaiting_live_acceptance",
        }
        assert values["critical_journey_acceptance"] == "not_verified"
        assert values["genuine_blocker"] != "none"
    else:
        assert values["genuine_blocker"] != "none"

    text = RECORD.read_text(encoding="utf-8")
    required_phrases = (
        "FICTIONAL DEMONSTRATION",
        "fails closed",
        "server-controlled",
        "immutable image digest",
        "cross-tenant isolation",
        "Database rollback uses an independently validated restore",
        "does not authorize production cutover",
    )
    for phrase in required_phrases:
        assert phrase.lower() in text.lower(), phrase

    credential = re.compile(
        r"(?im)^\s*(password|passwd|token|api[_-]?key|client[_-]?secret|connection[_-]?string)\s*[:=]\s*\S+"
    )
    assert not credential.search(text), "demonstration continuity contains credential-like material"
    assert "-----BEGIN " not in text, "demonstration continuity contains private key material"
    print("SalCAPA demonstration deployment continuity checks passed.")


if __name__ == "__main__":
    main()
