@echo off
cd /d %~dp0
if not exist app.py (
  echo Reconstructing verified SalCAPA source from GitHub archive parts...
  python tools\reconstruct_v27_source.py || goto :error
)
if not exist static\app.js (
  echo Reconstructing verified SalCAPA source from GitHub archive parts...
  python tools\reconstruct_v27_source.py || goto :error
)
python tools\verify_v27_source.py || goto :error
python -m uvicorn app:app --host 127.0.0.1 --port 8000
goto :eof
:error
echo SalCAPA source verification failed.
pause
exit /b 1
