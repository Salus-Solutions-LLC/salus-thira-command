"""Proposed staff-only encrypted source metadata export; no source-content export.

Run only through the separately approved one-shot protected workflow. This module
does not activate a reader, remediate intake, grant access or qualify a source.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import re
import zlib
import contextlib
import io
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import urlsplit, quote

MAX_SOURCES = 100_000
MAX_PLAINTEXT = 48 * 1024 * 1024
MAX_ENVELOPE = 3_200_000
CONTEXT = b'salus-private-source-manifest-v1'
COORDINATION_QUERIES = (
    ('responder_handoff','liaison command transfer briefing acknowledgement responsibility communications interoperability'),
    ('public_warnings','warning alert accessibility comprehension language accountability evacuation shelter'),
    ('family_reunification','reunification custody caregiver guardian verification family assistance supervision privacy'),
    ('recovery_and_review','reentry re-entry reopening repopulation debrief improvement corrective-action evidence evaluation'),
)

class ReadRetryClient:
    """Bounded retries for GET only; never repeat a write or job start."""
    def __init__(self, inner, *, clock=time.monotonic, sleep=time.sleep, seconds=800):
        self.inner,self.clock,self.sleep=inner,clock,sleep;self.deadline=clock()+seconds
    def get(self,url,**kwargs):
        for attempt in range(4):
            require(self.clock()<self.deadline,'READ_BUDGET')
            response=self.inner.get(url,**kwargs)
            if response.status_code not in {429,500,502,503,504}:return response
            if attempt==3:return response
            value=response.headers.get('Retry-After');delay=2**attempt
            if value:
                try:delay=max(delay,float(value))
                except ValueError:
                    try:delay=max(delay,(parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
                    except (TypeError,ValueError,OverflowError):raise ValueError('READ_RETRY_AFTER_INVALID')from None
            require(0<=delay<=60 and delay<self.deadline-self.clock(),'READ_RETRY_DEFERRED')
            self.sleep(delay)
        raise ValueError('READ_RETRY_BOUND')
    def post(self,*args,**kwargs):return self.inner.post(*args,**kwargs)
    def put(self,*args,**kwargs):return self.inner.put(*args,**kwargs)
    def close(self):return self.inner.close()

def digest(value):
    return hashlib.sha256(value).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def require(condition, code):
    if not condition:
        raise ValueError(code)

def safe_identity(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_!.-]{8,256}', value), 'SOURCE_ID_INVALID')
    return value

class AuditLimitedConnection:
    """No source writes; only four narrowly validated consideration audit inserts."""
    def __init__(self, inner, actor, query_hashes):
        self.inner, self.actor, self.query_hashes = inner, actor, set(query_hashes)
        self.backend = getattr(inner, 'backend', 'sqlite')
        self.inserted = set()
    def execute(self, sql, params=()):
        clean = re.sub(r"'(?:''|[^'])*'", "''", sql).strip().rstrip(';').strip()
        require(';' not in clean and '--' not in clean and '/*' not in clean, 'SQL_SCOPE')
        words = set(re.findall('[A-Z_]+', clean.upper()))
        if clean.upper().startswith(('SELECT ', 'WITH ')):
            require(not words.intersection({'INSERT','UPDATE','DELETE','MERGE','CREATE','ALTER','DROP','TRUNCATE','COPY','CALL','DO','INTO','LOCK','COMMIT','GRANT','REVOKE','VACUUM','ANALYZE','SET','PRAGMA'}), 'SQL_WRITE_DENIED')
            names = set(re.findall(r'\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)', clean, re.I))
            require(names <= {'m365_knowledge_candidates','m365_knowledge_holds','m365_bulk_items','m365_bulk_extraction_checks','m365_knowledge_consideration_receipts','represented','searchable','matched'}, 'SQL_TABLE_SCOPE')
        else:
            require(re.fullmatch(r'INSERT\s+INTO\s+m365_knowledge_consideration_receipts\s+VALUES\s*\(\s*\?(?:\s*,\s*\?){9}\s*\)', clean, re.I), 'SQL_WRITE_DENIED')
            require(len(params) == 10 and params[1] in self.query_hashes and params[1] not in self.inserted and str(params[8]).startswith(self.actor+' / ') and len(self.inserted) < 4, 'AUDIT_INSERT_SCOPE')
            self.inserted.add(params[1])
        return self.inner.execute(sql, params)
    def executescript(self, sql):
        expected = '''CREATE TABLE IF NOT EXISTS m365_knowledge_consideration_receipts (
          receipt_id TEXT PRIMARY KEY, query_sha256 TEXT NOT NULL, boundary_count INTEGER NOT NULL,
          considered_count INTEGER NOT NULL, matched_count INTEGER NOT NULL, content_available_count INTEGER NOT NULL,
          metadata_only_count INTEGER NOT NULL, governed_hold_count INTEGER NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL
        );'''
        norm = lambda s: re.sub(r'\s+','',s).casefold()
        require(norm(sql) == norm(expected), 'DDL_DENIED')
        # Existing table must already exist. Do not create or alter any schema.
        return self.inner.execute('SELECT COUNT(*) count FROM m365_knowledge_consideration_receipts')
    def commit(self):self.inner.commit()

def run_export(inner, intake, helper, public_pem, binding):
    """Reuses the approved census/consideration implementation under new authority.

    The old consumed activation is not replayed. Four new audit records require
    the new exact-revision/one-execution authorization. Sources stay unchanged.
    """
    task = binding['task']
    require(re.fullmatch(r'salus-private-source-reconciliation-\d{8}',task), 'TASK_SCOPE')
    require(str(binding['attempt']) == '1' and re.fullmatch(r'\d+',str(binding['run'])), 'RUN_SCOPE')
    helper.TASK_KEY = task
    helper.ACTOR = 'System Administrator - task consideration '+task
    conn = AuditLimitedConnection(inner, helper.ACTOR, [digest(q.strip().encode())for _label,q in COORDINATION_QUERIES])
    controls_before=helper.protected_source_controls(conn)
    before = collect_metadata(conn, COORDINATION_QUERIES)
    censuses = []
    def census():
        value = helper.source_census(intake)
        censuses.append(value)
        return value
    aggregate_trace = io.StringIO()
    try:
        with contextlib.redirect_stdout(aggregate_trace):
            receipts = helper.run_search(conn, source_census_fn=census,queries=COORDINATION_QUERIES)
        after = collect_metadata(conn, COORDINATION_QUERIES)
    finally:
        controls_after=helper.protected_source_controls(conn)
        require(controls_before==controls_after,'PROTECTED_SOURCE_CONTROLS_DRIFT')
        print('PRIVATE_MANIFEST_PROTECTED_CONTROLS_UNCHANGED=1',flush=True)
    require(before == after and len(censuses) == 2 and censuses[0] == censuses[1], 'SOURCE_OR_VERSION_DRIFT')
    require(len(conn.inserted) == len(receipts) == 4 and set(censuses[0]) <= set(after), 'MANIFEST_MEMBERSHIP')
    for i, receipt in enumerate(receipts):
        matched = sum(bool(records[0][-1] & (1 << i)) for records in after.values())
        require(matched == receipt['matched_files'], 'MATCH_RECEIPT_MISMATCH')
        require(len(after) == receipt['represented_files'], 'REPRESENTED_RECEIPT_MISMATCH')
    compact = []
    for sid, rows in after.items():
        compact.append([sid, sorted({r[1]for r in rows}), censuses[0].get(sid),
                        sorted({(r[2],r[3])for r in rows if r[0]=='candidate'}),
                        sorted({(r[0],r[4],r[5])for r in rows}), rows[0][-1]])
    payload = {'schema':1,'binding':binding,'at_utc':datetime.now(timezone.utc).isoformat(),
               'row_columns':['source_item_id','recorded_source_names','current_physical_eTag_and_modified_or_null','recorded_candidate_original_sha256_and_modified_versions','representation_kind_state_and_service_availability_flag','query_match_bitmask'],
               'representation_set_sha256':digest(canonical(after)),
               'protected_source_controls':controls_after,
               'representation_integrity_scope':'Full before/after source/rights/search-input hashes compared in the isolated job. Raw representations and their per-row hashes are not exported; this global binding is not independently reconstructible from the minimized metadata rows.',
               'source_content_exported':False,'permissions_changed':False,'reader_activated':False,'qualification_completed':False,
               'source_rows':compact,'physical_files':len(censuses[0]),'represented_files':len(after),
               'aggregate_trace_sha256':digest(aggregate_trace.getvalue().encode()),
               'queries':[{'label':label,'query_sha256':digest(q.strip().encode())}for label,q in COORDINATION_QUERIES],
               'consideration_receipts':receipts,'scope':'Staff-only candidate metadata and current corpus consideration; no source-body reading, assignment, qualification or release inferred.'}
    return seal(payload, public_pem, binding)

def collect_metadata(conn, queries):
    """Inspect each representation in memory, export only allowlisted metadata.

    Query terms follow the existing consideration service (lower-case substring,
    OR, distinct source identity). Classification bodies are never exported.
    """
    from salcapa_knowledge_consideration import _terms, _patterns
    terms = [_terms(query) for _label, query in queries]
    require(len(terms) == 4 and all(terms), 'QUERY_SCOPE')
    out = {}
    # Hash and search source representations on the database side. Never transfer
    # corpus text into this job just to build a metadata list or allocate all
    # classification bodies with fetchall(). Physical eTags come from Graph.
    postgres=getattr(conn,'backend','sqlite')=='postgres'
    def hashed(expr):return "encode(sha256(convert_to(COALESCE("+expr+",''),'UTF8')),'hex')" if postgres else 'salus_sha256(COALESCE('+expr+",''))"
    def row_hash(columns):
        expression=('json_build_array('+columns+')::text') if postgres else ('json_array('+columns+')')
        return hashed(expression)
    sql = (
        ('candidate', "SELECT source_item_id,source_name,source_sha256,source_modified_at,status,"+row_hash('source_name,source_relative_path,source_sha256,source_modified_at,source_owner,status,target_folder,classification_json')+" representation_sha256,CASE WHEN classification_json LIKE '%\"status\": \"Complete\"%' THEN 1 ELSE 0 END service_content_flag FROM m365_knowledge_candidates"),
        ('bulk', "SELECT item_id,name,status,"+row_hash('name,metadata_json,status,reason')+" representation_sha256 FROM m365_bulk_items WHERE kind='file' AND status<>'Removed'"),
        ('hold', "SELECT source_item_id,source_name,"+hashed("source_name || ' ' || source_relative_path || ' ' || source_area || ' ' || hold_reason")+" representation_sha256 FROM m365_knowledge_holds WHERE status='Governed Hold'"),
    )
    for kind, statement in sql:
        for r in conn.execute(statement).fetchall():
            sid = safe_identity(str(r['item_id' if kind == 'bulk' else 'source_item_id']))
            require(len(out) < MAX_SOURCES or sid in out, 'SOURCE_BOUND')
            # [identity, representation kind, name, original hash, date,
            # status, service availability flag (not usability proof), metadata
            # hash, version token, match mask]
            if kind == 'candidate':
                details = [kind, str(r['source_name'] or ''), str(r['source_sha256'] or ''), str(r['source_modified_at'] or ''), str(r['status'] or ''), 'Service representation flag only: '+str(r['service_content_flag']), str(r['representation_sha256']), '']
            elif kind == 'bulk':
                details = [kind, str(r['name'] or ''), '', '', str(r['status'] or ''), 'Unverified', str(r['representation_sha256']), '']
            else:
                details = [kind, str(r['source_name'] or ''), '', '', 'Governed Hold', 'Not reviewed', str(r['representation_sha256']), '']
            require(all(len(v) <= 4096 for v in details), 'METADATA_FIELD_BOUND')
            out.setdefault(sid, []).append(details + [0])
    # Match each source using the exact service SQL expression, rather than a
    # Python case/substring approximation that could differ by database locale.
    searchable = """WITH searchable AS (
      SELECT source_item_id,source_name || ' ' || source_relative_path || ' ' || classification_json search_text FROM m365_knowledge_candidates
      UNION ALL
      SELECT item_id,name || ' ' || metadata_json || ' ' || status || ' ' || reason search_text FROM m365_bulk_items WHERE kind='file' AND status<>'Removed'
      UNION ALL
      SELECT source_item_id,source_name || ' ' || source_relative_path || ' ' || source_area || ' ' || hold_reason search_text FROM m365_knowledge_holds WHERE status='Governed Hold'
    ) SELECT DISTINCT source_item_id FROM searchable WHERE """
    for i, group in enumerate(terms):
        clause, parameters = _patterns(group)
        for r in conn.execute(searchable + clause, parameters).fetchall():
            sid = safe_identity(str(r['source_item_id']))
            require(sid in out, 'MATCH_MEMBERSHIP_DRIFT')
            for detail in out[sid]:
                detail[-1] |= 1 << i
    return {sid: sorted(rows, key=canonical) for sid, rows in sorted(out.items())}

def seal(payload, public_pem, binding):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    public = serialization.load_pem_public_key(public_pem)
    require(isinstance(public, rsa.RSAPublicKey) and public.key_size >= 3072, 'KEY_TYPE')
    raw = canonical(payload)
    require(len(raw) <= MAX_PLAINTEXT, 'PLAINTEXT_BOUND')
    aad = canonical(binding)
    key, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    encrypted = AESGCM(key).encrypt(nonce, zlib.compress(raw, 9), aad)
    wrapped = public.encrypt(key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=CONTEXT))
    result = {'schema': 1, 'algorithm': 'RSA-OAEP-SHA256+A256GCM', 'binding': binding,
              'public_key_sha256': digest(public_pem), 'wrapped_key': base64.b64encode(wrapped).decode(),
              'nonce': base64.b64encode(nonce).decode(), 'ciphertext': base64.b64encode(encrypted).decode()}
    envelope = canonical(result)
    require(len(envelope) <= MAX_ENVELOPE, 'ENCRYPTED_TRANSPORT_BOUND')
    return envelope



def open_envelope(envelope, private_pem, expected_binding):
    """Local restricted operator only; never install the private key in a job."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    require(len(envelope) <= MAX_ENVELOPE, 'ENVELOPE_BOUND')
    r = json.loads(envelope)
    require(r['schema'] == 1 and r['algorithm'] == 'RSA-OAEP-SHA256+A256GCM' and r['binding'] == expected_binding, 'ENVELOPE_SCOPE')
    private = serialization.load_pem_private_key(private_pem, password=None)
    public = private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
    require(digest(public) == r['public_key_sha256'], 'KEY_MISMATCH')
    key = private.decrypt(base64.b64decode(r['wrapped_key'],validate=True), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(),label=CONTEXT))
    compressed = AESGCM(key).decrypt(base64.b64decode(r['nonce'],validate=True),base64.b64decode(r['ciphertext'],validate=True),canonical(expected_binding))
    decoder = zlib.decompressobj()
    plain = decoder.decompress(compressed,MAX_PLAINTEXT+1)
    require(len(plain) <= MAX_PLAINTEXT and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail, 'DECOMPRESSION_BOUND')
    return json.loads(plain)

