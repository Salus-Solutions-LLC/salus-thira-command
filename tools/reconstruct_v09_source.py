#!/usr/bin/env python3
import base64, gzip, hashlib, json, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = ROOT / 'source_archives' / 'v0.9'
manifest = json.loads((ARCH / 'manifest.json').read_text(encoding='utf-8'))

# Reconstruct the exact frozen v0.8 baseline for archived large files.
v08 = ROOT / 'tools' / 'reconstruct_v08_source.py'
if v08.is_file():
    runpy.run_path(str(v08), run_name='__main__')

encoded_parts = []
for meta in manifest['delta']['chunks']:
    path = ARCH / meta['path']
    if not path.is_file():
        raise SystemExit(f'Missing v0.9 delta chunk: {path}')
    text = path.read_text(encoding='ascii')
    if len(text) != meta['chars']:
        raise SystemExit(f'v0.9 delta chunk length mismatch: {meta["path"]}')
    if hashlib.sha256(text.encode('ascii')).hexdigest() != meta['sha256']:
        raise SystemExit(f'v0.9 delta chunk SHA-256 mismatch: {meta["path"]}')
    encoded_parts.append(text)

try:
    compressed = base64.b64decode(''.join(encoded_parts), validate=True)
except Exception as exc:
    raise SystemExit(f'Invalid v0.9 delta base64: {exc}')
if len(compressed) != manifest['delta']['gzip_size_bytes']:
    raise SystemExit('v0.9 delta gzip size mismatch')
if hashlib.sha256(compressed).hexdigest() != manifest['delta']['gzip_sha256']:
    raise SystemExit('v0.9 delta gzip SHA-256 mismatch')
raw = gzip.decompress(compressed)
if hashlib.sha256(raw).hexdigest() != manifest['delta']['json_sha256']:
    raise SystemExit('v0.9 delta JSON SHA-256 mismatch')
delta = json.loads(raw.decode('utf-8'))

for rel, spec in delta['files'].items():
    path = ROOT / rel
    if not path.is_file():
        raise SystemExit(f'Missing v0.8 baseline file for delta: {rel}')
    baseline = path.read_bytes()
    if hashlib.sha256(baseline).hexdigest() != spec['baseline_sha256']:
        raise SystemExit(f'v0.8 baseline SHA-256 mismatch before v0.9 delta: {rel}')
    lines = baseline.decode('utf-8').splitlines(keepends=True)
    for op in reversed(spec['operations']):
        lines[op['i1']:op['i2']] = op['lines']
    target = ''.join(lines).encode('utf-8')
    if len(target) != spec['target_size_bytes']:
        raise SystemExit(f'v0.9 target size mismatch after delta: {rel}')
    if hashlib.sha256(target).hexdigest() != spec['target_sha256']:
        raise SystemExit(f'v0.9 target SHA-256 mismatch after delta: {rel}')
    path.write_bytes(target)
    print(f'reconstructed {rel} {spec["target_sha256"]}')
