"""Reconcile a source moved to the archive before a lost database commit."""

import hashlib
import os
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import salcapa_knowledge_promotion as promotion


class App:
    def __init__(self): self.state=SimpleNamespace()
    def post(self,*args,**kwargs): return lambda fn: fn
    def get(self,*args,**kwargs): return lambda fn: fn
    def on_event(self,*args,**kwargs): return lambda fn: fn


class Response:
    def __init__(self,status,payload=None,content=b""):
        self.status_code,self.payload,self.content,self.headers=status,payload or {},content,{}
    def json(self): return self.payload


class Client:
    def __init__(self): self.parent="archive-12345678"
    def get(self,url,**kwargs):
        if url.endswith("/content"): return Response(200,content=b"exact-source")
        return Response(200,{"id":"item-12345678","file":{},"eTag":"archived","size":12,
            "parentReference":{"id":self.parent},"webUrl":"https://tenant.sharepoint.com/archive"})


def check():
    destination=promotion.KnowledgeDestinationConfig("target-12345678","root-12345678","archive-12345678")
    client=Client()
    writer=promotion.GraphKnowledgeWriter(SimpleNamespace(managed_identity_client_id="unused",drive_id="drive-12345678",max_file_bytes=100),
                                           destination,credential=object(),client=client)
    writer._headers=lambda: {}
    sha=hashlib.sha256(b"exact-source").hexdigest()
    assert writer.verify_already_archived_source("item-12345678",sha)["item_id"]=="item-12345678"
    client.parent="pending-12345678"
    assert writer.verify_already_archived_source("item-12345678",sha) is None
    client.parent="archive-12345678"
    try: writer.verify_already_archived_source("item-12345678","0"*64)
    except promotion.KnowledgePromotionError: pass
    else: raise AssertionError("incorrect archived hash accepted")

    with tempfile.TemporaryDirectory() as directory:
        path=os.path.join(directory,"reconcile.sqlite")
        def connect():
            conn=sqlite3.connect(path)
            conn.row_factory=sqlite3.Row
            return conn
        conn=connect()
        promotion._init_tables(conn)
        conn.execute("""INSERT INTO m365_knowledge_candidates
          (source_drive_id,source_item_id,source_name,source_relative_path,source_etag,
           source_sha256,source_size,source_modified_at,source_owner,discovered_at,
           status,destination_item_id,classification_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          ("drive-12345678","item-12345678","x.txt","10 Pending Classification/x.txt",
           '"old"',sha,12,"2026-09-24T00:00:00Z","","2026-09-24T00:00:00Z",
           "Destination Verified","dest-12345678","{}"))
        conn.commit();conn.close()
        saved={name:getattr(promotion,name) for name in (
            "GovernedM365Intake","GraphKnowledgeWriter","discover","resolve_pending","claim_work")}
        prior=os.environ.get("SALUS_KNOWLEDGE_BULK_DELTA")
        prior_route=os.environ.get("SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID")
        try:
            os.environ["SALUS_KNOWLEDGE_BULK_DELTA"]="1"
            os.environ["SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID"]="enterprise-12345678"
            promotion.GovernedM365Intake=lambda config: object()
            promotion.GraphKnowledgeWriter=lambda *args: writer
            promotion.discover=lambda *args,**kwargs: {"pages":0}
            promotion.resolve_pending=lambda *args: "pending-12345678"
            promotion.claim_work=lambda *args,**kwargs: []
            promotion.GovernedM365Config.from_environment=lambda: SimpleNamespace(drive_id="drive-12345678")
            promotion.KnowledgeDestinationConfig.from_environment=lambda: destination
            app=App()
            promotion.register_knowledge_promotion(app,dict(Request=object,HTTPException=Exception,
                db=connect,now=lambda:"2026-09-24T00:00:01Z",auth_context=lambda request:{"role":"System Administrator"}))
            result=app.state.process_knowledge_pending("test actor")
            assert result["automatically_promoted"]==1,result
            conn=connect()
            assert conn.execute("SELECT status FROM m365_knowledge_candidates").fetchone()[0]=="Ingested and Verified"
            assert conn.execute("SELECT event_type FROM m365_knowledge_events").fetchone()[0]=="ArchivedSourceReconciled"
            conn.close()
        finally:
            for name,value in saved.items(): setattr(promotion,name,value)
            if prior is None: os.environ.pop("SALUS_KNOWLEDGE_BULK_DELTA",None)
            else: os.environ["SALUS_KNOWLEDGE_BULK_DELTA"]=prior
            if prior_route is None: os.environ.pop("SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID",None)
            else: os.environ["SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID"]=prior_route
    print("bulk archive reconciliation smoke passed")


if __name__=="__main__": check()
