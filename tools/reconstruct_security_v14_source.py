#!/usr/bin/env python3
import base64,gzip,hashlib,json,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ARCH=ROOT/'source_archives'/'security-codeql-v14'
manifest=json.loads((ARCH/'manifest.json').read_text()); target=manifest['files']['app.py']; path=ROOT/'app.py'
digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ''
if digest(path)==target['target_sha256']: raise SystemExit(0)
if digest(path)!=target['baseline_sha256']: runpy.run_path(str(ROOT/'tools'/'reconstruct_v14_source.py'),run_name='__main__')
if digest(path)!=target['baseline_sha256']: raise SystemExit('Unable to establish exact v1.4 baseline')
parts=[]
for meta in manifest['delta']['chunks']:
 text=(ARCH/meta['path']).read_text()
 if len(text)!=meta['chars'] or hashlib.sha256(text.encode()).hexdigest()!=meta['sha256']: raise SystemExit('Invalid security delta chunk')
 parts.append(text)
compressed=base64.b64decode(''.join(parts),validate=True); raw=gzip.decompress(compressed)
if len(compressed)!=manifest['delta']['gzip_size_bytes'] or hashlib.sha256(compressed).hexdigest()!=manifest['delta']['gzip_sha256'] or hashlib.sha256(raw).hexdigest()!=manifest['delta']['json_sha256']: raise SystemExit('Security delta verification failed')
spec=json.loads(raw.decode())['files']['app.py']; lines=path.read_text().splitlines(keepends=True)
for op in reversed(spec['operations']): lines[op['i1']:op['i2']]=op['lines']
out=''.join(lines).encode()
if len(out)!=target['target_size_bytes'] or hashlib.sha256(out).hexdigest()!=target['target_sha256']: raise SystemExit('Security target verification failed')
path.write_bytes(out); print(f'reconstructed app.py {target["target_sha256"]}')
