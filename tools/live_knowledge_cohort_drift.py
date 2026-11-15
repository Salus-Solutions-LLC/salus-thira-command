"""Read-only current-cohort diagnostic; no search, plan or baseline adoption."""
from __future__ import annotations
import os
import re
import sys
from datetime import datetime, timezone

try:
    import salus_postsearch_support as support
except ModuleNotFoundError:
    from tools import live_knowledge_postsearch_resume as support

STAGE = "not_started"


class ReadOnlyConnection:
    def __init__(self, inner):
        self.inner = inner
        self.backend = getattr(inner, "backend", "sqlite")

    def execute(self, sql, params=()):
        # Permit reviewed read queries only, including the materialized SELECT
        # CTE in read_evidence. Reject all other tokens and multiple statements.
        clean = re.sub(r"'(?:''|[^'])*'", "''", sql).strip().rstrip(';').strip()
        if ';' in clean or '--' in clean or '/*' in clean:
            raise ValueError("QUERY_DENIED")
        words = re.findall(r'[A-Z_]+', clean.upper())
        forbidden = {'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'CREATE', 'ALTER', 'DROP',
                     'TRUNCATE', 'COPY', 'CALL', 'DO', 'INTO', 'LOCK', 'COMMIT',
                     'GRANT', 'REVOKE', 'VACUUM', 'ANALYZE'}
        if not words or words[0] not in {'SELECT', 'WITH'} or forbidden.intersection(words):
            raise ValueError("QUERY_DENIED")
        return self.inner.execute(sql, params)


def summarize(evidence):
    represented = set(evidence['represented'])
    by_source = {}
    for row in evidence['candidates']:
        if row['source_item_id'] not in represented:
            raise ValueError('CANDIDATE_MEMBERSHIP')
        by_source.setdefault(row['source_item_id'], []).append(row)
    held = {r['source_item_id'] for r in evidence['holds']}
    available = {s for s, rows in by_source.items() if any(r['legacy_complete'] for r in rows)}
    exact = {s for s, rows in by_source.items()
             if any(r['extraction_status'] == 'Complete' and r['has_text'] for r in rows)}
    strict = {s for s, rows in by_source.items()
              if any(r['extraction_status'] == 'Complete' and r['strict_text'] for r in rows)}
    unresolved = represented - available
    categories = {key: 0 for key in support.CATEGORIES}
    for source in unresolved:
        categories[support.cohort(by_source.get(source, []), source in held)] += 1
    if sum(categories.values()) != len(unresolved):
        raise ValueError('PARTITION_INVALID')
    result = {'REPRESENTED_FILES': len(represented), 'CANDIDATE_ROWS': len(evidence['candidates']),
              'LEGACY_CONTENT_AVAILABLE': len(available), 'EXACT_COMPLETE_NONEMPTY_TEXT': len(exact),
              'STRICT_COMPLETE_TEXT': len(strict), 'UNRESOLVED_FILES': len(unresolved),
              'AVAILABILITY_EXCEPTIONS': len(available - exact),
              'EXACT_NOT_LEGACY': len(exact - available), 'EXACT_STRICT_DIFFERENCE': len(exact ^ strict),
              'GOVERNED_HOLD_SOURCES': len(held),
              'REPRESENTED_COUNT_DELTA_FROM_RECEIPTS': len(represented) - 23632,
              'UNRESOLVED_COUNT_DELTA_FROM_RECEIPTS': len(unresolved) - 8404,
              'REPRESENTED_SET_SHA256': support.digest(sorted(represented)),
              'HOLD_SOURCE_SET_SHA256': support.digest(sorted(held)),
              'MULTI_CANDIDATE_UNRESOLVED_SOURCES': sum(len(by_source.get(s, [])) > 1 for s in unresolved),
              'NO_RECORDED_ARCHIVE_UNRESOLVED_SOURCES': sum(
                  bool(by_source.get(s)) and not any(r['source_archive_item_id'] for r in by_source[s])
                  for s in unresolved),
              'PROJECTION_SHA256': support.baseline_digest(evidence),
              'CORE_INVARIANTS_SHA256': support.digest(support.invariant_view(evidence))}
    result['ACCEPTED_PROJECTION_MATCH'] = int(result['PROJECTION_SHA256'] == support.BASELINE_SHA256)
    result.update({'CATEGORY_' + key.upper(): count for key, count in categories.items()})
    return result


