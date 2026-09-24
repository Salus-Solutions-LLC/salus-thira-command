"""Fail-closed reads after delta discovery, including a concurrent move."""

import os
import sys
import types

sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
try:
    import httpx
except ModuleNotFoundError:
    sys.modules["httpx"]=types.ModuleType("httpx")
try:
    import azure.identity
except ModuleNotFoundError:
    azure=types.ModuleType("azure")
    identity=types.ModuleType("azure.identity")
    identity.ManagedIdentityCredential=object
    azure.identity=identity
    sys.modules["azure"]=azure
    sys.modules["azure.identity"]=identity

from salcapa_m365_intake import GovernedM365Intake, GovernedM365Config, M365IntakeError, M365RouteError

DRIVE="drive-12345678"
ROOT="root-12345678"
PENDING="pending-12345678"
FOLDER="folder-12345678"
ITEM="item-12345678"
OUTSIDE="outside-12345678"

class Response:
    def __init__(self,status,payload=None,content=b""):
        self.status_code,self.payload,self.content,self.headers=status,payload or {},content,{}
    def json(self): return self.payload

class Client:
    def __init__(self):
        self.ancestor_parent=PENDING
        self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append(url)
        if url.endswith("/"+ITEM):
            return Response(200,{"id":ITEM,"name":"x.txt","file":{},"eTag":'"one"',
                                 "size":3,"parentReference":{"id":FOLDER}})
        if url.endswith("/"+FOLDER):
            return Response(200,{"id":FOLDER,"name":"Sub","folder":{},
                                 "parentReference":{"id":self.ancestor_parent}})
        if url.endswith("/"+OUTSIDE):
            return Response(404)
        if url.endswith("/"+ITEM+"/content"):
            assert kwargs["headers"]["If-Match"]=='"one"'
            return Response(200,content=b"abc")
        raise AssertionError("Unexpected request")

class Credential:
    def get_token(self,*args): return types.SimpleNamespace(token="test")

def check():
    client=Client()
    config=GovernedM365Config("tenant-12345678","client-12345678","identity-12345678",DRIVE,ROOT)
    intake=GovernedM365Intake(config,client=client,credential=Credential())
    intake._token=("test",9999999999)
    row=dict(id=ITEM,name="x.txt",etag='"one"',size=3,parent_id=FOLDER,
             mime_type="text/plain",ctag="",last_modified="2026-09-24T00:00:00Z",
             source_owner="",source_owner_id="",last_modified_by="",web_url="")
    assert intake.read_scoped_document(row,pending_folder_id=PENDING,
                                      required_ancestor_id=FOLDER).relative_path=="10 Pending Classification/Sub/x.txt"
    client.calls.clear()
    try: intake.read_scoped_document(row,pending_folder_id=PENDING,
                                     required_ancestor_id="enterprise-12345678")
    except M365RouteError: pass
    else: raise AssertionError("unassigned source was accepted as enterprise")
    assert not any(url.endswith("/content") for url in client.calls)
    client.calls.clear()
    client.ancestor_parent=OUTSIDE
    try: intake.read_scoped_document(row,pending_folder_id=PENDING)
    except M365IntakeError: pass
    else: raise AssertionError("Moved-out source was read")
    assert not any(url.endswith("/content") for url in client.calls)
    print("scoped read smoke passed")

if __name__=="__main__": check()
