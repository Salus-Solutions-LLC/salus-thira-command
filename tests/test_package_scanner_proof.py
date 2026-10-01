"""The candidate image must distinguish clean files from the EICAR test file."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from tools import verify_package_scanner as proof


def test_scanner_proof_requires_configured_clamav(monkeypatch):
    monkeypatch.setattr(proof.security_controls, 'scanner_configuration',
                        lambda: {'mode': 'off', 'configured': False})
    monkeypatch.setattr(proof.security_controls, 'scan_bytes',
                        lambda *_args: (_ for _ in ()).throw(AssertionError('scan must not run')))
    assert proof.scanner_proof()['passed'] is False


def test_scanner_proof_requires_both_results(monkeypatch):
    monkeypatch.setattr(proof.security_controls, 'scanner_configuration',
                        lambda: {'mode': 'clamav', 'configured': True})
    monkeypatch.setattr(proof, 'current_daily_signatures', lambda: True)
    seen = []

    def scan(data, filename):
        seen.append((data, filename))
        if len(seen) == 1:
            return {'ok': True, 'status': 'Clean'}
        return {'ok': False, 'status': 'Infected'}

    monkeypatch.setattr(proof.security_controls, 'scan_bytes', scan)
    result = proof.scanner_proof()
    assert result['passed'] is True
    assert seen[0][0] != seen[1][0]
    assert len(seen[1][0]) == 68


def test_scanner_proof_rejects_missing_detection(monkeypatch):
    monkeypatch.setattr(proof.security_controls, 'scanner_configuration',
                        lambda: {'mode': 'clamav', 'configured': True})
    monkeypatch.setattr(proof, 'current_daily_signatures', lambda: True)
    monkeypatch.setattr(proof.security_controls, 'scan_bytes',
                        lambda *_args: {'ok': True, 'status': 'Clean'})
    result = proof.scanner_proof()
    assert result['clean_detected'] is True
    assert result['test_threat_detected'] is False
    assert result['passed'] is False


def test_scanner_proof_rejects_clean_scan_error(monkeypatch):
    monkeypatch.setattr(proof.security_controls, 'scanner_configuration',
                        lambda: {'mode': 'clamav', 'configured': True})
    monkeypatch.setattr(proof, 'current_daily_signatures', lambda: True)
    monkeypatch.setattr(proof.security_controls, 'scan_bytes',
                        lambda *_args: {'ok': False, 'status': 'Scan Error'})
    result = proof.scanner_proof()
    assert result['passed'] is False
    assert result['clean_detected'] is False


def test_scanner_proof_rejects_stale_signatures_before_scanning(monkeypatch):
    monkeypatch.setattr(proof.security_controls, 'scanner_configuration',
                        lambda: {'mode': 'clamav', 'configured': True})
    monkeypatch.setattr(proof, 'current_daily_signatures', lambda: False)
    monkeypatch.setattr(proof.security_controls, 'scan_bytes',
                        lambda *_args: (_ for _ in ()).throw(AssertionError('stale signatures must not scan')))
    result = proof.scanner_proof()
    assert result['configured'] is True
    assert result['signatures_current'] is False
    assert result['passed'] is False


def test_daily_signature_currency_requires_verified_recent_database(tmp_path, monkeypatch):
    (tmp_path / 'daily.cvd').write_bytes(b'fictional test database')
    monkeypatch.setattr(proof.shutil, 'which', lambda *_args: '/fake/sigtool')
    current = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    def sigtool_result(build_time, verification='Verification OK.'):
        return SimpleNamespace(returncode=0,
                               stdout=f'Build time: {build_time:%d %b %Y %H:%M %z}\n{verification}\n')
    monkeypatch.setattr(proof.subprocess, 'run', lambda *_args, **_kwargs: sigtool_result(current - timedelta(hours=1)))
    assert proof.current_daily_signatures(tmp_path, current) is True
    monkeypatch.setattr(proof.subprocess, 'run', lambda *_args, **_kwargs: sigtool_result(current - timedelta(hours=73)))
    assert proof.current_daily_signatures(tmp_path, current) is False
    monkeypatch.setattr(proof.subprocess, 'run', lambda *_args, **_kwargs: sigtool_result(current, 'Verification failed.'))
    assert proof.current_daily_signatures(tmp_path, current) is False
