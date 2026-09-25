"""Transactional delta discovery checks without external Microsoft 365 access."""

import os
import sqlite3
import sys
import tempfile
import re
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    import salcapa_m365_intake
except ModuleNotFoundError:
    module=types.ModuleType("salcapa_m365_intake")
    module.GRAPH_ROOT="https://graph.microsoft.com/v1.0"
    module._IDENTIFIER=re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")
    class M365IntakeError(RuntimeError): pass
    module.M365IntakeError=M365IntakeError
    sys.modules["salcapa_m365_intake"]=module
from salcapa_bulk_delta import (
    checkpoint_oversize, discover, claim_work, complete_work, _scoped_link,
)
from salcapa_m365_intake import M365IntakeError


DRIVE = "drive-12345678"
ROOT = "root-12345678"
PENDING = "pending-12345678"
BASE = f"https://graph.microsoft.com/v1.0/drives/{DRIVE}/items/{PENDING}/delta"


class Response:
    def __init__(self, status, payload=None, headers=None):
        self.status_code, self.payload, self.headers = status, payload or {}, headers or {}
    def json(self):
        return self.payload


class Client:
    def __init__(self):
        self.pages = {}
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append(url)
        if url.endswith(f"/items/{ROOT}/children"):
            return Response(200,{"value":[{"id":PENDING,"name":"10 Pending Classification","folder":{}}]})
        return self.pages[url]


class Intake:
    config = SimpleNamespace(drive_id=DRIVE,folder_item_id=ROOT,max_file_bytes=100)
    def __init__(self,client): self.client=client
    def _headers(self): return {}
    @staticmethod
    def _safe_path_component(s):
        if not s or "/" in s or s in (".",".."):
            raise M365IntakeError("bad name")
        return s
    @staticmethod
    def _identity(value): return "", ""
    @staticmethod
    def _trusted_source_url(value): return value or ""


def file(i, *, size=12):
    return {"id":f"file-{i:08d}","name":f"{i}.txt","file":{"mimeType":"text/plain"},
            "size":size,"eTag":f'"{i}"',"parentReference":{"id":f"folder-{i//200:08d}"},
            "lastModifiedDateTime":"2026-09-24T00:00:00Z"}


