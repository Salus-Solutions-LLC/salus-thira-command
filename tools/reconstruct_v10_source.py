#!/usr/bin/env python3
import base64, gzip, hashlib, json, runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/'source_archives'/'v1.0'
manifest=json.loads((ARCH/'manifest.json').read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''

def state(kind):
    key='target_sha256' if kind=='target' else 'baseline_sha256'
    return all(digest(ROOT/rel)==meta[key] for rel,meta in manifest['files'].items())

if state('target'):
    for rel,meta in manifest['files'].items(): print(f'already reconstructed {rel} {meta["target_sha256"]}')
    raise SystemExit(0)

# A GitHub checkout may still contain the native v0.8-era files. Reconstruct the
# exact v0.9 baseline only when the v1.0 baseline is not already present.
if not state('baseline'):
    v09=ROOT/'tools'/'reconstruct_v09_source.py'
    if not v09.is_file(): raise SystemExit('Missing v0.9 reconstruction baseline')
    runpy.run_path(str(v09),run_name='__main__')
if not state('baseline'):
    raise SystemExit('Unable to establish the exact v0.9 baseline for v1.0 reconstruction')

parts=[]
for meta in manifest['delta']['chunks']:
    path=ARCH/meta['path']
    if not path.is_file(): raise SystemExit(f'Missing v1.0 delta chunk: {path}')
    text=path.read_text(encoding='ascii')
    if len(text)!=meta['chars']: raise SystemExit(f'v1.0 delta chunk length mismatch: {meta["path"]}')
    if hashlib.sha256(text.encode('ascii')).hexdigest()!=meta['sha256']: raise SystemExit(f'v1.0 delta chunk SHA-256 mismatch: {meta["path"]}')
    parts.append(text)
try: compressed=base64.b64decode(''.join(parts),validate=True)
except Exception as exc: raise SystemExit(f'Invalid v1.0 delta base64: {exc}')
if len(compressed)!=manifest['delta']['gzip_size_bytes']: raise SystemExit('v1.0 delta gzip size mismatch')
if hashlib.sha256(compressed).hexdigest()!=manifest['delta']['gzip_sha256']: raise SystemExit('v1.0 delta gzip SHA-256 mismatch')
raw=gzip.decompress(compressed)
if hashlib.sha256(raw).hexdigest()!=manifest['delta']['json_sha256']: raise SystemExit('v1.0 delta JSON SHA-256 mismatch')
delta=json.loads(raw.decode('utf-8'))
for rel,spec in delta['files'].items():
    path=ROOT/rel; baseline=path.read_bytes()
    if hashlib.sha256(baseline).hexdigest()!=spec['baseline_sha256']: raise SystemExit(f'v0.9 baseline SHA-256 mismatch before v1.0 delta: {rel}')
    lines=baseline.decode('utf-8').splitlines(keepends=True)
    for op in reversed(spec['operations']): lines[op['i1']:op['i2']]=op['lines']
    out=''.join(lines).encode('utf-8')
    if len(out)!=spec['target_size_bytes']: raise SystemExit(f'v1.0 target size mismatch after delta: {rel}')
    got=hashlib.sha256(out).hexdigest()
    if got!=spec['target_sha256']: raise SystemExit(f'v1.0 target SHA-256 mismatch after delta: {rel}')
    path.write_bytes(out); print(f'reconstructed {rel} {got}')
