"""ZIP member indexing checkpoints pages and survives an interrupted decoder."""

import hashlib
import io
import os
import sqlite3
import sys
import tempfile
import warnings
import zipfile

sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from salcapa_zip_index import enqueue,process_page
from salcapa_zip_members import iter_zip_members,zip_entry_count


def check():
    data=io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore",UserWarning)
        with zipfile.ZipFile(data,"w") as archive:
            archive.writestr("folder/",b"")
            archive.writestr("folder/a.txt",b"A")
            archive.writestr("folder/b.txt",b"B")
            archive.writestr("../escape.txt",b"unsafe")
            archive.writestr("folder/a.txt",b"duplicate")
            archive.writestr("folder/c.txt",b"C")
    source=data.getvalue()
    assert zip_entry_count(source)==6
    assert [m["ordinal"] for m in iter_zip_members(source,start=1,limit=2)]==[1,2]
    with tempfile.TemporaryDirectory() as directory:
        path=os.path.join(directory,"zip.sqlite")
        def connect():
            conn=sqlite3.connect(path)
            conn.row_factory=sqlite3.Row
            return conn
        conn=connect()
        sha=hashlib.sha256(source).hexdigest()
        enqueue(conn,42,sha,"archived-12345678",now=100)
        enqueue(conn,42,sha,"archived-12345678",now=100)
        conn.close()
        calls=[]
        def decoder(blob,name,mime):
            calls.append(name)
            return blob.decode("utf-8")
        assert process_page(connect,42,source,decoder,limit=2,now=101)["next_ordinal"]==2
        assert process_page(connect,42,source,decoder,limit=2,now=102)["next_ordinal"]==4
        assert process_page(connect,42,source,decoder,limit=2,now=103)["status"]=="Complete"
        with connect() as conn:
            rows=conn.execute("SELECT ordinal,status FROM m365_zip_member_index ORDER BY ordinal").fetchall()
            assert [(r["ordinal"],r["status"]) for r in rows]==[
                (1,"Indexed"),(2,"Indexed"),(3,"Review"),(4,"Review"),(5,"Indexed")]
            assert conn.execute("SELECT COUNT(*) FROM m365_zip_jobs").fetchone()[0]==1
        assert process_page(connect,42,source,decoder,limit=2,now=110)["busy_or_complete"]
        with connect() as conn:
            assert conn.execute("SELECT attempts FROM m365_zip_member_index WHERE ordinal=3").fetchone()[0]==1
            assert conn.execute("SELECT COUNT(*) FROM m365_zip_member_index").fetchone()[0]==5
        # A transient decoder crash leaves the page uncommitted; lease expiry
        # allows another worker to replay it from the same ordinal.
        conn=connect()
        conn.execute("UPDATE m365_zip_jobs SET next_ordinal=5,status='Pending',next_attempt=0")
        conn.commit();conn.close()
        def interrupted(blob,name,mime): raise RuntimeError("worker died")
        try: process_page(connect,42,source,interrupted,limit=1,now=200)
        except RuntimeError: pass
        else: raise AssertionError("unexpected decoder failure was swallowed")
        assert process_page(connect,42,source,decoder,limit=1,now=201)["busy_or_complete"]
        assert process_page(connect,42,source,decoder,limit=1,now=502)["next_ordinal"]==6
    print("ZIP member index smoke passed")


if __name__=="__main__": check()
