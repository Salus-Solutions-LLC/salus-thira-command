#!/usr/bin/env python3
import base64, gzip, hashlib, json, runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/'source_archives'/'v1.2'
manifest=json.loads((ARCH/'manifest.json').read_text(encoding='utf-8'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''
def state(kind):
    key='target_sha256' if kind=='target' else 'baseline_sha256'
    return all(digest(ROOT/rel)==meta[key] for rel,meta in manifest['files'].items())
if state('target'):
    for rel,meta in manifest['files'].items(): print(f'already reconstructed {rel} {meta["target_sha256"]}')
    raise SystemExit(0)
if not state('baseline'):
    v11=ROOT/'tools'/'reconstruct_v11_source.py'
    if not v11.is_file(): raise SystemExit('Missing v1.1 reconstruction baseline')
    runpy.run_path(str(v11),run_name='__main__')
if not state('baseline'): raise SystemExit('Unable to establish the exact v1.1 baseline for v1.2 reconstruction')
parts=[]
for meta in manifest['delta']['chunks']:
    path=ARCH/meta['path']
    if not path.is_file(): raise SystemExit(f'Missing v1.2 delta chunk: {path}')
    text=path.read_text(encoding='ascii')
    if len(text)!=meta['chars']: raise SystemExit(f'v1.2 delta chunk length mismatch: {meta["path"]}')
    if hashlib.sha256(text.encode()).hexdigest()!=meta['sha256']: raise SystemExit(f'v1.2 delta chunk SHA-256 mismatch: {meta["path"]}')
    parts.append(text)
compressed=base64.b64decode(''.join(parts),validate=True)
if len(compressed)!=manifest['delta']['gzip_size_bytes']: raise SystemExit('v1.2 delta gzip size mismatch')
if hashlib.sha256(compressed).hexdigest()!=manifest['delta']['gzip_sha256']: raise SystemExit('v1.2 delta gzip SHA-256 mismatch')
raw=gzip.decompress(compressed)
if hashlib.sha256(raw).hexdigest()!=manifest['delta']['json_sha256']: raise SystemExit('v1.2 delta JSON SHA-256 mismatch')
delta=json.loads(raw.decode())
for rel,spec in delta['files'].items():
    path=ROOT/rel; base=path.read_bytes()
    if hashlib.sha256(base).hexdigest()!=spec['baseline_sha256']: raise SystemExit(f'v1.1 baseline SHA-256 mismatch before v1.2 delta: {rel}')
    lines=base.decode().splitlines(keepends=True)
    for op in reversed(spec['operations']): lines[op['i1']:op['i2']]=op['lines']
    out=''.join(lines).encode()
    if len(out)!=spec['target_size_bytes'] or hashlib.sha256(out).hexdigest()!=spec['target_sha256']: raise SystemExit(f'v1.2 target verification failed: {rel}')
    path.write_bytes(out); print(f'reconstructed {rel} {spec["target_sha256"]}')
