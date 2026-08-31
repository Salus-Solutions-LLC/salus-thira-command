#!/usr/bin/env python3
"""Fail closed when user, runtime, or workflow entrypoints select stale source."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECONSTRUCT = 'tools/reconstruct_v114_source.py'
VERIFY = 'tools/verify_v114_source.py'
FILES = (
    'README.md',
    'Dockerfile',
    'run_mac_linux.sh',
    'run_windows.bat',
    '.github/workflows/ci.yml',
    '.github/workflows/codeql.yml',
)


for relative in FILES:
    text = (ROOT / relative).read_text(encoding='utf-8').replace('\\', '/')
    missing = [command for command in (RECONSTRUCT, VERIFY) if command not in text]
    if missing:
        raise SystemExit(f'{relative} does not select current verified source: {", ".join(missing)}')

print('RELEASE_ENTRYPOINTS_PASS')
