"""Five pinned modules with unchanged resource limits."""
import base64,hashlib,json,zlib
from pathlib import Path
MODULES=(('salus_postsearch_support','live_knowledge_postsearch_resume.py'),('salus_baseline_support','live_knowledge_baseline_proposal.py'),('salus_streamed_plan_support','live_knowledge_streamed_recovery_plan.py'),('salus_remediation_support','live_knowledge_remediation_proposals.py'),('__main__','live_knowledge_inventory_reconciliation.py'))
def bundle(root):
 rows=[]
 for name,file in MODULES:
  code=(Path(root)/'tools'/file).read_bytes();rows.append({'name':name,'sha256':hashlib.sha256(code).hexdigest(),'source':base64.b64encode(code).decode()})
 raw=json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode();assert len(raw)<=262144
 encoded=base64.b64encode(zlib.compress(raw,9)).decode();assert len(encoded)+4096<128000
 return encoded,hashlib.sha256(raw).hexdigest()
if __name__=='__main__':
 import sys
 encoded,checksum=bundle(Path(__file__).resolve().parent.parent);print(checksum if len(sys.argv)>1 and sys.argv[1]=='--sha256' else encoded)
