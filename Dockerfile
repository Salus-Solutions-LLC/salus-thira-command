FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 salus
COPY . .
RUN python tools/reconstruct_v13_source.py && python tools/verify_v13_source.py
RUN mkdir -p /app/attachments /app/backups /app/data && chown -R salus:salus /app
USER salus
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000","--proxy-headers"]
