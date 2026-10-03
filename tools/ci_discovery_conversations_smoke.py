"""Fictional session-backed lifecycle and adversarial acceptance tests."""
import concurrent.futures
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SANDBOX = tempfile.TemporaryDirectory(prefix='salus-discovery-')
if os.getenv('SALUS_DISCOVERY_TEST_POSTGRES') == '1':
    # CI supplies a disposable, dedicated test database, never a live Salus DSN.
    os.environ['SALUS_DB_BACKEND'] = 'postgres'
else:
    os.environ['SALUS_DB_BACKEND'] = 'sqlite'
os.environ.update(SALUS_DB_PATH=str(Path(SANDBOX.name)/'test.db'),
    SALUS_AUTH_MODE='session', SALUS_SEED_DEMO='0', SALUS_ENV='development',
    SALUS_LOCAL_STORAGE_DIR=str(Path(SANDBOX.name)/'attachments'),
    SALUS_BACKUP_DIR=str(Path(SANDBOX.name)/'backups'),
    SALUS_DISCOVERY_ENABLED='1', SALUS_DISCOVERY_STAFF_TENANT_ID='1',
    SALUS_DISCOVERY_REVIEWER_IDS='101,102', SALUS_RATE_LIMIT_ENABLED='0')

from fastapi.testclient import TestClient
import app as application
from salus_discovery_conversations import POLICY_VERSION

HEADERS = {'Origin':'http://testserver','X-Salus-Discovery':'1'}


class DiscoveryAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn=application.db()
        for tid in (1,2,3):
            conn.execute("INSERT INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,'Active',?) ON CONFLICT(id) DO NOTHING",
                         (tid,'Fictional tenant '+str(tid),'discovery-test-'+str(tid),application.now()))
        for uid,tid,role in ((101,1,'Assessment Director'),(102,1,'System Administrator'),
                             (201,2,'Client Executive'),(301,3,'System Administrator')):
            conn.execute('''INSERT INTO users(id,tenant_id,username,display_name,role,status,created_at,updated_at)
              VALUES(?,?,?,?,?,'Active',?,?) ON CONFLICT(id) DO NOTHING''', (uid,tid,'fictional-'+str(uid),'Private account '+str(uid),role,application.now(),application.now()))
            raw='fictional-session-'+str(uid)
            conn.execute('''INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at)
              VALUES(?,?,'2099-01-01T00:00:00Z',?,?) ON CONFLICT(token_hash) DO NOTHING''', (uid,application._hash_token(raw),application.now(),application.now()))
        conn.commit();conn.close()

    def setUp(self):
        conn=application.db()
        for table in ('discovery_candidates','discovery_flags','discovery_events','discovery_revisions',
                      'discovery_rate_buckets','discovery_contributions','discovery_threads','discovery_participants'):
            conn.execute('DELETE FROM '+table)
        conn.commit();conn.close()
        self.alice=self.client(201);self.bob=self.client(301);self.staff=self.client(101);self.staff2=self.client(102)
        self.profile(self.alice,'Fictional Alice');self.profile(self.bob,'Fictional Bob');self.profile(self.staff,'Fictional Reviewer')
        self.thread=self.post(self.staff,'/insights',dict(insight_id='fictional-insight',title='Fictional Insight for acceptance',
            url='https://www.salus.solutions/insights/fictional-acceptance',source_version='fictional-v1',
            publication_review='Fictional reviewed publication reference')).json()['id']

    def tearDown(self):
        for client in (self.alice,self.bob,self.staff,self.staff2):client.close()

    def client(self, uid=None):
        client=TestClient(application.app)
        if uid:client.cookies.set('salus_session','fictional-session-'+str(uid))
        return client

    def post(self, client, path, data, code=201):
        response=client.post('/api/discovery'+path,json=data,headers=HEADERS)
        self.assertEqual(response.status_code,code,response.text);return response

    def profile(self,client,name):
        self.post(client,'/profile',dict(display_name=name,consent=True,policy_version=POLICY_VERSION),200)

    def submit(self, client=None, **changes):
        data=dict(body='Fictional experience suggests testing alternative explanations.',prompt='What did we miss?',request_key=uuid.uuid4().hex)
        data.update(changes)
        return self.post(client or self.alice,'/threads/'+self.thread+'/perspectives',data).json(),data

    def moderate(self, row, action='Approve', client=None, code=200):
        return self.post(client or self.staff,'/review/'+row['id'],dict(version=row['version'],action=action,
            reason='Fictional exact-version privacy and rights review.',privacy_and_rights_checked=True),code)

    def public(self):
        return self.alice.get('/api/discovery/threads/'+self.thread).json()['items']

    def candidate(self,row):
        return self.post(self.staff,'/perspectives/'+row['id']+'/candidate',dict(version=row['version'],kind='Research lead',
            summary='Test the competing explanation with original evidence.',applicability='Fictional context only; requires current evidence.',
            restrictions='Member-neutral candidate; no validated finding.')).json()

    def test_review_before_publication_and_private_identity(self):
        row,_=self.submit();self.assertEqual(self.public(),[])
        approved=self.moderate(row).json();public=self.public()[0]
        self.assertEqual(public['public_name'],'Fictional Alice');self.assertEqual(public['version'],approved['version'])
        self.assertNotIn('user_id',public);self.assertNotIn('tenant_id',public);self.assertNotIn('request_key',public)
        self.assertNotIn('Private account',str(public))
        with self.client() as anonymous:self.assertEqual(anonymous.get('/api/discovery/threads/'+self.thread).status_code,200)

    def test_anonymous_prototype_and_cross_tenant_staff_denied(self):
        with self.client() as anonymous:
            self.assertEqual(anonymous.get('/api/discovery/me').status_code,401)
            response=anonymous.get('/api/discovery/review',headers={'X-Salus-Role':'System Administrator','X-Salus-Tenant':'1'})
            self.assertEqual(response.status_code,401)
        self.assertEqual(self.bob.get('/api/discovery/review').status_code,403)
        self.assertEqual(self.alice.get('/api/discovery/candidates').status_code,403)

    def test_owner_edit_resubmission_stale_conflict_and_cross_user_denial(self):
        row,_=self.submit();row=self.moderate(row).json();self.candidate(row)
        response=self.bob.patch('/api/discovery/perspectives/'+row['id'],json={'version':row['version'],'body':'A fictional unauthorized attempt.'},headers=HEADERS)
        self.assertEqual(response.status_code,404)
        body={'version':row['version'],'body':'A revised fictional perspective requires renewed review.'}
        edited=self.alice.patch('/api/discovery/perspectives/'+row['id'],json=body,headers=HEADERS)
        self.assertEqual(edited.status_code,200);self.assertEqual(self.public(),[])
        self.assertEqual(self.alice.patch('/api/discovery/perspectives/'+row['id'],json=body,headers=HEADERS).status_code,409)
        self.moderate(row,code=409)
        records=self.staff.get('/api/discovery/candidates').json()['items']
        self.assertEqual(records[0]['status'],'Source unavailable - re-review required')

    def test_withdrawal_never_republished_and_revision_retained(self):
        row,_=self.submit();row=self.moderate(row).json();self.candidate(row)
        removed=self.post(self.alice,'/perspectives/'+row['id']+'/withdraw',{'version':row['version']},200).json()
        self.assertEqual(self.public(),[])
        self.moderate({**row,'version':removed['version']},code=409)
        conn=application.db();n=conn.execute('SELECT COUNT(*) c FROM discovery_revisions WHERE contribution_id=?',(row['id'],)).fetchone()['c'];conn.close()
        self.assertEqual(n,3)
        history=self.staff.get('/api/discovery/history/'+row['id']).json()
        self.assertEqual(len(history['revisions']),3)
        self.assertEqual(self.bob.get('/api/discovery/history/'+row['id']).status_code,403)

    def test_reply_boundaries_depth_and_parent_hold(self):
        parent,_=self.submit();parent=self.moderate(parent).json()
        child,_=self.submit(self.bob,parent_id=parent['id'],body='Fictional reply contributes another interpretation.');child=self.moderate(child).json()
        grand,_=self.submit(parent_id=child['id'],body='Fictional second-level reply asks for corroboration.');grand=self.moderate(grand).json();self.candidate(grand)
        self.post(self.alice,'/threads/'+self.thread+'/perspectives',dict(body='Fictional reply is too deeply nested.',prompt='What did we miss?',request_key=uuid.uuid4().hex,parent_id=grand['id']),409)
        self.moderate(parent,'Hide');self.assertEqual(self.public(),[])
        self.assertEqual(self.staff.get('/api/discovery/candidates').json()['items'][0]['status'],'Source unavailable - re-review required')

    def test_question_pending_approved_and_withdrawn_visibility(self):
        data=dict(title='What should a fictional team investigate?',body='A fictional question needs evidence and competing interpretations.',prompt='What question should we be asking?',request_key=uuid.uuid4().hex)
        row=self.post(self.alice,'/questions',data).json();self.assertNotIn(row['thread_id'],[r['id'] for r in self.alice.get('/api/discovery/threads').json()['items']])
        retry=self.post(self.alice,'/questions',data).json();self.assertEqual(row['id'],retry['id'])
        row=self.moderate(row).json();self.assertIn(retry['thread_id'],[r['id'] for r in self.alice.get('/api/discovery/threads').json()['items']])
        self.post(self.alice,'/perspectives/'+row['id']+'/withdraw',{'version':row['version']},200)
        self.assertEqual(self.alice.get('/api/discovery/threads/'+retry['thread_id']).status_code,404)

    def test_idempotency_and_duplicate_and_closed_thread(self):
        row,data=self.submit();retry=self.post(self.alice,'/threads/'+self.thread+'/perspectives',data).json();self.assertEqual(row['id'],retry['id'])
        self.post(self.alice,'/threads/'+self.thread+'/perspectives',{**data,'request_key':uuid.uuid4().hex},409)
        self.post(self.alice,'/threads/'+self.thread+'/perspectives',{**data,'body':'Another distinct fictional perspective.'},409)
        self.post(self.staff,'/threads/'+self.thread+'/state',{'open':False,'reason':'Fictional closed conversation test.'},200)
        self.post(self.bob,'/threads/'+self.thread+'/perspectives',{**data,'request_key':uuid.uuid4().hex},409)

    def test_flags_private_deduplicated_disposition(self):
        row,_=self.submit();row=self.moderate(row).json()
        data={'reason':'Other concern','detail':'A fictional concern needs staff attention.'}
        flag=self.post(self.bob,'/perspectives/'+row['id']+'/flags',data).json()
        self.assertEqual(flag['id'],self.post(self.bob,'/perspectives/'+row['id']+'/flags',data).json()['id'])
        self.assertEqual(len(self.staff.get('/api/discovery/review').json()['flags']),1)
        self.assertNotIn('flags',self.alice.get('/api/discovery/threads/'+self.thread).json())
        self.post(self.staff,'/flags/'+flag['id']+'/disposition',{'disposition':'Reviewed - no change','reason':'Fictional concern investigated and resolved.'},200)
        self.assertEqual(self.staff.get('/api/discovery/review').json()['flags'],[])

    def test_blocked_user_cannot_bypass_pause_can_withdraw(self):
        row,_=self.submit();row=self.moderate(row).json()
        self.post(self.staff,'/participants/201/state',{'blocked':True,'reason':'Fictional temporary abuse-control test.'},200)
        self.post(self.alice,'/profile',dict(display_name='Fictional Alice',consent=True,policy_version=POLICY_VERSION),409)
        self.post(self.alice,'/questions',dict(title='A fictional paused question?',body='This fictional participant remains paused.',prompt='What did we miss?',request_key=uuid.uuid4().hex),403)
        self.post(self.alice,'/perspectives/'+row['id']+'/withdraw',{'version':row['version']},200)

    def test_no_self_review_and_candidate_cannot_be_knowledge(self):
        row,_=self.submit(self.staff);self.moderate(row,code=403);row=self.moderate(row,client=self.staff2).json()
        first=self.candidate(row);self.assertEqual(first['id'],self.candidate(row)['id'])
        self.assertEqual(first['status'],'Candidate - unvalidated')
        self.assertEqual(self.staff.post('/api/discovery/candidates/'+first['id']+'/validate',json={},headers=HEADERS).status_code,404)

    def test_origin_content_type_size_spam_schema_and_rate(self):
        path='/api/discovery/questions'
        data=dict(title='A fictional boundary test?',body='A fictional meaningful question for testing.',prompt='What did we miss?',request_key=uuid.uuid4().hex)
        self.assertEqual(self.alice.post(path,json=data).status_code,403)
        self.assertEqual(self.alice.post(path,json=data,headers={**HEADERS,'Origin':'https://evil.invalid'}).status_code,403)
        self.assertEqual(self.alice.post(path,content='plain',headers={**HEADERS,'Content-Type':'text/plain'}).status_code,415)
        self.assertEqual(self.alice.post(path,content='x'*33000,headers={**HEADERS,'Content-Type':'application/json'}).status_code,413)
        self.post(self.alice,'/questions',{**data,'website':'bot-filled'},422)
        self.post(self.alice,'/questions',{**data,'status':'Approved'},422)
        self.post(self.alice,'/questions',{**data,'body':'http://a http://b http://c http://d'},422)
        # Clear preceding quota use and test the durable threshold.
        conn=application.db();conn.execute('DELETE FROM discovery_rate_buckets');conn.commit();conn.close()
        for i in range(10):self.post(self.alice,'/questions',{**data,'request_key':uuid.uuid4().hex,'title':f'Fictional rate question number {i}?'})
        limited=self.alice.post(path,json={**data,'request_key':uuid.uuid4().hex},headers=HEADERS)
        self.assertEqual(limited.status_code,429);self.assertEqual(limited.headers['Retry-After'],'600')

    def test_feature_off_and_markup_served_with_csp(self):
        response=self.alice.get('/discovery-conversations');self.assertEqual(response.status_code,200)
        self.assertIn('Add Your Perspective',response.text);self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
        os.environ['SALUS_DISCOVERY_ENABLED']='0'
        try:self.assertEqual(self.alice.get('/api/discovery/threads').status_code,503)
        finally:os.environ['SALUS_DISCOVERY_ENABLED']='1'

    def test_disabled_start_creates_no_community_tables(self):
        with tempfile.TemporaryDirectory(prefix='salus-discovery-off-') as directory:
            environment={**os.environ,'SALUS_DB_BACKEND':'sqlite','SALUS_DISCOVERY_ENABLED':'0',
                'SALUS_DB_PATH':str(Path(directory)/'disabled.db'),
                'SALUS_LOCAL_STORAGE_DIR':str(Path(directory)/'attachments'),
                'SALUS_BACKUP_DIR':str(Path(directory)/'backups')}
            result=subprocess.run([sys.executable,'-c',
                "import app; c=app.db(); rows=c.execute(\"SELECT name FROM sqlite_master WHERE name LIKE 'discovery_%'\").fetchall(); c.close(); assert not rows; print('DEFAULT_OFF_SCHEMA_PASS')"],
                cwd=ROOT,env=environment,check=True,capture_output=True,text=True)
            self.assertIn('DEFAULT_OFF_SCHEMA_PASS',result.stdout)

    def test_pagination_is_bounded_and_complete(self):
        row,_=self.submit();self.moderate(row)
        response=self.alice.get('/api/discovery/threads?limit=1').json()
        self.assertEqual(len(response['items']),1)
        self.assertEqual(self.alice.get('/api/discovery/threads?after='+response['items'][0]['id']).json()['items'],[])
        own=self.alice.get('/api/discovery/mine?limit=1').json()
        self.assertEqual(len(own['items']),1)
        self.assertEqual(self.alice.get('/api/discovery/mine?after='+own['items'][0]['id']).json()['items'],[])

    def test_insight_origin_allowlist_idempotency_and_version_conflict(self):
        data=dict(insight_id='bad',title='A fictional published title',url='https://evil.invalid/insights/test',source_version='v1',publication_review='Fictional published source review.')
        self.post(self.staff,'/insights',data,422)
        self.post(self.bob,'/insights',{**data,'url':'https://www.salus.solutions/insights/test'},403)
        data.update(insight_id='fictional-insight',url='https://www.salus.solutions/insights/fictional-acceptance',title='Fictional Insight for acceptance',source_version='fictional-v1')
        self.assertEqual(self.post(self.staff,'/insights',data).json()['id'],self.thread)
        self.post(self.staff,'/insights',{**data,'source_version':'v2'},409)

    def test_two_reviewers_conflict_on_same_version(self):
        row,_=self.submit()
        payload=dict(version=row['version'],action='Approve',reason='Fictional concurrent exact-version review.',privacy_and_rights_checked=True)
        def run(client):return client.post('/api/discovery/review/'+row['id'],json=payload,headers=HEADERS).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(run,(self.staff,self.staff2)))
        self.assertEqual(sorted(statuses),[200,409])


if __name__=='__main__':
    try:unittest.main()
    finally:SANDBOX.cleanup()
