#!/usr/bin/env python3
"""Fail closed when runtime/workflow entrypoints select stale or mutating source."""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECONSTRUCT = "tools/reconstruct_v343_source.py"
VERIFY = "tools/verify_v343_source.py"
ARCHIVE_VERIFY = "tools/verify_v343_archive.py"
FILES = (
    "README.md",
    "Dockerfile",
    "run_mac_linux.sh",
    "run_windows.bat",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
)
PROTECTED_CURRENT_FILES = (
    "static/app.js",
    "static/index.html",
    "static/styles.css",
)

for relative in FILES:
    text = (ROOT / relative).read_text(encoding="utf-8").replace("\\", "/")
    selects_pair = RECONSTRUCT in text and VERIFY in text
    selects_isolated = ARCHIVE_VERIFY in text
    if not (selects_pair or selects_isolated):
        raise SystemExit(
            f"{relative} does not select verified archive evidence through "
            f"{ARCHIVE_VERIFY} or the governed reconstruct/verify pair"
        )


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

before = {
    relative: digest(ROOT / relative)
    for relative in PROTECTED_CURRENT_FILES
    if (ROOT / relative).is_file()
}

# Use the same isolated archive verifier that CI and CodeQL use. It reconstructs
# v3.43 only under a temporary reference directory and must never touch current
# governed runtime/UI files.
subprocess.run([sys.executable, str(ROOT / ARCHIVE_VERIFY)], cwd=ROOT, check=True)

after = {relative: digest(ROOT / relative) for relative in before}
if before != after:
    changed = sorted(relative for relative in before if before[relative] != after[relative])
    raise SystemExit(
        "Historical v3.43 archive verification mutated current runtime source: "
        + ", ".join(changed)
    )

print("ARCHIVE_RUNTIME_ISOLATION_PASS")
print("RELEASE_ENTRYPOINTS_PASS")
