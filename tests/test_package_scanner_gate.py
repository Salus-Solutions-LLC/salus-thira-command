"""Production readiness must not pass when upload scanning is unavailable."""

import os
import subprocess
import sys
import textwrap


def test_production_readiness_rejects_missing_scanner(tmp_path):
    env = os.environ.copy()
    env.update({
        'SALUS_DB_PATH': str(tmp_path / 'candidate.db'),
        'SALUS_LOCAL_STORAGE_DIR': str(tmp_path / 'attachments'),
        'SALUS_BACKUP_DIR': str(tmp_path / 'backups'),
        'SALUS_SEED_DEMO': '0',
        'SALUS_AUTH_MODE': 'prototype',
        'PYTHONPATH': os.pathsep.join(filter(None, (os.getcwd(), env.get('PYTHONPATH', '')))),
    })
    program = textwrap.dedent('''
        import app
        import security_controls

        app.ENVIRONMENT = 'production'
        app.AV_REQUIRED = True
        app.PACKAGE_COMMERCIAL_WORKFLOW_ENABLED = True
        security_controls.AV_MODE = 'clamav'
        security_controls.CLAMSCAN_PATH = '/missing/salus-clamscan'
        app.scanner_configuration = security_controls.scanner_configuration
        result = app.production_readiness()
        assert result['package_scanner'] == {'mode': 'clamav', 'configured': False}
        assert result['ready'] is False
        assert any('scanner executable is required' in issue for issue in result['issues'])

        security_controls.AV_MODE = 'off'
        result = app.production_readiness()
        assert result['package_scanner'] == {'mode': 'off', 'configured': False}
        assert result['ready'] is False

        app.PACKAGE_COMMERCIAL_WORKFLOW_ENABLED = False
        result = app.production_readiness()
        assert not any('scanner executable is required' in issue for issue in result['issues'])
    ''')
    child = tmp_path / 'scanner_gate.py'
    child.write_text(program, encoding='utf-8')
    result = subprocess.run([sys.executable, str(child)], env=env, text=True,
                            capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
