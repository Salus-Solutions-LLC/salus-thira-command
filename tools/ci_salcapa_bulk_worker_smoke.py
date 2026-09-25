"""Gated worker consumes scoped leases and persists per-item outcomes."""

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


def check():
    with tempfile.TemporaryDirectory() as directory:
        path=os.path.join(directory,"worker.sqlite")
        def connect():
            conn=sqlite3.connect(path)
            conn.row_factory=sqlite3.Row
            return conn
        row=lambda i: dict(id=f"file-{i:08d}",name=f"{i}.txt",etag=f'"{i}"',
                           parent_id="pending-12345678",size=3,mime_type="text/plain",
                           ctag="",last_modified="2026-09-24T00:00:00Z",
                           source_owner="",source_owner_id="",last_modified_by="",web_url="",
                           lease_owner=f"owner-{i}",attempts=1)
        files=[row(1),row(2)]
        class Intake:
            def __init__(self,config): pass
            def verify_sibling_folder(self,pending,customer):
                return pending=="pending-12345678" and customer=="customer-12345678"
            def read_scoped_document(self,item,**kwargs):
                assert kwargs["pending_folder_id"]=="pending-12345678"
                assert kwargs["required_ancestor_id"] in ("enterprise-12345678",None)
                if item["id"]==files[0]["id"]:
                    raise promotion.M365RouteError("unassigned source")
                return SimpleNamespace(item_id=item["id"],name=item["name"],
                    relative_path="10 Pending Classification/2.txt",content=b"two",
                    size=3,mime_type="text/plain",sha256="a"*64,etag=item["etag"],
                    ctag="",last_modified="2026-09-24T00:00:00Z",source_owner="",
                    source_owner_id="",last_modified_by="",web_url="")
        class Writer:
            def __init__(self,*args): self.destination=SimpleNamespace(drive_id="target-12345678")
            def put_verified(self,*args): return {"item_id":"new-12345678","web_url":"https://example.test/verified","etag":"new"}
            def archive_verified_source(self,*args): return {"item_id":"archived-12345678","web_url":"https://example.test/archive","etag":"archived"}
        saved={name:getattr(promotion,name) for name in (
            "GovernedM365Intake","GraphKnowledgeWriter","discover","resolve_pending",
            "claim_work","complete_work","automatic_classification")}
        previous=os.environ.get("SALUS_KNOWLEDGE_BULK_DELTA")
        previous_route=os.environ.get("SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID")
        previous_customer=os.environ.get("SALUS_M365_CUSTOMER_BATCH_STAGING_FOLDER_ITEM_ID")
        outcomes=[]
        try:
            os.environ["SALUS_KNOWLEDGE_BULK_DELTA"]="1"
            os.environ["SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID"]="enterprise-12345678"
            promotion.GovernedM365Intake=Intake
            promotion.GraphKnowledgeWriter=Writer
            promotion.discover=lambda *args,**kwargs: {"pages":1}
            promotion.resolve_pending=lambda *args: "pending-12345678"
            promotion.claim_work=lambda *args,**kwargs: files
            promotion.complete_work=lambda *args,**kwargs: outcomes.append((
                args[3]["id"],kwargs["success"],kwargs.get("hold",False)))
            promotion.GovernedM365Config.from_environment=lambda: SimpleNamespace(drive_id="drive-12345678")
            promotion.KnowledgeDestinationConfig.from_environment=lambda: SimpleNamespace()
            promotion.automatic_classification=lambda *args,**kwargs: ({
                "extraction":{"status":"Complete"},"target_folder":"05 Research and Reference",
                "rationale":"Enterprise source","permit_products":["SalCAPA"]},"")
            app=App()
            promotion.register_knowledge_promotion(app,dict(Request=object,HTTPException=Exception,
                db=connect,now=lambda:"2026-09-24T00:00:00Z",auth_context=lambda request:{"role":"System Administrator"}))
            result=app.state.process_knowledge_pending("test actor")
            assert result["automatically_promoted"]==1 and result["automatic_retry_required"]==1,result
            assert outcomes==[(files[0]["id"],False,True),(files[1]["id"],True,False)],outcomes
            # The existing Salus pending root is eligible only with a distinct,
            # verified customer staging sibling. No material is moved.
            files[:]=[row(3)]
            os.environ["SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID"]="pending-12345678"
            os.environ["SALUS_M365_CUSTOMER_BATCH_STAGING_FOLDER_ITEM_ID"]="customer-12345678"
            root_result=app.state.process_knowledge_pending("test actor")
            assert root_result["automatically_promoted"]==1,root_result
            assert outcomes[-1]==(files[0]["id"],True,False),outcomes
            os.environ["SALUS_M365_CUSTOMER_BATCH_STAGING_FOLDER_ITEM_ID"]="pending-12345678"
            try:
                app.state.process_knowledge_pending("test actor")
            except promotion.KnowledgePromotionError:
                pass
            else:
                raise AssertionError("same-folder customer staging must fail closed")
        finally:
            for name,value in saved.items(): setattr(promotion,name,value)
            if previous is None: os.environ.pop("SALUS_KNOWLEDGE_BULK_DELTA",None)
            else: os.environ["SALUS_KNOWLEDGE_BULK_DELTA"]=previous
            if previous_route is None: os.environ.pop("SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID",None)
            else: os.environ["SALUS_M365_ENTERPRISE_INTAKE_FOLDER_ITEM_ID"]=previous_route
            if previous_customer is None: os.environ.pop("SALUS_M365_CUSTOMER_BATCH_STAGING_FOLDER_ITEM_ID",None)
            else: os.environ["SALUS_M365_CUSTOMER_BATCH_STAGING_FOLDER_ITEM_ID"]=previous_customer
    print("bulk worker smoke passed")


if __name__=="__main__": check()
