#!/usr/bin/env python3
import os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app
from storage import LocalStorage,StorageError

def denied(fn):
    try:
        fn()
    except StorageError:
        return
    raise AssertionError('unsafe storage key was accepted')

def main():
    with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as outside_dir:
        store=LocalStorage(root_dir)
        store.put_bytes('tenant/1/evidence/2/object.bin',b'ok')
        assert store.get_bytes('tenant/1/evidence/2/object.bin')==b'ok'
        for key in ('../escape','tenant/../escape','/absolute','tenant//escape','tenant/./escape','tenant\\..\\escape',''):
            denied(lambda key=key: store._path(key))
        outside=Path(outside_dir)
        link=Path(root_dir)/'escape-link'
        try:
            link.symlink_to(outside,target_is_directory=True)
            denied(lambda: store._path('escape-link/object.bin'))
        except (OSError,NotImplementedError):
            pass

    original=app.storage.health
    try:
        def fail_health():
            raise RuntimeError('sensitive-internal-storage-detail')
        app.storage.health=fail_health
        response=TestClient(app.app).get('/health/ready')
        text=response.text
        assert 'sensitive-internal-storage-detail' not in text
        assert 'Storage unavailable. Reference:' in text
    finally:
        app.storage.health=original
    assert app.sql_table_name('evidence')=='evidence'
    try:
        app.sql_table_name('evidence; DROP TABLE evidence')
    except Exception:
        pass
    else:
        raise AssertionError('unsafe SQL table identifier was accepted')
    print('SECURITY_REGRESSION_PASS')

if __name__=='__main__':
    main()
