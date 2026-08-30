#!/usr/bin/env python3
"""Verify readiness checks do not disclose exception or infrastructure detail."""
import os

import managed_database
import rate_limit
import secret_provider


MARKER = 'sensitive-marker-must-not-escape'


sqlite_status = managed_database.sqlite_runtime_status(f'/missing/{MARKER}/database.sqlite')
assert not sqlite_status['healthy'] and MARKER not in str(sqlite_status)

original_dsn = managed_database._postgres_dsn
original_connect = managed_database._postgres_connect
managed_database._postgres_dsn = lambda: 'configured'
def fail_postgres(*args, **kwargs):
    raise RuntimeError(MARKER)
managed_database._postgres_connect = fail_postgres
try:
    postgres_status = managed_database.postgres_runtime_status()
    assert not postgres_status['healthy'] and MARKER not in str(postgres_status)
finally:
    managed_database._postgres_dsn = original_dsn
    managed_database._postgres_connect = original_connect

limiter = rate_limit.RateLimiter()
limiter.enabled = True
limiter.backend = 'redis'
class BrokenRedis:
    def ping(self):
        raise RuntimeError(MARKER)
limiter._redis = BrokenRedis()
redis_status = limiter.health()
assert not redis_status['healthy'] and MARKER not in str(redis_status)

original_provider = secret_provider._PROVIDER
class BrokenProvider:
    def health(self):
        raise RuntimeError(MARKER)
secret_provider._PROVIDER = BrokenProvider()
try:
    secret_status = secret_provider.readiness()
    assert not secret_status['configured'] and MARKER not in str(secret_status)
finally:
    secret_provider._PROVIDER = original_provider

print('READINESS_SECURITY_PASS')
