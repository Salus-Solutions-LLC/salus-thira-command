"""Verify resumable ZIP member indexing through the production PostgreSQL adapter."""

import hashlib
import io
import os
import sys
import zipfile

sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from database import connect_database
from salcapa_zip_index import enqueue,process_page


def check():
    assert os.getenv("SALUS_DB_BACKEND")=="postgres"
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w") as archive:
        for number in range(25):
            archive.writestr(f"folder/{number:02}.txt",f"member {number}")
    source=buffer.getvalue()
    conn=connect_database()
    try:
        enqueue(conn,920024,hashlib.sha256(source).hexdigest(),"archive-920024",now=100)
    finally:
        conn.close()
    try:
        decode=lambda blob,name,mime: blob.decode("utf-8")
        assert process_page(connect_database,920024,source,decode,limit=20,now=101)["next_ordinal"]==20
        assert process_page(connect_database,920024,source,decode,limit=20,now=102)["status"]=="Complete"
        conn=connect_database()
        try:
            assert conn.execute("SELECT COUNT(*) FROM m365_zip_member_index WHERE status='Indexed'").fetchone()[0]==25
            assert conn.execute("SELECT content_text FROM m365_zip_member_index WHERE candidate_id=? AND ordinal=?",
                                (920024,24)).fetchone()[0]=="member 24"
        finally:
            conn.close()
    finally:
        conn=connect_database()
        try:
            conn.execute("DROP TABLE IF EXISTS m365_zip_member_index")
            conn.execute("DROP TABLE IF EXISTS m365_zip_jobs")
            conn.commit()
        finally:
            conn.close()
    print("PostgreSQL ZIP member index smoke passed")


if __name__=="__main__": check()
