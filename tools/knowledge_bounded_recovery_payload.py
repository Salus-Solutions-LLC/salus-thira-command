"""Deterministic bounded source bundle; compression avoids Linux's per-argument limit."""
import base64
import hashlib
import json
from pathlib import Path
import zlib
MODULES = (('salus_postsearch_support','live_knowledge_postsearch_resume.py'),
           ('salus_baseline_support','live_knowledge_baseline_proposal.py'),
           ('__main__','live_knowledge_bounded_recovery_plan.py'))
MAX_RAW = 262144


def bundle(root):
    modules=[]
    for name,filename in MODULES:
        code=(Path(root)/'tools'/filename).read_bytes()
        modules.append({'name':name,'sha256':hashlib.sha256(code).hexdigest(),'source':base64.b64encode(code).decode()})
    raw=json.dumps(modules,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
    assert len(raw)<=MAX_RAW
    encoded=base64.b64encode(zlib.compress(raw,9)).decode()
    assert len(encoded)+4096<128000
    return encoded,hashlib.sha256(raw).hexdigest()


if __name__=='__main__':
    import sys
    encoded,checksum=bundle(Path(__file__).resolve().parent.parent)
    print(checksum if len(sys.argv)>1 and sys.argv[1]=='--sha256' else encoded)
