FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 salus
COPY . .
RUN python tools/reconstruct_v343_source.py && python tools/verify_v343_source.py
RUN python tools/reconstruct_salops_preparedness.py
RUN python tools/reconstruct_personnel_assessment.py
RUN python tools/reconstruct_salintel_relationships.py
RUN python -m py_compile salcapa_runtime.py salops_preparedness.py personnel_assessment.py salintel_relationships.py tools/ci_salops_preparedness_smoke.py tools/ci_personnel_assessment_smoke.py tools/ci_salintel_relationships_smoke.py
RUN mkdir -p /app/attachments /app/backups /app/data && chown -R salus:salus /app
USER salus
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"
CMD ["uvicorn","salcapa_runtime:app","--host","0.0.0.0","--port","8000","--proxy-headers"]

