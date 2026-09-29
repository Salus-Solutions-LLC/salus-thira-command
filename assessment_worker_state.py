"""Durable, tenant-scoped assessment queue primitives.

This module is deliberately free of AI, source retrieval, and report publication.
Those operations require separately reviewed adapters and authorization. The state
machine is usable in a local interruption test; the production store is PostgreSQL.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS assessment_work_packages (
  package_id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  engagement_id TEXT NOT NULL,
  assessment_level INTEGER NOT NULL CHECK(assessment_level BETWEEN 1 AND 3),
  state TEXT NOT NULL DEFAULT 'active' CHECK(state IN ('active','human_gate','complete','operator_paused')),
  lease_owner TEXT,
  lease_until REAL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  UNIQUE(tenant_id, engagement_id, assessment_level)
);
CREATE TABLE IF NOT EXISTS assessment_work_items (
  item_id TEXT PRIMARY KEY,
  package_id TEXT NOT NULL REFERENCES assessment_work_packages(package_id),
  tenant_id TEXT NOT NULL,
  item_key TEXT NOT NULL,
  stage TEXT NOT NULL CHECK(stage IN ('source','analysis','report','qa')),
  priority INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN
    ('queued','working','retry_wait','review_required','complete','blocked_access','blocked_rights','blocked_expertise','failed_escalated')),
  source_ref TEXT NOT NULL,
  source_sha256 TEXT,
  checkpoint_json TEXT NOT NULL DEFAULT '{}',
  output_ref TEXT,
  output_sha256 TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  next_eligible_at REAL NOT NULL,
  lease_owner TEXT,
  lease_until REAL,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  UNIQUE(package_id, item_key)
);
CREATE INDEX IF NOT EXISTS assessment_work_ready_idx
  ON assessment_work_items(tenant_id, state, next_eligible_at, priority);
CREATE TABLE IF NOT EXISTS assessment_work_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  package_id TEXT NOT NULL,
  item_id TEXT,
  tenant_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  observed_at REAL NOT NULL,
  worker_id TEXT,
  detail_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS assessment_work_events_pkg_idx
  ON assessment_work_events(tenant_id, package_id, observed_at);
"""

_OPAQUE_REF = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,159}\Z')
_SHA256 = re.compile(r'[0-9a-fA-F]{64}\Z')


def _check_ref(value: str):
    if not _OPAQUE_REF.fullmatch(value):
        raise ValueError('opaque reference required; paths and personal data are forbidden')


def _check_sha(value: str | None):
    if value is not None and not _SHA256.fullmatch(value):
        raise ValueError('SHA-256 hex digest required')


@dataclass(frozen=True)
class ClaimedItem:
    item_id: str
    package_id: str
    tenant_id: str
    item_key: str
    stage: str
    source_ref: str
    source_sha256: str | None
    checkpoint: dict[str, Any]
    attempts: int


