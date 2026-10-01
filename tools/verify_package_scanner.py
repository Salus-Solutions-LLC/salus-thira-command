"""Fail-closed scanner proof for the exact package-upload release image.

Run inside the candidate image before enabling package uploads. This checks
both a clean sample and the harmless EICAR test file against the configured
scanner. It does not establish signature currency, capacity, or live storage
integration; those require separate release evidence.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import security_controls  # noqa: E402


_EICAR_HEX = (
    '58354f2150254041505b345c505a58353428505e2937434329377d24'
    '45494341522d5354414e444152442d414e544956495255532d544553'
    '542d46494c452124482b482a'
)


def current_daily_signatures(database_dir=None, now_utc=None):
    """Fail closed unless sigtool verifies a recent official daily database."""
    directory = Path(database_dir or os.getenv('SALUS_CLAMAV_DATABASE_DIR', '/var/lib/clamav'))
    database = next((directory / name for name in ('daily.cld', 'daily.cvd')
                     if (directory / name).is_file()), None)
    sigtool = shutil.which('sigtool')
    if database is None or not sigtool:
        return False
    try:
        result = subprocess.run([sigtool, '--info', str(database)], capture_output=True,
                                text=True, timeout=10)
        if result.returncode != 0 or 'Verification OK.' not in result.stdout:
            return False
        match = re.search(r'^Build time:\s*(.+)$', result.stdout, re.MULTILINE)
        if not match:
            return False
        built = datetime.strptime(match.group(1).strip(), '%d %b %Y %H:%M %z')
        age = (now_utc or datetime.now(timezone.utc)) - built.astimezone(timezone.utc)
        return -timedelta(hours=1) <= age <= timedelta(hours=72)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def scanner_proof():
    configuration = security_controls.scanner_configuration()
    result = {
        'mode': configuration.get('mode'),
        'configured': bool(configuration.get('configured')),
        'signatures_current': False,
        'clean_detected': False,
        'test_threat_detected': False,
        'passed': False,
    }
    if result['mode'] != 'clamav' or not result['configured']:
        return result
    result['signatures_current'] = current_daily_signatures()
    if not result['signatures_current']:
        return result

    clean = security_controls.scan_bytes(b'Salus package scanner clean test.\n', 'salus-clean.txt')
    result['clean_detected'] = clean.get('ok') is True and clean.get('status') == 'Clean'
    if not result['clean_detected']:
        return result

    test_file = bytes.fromhex(_EICAR_HEX)
    assert len(test_file) == 68
    threat = security_controls.scan_bytes(test_file, 'salus-eicar-test.com')
    result['test_threat_detected'] = threat.get('ok') is False and threat.get('status') == 'Infected'
    result['passed'] = result['clean_detected'] and result['test_threat_detected']
    return result


def main():
    result = scanner_proof()
    print(json.dumps(result, sort_keys=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
