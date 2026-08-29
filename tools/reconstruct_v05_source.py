#!/usr/bin/env python3
"""Reconstruct the exact tested Salus THIRA Command v0.5 large source files.

The ChatGPT GitHub connector used to publish v0.5 has a per-file transfer limit.
The two largest files are therefore stored as ordered gzip+Base64 parts under
source_archives/v0.5/. This script joins, decodes, decompresses, writes, and
verifies them byte-for-byte using their known SHA-256 hashes.
"""
from pathlib import Path
import base64
import gzip
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "source_archives" / "v0.5"
TARGETS = {
    "app.py": {
        "pattern": "app.py.gz.b64.part*",
        "sha256": "5572cf66373ecf906a1565a6f8d1e10cf3a294e24dbb79550f2cefef86fe06cf",
    },
    "static/app.js": {
        "pattern": "app.js.gz.b64.part*",
        "sha256": "1a6dafabb637dc477143c3666d519f4d9d7ebe844fca067ee2566af373f5af8c",
    },
}


def reconstruct(target_name, spec):
    parts = sorted(ARCHIVE.glob(spec["pattern"]))
    if not parts:
        raise RuntimeError(f"No archive parts found for {target_name}")
    encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    raw = gzip.decompress(base64.b64decode(encoded))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != spec["sha256"]:
        raise RuntimeError(
            f"SHA-256 mismatch for {target_name}: expected {spec['sha256']}, got {digest}"
        )
    target = ROOT / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    print(f"verified {target_name}  {digest}")


def main():
    for target_name, spec in TARGETS.items():
        reconstruct(target_name, spec)
    print("Salus THIRA Command v0.5 source reconstructed successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
