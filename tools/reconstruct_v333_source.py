#!/usr/bin/env python3
import hashlib, json, runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ARCH=ROOT/'source_archives'/'v3.33'; manifest=json.loads((ARCH/'manifest.json').read_text()); delta_path=ARCH/'delta.json'
actual_delta_sha256=hashlib.sha256(delta_path.read_bytes()).hexdigest()
if actual_delta_sha256!=manifest['delta_sha256']: raise SystemExit(f'Invalid v3.33 delta digest: expected {manifest["delta_sha256"]}; actual {actual_delta_sha256}')
delta=json.loads(delta_path.read_text())
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''
def state(kind):
    key='target_sha256' if kind=='target' else 'baseline_sha256'
    return all(digest(ROOT/rel)==meta[key] for rel,meta in manifest['files'].items())
if state('target'):
    for rel,meta in manifest['files'].items(): print(f'already reconstructed {rel} {meta["target_sha256"]}')
    raise SystemExit(0)
if not state('baseline'): runpy.run_path(str(ROOT/'tools'/'reconstruct_v332_source.py'),run_name='__main__')
if not state('baseline'): raise SystemExit('Unable to establish exact SalCAPA v3.32 baseline')
for rel,spec in delta['files'].items():
    path=ROOT/rel; text=path.read_text()
    if hashlib.sha256(text.encode()).hexdigest()!=spec['baseline_sha256']: raise SystemExit(f'v3.33 baseline mismatch: {rel}')
    for op in spec['operations']:
        actual=text.count(op['old'])
        if actual!=op['count']: raise SystemExit(f'v3.33 operation mismatch: {rel}; expected {op["count"]}, found {actual}')
        text=text.replace(op['old'],op['new'])
    data=text.encode()
    if len(data)!=spec['target_size_bytes'] or hashlib.sha256(data).hexdigest()!=spec['target_sha256']: raise SystemExit(f'v3.33 reconstruction failed: {rel}')
    path.write_bytes(data); print(f'reconstructed {rel} {spec["target_sha256"]}')
