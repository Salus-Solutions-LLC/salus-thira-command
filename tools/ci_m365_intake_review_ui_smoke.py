from pathlib import Path


def main() -> None:
    js = Path('static/salcapa-intake-review.js').read_text(encoding='utf-8')
    css = Path('static/salcapa-intake-review.css').read_text(encoding='utf-8')
    runtime = Path('salcapa_runtime.py').read_text(encoding='utf-8')
    required_js = (
        "currentRole === 'System Administrator'",
        '/api/integrations/m365/intake/reconcile-source-versions',
        '/api/integrations/m365/intake/review-queue/batch-decision',
        '/api/integrations/m365/intake/review-queue/execute-approved',
        'const REVIEW_LIMIT = 50',
        'const EXECUTE_LIMIT = 25',
        'Nothing is captured, reprocessed, indexed, or routed',
        'Missing sources fail closed',
    )
    for marker in required_js:
        assert marker in js, marker
    assert '/static/salcapa-intake-review.css' in runtime
    assert '/static/salcapa-intake-review.js' in runtime
    assert 'max-height' not in css or 'overflow' in css
    assert '/static/salcapa-intake-review.js' in runtime
    print('M365_INTAKE_REVIEW_UI_PASS')


if __name__ == '__main__':
    main()
