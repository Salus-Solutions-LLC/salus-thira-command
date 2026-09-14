#!/usr/bin/env python3
"""Fail closed when runtime/workflow entrypoints select stale or mutating source."""

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECONSTRUCT = "tools/reconstruct_v343_source.py"
VERIFY = "tools/verify_v343_source.py"
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
    missing = [command for command in (RECONSTRUCT, VERIFY) if command not in text]
    if missing:
        raise SystemExit(f"{relative} does not select verified archive evidence: {', '.join(missing)}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

before = {
    relative: digest(ROOT / relative)
    for relative in PROTECTED_CURRENT_FILES
    if (ROOT / relative).is_file()
}

subprocess.run([sys.executable, str(ROOT / RECONSTRUCT)], cwd=ROOT, check=True)
subprocess.run([sys.executable, str(ROOT / VERIFY)], cwd=ROOT, check=True)

after = {relative: digest(ROOT / relative) for relative in before}
if before != after:
    changed = sorted(relative for relative in before if before[relative] != after[relative])
    raise SystemExit(
        "Historical v3.43 archive verification mutated current runtime source: "
        + ", ".join(changed)
    )

print("ARCHIVE_RUNTIME_ISOLATION_PASS")
print("RELEASE_ENTRYPOINTS_PASS")
