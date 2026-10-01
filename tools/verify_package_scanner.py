"""Fail-closed scanner proof for the exact package-upload release image.

Run inside the candidate image before enabling package uploads. This checks
recent verified signatures, a clean sample and the harmless EICAR test file.
It does not establish capacity or live storage integration.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import security_controls  # noqa: E402


_EICAR_HEX = (
    '58354f2150254041505b345c505a58353428505e2937434329377d24'
    '45494341522d5354414e444152442d414e544956495255532d544553'
    '542d46494c452124482b482a'
)


current_daily_signatures = security_controls.current_daily_signatures


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
