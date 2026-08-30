#!/bin/sh
set -e
cd "$(dirname "$0")"
if [ ! -f app.py ] || [ ! -f static/app.js ]; then
  echo "Reconstructing verified v1.1 source from GitHub archive parts..."
  python tools/reconstruct_v11_source.py
fi
python tools/verify_v11_source.py
exec python -m uvicorn app:app --host 127.0.0.1 --port 8000
