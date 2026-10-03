"""Governed public dialogue. Candidate source only; disabled until release review."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os
import re
import time
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal

POLICY_VERSION = 'discovery-2026-10-03-v1'
PROMPTS = ('What did we miss?', 'What are you seeing differently?',
           'What has your experience taught you?', 'Have you encountered something similar?',
           'What question should we be asking?', 'What should Salus investigate next?')
STAFF_ROLES = {'System Administrator', 'Assessment Director'}
MAX_BODY_BYTES = 32768


def stamp():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def identifier():
    return f'{int(time.time() * 1000000):016x}' + uuid.uuid4().hex[:16]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ProfileIn(Input):
    display_name: str = Field(min_length=2, max_length=60)
    consent: Literal[True]
    policy_version: Literal['discovery-2026-10-03-v1']

    @field_validator('display_name')
    @classmethod
    def alias(cls, value):
        if re.search(r'[<>@\x00-\x1f\x7f]', value):
            raise ValueError('Use a professional public name without markup or contact details.')
        return value


class PerspectiveIn(Input):
    body: str = Field(min_length=10, max_length=4000)
    prompt: Literal['What did we miss?', 'What are you seeing differently?',
                    'What has your experience taught you?', 'Have you encountered something similar?',
                    'What question should we be asking?', 'What should Salus investigate next?']
    parent_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    request_key: str = Field(pattern=r'^[a-f0-9]{32}$')
    website: str = Field(default='', max_length=200)  # honeypot

    @field_validator('body')
    @classmethod
    def plain_text(cls, value):
        if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', value):
            raise ValueError('Remove control characters.')
        if len(re.findall(r'https?://', value, flags=re.I)) > 3:
            raise ValueError('Use at most three relevant source links.')
        return value


class QuestionIn(PerspectiveIn):
    title: str = Field(min_length=10, max_length=180)


class EditIn(Input):
    body: str = Field(min_length=10, max_length=4000)
    version: int = Field(ge=1)
    _body_check = field_validator('body')(PerspectiveIn.plain_text.__func__)


class VersionIn(Input):
    version: int = Field(ge=1)


class ReviewIn(VersionIn):
    action: Literal['Approve', 'Hide', 'Reject']
    reason: str = Field(min_length=10, max_length=1000)
    privacy_and_rights_checked: Literal[True]


class FlagIn(Input):
    reason: Literal['Privacy or confidential information', 'Harassment or threats',
                    'Spam or promotion', 'Misleading or unsafe content', 'Other concern']
    detail: str = Field(default='', max_length=1000)


class InsightIn(Input):
    insight_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    title: str = Field(min_length=5, max_length=180)
    url: str = Field(max_length=500)
    source_version: str = Field(min_length=1, max_length=100)
    publication_review: str = Field(min_length=10, max_length=1000)

    @field_validator('url')
    @classmethod
    def approved_origin(cls, value):
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or parsed.netloc not in ('www.salus.solutions', 'salus.solutions')
                or not parsed.path.startswith(('/insights/', '/post/')) or parsed.query or parsed.fragment
                or any(ord(c) < 33 for c in value) or '\\' in value):
            raise ValueError('Use the exact published HTTPS Salus Insights URL.')
        return value


class ThreadStateIn(Input):
    open: bool
    reason: str = Field(min_length=10, max_length=1000)


class ParticipantStateIn(Input):
    blocked: bool
    reason: str = Field(min_length=10, max_length=1000)


class CandidateIn(VersionIn):
    kind: Literal['Question', 'Perspective', 'Research lead']
    summary: str = Field(min_length=10, max_length=2000)
    applicability: str = Field(min_length=10, max_length=1000)
    restrictions: str = Field(min_length=10, max_length=1000)


class FlagDispositionIn(Input):
    disposition: Literal['Reviewed - no change', 'Action taken']
    reason: str = Field(min_length=10, max_length=1000)


def ensure_schema(conn):
    # Public community records deliberately have no Member/assessment foreign key.
    # UUID keys work with the existing SQLite/PostgreSQL adapter without ID_TABLES changes.
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS discovery_participants (
      user_id INTEGER PRIMARY KEY, display_name TEXT NOT NULL,
      consent_at TEXT NOT NULL, policy_version TEXT NOT NULL, blocked INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS discovery_threads (
      id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
      insight_id TEXT UNIQUE, source_url TEXT NOT NULL DEFAULT '', source_version TEXT NOT NULL DEFAULT '',
      publication_review TEXT NOT NULL DEFAULT '', open INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS discovery_contributions (
      id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, parent_id TEXT,
      user_id INTEGER NOT NULL, public_name TEXT NOT NULL, body TEXT NOT NULL,
      prompt TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
      content_hash TEXT NOT NULL, request_key TEXT NOT NULL,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(user_id,request_key),
      FOREIGN KEY(thread_id) REFERENCES discovery_threads(id),
      FOREIGN KEY(parent_id) REFERENCES discovery_contributions(id));
    CREATE INDEX IF NOT EXISTS discovery_conversation_order ON discovery_contributions(thread_id,created_at,id);
    CREATE INDEX IF NOT EXISTS discovery_review_order ON discovery_contributions(status,updated_at,id);
    CREATE TABLE IF NOT EXISTS discovery_revisions (
      contribution_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL,
      content_hash TEXT NOT NULL, created_at TEXT NOT NULL,
      PRIMARY KEY(contribution_id,version));
    CREATE TABLE IF NOT EXISTS discovery_events (
      id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, actor_id INTEGER NOT NULL,
      action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS discovery_flags (
      id TEXT PRIMARY KEY, contribution_id TEXT NOT NULL, user_id INTEGER NOT NULL,
      reason TEXT NOT NULL, detail TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open',
      disposition TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
      UNIQUE(contribution_id,user_id));
    CREATE TABLE IF NOT EXISTS discovery_rate_buckets (
      user_id INTEGER NOT NULL, bucket INTEGER NOT NULL, hits INTEGER NOT NULL,
      PRIMARY KEY(user_id,bucket));
    CREATE TABLE IF NOT EXISTS discovery_candidates (
      id TEXT PRIMARY KEY, contribution_id TEXT NOT NULL, source_version INTEGER NOT NULL,
      source_hash TEXT NOT NULL, kind TEXT NOT NULL, summary TEXT NOT NULL,
      applicability TEXT NOT NULL, restrictions TEXT NOT NULL, created_by INTEGER NOT NULL,
      created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Candidate - unvalidated',
      UNIQUE(contribution_id,source_version));
    ''')
    conn.commit()


def register_discovery_conversations(app, host):
    router = APIRouter(prefix='/api/discovery')

    def enabled():
        return os.getenv('SALUS_DISCOVERY_ENABLED', '0') == '1'

    if enabled():
        conn = host['db']()
        try:
            ensure_schema(conn)
        finally:
            conn.close()

    @contextmanager
    def transaction():
        conn = host['db']()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def identity(request):
        ctx = host['auth_context'](request)
        if ctx.get('auth_mode') not in ('session', 'oidc') or not ctx.get('user_id'):
            raise HTTPException(401, 'Sign in with an approved Salus account to participate.')
        if host.get('ENVIRONMENT') == 'production' and ctx.get('auth_mode') != 'oidc':
            raise HTTPException(401, 'Verified sign-in is required.')
        return ctx

    def staff(request):
        ctx = identity(request)
        # A Member administrator is never automatically a public community moderator.
        tenant = os.getenv('SALUS_DISCOVERY_STAFF_TENANT_ID', '')
        reviewers = {v.strip() for v in os.getenv('SALUS_DISCOVERY_REVIEWER_IDS', '').split(',') if v.strip()}
        if (str(ctx.get('tenant_id')) != tenant or str(ctx['user_id']) not in reviewers
                or ctx.get('role') not in STAFF_ROLES):
            raise HTTPException(403, 'An assigned Salus conversation reviewer is required.')
        return ctx

    def participant(conn, request):
        ctx = identity(request)
        row = conn.execute('SELECT * FROM discovery_participants WHERE user_id=?', (ctx['user_id'],)).fetchone()
        if not row or row['policy_version'] != POLICY_VERSION:
            raise HTTPException(403, 'Choose your public name and accept the conversation guidelines first.')
        if row['blocked']:
            raise HTTPException(403, 'Participation is paused. Contact Salus for review.')
        return ctx, row

    def event(conn, entity, ctx, action, detail):
        conn.execute('INSERT INTO discovery_events VALUES(?,?,?,?,?,?)',
                     (identifier(), entity, ctx['user_id'], action, detail, stamp()))

    def quota(conn, ctx):
        # Shared DB upsert serializes each actor's writes across app processes.
        bucket = int(datetime.now(timezone.utc).timestamp()) // 600
        for current, limit in ((bucket, 10), (-(bucket // 144) - 1, 50)):
            conn.execute('''INSERT INTO discovery_rate_buckets(user_id,bucket,hits) VALUES(?,?,1)
              ON CONFLICT(user_id,bucket) DO UPDATE SET hits=discovery_rate_buckets.hits+1''',
                         (ctx['user_id'], current))
            hits = conn.execute('SELECT hits FROM discovery_rate_buckets WHERE user_id=? AND bucket=?',
                                (ctx['user_id'], current)).fetchone()['hits']
            if hits > limit:
                raise HTTPException(429, 'Please pause before contributing again.', headers={'Retry-After': '600'})
        conn.execute('DELETE FROM discovery_rate_buckets WHERE bucket>0 AND bucket<?', (bucket - 288,))
        conn.execute('DELETE FROM discovery_rate_buckets WHERE bucket<0 AND bucket>?', (-(bucket // 144) + 1,))

    def contribution(conn, key):
        row = conn.execute('SELECT * FROM discovery_contributions WHERE id=?', (key,)).fetchone()
        if not row:
            raise HTTPException(404, 'Perspective not found.')
        return dict(row)

    def thread(conn, key):
        row = conn.execute('SELECT * FROM discovery_threads WHERE id=?', (key,)).fetchone()
        if not row:
            raise HTTPException(404, 'Conversation not found.')
        if row['kind'] == 'Question':
            root = conn.execute('SELECT status FROM discovery_contributions WHERE thread_id=? AND parent_id IS NULL', (key,)).fetchone()
            if not root or root['status'] != 'Approved':
                raise HTTPException(404, 'Conversation not available.')
        return dict(row)

    def ancestry_visible(conn, row):
        depth = 0
        while row['parent_id']:
            depth += 1
            row = contribution(conn, row['parent_id'])
            if row['status'] != 'Approved':
                return False
            if depth > 2:
                return False
        return True

    def public_row(row):
        return {k: row[k] for k in ('id', 'thread_id', 'parent_id', 'public_name', 'body',
                                     'prompt', 'version', 'created_at', 'updated_at')}

    def invalidate_candidates(conn, key, status):
        conn.execute('''UPDATE discovery_candidates SET status=? WHERE contribution_id=?
          OR contribution_id IN (SELECT id FROM discovery_contributions WHERE parent_id=?)
          OR contribution_id IN (SELECT c.id FROM discovery_contributions c
            JOIN discovery_contributions p ON c.parent_id=p.id WHERE p.parent_id=?)''',
                     (status, key, key, key))

    @app.middleware('http')
    async def discovery_boundary(request: Request, call_next):
        if request.url.path == '/discovery-conversations' or request.url.path.startswith('/api/discovery/'):
            if not enabled():
                return JSONResponse({'detail': 'Discovery Conversations is awaiting release review.'}, status_code=503)
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                origin = request.headers.get('origin', '')
                expected = f'{request.url.scheme}://{request.url.netloc}'
                if origin != expected or request.headers.get('x-salus-discovery') != '1':
                    return JSONResponse({'detail': 'Use the same-site conversation form.'}, status_code=403)
                if request.headers.get('content-type', '').split(';')[0] != 'application/json':
                    return JSONResponse({'detail': 'Use a text-only conversation submission.'}, status_code=415)
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > MAX_BODY_BYTES:
                        return JSONResponse({'detail': 'Submission is too large.'}, status_code=413)
                request._body = bytes(body)
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            if request.url.path == '/discovery-conversations':
                response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            return response
        return await call_next(request)

    @app.get('/discovery-conversations')
    def page():
        return FileResponse(Path(__file__).parent / 'static' / 'discovery-conversations.html')

    @router.get('/policy')
    def policy():
        return {'version': POLICY_VERSION, 'prompts': PROMPTS,
                'invitation': "Don't just read our perspective. Add yours.",
                'purpose': 'Help us understand the problem better.',
                'knowledge_status': 'Contributions are perspectives, questions and leads until separately validated.'}

    @router.get('/me')
    def me(request: Request):
        ctx = identity(request)
        with transaction() as conn:
            row = conn.execute('SELECT * FROM discovery_participants WHERE user_id=?', (ctx['user_id'],)).fetchone()
        try:
            staff(request)
            reviewer = True
        except HTTPException:
            reviewer = False
        return {'participant': dict(row) if row else None, 'reviewer': reviewer}

    @router.post('/profile')
    def profile(data: ProfileIn, request: Request):
        ctx = identity(request)
        with transaction() as conn:
            existing = conn.execute('SELECT * FROM discovery_participants WHERE user_id=?', (ctx['user_id'],)).fetchone()
            if existing and (existing['blocked'] or existing['display_name'] != data.display_name):
                raise HTTPException(409, 'Contact Salus to review a public-name change or participation pause.')
            quota(conn, ctx)
            conn.execute('''INSERT INTO discovery_participants(user_id,display_name,consent_at,policy_version)
              VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET consent_at=excluded.consent_at,policy_version=excluded.policy_version''',
                         (ctx['user_id'], data.display_name, stamp(), POLICY_VERSION))
            event(conn, str(ctx['user_id']), ctx, 'Consent', POLICY_VERSION)
        return {'status': 'Ready', 'display_name': data.display_name}

    @router.get('/threads')
    def threads(after: str = '', limit: int = 20):
        limit = max(1, min(limit, 50))
        with transaction() as conn:
            rows = conn.execute('''SELECT t.* FROM discovery_threads t WHERE t.id>?
              AND (t.kind='Insight' OR EXISTS(SELECT 1 FROM discovery_contributions c
                WHERE c.thread_id=t.id AND c.parent_id IS NULL AND c.status='Approved'))
              ORDER BY t.id LIMIT ?''', (after, limit + 1)).fetchall()
        return {'items': [{k: r[k] for k in ('id', 'kind', 'title', 'source_url', 'source_version', 'open', 'created_at')} for r in rows[:limit]],
                'next': rows[limit-1]['id'] if len(rows) > limit else None}

    @router.get('/threads/{thread_id}')
    def conversation(thread_id: str, after: str = '', limit: int = 50):
        limit = max(1, min(limit, 100))
        with transaction() as conn:
            t = thread(conn, thread_id)
            rows = conn.execute('''SELECT * FROM discovery_contributions WHERE thread_id=?
              AND status='Approved' AND id>? ORDER BY id LIMIT ?''', (thread_id, after, limit + 1)).fetchall()
            visible = [public_row(r) for r in rows[:limit] if ancestry_visible(conn, r)]
        return {'thread': {k: t[k] for k in ('id', 'kind', 'title', 'source_url', 'source_version', 'open', 'created_at')},
                'items': visible, 'next': rows[limit-1]['id'] if len(rows) > limit else None}

    def add(conn, t, data, ctx, p):
        if data.website:
            raise HTTPException(422, 'The submission could not be accepted.')
        if not t['open']:
            raise HTTPException(409, 'This conversation is closed to new perspectives.')
        parent = None
        if data.parent_id:
            parent = contribution(conn, data.parent_id)
            if parent['thread_id'] != t['id'] or parent['status'] != 'Approved' or not ancestry_visible(conn, parent):
                raise HTTPException(409, 'Reply to a currently published perspective in this conversation.')
            if parent['parent_id'] and contribution(conn, parent['parent_id'])['parent_id']:
                raise HTTPException(409, 'Add a perspective to the conversation instead of nesting further.')
        digest = hashlib.sha256(data.body.encode('utf-8')).hexdigest()
        existing = conn.execute('SELECT * FROM discovery_contributions WHERE user_id=? AND request_key=?',
                                (ctx['user_id'], data.request_key)).fetchone()
        if existing:
            if existing['thread_id'] != t['id'] or existing['content_hash'] != digest or existing['parent_id'] != data.parent_id or existing['prompt'] != data.prompt:
                raise HTTPException(409, 'That submission reference already belongs to a different perspective.')
            return {'id': existing['id'], 'thread_id': t['id'], 'status': existing['status'], 'version': existing['version']}
        if conn.execute('SELECT 1 FROM discovery_contributions WHERE user_id=? AND thread_id=? AND content_hash=?',
                        (ctx['user_id'], t['id'], digest)).fetchone():
            raise HTTPException(409, 'You already shared this perspective here.')
        key, ts = identifier(), stamp()
        conn.execute('''INSERT INTO discovery_contributions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                     (key, t['id'], data.parent_id, ctx['user_id'], p['display_name'], data.body,
                      data.prompt, 'Pending', 1, digest, data.request_key, ts, ts))
        conn.execute('INSERT INTO discovery_revisions VALUES(?,?,?,?,?)', (key, 1, data.body, digest, ts))
        event(conn, key, ctx, 'Submitted', 'Pending staff review; ' + POLICY_VERSION)
        return {'id': key, 'thread_id': t['id'], 'status': 'Pending', 'version': 1}

    @router.post('/threads/{thread_id}/perspectives', status_code=201)
    def perspective(thread_id: str, data: PerspectiveIn, request: Request):
        with transaction() as conn:
            ctx, p = participant(conn, request)
            quota(conn, ctx)
            return add(conn, thread(conn, thread_id), data, ctx, p)

    @router.post('/questions', status_code=201)
    def question(data: QuestionIn, request: Request):
        if data.parent_id:
            raise HTTPException(422, 'A new Discovery Question starts its own conversation.')
        with transaction() as conn:
            ctx, p = participant(conn, request)
            quota(conn, ctx)
            existing = conn.execute('''SELECT t.* FROM discovery_threads t JOIN discovery_contributions c ON c.thread_id=t.id
              WHERE c.user_id=? AND c.request_key=?''', (ctx['user_id'], data.request_key)).fetchone()
            if existing:
                if existing['kind'] != 'Question' or existing['title'] != data.title:
                    raise HTTPException(409, 'That submission reference belongs to a different question.')
                return add(conn, dict(existing), data, ctx, p)
            t = {'id': identifier(), 'open': 1}
            conn.execute('INSERT INTO discovery_threads(id,kind,title,created_at) VALUES(?,?,?,?)',
                         (t['id'], 'Question', data.title, stamp()))
            return add(conn, t, data, ctx, p)

    @router.get('/mine')
    def mine(request: Request, after: str = '', limit: int = 50):
        ctx = identity(request)
        limit = max(1, min(limit, 100))
        with transaction() as conn:
            rows = conn.execute('SELECT * FROM discovery_contributions WHERE user_id=? AND id>? ORDER BY id LIMIT ?',
                                (ctx['user_id'], after, limit + 1)).fetchall()
        return {'items': [{**public_row(r), 'status': r['status']} for r in rows[:limit]],
                'next': rows[limit-1]['id'] if len(rows) > limit else None}

    def owned(conn, key, ctx, version):
        row = contribution(conn, key)
        if row['user_id'] != ctx['user_id']:
            raise HTTPException(404, 'Your perspective was not found.')
        if row['version'] != version or row['status'] == 'Withdrawn':
            raise HTTPException(409, 'Refresh the current perspective before changing it.')
        return row

    @router.patch('/perspectives/{key}')
    def edit(key: str, data: EditIn, request: Request):
        with transaction() as conn:
            ctx, _ = participant(conn, request)
            quota(conn, ctx)
            row = owned(conn, key, ctx, data.version)
            digest, ts = hashlib.sha256(data.body.encode('utf-8')).hexdigest(), stamp()
            cursor = conn.execute('''UPDATE discovery_contributions SET body=?,content_hash=?,version=version+1,status='Pending',updated_at=?
              WHERE id=? AND version=? AND status<>'Withdrawn' ''', (data.body, digest, ts, key, data.version))
            if cursor.rowcount != 1:
                raise HTTPException(409, 'Another change occurred. Refresh before editing.')
            conn.execute('INSERT INTO discovery_revisions VALUES(?,?,?,?,?)', (key, row['version']+1, data.body, digest, ts))
            invalidate_candidates(conn, key, 'Source changed - re-review required')
            event(conn, key, ctx, 'Edited', 'New version held for staff review.')
        return {'id': key, 'version': data.version+1, 'status': 'Pending'}

    @router.post('/perspectives/{key}/withdraw')
    def withdraw(key: str, data: VersionIn, request: Request):
        # Blocked contributors can still remove their own public contributions.
        ctx = identity(request)
        with transaction() as conn:
            quota(conn, ctx)
            row = owned(conn, key, ctx, data.version)
            cursor = conn.execute("UPDATE discovery_contributions SET status='Withdrawn',version=version+1,updated_at=? WHERE id=? AND version=?", (stamp(), key, data.version))
            if cursor.rowcount != 1:
                raise HTTPException(409, 'Refresh before withdrawing.')
            conn.execute('INSERT INTO discovery_revisions VALUES(?,?,?,?,?)', (key, data.version+1, row['body'], row['content_hash'], stamp()))
            invalidate_candidates(conn, key, 'Source withdrawn - re-review required')
            event(conn, key, ctx, 'Withdrawn', 'Public access removed; restricted review history retained.')
        return {'status': 'Withdrawn', 'version': data.version+1}

    @router.post('/perspectives/{key}/flags', status_code=201)
    def flag(key: str, data: FlagIn, request: Request):
        ctx = identity(request)
        with transaction() as conn:
            quota(conn, ctx)
            row = contribution(conn, key)
            thread(conn, row['thread_id'])
            if row['status'] != 'Approved' or not ancestry_visible(conn, row):
                raise HTTPException(404, 'Published perspective not found.')
            old = conn.execute('SELECT id FROM discovery_flags WHERE contribution_id=? AND user_id=?', (key, ctx['user_id'])).fetchone()
            if old:
                return {'id': old['id'], 'status': 'Received'}
            flag_id = identifier()
            conn.execute('INSERT INTO discovery_flags(id,contribution_id,user_id,reason,detail,created_at) VALUES(?,?,?,?,?,?)',
                         (flag_id, key, ctx['user_id'], data.reason, data.detail, stamp()))
            event(conn, key, ctx, 'Flagged', flag_id)
        return {'id': flag_id, 'status': 'Received'}

    @router.get('/review')
    def review_queue(request: Request, after: str = '', limit: int = 50):
        staff(request)
        limit = max(1, min(limit, 100))
        with transaction() as conn:
            rows = conn.execute('''SELECT c.*,t.title,t.kind,t.source_url FROM discovery_contributions c
              JOIN discovery_threads t ON t.id=c.thread_id WHERE c.id>? ORDER BY c.id LIMIT ?''', (after, limit+1)).fetchall()
            flags = conn.execute("SELECT * FROM discovery_flags WHERE status='Open' ORDER BY created_at,id LIMIT 100").fetchall()
        return {'items': [dict(r) for r in rows[:limit]], 'flags': [dict(r) for r in flags],
                'next': rows[limit-1]['id'] if len(rows)>limit else None}

    @router.post('/review/{key}')
    def moderate(key: str, data: ReviewIn, request: Request):
        ctx = staff(request)
        with transaction() as conn:
            row = contribution(conn, key)
            if row['user_id'] == ctx['user_id']:
                raise HTTPException(403, 'A different assigned reviewer must review your contribution.')
            if row['version'] != data.version or row['status'] == 'Withdrawn':
                raise HTTPException(409, 'Review the current version. Withdrawn perspectives cannot be republished.')
            if data.action == 'Approve':
                p = conn.execute('SELECT blocked FROM discovery_participants WHERE user_id=?', (row['user_id'],)).fetchone()
                if not p or p['blocked'] or not ancestry_visible(conn, row):
                    raise HTTPException(409, 'Resolve the participation or parent review hold first.')
            status = {'Approve': 'Approved', 'Hide': 'Hidden', 'Reject': 'Rejected'}[data.action]
            cursor = conn.execute('UPDATE discovery_contributions SET status=?,version=version+1,updated_at=? WHERE id=? AND version=?',
                                  (status, stamp(), key, data.version))
            if cursor.rowcount != 1:
                raise HTTPException(409, 'The perspective changed during review.')
            conn.execute('INSERT INTO discovery_revisions VALUES(?,?,?,?,?)', (key, data.version+1, row['body'], row['content_hash'], stamp()))
            if status != 'Approved':
                invalidate_candidates(conn, key, 'Source held - re-review required')
            event(conn, key, ctx, 'Review - ' + status, data.reason)
        return {'id': key, 'status': status, 'version': data.version+1}

    @router.get('/history/{key}')
    def history(key: str, request: Request):
        staff(request)
        with transaction() as conn:
            contribution(conn, key)
            revisions = conn.execute('SELECT * FROM discovery_revisions WHERE contribution_id=? ORDER BY version', (key,)).fetchall()
            events = conn.execute('SELECT * FROM discovery_events WHERE entity_id=? ORDER BY created_at,id', (key,)).fetchall()
        return {'revisions': [dict(r) for r in revisions], 'events': [dict(r) for r in events]}

    @router.post('/insights', status_code=201)
    def register_insight(data: InsightIn, request: Request):
        ctx = staff(request)
        with transaction() as conn:
            existing = conn.execute('SELECT * FROM discovery_threads WHERE insight_id=?', (data.insight_id,)).fetchone()
            if existing:
                if existing['source_url'] != data.url or existing['source_version'] != data.source_version or existing['title'] != data.title:
                    raise HTTPException(409, 'The registered Insight differs. Resolve the source-version impact before replacement.')
                return {'id': existing['id'], 'status': 'Registered'}
            key = identifier()
            conn.execute('''INSERT INTO discovery_threads(id,kind,title,insight_id,source_url,source_version,publication_review,created_at)
              VALUES(?,?,?,?,?,?,?,?)''', (key, 'Insight', data.title, data.insight_id, data.url, data.source_version, data.publication_review, stamp()))
            event(conn, key, ctx, 'Insight registered', data.publication_review)
        return {'id': key, 'status': 'Registered'}

    @router.post('/threads/{key}/state')
    def thread_state(key: str, data: ThreadStateIn, request: Request):
        ctx = staff(request)
        with transaction() as conn:
            row = conn.execute('SELECT id FROM discovery_threads WHERE id=?', (key,)).fetchone()
            if not row:
                raise HTTPException(404, 'Conversation not found.')
            conn.execute('UPDATE discovery_threads SET open=? WHERE id=?', (int(data.open), key))
            event(conn, key, ctx, 'Conversation opened' if data.open else 'Conversation closed', data.reason)
        return {'open': data.open}

    @router.post('/participants/{user_id}/state')
    def participant_state(user_id: int, data: ParticipantStateIn, request: Request):
        ctx = staff(request)
        with transaction() as conn:
            cursor = conn.execute('UPDATE discovery_participants SET blocked=? WHERE user_id=?', (int(data.blocked), user_id))
            if cursor.rowcount != 1:
                raise HTTPException(404, 'Participant not found.')
            event(conn, str(user_id), ctx, 'Participant paused' if data.blocked else 'Participant restored', data.reason)
        return {'blocked': data.blocked}

    @router.post('/flags/{key}/disposition')
    def disposition(key: str, data: FlagDispositionIn, request: Request):
        ctx = staff(request)
        with transaction() as conn:
            cursor = conn.execute("UPDATE discovery_flags SET status='Reviewed',disposition=? WHERE id=? AND status='Open'",
                                  (data.disposition + ': ' + data.reason, key))
            if cursor.rowcount != 1:
                raise HTTPException(409, 'The flag is unavailable or already reviewed.')
            event(conn, key, ctx, 'Flag disposition', data.disposition + ': ' + data.reason)
        return {'status': 'Reviewed'}

    @router.post('/perspectives/{key}/candidate', status_code=201)
    def candidate(key: str, data: CandidateIn, request: Request):
        ctx = staff(request)
        with transaction() as conn:
            row = contribution(conn, key)
            thread(conn, row['thread_id'])
            if row['status'] != 'Approved' or row['version'] != data.version or not ancestry_visible(conn, row):
                raise HTTPException(409, 'Only the current published version can supply a candidate lead.')
            # Lock/recheck the exact source revision against concurrent edit/withdrawal.
            cursor = conn.execute("UPDATE discovery_contributions SET version=version WHERE id=? AND version=? AND status='Approved'", (key, data.version))
            if cursor.rowcount != 1:
                raise HTTPException(409, 'The source changed during candidate capture.')
            old = conn.execute('SELECT id FROM discovery_candidates WHERE contribution_id=? AND source_version=?', (key, data.version)).fetchone()
            if old:
                return {'id': old['id'], 'status': 'Candidate - unvalidated'}
            candidate_id = identifier()
            conn.execute('''INSERT INTO discovery_candidates(id,contribution_id,source_version,source_hash,kind,summary,applicability,restrictions,created_by,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?)''', (candidate_id, key, data.version, row['content_hash'], data.kind,
                  data.summary, data.applicability, data.restrictions, ctx['user_id'], stamp()))
            event(conn, key, ctx, 'Candidate captured', candidate_id + '; not validated knowledge or publication authority.')
        return {'id': candidate_id, 'status': 'Candidate - unvalidated'}

    @router.get('/candidates')
    def candidates(request: Request, after: str = '', limit: int = 50):
        staff(request)
        limit = max(1, min(limit, 100))
        with transaction() as conn:
            rows = conn.execute('SELECT * FROM discovery_candidates WHERE id>? ORDER BY id LIMIT ?', (after, limit+1)).fetchall()
            items = []
            for r in rows[:limit]:
                item = dict(r)
                source = contribution(conn, r['contribution_id'])
                try:
                    thread(conn, source['thread_id'])
                    available = (source['status'] == 'Approved' and source['version'] == r['source_version']
                                 and source['content_hash'] == r['source_hash'] and ancestry_visible(conn, source))
                except HTTPException:
                    available = False
                if not available:
                    item['status'] = 'Source unavailable - re-review required'
                items.append(item)
        return {'items': items, 'next': rows[limit-1]['id'] if len(rows)>limit else None}

    app.include_router(router)
