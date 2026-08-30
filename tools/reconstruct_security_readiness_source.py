#!/usr/bin/env python3
import base64,gzip,hashlib,json,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ARCH=ROOT/'source_archives'/'security-codeql-readiness'; m=json.loads((ARCH/'manifest.json').read_text()); target=m['files']['app.py']; path=ROOT/'app.py'; digest=lambda: hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''
if digest()==target['target_sha256']: raise SystemExit(0)
if digest()!=target['baseline_sha256']: runpy.run_path(str(ROOT/'tools'/'reconstruct_security_v14_source.py'),run_name='__main__')
if digest()!=target['baseline_sha256']: raise SystemExit('Unable to establish remediated v1.4 baseline')
text=''.join((ARCH/x['path']).read_text() for x in m['delta']['chunks']); comp=base64.b64decode(text,validate=True); raw=gzip.decompress(comp)
if len(comp)!=m['delta']['gzip_size_bytes'] or hashlib.sha256(comp).hexdigest()!=m['delta']['gzip_sha256'] or hashlib.sha256(raw).hexdigest()!=m['delta']['json_sha256']: raise SystemExit('Readiness delta verification failed')
spec=json.loads(raw.decode())['files']['app.py']; lines=path.read_text().splitlines(keepends=True)
for op in reversed(spec['operations']): lines[op['i1']:op['i2']]=op['lines']
out=''.join(lines).encode()
if len(out)!=target['target_size_bytes'] or hashlib.sha256(out).hexdigest()!=target['target_sha256']: raise SystemExit('Readiness target verification failed')
path.write_bytes(out)
