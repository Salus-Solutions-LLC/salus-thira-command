#!/usr/bin/env python3
import base64, gzip, hashlib, json, runpy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; ARCH=ROOT/'source_archives'/'v2.7'; manifest=json.loads((ARCH/'manifest.json').read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''
def state(kind):
    key='target_sha256' if kind=='target' else 'baseline_sha256'; return all(digest(ROOT/rel)==meta[key] for rel,meta in manifest['files'].items())
if state('target'):
    for rel,meta in manifest['files'].items(): print(f'already reconstructed {rel} {meta["target_sha256"]}')
    raise SystemExit(0)
if not state('baseline'): runpy.run_path(str(ROOT/'tools'/'reconstruct_v26_source.py'),run_name='__main__')
if not state('baseline'): raise SystemExit('Unable to establish exact SalCAPA v2.6 baseline')
parts=[]
for meta in manifest['delta']['chunks']:
    value=(ARCH/meta['path']).read_text()
    if len(value)!=meta['chars'] or hashlib.sha256(value.encode()).hexdigest()!=meta['sha256']: raise SystemExit('Invalid v2.7 delta chunk')
    parts.append(value)
compressed=base64.b64decode(''.join(parts),validate=True); raw=gzip.decompress(compressed)
if len(compressed)!=manifest['delta']['gzip_size_bytes'] or hashlib.sha256(compressed).hexdigest()!=manifest['delta']['gzip_sha256'] or hashlib.sha256(raw).hexdigest()!=manifest['delta']['json_sha256']: raise SystemExit('v2.7 delta verification failed')
delta=json.loads(raw.decode())
for rel,spec in delta['files'].items():
    path=ROOT/rel; lines=path.read_text().splitlines(keepends=True)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=spec['baseline_sha256']: raise SystemExit(f'v2.7 baseline mismatch: {rel}')
    for op in reversed(spec['operations']): lines[op['i1']:op['i2']]=op['lines']
    out=''.join(lines).encode()
    if len(out)!=spec['target_size_bytes'] or hashlib.sha256(out).hexdigest()!=spec['target_sha256']: raise SystemExit(f'v2.7 reconstruction failed: {rel}')
    path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(out); print(f'reconstructed {rel} {spec["target_sha256"]}')
