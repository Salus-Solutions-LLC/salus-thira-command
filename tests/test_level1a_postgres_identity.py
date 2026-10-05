"""PostgreSQL must return real IDs for the paid intake and receipt chain."""

from database import PostgresConnection


class _Cursor:
    description = None
    rowcount = 1

    def __init__(self):
        self.statement = ''
        self.parameters = ()

    def execute(self, statement, parameters):
        self.statement = statement
        self.parameters = parameters

    def fetchone(self):
        return (427,)


class _Raw:
    def __init__(self):
        self.current = None

    def cursor(self):
        self.current = _Cursor()
        return self.current


def test_level1a_postgres_inserts_return_new_record_identity():
    connection = object.__new__(PostgresConnection)
    connection.raw = _Raw()
    connection._lastrowid = None
    for table in ('level1a_checkout_sessions','level1a_payment_events',
                  'level1a_intake_items','level1a_intake_uploads',
                  'level1a_pending_scans'):
        result = connection.execute(f'INSERT INTO {table}(tenant_id) VALUES(?)', (7,))
        assert result.lastrowid == 427
        assert connection.raw.current.statement.endswith('RETURNING id')
        assert connection.raw.current.parameters == (7,)