def check():
    try:
        _scoped_link("https://evil.example/v1.0/drives/"+DRIVE+"/items/"+PENDING+"/delta?x=y",DRIVE,PENDING)
    except M365IntakeError: pass
    else: raise AssertionError("cross-origin continuation accepted")
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory,"ledger.sqlite")
        def connect():
            conn=sqlite3.connect(path)
            conn.row_factory=sqlite3.Row
            return conn
        client=Client()
        intake=Intake(client)
        # Fifty folders followed by 10,000 nested files across fifty full pages.
        for n in range(51):
            url=BASE if n==0 else BASE+f"?page={n}"
            values=[file((n-1)*200+i) for i in range(200)] if n else [
                {"id":f"folder-{i:08d}","name":f"Subfolder {i}","folder":{},
                 "parentReference":{"id":PENDING},"size":0} for i in range(50)]
            if n==1: values[1]=file(1,size=101)
            link=BASE+f"?page={n+1}" if n<50 else BASE+"?token=done"
            client.pages[url]=Response(200,{"value":values,
                "@odata.nextLink" if n<50 else "@odata.deltaLink":link})
        for _ in range(5):
            result=discover(intake,connect,max_pages=10,now=100)
        assert result=={"pages":10,"complete":False},result
        assert discover(intake,connect,max_pages=10,now=101)=={"pages":1,"complete":True}
        with connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM m365_bulk_items").fetchone()[0]==10050
            assert conn.execute("SELECT COUNT(*) FROM m365_bulk_items WHERE kind='file'").fetchone()[0]==10000
            assert conn.execute("SELECT status FROM m365_bulk_items WHERE item_id='file-00000001'").fetchone()[0]=="Oversize"
            conn.execute("UPDATE m365_bulk_items SET status='Done' WHERE item_id='file-00000200'")
            conn.commit()
        client.pages[BASE+"?token=done"]=Response(200,{"value":[file(200),
            {"id":"file-00000300","deleted":{}}],"@odata.deltaLink":BASE+"?token=next"})
        assert discover(intake,connect,max_pages=10,now=200)["pages"]==1
        with connect() as conn:
            assert conn.execute("SELECT status FROM m365_bulk_items WHERE item_id='file-00000200'").fetchone()[0]=="Done"
            assert conn.execute("SELECT status FROM m365_bulk_items WHERE item_id='file-00000300'").fetchone()[0]=="Removed"
        client.pages[BASE+"?token=next"]=Response(429,headers={"Retry-After":"90"})
        assert discover(intake,connect,now=300)["throttled"]
        assert discover(intake,connect,now=350)["busy"]
        client.pages[BASE+"?token=next"]=Response(410)
        assert discover(intake,connect,now=391)["resync"]
        with connect() as conn:
            assert conn.execute("SELECT link FROM m365_bulk_cursors").fetchone()[0]==""
        client.pages[BASE]=Response(200,{"value":[
            {"id":"folder-00000001","name":"Subfolder 1","folder":{},
             "parentReference":{"id":PENDING},"size":0},file(200)],
            "@odata.deltaLink":BASE+"?token=resynced"})
        assert discover(intake,connect,now=392)["complete"]
        with connect() as conn:
            assert conn.execute("SELECT status FROM m365_bulk_items WHERE item_id='file-00000400'").fetchone()[0]=="Removed"
            assert conn.execute("SELECT status FROM m365_bulk_items WHERE item_id='file-00000200'").fetchone()[0]=="Done"
        client.pages[BASE+"?token=resynced"]=Response(200,{"value":[file(10001)],
            "@odata.nextLink":"https://evil.example/?token=bad"})
        try: discover(intake,connect,now=393)
        except M365IntakeError: pass
        else: raise AssertionError("untrusted continuation accepted")
        with connect() as conn:
            assert conn.execute("SELECT link FROM m365_bulk_cursors").fetchone()[0]==BASE+"?token=resynced"
            assert conn.execute("SELECT COUNT(*) FROM m365_bulk_items WHERE item_id='file-00010001'").fetchone()[0]==0
        client.pages[BASE+"?token=resynced"]=Response(200,{"value":[file(10001),file(10002)],
            "@odata.deltaLink":BASE+"?token=fresh"})
        discover(intake,connect,now=600)
        work=claim_work(connect,DRIVE,PENDING,limit=2,now=601)
        assert [row["id"] for row in work]==["file-00010001","file-00010002"]
        assert not claim_work(connect,DRIVE,PENDING,limit=1,now=601)
        assert complete_work(connect,DRIVE,PENDING,work[1],success=False,
                             reason="enterprise_route_assignment_required",hold=True,now=602)
        with connect() as conn:
            assert conn.execute("SELECT status FROM m365_bulk_items WHERE item_id='file-00010002'").fetchone()[0]=="Assignment Required"
        assert complete_work(connect,DRIVE,PENDING,work[0],success=False,reason="source_changed",now=602)
        assert not claim_work(connect,DRIVE,PENDING,limit=1,now=603)
        assert claim_work(connect,DRIVE,PENDING,limit=1,now=632)[0]["id"]=="file-00010001"
        with connect() as conn:
            conn.execute("UPDATE m365_bulk_items SET etag='new' WHERE item_id='file-00010002'")
            conn.commit()
        assert not complete_work(connect,DRIVE,PENDING,work[1],success=True,now=604)
        # A size hold survives restart and cannot be leased for byte processing.
        held = dict(id="file-99999999",parent_id="folder-00000001",name="large.bin",
                    etag='"large-v1"',size=101,relative_path="10 Pending Classification/large.bin",
                    last_modified="2026-09-24T00:00:00Z")
        assert checkpoint_oversize(connect,DRIVE,PENDING,[held],now=700)==1
        with connect() as conn:
            saved=conn.execute("SELECT status,reason,metadata_json FROM m365_bulk_items "
                               "WHERE item_id=?",(held["id"],)).fetchone()
            assert saved["status"]=="Oversize" and saved["reason"]=="file_size_limit"
            assert "large.bin" in saved["metadata_json"]
        assert not any(row["id"]==held["id"] for row in
                       claim_work(connect,DRIVE,PENDING,limit=100,now=701))
    print("bulk delta smoke passed")


if __name__=="__main__": check()
