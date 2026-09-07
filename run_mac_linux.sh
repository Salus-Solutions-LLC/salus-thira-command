#!/bin/sh
set -e
cd "$(dirname "$0")"
echo "Reconstructing verified SalCAPA v3.43 base source..."
python tools/reconstruct_v343_source.py
python tools/verify_v343_source.py
python tools/reconstruct_salops_preparedness.py
python tools/reconstruct_personnel_assessment.py
python tools/reconstruct_salintel_relationships.py
python -m py_compile salcapa_runtime.py salops_preparedness.py personnel_assessment.py salintel_relationships.py
exec python -m uvicorn salcapa_runtime:app --host 127.0.0.1 --port 8000

