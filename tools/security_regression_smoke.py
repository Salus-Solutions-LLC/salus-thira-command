#!/usr/bin/env python3
import sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app
from storage import LocalStorage,StorageError
def denied(fn):
 try: fn()
 except StorageError: return
 raise AssertionError('unsafe value accepted')
def main():
 with tempfile.TemporaryDirectory() as root_dir,tempfile.TemporaryDirectory() as outside_dir:
  store=LocalStorage(root_dir); store.put_bytes('tenant/1/evidence/2/object.bin',b'ok')
  assert store.get_bytes('tenant/1/evidence/2/object.bin')==b'ok'
  for key in ('../escape','tenant/../escape','/absolute','tenant//escape','tenant/./escape','tenant\\..\\escape',''): denied(lambda key=key: store._path(key))
  link=Path(root_dir)/'escape-link'
  try: link.symlink_to(Path(outside_dir),target_is_directory=True); denied(lambda: store._path('escape-link/object.bin'))
  except (OSError,NotImplementedError): pass
 original=app.storage.health
 try:
  def fail(): raise RuntimeError('sensitive-internal-storage-detail')
  app.storage.health=fail; text=TestClient(app.app).get('/health/ready').text
  assert 'sensitive-internal-storage-detail' not in text and 'Storage unavailable. Reference:' in text
 finally: app.storage.health=original
 assert app.sql_table_name('evidence')=='evidence'
 denied_sql=False
 try: app.sql_table_name('evidence; DROP TABLE evidence')
 except Exception: denied_sql=True
 assert denied_sql
 print('SECURITY_REGRESSION_PASS')
if __name__=='__main__': main()