def observe(inner):
    # DB-enforced READ ONLY is established before any diagnostic query. The
    # facade independently rejects DML/DDL, mutating CTEs and multi-statements.
    if getattr(inner, 'backend', 'sqlite') == 'postgres':
        inner.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        inner.execute("SET LOCAL statement_timeout='90s'")
    else:
        inner.execute('PRAGMA query_only=ON')
        inner.execute('BEGIN')
    conn = ReadOnlyConnection(inner)
    receipt_sha = support.preserved_receipts(conn)
    support.target_empty(conn)
    evidence = support.read_evidence(conn)
    return summarize(evidence), receipt_sha, evidence


def verify_pair(first, second):
    if first[0] != second[0] or first[1] != second[1]:
        raise ValueError('INDEPENDENT_CORE_DRIFT')
    return support.scheduling_changes(first[2], second[2])


def main():
    global STAGE
    from database import connect_database
    if os.getenv('SALUS_DB_BACKEND', '').lower() != 'postgres':
        raise SystemExit('Managed PostgreSQL required')
    inner = None
    try:
        STAGE = 'first_read_only_snapshot'
        inner = connect_database()
        first = observe(inner)
        inner.close()
        inner = None
        print('COHORT_DRIFT_FIRST_SNAPSHOT_AT=' + datetime.now(timezone.utc).isoformat(), flush=True)
        STAGE = 'independent_read_only_snapshot'
        inner = connect_database()
        second = observe(inner)
        changes = verify_pair(first, second)
        print('COHORT_DRIFT_READBACK_AT=' + datetime.now(timezone.utc).isoformat(), flush=True)
        for key, value in sorted(second[0].items()):
            print('COHORT_DRIFT_' + key + '=' + str(value), flush=True)
        print('COHORT_DRIFT_RECEIPT_SNAPSHOT_SHA256=' + second[1], flush=True)
        for key, value in changes.items():
            print('COHORT_DRIFT_SCHEDULING_' + key.upper() + '_CHANGED=' + str(value), flush=True)
        for key, value in {'PRESERVED_RECEIPTS': 4, 'PLAN_ROWS': 0, 'BATCH_ROWS': 0, 'EVENT_ROWS': 0,
                           'DATABASE_WRITES': 0, 'NEW_RECEIPTS': 0, 'PLAN_PREPARATION': 0,
                           'SOURCE_CONTENT_DOWNLOADS': 0, 'HISTORICAL_MEMBERSHIP_RECONSTRUCTED': 0,
                           'NEW_BASELINE_ADOPTED': 0, 'FRESH_CONNECTION_VERIFIED': 1, 'COMPLETE': 1}.items():
            print('COHORT_DRIFT_' + key + '=' + str(value), flush=True)
    except Exception as exc:
        allowed = {'QUERY_DENIED', 'CANDIDATE_MEMBERSHIP', 'PARTITION_INVALID', 'INDEPENDENT_CORE_DRIFT'}
        code = exc.code if isinstance(exc, support.CensusFailure) else str(exc) if str(exc) in allowed else 'UNEXPECTED_FAILURE'
        state = getattr(exc, 'sqlstate', '')
        if not isinstance(state, str) or not re.fullmatch('[A-Z0-9]{5}', state):
            state = 'UNAVAILABLE'
        print('COHORT_DRIFT_FAILURE_CODE=' + code, flush=True)
        print('COHORT_DRIFT_FAILURE_STAGE=' + STAGE, flush=True)
        print('COHORT_DRIFT_SQLSTATE=' + state, flush=True)
        raise SystemExit(1) from None
    finally:
        if inner is not None:
            inner.close()


if __name__ == '__main__':
    main()
