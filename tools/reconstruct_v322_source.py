#!/usr/bin/env python3
import hashlib, json, runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ARCH=ROOT/'source_archives'/'v3.22'; manifest=json.loads((ARCH/'manifest.json').read_text()); delta_path=ARCH/'delta.json'
if hashlib.sha256(delta_path.read_bytes()).hexdigest()!=manifest['delta_sha256']: raise SystemExit('Invalid v3.22 delta digest')
delta=json.loads(delta_path.read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''
def state(kind):
    key='target_sha256' if kind=='target' else 'baseline_sha256'
    return all(digest(ROOT/rel)==meta[key] for rel,meta in manifest['files'].items())
if state('target'):
    for rel,meta in manifest['files'].items(): print(f'already reconstructed {rel} {meta["target_sha256"]}')
    raise SystemExit(0)
if not state('baseline'): runpy.run_path(str(ROOT/'tools'/'reconstruct_v33_source.py'),run_name='__main__')
if not state('baseline'): raise SystemExit('Unable to establish exact SalCAPA v3.3 baseline')
for rel,spec in delta['files'].items():
    path=ROOT/rel; text=path.read_text()
    if hashlib.sha256(text.encode()).hexdigest()!=spec['baseline_sha256']: raise SystemExit(f'v3.22 baseline mismatch: {rel}')
    for op in spec['operations']:
        actual=text.count(op['old'])
        if actual!=op['count']: raise SystemExit(f'v3.22 operation mismatch: {rel}; expected {op["count"]}, found {actual}')
        text=text.replace(op['old'],op['new'])
    data=text.encode()
    if len(data)!=spec['target_size_bytes'] or hashlib.sha256(data).hexdigest()!=spec['target_sha256']: raise SystemExit(f'v3.22 reconstruction failed: {rel}')
    path.write_bytes(data); print(f'reconstructed {rel} {spec["target_sha256"]}')