def verify_owner_only(intake, item_id, expected_owner_hash):
    drive = intake.config.drive_id
    response = intake.client.get(f'https://graph.microsoft.com/v1.0/drives/{drive}/items/{safe_identity(item_id)}/permissions',headers=intake._headers())
    require(response.status_code == 200, 'DESTINATION_PERMISSION_UNAVAILABLE')
    result = response.json()
    require(not result.get('@odata.nextLink') and len(result.get('value',[])) == 1, 'DESTINATION_NOT_OWNER_ONLY')
    p = result['value'][0]
    principal = (p.get('grantedToV2') or p.get('grantedTo') or {}).get('user') or {}
    require(p.get('roles') == ['owner'] and not p.get('link') and not p.get('invitation') and digest(str(principal.get('id','')).lower().encode()) == expected_owner_hash, 'DESTINATION_OWNER_MISMATCH')

def private_destination(intake, destination_hash, expected_owner_hash):
    """Resolve the preapproved private folder; no destination IDs in public code."""
    drive = intake.config.drive_id
    base = f'https://graph.microsoft.com/v1.0/drives/{drive}'
    root = intake.client.get(base+'/root',headers=intake._headers(),params={'$select':'id,folder,remoteItem'})
    require(root.status_code == 200 and 'folder' in root.json() and 'remoteItem' not in root.json(), 'DESTINATION_ROOT')
    root_id = safe_identity(root.json()['id'])
    endpoint = base+f'/items/{root_id}/children'
    page, params, seen, matches = endpoint, {'$select':'id,name,folder,remoteItem,parentReference','$top':'200'}, set(), []
    while page:
        require(page not in seen and len(seen)<10, 'DESTINATION_LIST_BOUND');seen.add(page)
        response = intake.client.get(page,headers=intake._headers(),params=params)
        require(response.status_code == 200, 'DESTINATION_LIST_UNAVAILABLE')
        value = response.json();require(isinstance(value.get('value'),list), 'DESTINATION_LIST_SHAPE')
        for item in value['value']:
            if item.get('name') == 'Salus Restricted Review':matches.append(item)
        page, params = value.get('@odata.nextLink'), None
        if page:
            parsed=urlsplit(page);require(parsed.scheme=='https' and parsed.netloc=='graph.microsoft.com' and parsed.path==urlsplit(endpoint).path and parsed.query and not parsed.fragment,'DESTINATION_LIST_SCOPE')
    require(len(matches)==1,'DESTINATION_AMBIGUOUS');folder=matches[0];fid=safe_identity(folder['id'])
    require('folder'in folder and 'remoteItem'not in folder and (folder.get('parentReference')or{}).get('id')==root_id,'DESTINATION_NOT_ROOT_PRIVATE_FOLDER')
    require(digest((drive+':'+fid).encode())==destination_hash,'DESTINATION_BINDING')
    verify_owner_only(intake,fid,expected_owner_hash)
    return fid

