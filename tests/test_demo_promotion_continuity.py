"""Reject promotion records that blur a published candidate and accepted runtime."""

import json

import pytest

from tools import ci_demo_deployment_continuity_smoke as checks


SOURCE = "7b79b2845aaa6e2bf738e0c115c10b73e4c97dd3"
STABLE = "5dff59b381a0c455f99c6f15d0e2a37c273f4056"
BASE_DIGEST = "sha256:8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c"
IMAGE = "salcapadevb48224acr.azurecr.io/salcapa@sha256:550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944"


def amend_frontmatter(path, updates):
    text = path.read_text(encoding="utf-8")
    _, _, body = text.split("---", 2)
    values = checks.front_matter(path)
    values.update(updates)
    path.write_text("---\n" + "\n".join(f"{k}: {v}" for k, v in values.items()) + "\n---" + body,
                    encoding="utf-8")


@pytest.fixture
def pending_promotion(tmp_path, monkeypatch):
    original = checks.ROOT
    (tmp_path / "docs").mkdir()
    for name in ("demo-deployment-continuity.md", "build-continuity.md"):
        (tmp_path / "docs" / name).write_bytes((original / "docs" / name).read_bytes())
    monkeypatch.setattr(checks, "ROOT", tmp_path)
    monkeypatch.setattr(checks, "RECORD", tmp_path / "docs/demo-deployment-continuity.md")
    monkeypatch.setattr(checks, "BUILD_RECORD", tmp_path / "docs/build-continuity.md")
    amend_frontmatter(checks.RECORD, {
        "deployed_release": "v3.223", "deployed_commit": STABLE, "image_digest": BASE_DIGEST,
        "current_stable_release": "v3.223", "current_stable_commit": STABLE,
        "promotion_candidate": "v3.276", "promotion_candidate_image_commit": SOURCE,
        "promotion_candidate_image_digest": IMAGE.split("@")[1], "promotion_candidate_image_reference": IMAGE,
        "promotion_candidate_image_acceptance": "immutable_image_published_not_deployed",
        "promotion_readiness": "preflight_ready", "critical_journey_acceptance": "not_verified",
        "fictional_member_seed_state": "not_verified", "rollback_baseline": "v3.223",
        "genuine_blocker": "exact_candidate_approval_and_live_acceptance_pending",
    })
    amend_frontmatter(checks.BUILD_RECORD, {
        "current_frozen_release": "v3.276", "current_frozen_commit": SOURCE,
        "candidate_release": "v3.276", "validation_pr": "1230", "genuine_blockers": "approval_pending",
    })
    folder = tmp_path / "deploy/azure/activations"
    folder.mkdir(parents=True)
    publication = {"operation": "publish_image", "target_environment": "dev",
                   "source_release": "release/v3.276", "source_commit": SOURCE}
    application = {**publication, "operation": "deploy_application", "image_digest": IMAGE,
                   "rollback_release": "release/v3.223", "rollback_commit": STABLE}
    for field in ("rollback_image_digest", "previous_application_image_digest", "previous_worker_image_digest"):
        application[field] = "salcapadevb48224acr.azurecr.io/salcapa@" + BASE_DIGEST
    for name, data in (("image-dev.json", publication), ("application-dev.json", application)):
        (folder / name).write_text(json.dumps(data), encoding="utf-8")
    return folder


def test_pending_published_image_preserves_accepted_runtime(pending_promotion):
    checks.main()


@pytest.mark.parametrize("document,field,value", [
    ("demo", "promotion_readiness", "accepted"),
    ("demo", "promotion_candidate_image_acceptance", "immutable_image_deployed_and_accepted"),
    ("demo", "promotion_candidate_image_commit", "a" * 40),
    ("demo", "current_stable_commit", "a" * 40),
    ("build", "current_frozen_commit", "a" * 40),
    ("image-dev.json", "source_commit", "a" * 40),
    ("application-dev.json", "image_digest", "salcapadevb48224acr.azurecr.io/salcapa@sha256:" + "a" * 64),
    ("application-dev.json", "rollback_commit", "a" * 40),
    ("application-dev.json", "previous_worker_image_digest", IMAGE),
])
def test_pending_promotion_rejects_acceptance_and_lineage_drift(pending_promotion, document, field, value):
    if document in {"demo", "build"}:
        amend_frontmatter(checks.RECORD if document == "demo" else checks.BUILD_RECORD, {field: value})
    else:
        path = pending_promotion / document
        data = json.loads(path.read_text(encoding="utf-8"))
        data[field] = value
        path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AssertionError):
        checks.main()
