#!/usr/bin/env python3
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND','sqlite')
os.environ.setdefault('SALUS_DB_PATH',str(Path(WORKSPACE.name)/'salcapa-v33.db'))
os.environ.setdefault('SALUS_BACKUP_DIR',str(Path(WORKSPACE.name)/'backups'))
os.environ.setdefault('SALUS_LOCAL_STORAGE_DIR',str(Path(WORKSPACE.name)/'attachments'))
os.environ['SALUS_AUTH_MODE']='oidc'
os.environ['SALUS_ENV']='development'
os.environ['SALUS_SEED_DEMO']='1'
os.environ['SALUS_OIDC_CLIENT_AUTH_METHOD']='managed_identity'
os.environ['SALUS_OIDC_TENANT_ID']='11111111-2222-3333-4444-555555555555'
os.environ['SALUS_OIDC_DISCOVERY_URL']='https://login.microsoftonline.com/11111111-2222-3333-4444-555555555555/v2.0/.well-known/openid-configuration'
os.environ['SALUS_OIDC_CLIENT_ID']='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
os.environ['SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID']='99999999-8888-7777-6666-555555555555'
os.environ['SALUS_OIDC_REDIRECT_URI']='https://salcapa.example/api/auth/oidc/callback'
os.environ['SALUS_OIDC_PROVIDER_NAME']='entra'
os.environ['SALUS_OIDC_AUTO_PROVISION']='0'
sys.path.insert(0,str(ROOT))

from fastapi.testclient import TestClient
import app

ISSUER='https://login.microsoftonline.com/11111111-2222-3333-4444-555555555555/v2.0'
claims={}
decode_failure=None
token_requests=[]

class FakeResponse:
    def __init__(self,payload): self.payload=payload
    def raise_for_status(self): return None
    def json(self): return self.payload

class FakeCredential:
    def __init__(self,client_id=None):
        assert client_id==app.OIDC_MANAGED_IDENTITY_CLIENT_ID
    def get_token(self,scope):
        assert scope==app.OIDC_ASSERTION_SCOPE
        return SimpleNamespace(token='managed-identity-assertion',expires_on=4102444800)

class FakeJWKClient:
    def __init__(self,uri):
        assert uri=='https://login.microsoftonline.com/common/discovery/v2.0/keys'
    def get_signing_key_from_jwt(self,value):
        assert value=='signed-id-token'
        return SimpleNamespace(key='test-signing-key')

def fake_get(url,timeout):
    assert url==app.OIDC_DISCOVERY_URL and timeout==10
    return FakeResponse({
        'authorization_endpoint':ISSUER+'/oauth2/v2.0/authorize',
        'token_endpoint':ISSUER+'/oauth2/v2.0/token',
        'jwks_uri':'https://login.microsoftonline.com/common/discovery/v2.0/keys',
        'issuer':ISSUER,
    })

def fake_post(url,data,timeout):
    assert url==ISSUER+'/oauth2/v2.0/token' and timeout==15
    assert data['client_id']==app.OIDC_CLIENT_ID
    assert data['client_assertion']=='managed-identity-assertion'
    assert data['client_assertion_type']==app.OIDC_CLIENT_ASSERTION_TYPE
    assert 'client_secret' not in data
    token_requests.append(dict(data))
    return FakeResponse({'id_token':'signed-id-token'})

def fake_decode(value,key,algorithms,audience,issuer):
    if decode_failure: raise decode_failure('rejected')
    assert value=='signed-id-token' and key=='test-signing-key'
    assert audience==app.OIDC_CLIENT_ID and issuer==ISSUER
    return dict(claims)

def start(client):
    response=client.get('/api/auth/oidc/start',follow_redirects=False)
    assert response.status_code==302,response.text
    values=parse_qs(urlparse(response.headers['location']).query)
    return values['state'][0],values['nonce'][0]

def callback(client,state,status=302):
    response=client.get('/api/auth/oidc/callback',params={'code':'authorization-code','state':state},follow_redirects=False)
    assert response.status_code==status,response.text
    return response

def set_claims(nonce,oid='entra-object-member',tenant=app.OIDC_TENANT_ID,email='member@salus.solutions'):
    claims.clear()
    claims.update({'sub':'pairwise-subject','oid':oid,'tid':tenant,'nonce':nonce,'name':'Protected Member','email':email,'email_verified':True,'roles':['System Administrator'],'tenant_id':999})

def main():
    global decode_failure
    app.ManagedIdentityCredential=FakeCredential
    app.httpx.get=fake_get
    app.httpx.post=fake_post
    app.jwt.PyJWKClient=FakeJWKClient
    app.jwt.decode=fake_decode
    app._oidc_cache.clear()
    app._oidc_credential=None

    conn=app.db()
    conn.execute("DELETE FROM users WHERE username LIKE 'identity-smoke-%'")
    created=app.now()
    values=(1,'identity-smoke-member','Mapped Member','','Client Executive','Confidential','Active',created,created,'member@salus.solutions','entra-object-member','entra')
    conn.execute("INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email,external_subject,identity_provider) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",values)
    values=(1,'identity-smoke-disabled','Disabled Member','','Contributor','Standard','Disabled',created,created,'disabled@salus.solutions','entra-object-disabled','entra')
    conn.execute("INSERT INTO users(tenant_id,username,display_name,password_hash,role,sensitivity_clearance,status,created_at,updated_at,email,external_subject,identity_provider) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",values)
    conn.commit(); conn.close()

    client=TestClient(app.app)
    status=app.oidc_federation_status()
    assert status['configured'] and status['healthy'] and status['mode']=='managed_identity'

    state,nonce=start(client); set_claims(nonce)
    response=callback(client,state)
    assert response.headers['location']=='/'
    session=client.get('/api/auth/session').json()
    assert session['tenant_id']==1 and session['role']=='Client Executive' and session['clearance']=='Confidential'
    assert session['role']!='System Administrator' and session['tenant_id']!=999
    assert token_requests and 'client_secret' not in token_requests[-1]

    replay_client=TestClient(app.app)
    replay_client.cookies.set('salus_oidc_state',state)
    callback(replay_client,state,401)

    state,nonce=start(client); set_claims(nonce,oid='unknown-object')
    callback(client,state,403)

    state,nonce=start(client); set_claims(nonce,oid='unknown-email-object',email='member@salus.solutions')
    callback(client,state,403)

    state,nonce=start(client); set_claims(nonce,oid='entra-object-disabled',email='disabled@salus.solutions')
    callback(client,state,403)

    state,nonce=start(client); set_claims(nonce,tenant='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')
    callback(client,state,401)

    for failure in (app.jwt.InvalidIssuerError,app.jwt.InvalidAudienceError):
        decode_failure=failure
        state,nonce=start(client); set_claims(nonce)
        callback(client,state,401)
    decode_failure=None

    app.ENVIRONMENT='production'
    app.OIDC_AUTO_PROVISION=False
    app._oidc_cache.pop('client_assertion',None)
    readiness=app.production_readiness()
    serialized=' '.join(readiness['issues'])
    assert 'provider configuration is incomplete' not in serialized
    assert 'managed identity federation is unavailable' not in serialized
    assert readiness['oidc']['healthy'] is True
    app.OIDC_MANAGED_IDENTITY_CLIENT_ID=''
    assert not app.oidc_configured()
    assert 'provider configuration is incomplete' in ' '.join(app.production_readiness()['issues'])

    print('SALCAPA_V33_ENTRA_IDENTITY_PASS',app.DB_BACKEND)

if __name__=='__main__': main()
