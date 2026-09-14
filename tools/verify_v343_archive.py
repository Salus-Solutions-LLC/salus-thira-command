#!/usr/bin/env python3
"""Verify the immutable SalCAPA v3.43 archive without mutating current runtime source."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECONSTRUCT = ROOT / "tools" / "reconstruct_v343_source.py"
VERIFY = ROOT / "tools" / "verify_v343_source.py"

with tempfile.TemporaryDirectory(prefix="salcapa-v343-") as temp_dir:
    target = Path(temp_dir) / "reference"
    subprocess.run(
        [sys.executable, str(RECONSTRUCT), "--target", str(target)],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(VERIFY), "--root", str(target)],
        cwd=ROOT,
        check=True,
    )

print("V343_ARCHIVE_REFERENCE_PASS")
