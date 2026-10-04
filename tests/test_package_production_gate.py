"""Production package access remains closed until every release control is present."""

import os
import subprocess
import sys
import textwrap


def test_production_package_gate_requires_all_controls(tmp_path):
    env = os.environ.copy()
    env.update({
        'SALUS_DB_PATH': str(tmp_path / 'gate.db'),
        'SALUS_LOCAL_STORAGE_DIR': str(tmp_path / 'attachments'),
        'SALUS_BACKUP_DIR': str(tmp_path / 'backups'),
        'SALUS_SEED_DEMO': '0',
        'SALUS_ENV': 'production',
        'SALUS_AUTH_MODE': 'oidc',
        'SALUS_COOKIE_SECURE': '1',
        'SALUS_PACKAGE_COMMERCIAL_WORKFLOW_ENABLED': '0',
        'SALUS_PACKAGE_SCAN_MODE': 'off',
        'SALUS_PACKAGE_SCANNER_ACCEPTED': '0',
        'PYTHONPATH': os.pathsep.join(filter(None, (os.getcwd(), env.get('PYTHONPATH', '')))),
    })
    program = textwrap.dedent("""
        import os
        import app

        assert not app.package_workflow_ready()
        app.PACKAGE_COMMERCIAL_WORKFLOW_ENABLED = True
        assert not app.package_workflow_ready()
        app.PACKAGE_SCAN_MODE = 'defender'
        assert not app.package_workflow_ready()
        app.PACKAGE_SCANNER_ACCEPTED = True
        assert not app.package_workflow_ready()
        os.environ['SALUS_SCAN_QUARANTINE_URL'] = 'https://salusquarantine.blob.core.windows.net'
        assert app.package_workflow_ready()
        app.COOKIE_SECURE = False
        assert not app.package_workflow_ready()
        app.COOKIE_SECURE = True
        app.AUTH_MODE = 'prototype'
        assert not app.package_workflow_ready()
        app.AUTH_MODE = 'oidc'
        os.environ['SALUS_SCAN_QUARANTINE_URL'] = 'http://salusquarantine.blob.core.windows.net'
        assert not app.package_workflow_ready()
    """)
    result = subprocess.run(
        [sys.executable, '-c', program],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
