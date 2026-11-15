"""Exercise the full reference preflight against valid and drifted release records."""

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "7b79b2845aaa6e2bf738e0c115c10b73e4c97dd3"
ROLLBACK_COMMIT = "5dff59b381a0c455f99c6f15d0e2a37c273f4056"
ROLLBACK = "salcapadevb48224acr.azurecr.io/salcapa@sha256:8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c"
OTHER = "salcapadevb48224acr.azurecr.io/salcapa@sha256:" + "a" * 64
IMAGE = {
    "operation": "publish_image", "target_environment": "dev",
    "source_release": "release/v3.276", "source_commit": SOURCE,
    "activation_key": "salcapa-v3.276-image-7b79b284",
}
APPLICATION = {
    "operation": "deploy_application", "target_environment": "dev",
    "source_release": "release/v3.273", "source_commit": "3572f2b4cf7c2cb65c772d0a848db7d9e6951944",
    "activation_key": "salcapa-v3.273-application-3572f2b4", "activation_retry_attempt": 2,
    "image_digest": "salcapadevb48224acr.azurecr.io/salcapa@sha256:4ef49042f0c998e74b04c51affcdc838a7c3ae940d5667553ad33996b2333db9",
    "rollback_release": "release/v3.223", "rollback_commit": ROLLBACK_COMMIT,
    "rollback_image_digest": ROLLBACK, "previous_application_image_digest": ROLLBACK,
    "previous_worker_image_digest": ROLLBACK,
}
BUILD = ("---\ncurrent_frozen_release: v3.276\ncurrent_frozen_commit: " + SOURCE
         + "\ncandidate_release: v3.276\ndeployed_demo_release: v3.223\n---\n"
         "v3274_dependency_audit_withheld_before_publication\n"
         "v3275_codeql_withheld_before_publication\n")


def main():
    frozen = Path(os.environ.get("SALCAPA_FROZEN_V3109_ROOT", ROOT / "frozen-v3109")).resolve()
    if not frozen.is_dir():
        raise RuntimeError("Exact historical reference checkout is required")
    with tempfile.TemporaryDirectory(prefix="advisor-publication-lineage-") as directory:
        fixture = Path(directory)
        for name in ("tools/ci_salcapa_v3109_candidate_image_preflight.py",
                     "deploy/azure/candidates/v3.109-reference-image-preflight.json"):
            target = fixture / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        records = fixture / "deploy/azure/activations"
        records.mkdir(parents=True)
        (fixture / "docs").mkdir()
        env = {**os.environ, "SALCAPA_FROZEN_V3109_ROOT": str(frozen)}

        def check(image, application, build, allowed):
            (records / "image-dev.json").write_text(json.dumps(image), encoding="utf-8")
            (records / "application-dev.json").write_text(json.dumps(application), encoding="utf-8")
            (fixture / "docs/build-continuity.md").write_text(build, encoding="utf-8")
            result = subprocess.run([sys.executable, str(fixture / "tools/ci_salcapa_v3109_candidate_image_preflight.py")],
                                    env=env, capture_output=True, text=True)
            assert (result.returncode == 0) == allowed, "Publication lineage guard did not reject drift"

        check(IMAGE, APPLICATION, BUILD, True)
        rejected = 0
        for key, value in (
            ("source_commit", "b" * 40), ("activation_key", "unapproved-activation"),
            ("activation_retry_attempt", 3), ("rollback_release", "release/v3.222"),
            ("rollback_commit", "b" * 40), ("rollback_image_digest", OTHER),
            ("previous_application_image_digest", OTHER), ("previous_worker_image_digest", OTHER),
        ):
            application = copy.deepcopy(APPLICATION)
            application[key] = value
            check(IMAGE, application, BUILD, False)
            rejected += 1
        image = {**IMAGE, "source_commit": "b" * 40, "activation_key": "salcapa-v3.276-image-bbbbbbbb"}
        check(image, APPLICATION, BUILD, False)
        rejected += 1
        image = {**IMAGE, "source_release": "release/v3.277", "activation_key": "salcapa-v3.277-image-7b79b284"}
        check(image, APPLICATION, BUILD, False)
        rejected += 1
        for original, replacement in (
            (SOURCE, "b" * 40), ("current_frozen_release: v3.276", "current_frozen_release: v3.275"),
            ("candidate_release: v3.276", "candidate_release: v3.275"),
            ("deployed_demo_release: v3.223", "deployed_demo_release: v3.273"),
            ("v3274_dependency_audit_withheld_before_publication", "missing_first_withheld_record"),
            ("v3275_codeql_withheld_before_publication", "missing_second_withheld_record"),
        ):
            check(IMAGE, APPLICATION, BUILD.replace(original, replacement), False)
            rejected += 1
        print(f"ADVISOR_V3276_PUBLICATION_LINEAGE_PASS valid=1 rejected={rejected}")


if __name__ == "__main__":
    main()
