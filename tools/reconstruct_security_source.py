#!/usr/bin/env python3
import base64,gzip,hashlib,json,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/'source_archives'/'security-codeql'
manifest=json.loads((ARCH/'manifest.json').read_text(encoding='utf-8'))
target=manifest['files']['app.py']
path=ROOT/'app.py'
digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ''
if digest(path)==target['target_sha256']:
    print(f'already reconstructed app.py {target["target_sha256"]}')
    raise SystemExit(0)
if digest(path)!=target['baseline_sha256']:
    runpy.run_path(str(ROOT/'tools'/'reconstruct_v13_source.py'),run_name='__main__')
if digest(path)!=target['baseline_sha256']:
    raise SystemExit('Unable to establish exact v1.3 baseline')
parts=[]
for meta in manifest['delta']['chunks']:
    text=(ARCH/meta['path']).read_text(encoding='ascii')
    if len(text)!=meta['chars'] or hashlib.sha256(text.encode()).hexdigest()!=meta['sha256']:
        raise SystemExit(f'Invalid security delta chunk: {meta["path"]}')
    parts.append(text)
compressed=base64.b64decode(''.join(parts),validate=True)
if len(compressed)!=manifest['delta']['gzip_size_bytes'] or hashlib.sha256(compressed).hexdigest()!=manifest['delta']['gzip_sha256']:
    raise SystemExit('Security delta gzip verification failed')
raw=gzip.decompress(compressed)
if hashlib.sha256(raw).hexdigest()!=manifest['delta']['json_sha256']:
    raise SystemExit('Security delta JSON verification failed')
spec=json.loads(raw.decode())['files']['app.py']
lines=path.read_text(encoding='utf-8').splitlines(keepends=True)
for op in reversed(spec['operations']):
    lines[op['i1']:op['i2']]=op['lines']
out=''.join(lines).encode()
if len(out)!=target['target_size_bytes'] or hashlib.sha256(out).hexdigest()!=target['target_sha256']:
    raise SystemExit('Security-remediated app.py verification failed')
path.write_bytes(out)
print(f'reconstructed app.py {target["target_sha256"]}')
