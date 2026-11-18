"""Read-only exact-file check of SALUS-DOC-HEADING-SPACING-001."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from docx import Document
from salus_document_styles import heading_spacing_findings

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docx', type=Path, nargs='+')
    args = parser.parse_args()
    rows = []
    for path in args.docx:
        try:
            rows.append({'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'findings': heading_spacing_findings(Document(path))})
        except Exception as exc:
            rows.append({'file': str(path), 'error': type(exc).__name__})
    print(json.dumps({'scope': 'Heading spacing only; full rendering and Charter assurance remain separate',
                      'files': rows}, indent=2))
    return int(any(r.get('findings') or r.get('error') for r in rows))

if __name__ == '__main__':
    sys.exit(main())
