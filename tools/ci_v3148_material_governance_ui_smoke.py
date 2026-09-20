from pathlib import Path


def main() -> None:
    ui = Path('static/salcapa-material-review.js').read_text(encoding='utf-8')
    index = Path('salintel_material_index.py').read_text(encoding='utf-8')
    runtime = Path('salcapa_runtime.py').read_text(encoding='utf-8')
    for marker in (
        '/api/salintel/research/material-derivatives/${Number(id)}/index-status',
        '/api/salintel/research/material-derivatives/${Number(id)}/index',
        '/api/salthira/material-index/${Number(indexId)}/route-evidence',
        'Index for SalINTEL research',
        'Route to active SalTHIRA assessment',
        'does not establish source truth',
        'No finding, risk conclusion',
    ):
        assert marker in ui, marker
    assert 'def material_index_status(' in index
    assert 'require_sensitivity(request, row["sensitivity"])' in index
    assert 'SALCAPA_RELEASE_VERSION = "3.148"' in runtime
    print('V3148_MATERIAL_GOVERNANCE_UI_PASS')


if __name__ == '__main__':
    main()
