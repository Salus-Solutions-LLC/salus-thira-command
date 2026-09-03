#!/usr/bin/env python3
"""Build the deterministic v1.16 -> SalCAPA v2.0 generated-source archive."""
import base64, difflib, gzip, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT.parent/'v116-base'
ARCHIVE=ROOT/'source_archives'/'v2.0'
FILES=('app.py','static/app.js','static/index.html','database.py','portable_backup.py')
def sha(data): return hashlib.sha256(data).hexdigest()
delta={'files':{}}; manifest_files={}
for relative in FILES:
    baseline=(BASE/relative).read_bytes(); target=(ROOT/relative).read_bytes()
    before=baseline.decode().splitlines(keepends=True); after=target.decode().splitlines(keepends=True); operations=[]
    for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None,before,after,autojunk=False).get_opcodes():
        if tag!='equal': operations.append({'i1':i1,'i2':i2,'lines':after[j1:j2]})
    delta['files'][relative]={'baseline_sha256':sha(baseline),'target_sha256':sha(target),'target_size_bytes':len(target),'operations':operations}
    manifest_files[relative]={'baseline_sha256':sha(baseline),'target_sha256':sha(target),'target_size_bytes':len(target)}
raw=json.dumps(delta,sort_keys=True,separators=(',',':')).encode(); compressed=gzip.compress(raw,compresslevel=9,mtime=0); encoded=base64.b64encode(compressed).decode()
ARCHIVE.mkdir(parents=True,exist_ok=True); part=ARCHIVE/'delta.json.gz.b64.part01'; part.write_text(encoded)
manifest={'delta':{'chunks':[{'chars':len(encoded),'path':part.name,'sha256':sha(encoded.encode())}],'gzip_sha256':sha(compressed),'gzip_size_bytes':len(compressed),'json_sha256':sha(raw)},'files':manifest_files,'version':'2.0.0'}
(ARCHIVE/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n'); print(json.dumps(manifest,indent=2,sort_keys=True))
