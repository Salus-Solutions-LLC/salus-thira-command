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
from salcapa_bulk_delta import discover, _scoped_link
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
            "size":size,"eTag":f'"{i}"',"parentReference":{"id":PENDING},
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
        # Fifty pages, 200 files each, nested folder record, and an oversize file.
        for n in range(50):
            url=BASE if n==0 else BASE+f"?page={n}"
            values=[file(n*200+i) for i in range(200)]
            if n==0:
                values[0]={"id":"folder-12345678","name":"Subfolder","folder":{},
                           "parentReference":{"id":PENDING},"size":0}
                values[1]=file(1,size=101)
            link=BASE+f"?page={n+1}" if n<49 else BASE+"?token=done"
            client.pages[url]=Response(200,{"value":values,
                "@odata.nextLink" if n<49 else "@odata.deltaLink":link})
        for _ in range(5):
            result=discover(intake,connect,max_pages=10,now=100)
        assert result=={"pages":10,"complete":True},result
        with connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM m365_bulk_items").fetchone()[0]==10000
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
        client.pages[BASE]=Response(200,{"value":[file(200)],
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
    print("bulk delta smoke passed")


if __name__=="__main__": check()