class AssessmentQueue:
    """Local state engine; production use requires the reviewed PostgreSQL adapter."""

    def __init__(self, path: str | Path, *, clock=time.time):
        self.path = str(path)
        self.clock = clock
        self.conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA busy_timeout=30000')
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def _event(self, tenant_id, package_id, item_id, kind, worker_id=None, detail=None):
        # Never place source content, personal data, credentials or access settings here.
        self.conn.execute(
            'INSERT INTO assessment_work_events '
            '(package_id,item_id,tenant_id,event_type,observed_at,worker_id,detail_json) '
            'VALUES(?,?,?,?,?,?,?)',
            (package_id, item_id, tenant_id, kind, self.clock(), worker_id,
             json.dumps(detail or {}, sort_keys=True)),
        )

    def add_package(self, package_id, tenant_id, engagement_id, level):
        now = self.clock()
        self.conn.execute(
            'INSERT OR IGNORE INTO assessment_work_packages '
            '(package_id,tenant_id,engagement_id,assessment_level,created_at,updated_at) '
            'VALUES(?,?,?,?,?,?)',
            (package_id, tenant_id, engagement_id, level, now, now),
        )
        row = self.conn.execute('SELECT tenant_id,engagement_id,assessment_level FROM '
                                'assessment_work_packages WHERE package_id=?', (package_id,)).fetchone()
        if row is None or tuple(row) != (tenant_id, engagement_id, level):
            raise ValueError('package identity conflict')

    def add_item(self, item_id, package_id, tenant_id, item_key, stage, priority,
                 source_ref, source_sha256=None):
        _check_ref(source_ref)
        _check_sha(source_sha256)
        package = self.conn.execute('SELECT tenant_id,state FROM assessment_work_packages '
                                    'WHERE package_id=?', (package_id,)).fetchone()
        if package is None or package['tenant_id'] != tenant_id or package['state'] != 'active':
            raise ValueError('active package and matching tenant required')
        now = self.clock()
        self.conn.execute(
            'INSERT OR IGNORE INTO assessment_work_items '
            '(item_id,package_id,tenant_id,item_key,stage,priority,source_ref,source_sha256,'
            'next_eligible_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (item_id, package_id, tenant_id, item_key, stage, priority,
             source_ref, source_sha256, now, now, now),
        )
        row = self.conn.execute('SELECT item_id,stage,source_ref,source_sha256 FROM '
                                'assessment_work_items WHERE package_id=? AND item_key=?',
                                (package_id, item_key)).fetchone()
        if row is None or tuple(row) != (item_id, stage, source_ref, source_sha256):
            raise ValueError('item idempotency conflict')

    def claim(self, tenant_id, worker_id, lease_seconds=120):
        now = self.clock()
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            # One package writer prevents simultaneous mutations of its four draft identities.
            row = self.conn.execute(
                "SELECT i.* FROM assessment_work_items i JOIN assessment_work_packages p "
                "ON p.package_id=i.package_id AND p.tenant_id=i.tenant_id "
                "WHERE i.tenant_id=? AND p.state='active' "
                "AND (p.lease_until IS NULL OR p.lease_until<=?) "
                "AND i.state IN ('queued','retry_wait','working') "
                "AND i.next_eligible_at<=? AND (i.lease_until IS NULL OR i.lease_until<=?) "
                "ORDER BY i.priority DESC,i.created_at,i.item_id LIMIT 1",
                (tenant_id, now, now, now),
            ).fetchone()
            if row is None:
                self.conn.execute('COMMIT')
                return None
            recovered = row['state'] == 'working'
            until = now + lease_seconds
            self.conn.execute(
                'UPDATE assessment_work_packages SET lease_owner=?,lease_until=?,updated_at=? '
                'WHERE package_id=? AND tenant_id=?',
                (worker_id, until, now, row['package_id'], tenant_id),
            )
            self.conn.execute(
                "UPDATE assessment_work_items SET state='working',lease_owner=?,lease_until=?,"
                'attempts=attempts+1,updated_at=? WHERE item_id=? AND tenant_id=?',
                (worker_id, until, now, row['item_id'], tenant_id),
            )
            if recovered:
                self._event(tenant_id, row['package_id'], row['item_id'], 'recovered', worker_id,
                            {'expired_at': row['lease_until'], 'idle_seconds': max(0, now - row['lease_until'])})
            self._event(tenant_id, row['package_id'], row['item_id'], 'claimed', worker_id,
                        {'attempt': row['attempts'] + 1, 'lease_until': until})
            self.conn.execute('COMMIT')
            return ClaimedItem(row['item_id'], row['package_id'], tenant_id, row['item_key'],
                               row['stage'], row['source_ref'], row['source_sha256'],
                               json.loads(row['checkpoint_json']), row['attempts'] + 1)
        except Exception:
            self.conn.execute('ROLLBACK')
            raise

    def checkpoint(self, item: ClaimedItem, worker_id, data, lease_seconds=120):
        now = self.clock()
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            row = self.conn.execute('SELECT lease_owner,lease_until,state FROM assessment_work_items '
                                    'WHERE item_id=? AND tenant_id=?',
                                    (item.item_id, item.tenant_id)).fetchone()
            if row is None or row['lease_owner'] != worker_id or row['lease_until'] <= now or row['state'] != 'working':
                raise RuntimeError('current item lease required')
            until = now + lease_seconds
            self.conn.execute('UPDATE assessment_work_items SET checkpoint_json=?,lease_until=?,updated_at=? '
                              'WHERE item_id=? AND tenant_id=?',
                              (json.dumps(data, sort_keys=True), until, now, item.item_id, item.tenant_id))
            self.conn.execute('UPDATE assessment_work_packages SET lease_until=?,updated_at=? '
                              'WHERE package_id=? AND tenant_id=? AND lease_owner=?',
                              (until, now, item.package_id, item.tenant_id, worker_id))
            self._event(item.tenant_id, item.package_id, item.item_id, 'checkpointed', worker_id,
                        {'checkpoint_keys': sorted(data)})
            self.conn.execute('COMMIT')
        except Exception:
            self.conn.execute('ROLLBACK')
            raise

    def finish(self, item: ClaimedItem, worker_id, output_ref, output_sha256, *, review_required=False):
        _check_ref(output_ref)
        _check_sha(output_sha256)
        now = self.clock()
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            row = self.conn.execute('SELECT state,lease_owner,lease_until,output_ref,output_sha256 '
                                    'FROM assessment_work_items WHERE item_id=? AND tenant_id=?',
                                    (item.item_id, item.tenant_id)).fetchone()
            if row is None:
                raise ValueError('item not found in tenant')
            if row['state'] in ('complete', 'review_required'):
                if (row['output_ref'], row['output_sha256']) != (output_ref, output_sha256):
                    raise ValueError('conflicting repeated output')
                self.conn.execute('COMMIT')
                return False
            if row['state'] != 'working' or row['lease_owner'] != worker_id or row['lease_until'] <= now:
                raise RuntimeError('current item lease required')
            state = 'review_required' if review_required else 'complete'
            self.conn.execute('UPDATE assessment_work_items SET state=?,output_ref=?,output_sha256=?, '
                              'lease_owner=NULL,lease_until=NULL,updated_at=? '
                              'WHERE item_id=? AND tenant_id=?',
                              (state, output_ref, output_sha256, now, item.item_id, item.tenant_id))
            self.conn.execute('UPDATE assessment_work_packages SET lease_owner=NULL,lease_until=NULL,updated_at=? '
                              'WHERE package_id=? AND tenant_id=? AND lease_owner=?',
                              (now, item.package_id, item.tenant_id, worker_id))
            self._event(item.tenant_id, item.package_id, item.item_id, state, worker_id,
                        {'output_ref': output_ref, 'output_sha256': output_sha256})
            self.conn.execute('COMMIT')
            return True
        except Exception:
            self.conn.execute('ROLLBACK')
            raise

    def fail_retryable(self, item: ClaimedItem, worker_id, error_code, *, delay_seconds=30, max_attempts=3):
        now = self.clock()
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            row = self.conn.execute('SELECT attempts,lease_owner,lease_until,state FROM assessment_work_items '
                                    'WHERE item_id=? AND tenant_id=?',
                                    (item.item_id, item.tenant_id)).fetchone()
            if row is None or row['lease_owner'] != worker_id or row['lease_until'] <= now or row['state'] != 'working':
                raise RuntimeError('current item lease required')
            state = 'failed_escalated' if row['attempts'] >= max_attempts else 'retry_wait'
            self.conn.execute('UPDATE assessment_work_items SET state=?,next_eligible_at=?, '
                              'lease_owner=NULL,lease_until=NULL,updated_at=? WHERE item_id=? AND tenant_id=?',
                              (state, now + delay_seconds, now, item.item_id, item.tenant_id))
            self.conn.execute('UPDATE assessment_work_packages SET lease_owner=NULL,lease_until=NULL,updated_at=? '
                              'WHERE package_id=? AND tenant_id=? AND lease_owner=?',
                              (now, item.package_id, item.tenant_id, worker_id))
            self._event(item.tenant_id, item.package_id, item.item_id, state, worker_id,
                        {'error_code': error_code, 'attempts': row['attempts']})
            self.conn.execute('COMMIT')
            return state
        except Exception:
            self.conn.execute('ROLLBACK')
            raise

    def block(self, item: ClaimedItem, worker_id, state, reason_code):
        if state not in ('review_required', 'blocked_access', 'blocked_rights', 'blocked_expertise'):
            raise ValueError('unsupported gate state')
        now = self.clock()
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            row = self.conn.execute('SELECT state,lease_owner,lease_until FROM assessment_work_items '
                                    'WHERE item_id=? AND tenant_id=?',
                                    (item.item_id, item.tenant_id)).fetchone()
            if row is None or row['state'] != 'working' or row['lease_owner'] != worker_id or row['lease_until'] <= now:
                raise RuntimeError('current item lease required')
            self.conn.execute('UPDATE assessment_work_items SET state=?,lease_owner=NULL,lease_until=NULL,updated_at=? '
                              'WHERE item_id=? AND tenant_id=?',
                              (state, now, item.item_id, item.tenant_id))
            self.conn.execute('UPDATE assessment_work_packages SET lease_owner=NULL,lease_until=NULL,updated_at=? '
                              'WHERE package_id=? AND tenant_id=? AND lease_owner=?',
                              (now, item.package_id, item.tenant_id, worker_id))
            self._event(item.tenant_id, item.package_id, item.item_id, state, worker_id,
                        {'reason_code': reason_code})
            self.conn.execute('COMMIT')
        except Exception:
            self.conn.execute('ROLLBACK')
            raise

    def events(self, tenant_id, package_id):
        return [dict(r) for r in self.conn.execute(
            'SELECT event_type,observed_at,worker_id,detail_json FROM assessment_work_events '
            'WHERE tenant_id=? AND package_id=? ORDER BY event_id',
            (tenant_id, package_id),
        )]