def retain_private(intake, folder_id, envelope, binding, expected_owner_hash):
    """Create exactly one encrypted file with conflict=fail; no public artifact."""
    require(len(envelope)<=MAX_ENVELOPE,'ENVELOPE_BOUND')
    drive=intake.config.drive_id
    name='Salus_Private_Source_Manifest_20261123_'+str(binding['run'])+'.json'
    require(re.fullmatch(r'Salus_Private_Source_Manifest_20261123_\d+\.json',name),'DESTINATION_NAME')
    item_path=f'https://graph.microsoft.com/v1.0/drives/{drive}/items/{safe_identity(folder_id)}:/{quote(name,safe="")}:'
    existing=intake.client.get(item_path,headers=intake._headers())
    require(existing.status_code==404,'DESTINATION_ALREADY_EXISTS_OR_UNKNOWN')
    verify_owner_only(intake,folder_id,expected_owner_hash)
    session=intake.client.post(item_path+'/createUploadSession',headers=intake._headers()|{'Content-Type':'application/json'},json={'item':{'@microsoft.graph.conflictBehavior':'fail','name':name}})
    require(session.status_code==200,'DESTINATION_SESSION_UNAVAILABLE')
    upload_url=str(session.json().get('uploadUrl',''));parsed=urlsplit(upload_url)
    require(parsed.scheme=='https' and not parsed.username and not parsed.password and not parsed.fragment and ((parsed.hostname or '').lower()=='salussolutions-my.sharepoint.com' or (parsed.hostname or '').lower().endswith('.up.1drv.com')),'DESTINATION_SESSION_SCOPE')
    # Upload URLs are ephemeral bearer capabilities; never log or persist them,
    # attach Graph authorization, retry the write, or fall back to replacement.
    response=intake.client.put(upload_url,headers={'Content-Length':str(len(envelope)),'Content-Range':f'bytes 0-{len(envelope)-1}/{len(envelope)}'},content=envelope,timeout=60.0)
    require(response.status_code==201,'DESTINATION_CREATE_UNCONFIRMED');item=response.json();sid=safe_identity(item.get('id',''))
    require(item.get('name')==name and item.get('size')==len(envelope) and (item.get('parentReference')or{}).get('id')==folder_id and 'file'in item and 'remoteItem'not in item,'DESTINATION_CREATED_IDENTITY')
    verify=intake.client.get(f'https://graph.microsoft.com/v1.0/drives/{drive}/items/{sid}/content',headers=intake._headers(),timeout=60.0)
    if verify.status_code in {302,303,307,308}:
        location=str(verify.headers.get('Location',''));p=urlsplit(location)
        require(p.scheme=='https' and p.hostname=='salussolutions-my.sharepoint.com' and not p.username and not p.password and not p.fragment,'DESTINATION_READBACK_REDIRECT')
        verify=intake.client.get(location,headers={'Accept':'application/octet-stream'},timeout=60.0)
    require(verify.status_code==200 and len(verify.content)==len(envelope) and digest(verify.content)==digest(envelope),'DESTINATION_BYTE_READBACK')
    verify_owner_only(intake,folder_id,expected_owner_hash);verify_owner_only(intake,sid,expected_owner_hash)
    return {'encrypted_bytes':len(envelope),'encrypted_sha256':digest(envelope),'owner_only_verified':True,'source_content_exported':False,'public_artifact_created':False}
