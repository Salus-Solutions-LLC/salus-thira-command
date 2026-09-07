@echo off
cd /d %~dp0
echo Reconstructing verified SalCAPA v3.43 base source...
python tools\reconstruct_v343_source.py || goto :error
python tools\verify_v343_source.py || goto :error
python tools\reconstruct_salops_preparedness.py || goto :error
python tools\reconstruct_personnel_assessment.py || goto :error
python tools\reconstruct_salintel_relationships.py || goto :error
python tools\reconstruct_salintel_research.py || goto :error
python -m py_compile salcapa_runtime.py salops_preparedness.py personnel_assessment.py salintel_relationships.py salintel_research.py || goto :error
python -m uvicorn salcapa_runtime:app --host 127.0.0.1 --port 8000
goto :eof
:error
echo SalCAPA source or preparedness runtime verification failed.
pause
exit /b 1

