"""The candidate image must distinguish clean files from the EICAR test file."""

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
    monkeypatch.setattr(proof.security_controls, 'scan_bytes',
                        lambda *_args: {'ok': True, 'status': 'Clean'})
    result = proof.scanner_proof()
    assert result['clean_detected'] is True
    assert result['test_threat_detected'] is False
    assert result['passed'] is False


def test_scanner_proof_rejects_clean_scan_error(monkeypatch):
    monkeypatch.setattr(proof.security_controls, 'scanner_configuration',
                        lambda: {'mode': 'clamav', 'configured': True})
    monkeypatch.setattr(proof.security_controls, 'scan_bytes',
                        lambda *_args: {'ok': False, 'status': 'Scan Error'})
    result = proof.scanner_proof()
    assert result['passed'] is False
    assert result['clean_detected'] is False
