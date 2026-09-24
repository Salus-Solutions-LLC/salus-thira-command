"""Gated promotion worker indexes verified archived ZIP members independently."""

import hashlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import zipfile
from types import SimpleNamespace

sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import salcapa_knowledge_promotion as promotion


class App:
    def __init__(self): self.state=SimpleNamespace()
    def post(self,*args,**kwargs): return lambda fn: fn
    def get(self,*args,**kwargs): return lambda fn: fn
    def on_event(self,*args,**kwargs): return lambda fn: fn


def check():
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w") as archive:
        archive.writestr("reports/a.txt",b"First member")
        archive.writestr("reports/b.txt",b"Second member")
    source=buffer.getvalue()
    sha=hashlib.sha256(source).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        path=os.path.join(directory,"zip-worker.sqlite")
        def connect():
            conn=sqlite3.connect(path)
            conn.row_factory=sqlite3.Row
            return conn
        conn=connect()
        promotion._init_tables(conn)
        conn.execute("""INSERT INTO m365_knowledge_candidates
          (source_drive_id,source_item_id,source_name,source_relative_path,source_etag,
           source_sha256,source_size,source_modified_at,source_owner,discovered_at,
           status,source_archive_item_id,classification_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          ("drive-12345678","item-12345678","bundle.zip",
           "10 Pending Classification/Enterprise/bundle.zip",'"old"',sha,len(source),
           "2026-09-24T00:00:00Z","","2026-09-24T00:00:00Z",
           "Ingested and Verified","archived-12345678",
           json.dumps({"automation":{"source_route_folder_id":"enterprise-12345678"},
                       "extraction":{"status":"Automatic Retry Required"}})))
        conn.commit();conn.close()
        class Writer:
            def __init__(self,*args): pass
            def verify_already_archived_source(self,item_id,source_sha,*,include_content=False):
                assert item_id=="archived-12345678" and source_sha==sha and include_content
                return {"item_id":item_id,"content":source}
        saved={name:getattr(promotion,name) for name in (
            "GovernedM365Intake","GraphKnowledgeWriter","discover","resolve_pending","claim_work")}
        original_decode=promotion.full_processing._decode_media
        previous={name:os.environ.get(name) for name in (
            "SALUS_KNOWLEDGE_BULK_DELTA","SALUS_KNOWLEDGE_ZIP_MEMBERS",
            "SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID")}
        try:
            os.environ.update({"SALUS_KNOWLEDGE_BULK_DELTA":"1",
                "SALUS_KNOWLEDGE_ZIP_MEMBERS":"1",
                "SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID":"enterprise-12345678"})
            promotion.GovernedM365Intake=lambda config: object()
            promotion.GraphKnowledgeWriter=Writer
            promotion.discover=lambda *args,**kwargs: {"pages":0}
            promotion.resolve_pending=lambda *args: "pending-12345678"
            promotion.claim_work=lambda *args,**kwargs: []
            promotion.GovernedM365Config.from_environment=lambda: SimpleNamespace(drive_id="drive-12345678")
            promotion.KnowledgeDestinationConfig.from_environment=lambda: SimpleNamespace()
            promotion.full_processing._decode_media=lambda content,name,mime,**kwargs: (
                content.decode(),"test decoder",False,"test","1")
            app=App()
            promotion.register_knowledge_promotion(app,dict(Request=object,HTTPException=Exception,
                db=connect,now=lambda:"2026-09-24T00:00:01Z",
                auth_context=lambda request:{"role":"System Administrator"}))
            app.state.process_knowledge_pending("test actor")
            conn=connect()
            assert conn.execute("SELECT status FROM m365_zip_jobs").fetchone()[0]=="Complete"
            rows=conn.execute("SELECT ordinal,content_text,status FROM m365_zip_member_index ORDER BY ordinal").fetchall()
            assert [(r["ordinal"],r["content_text"],r["status"]) for r in rows]==[
                (0,"First member","Indexed"),(1,"Second member","Indexed")]
            classification=json.loads(conn.execute(
                "SELECT classification_json FROM m365_knowledge_candidates").fetchone()[0])
            assert classification["extraction"]["status"]=="Complete"
            conn.close()
        finally:
            for name,value in saved.items(): setattr(promotion,name,value)
            promotion.full_processing._decode_media=original_decode
            for name,value in previous.items():
                if value is None: os.environ.pop(name,None)
                else: os.environ[name]=value
    print("bulk ZIP worker smoke passed")


if __name__=="__main__": check()
