FROM debian:bookworm-slim AS whisper-assets
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /opt/whisper/bin /opt/whisper/lib /opt/whisper/models /tmp/whisper && \
    curl --fail --location --retry 3 --output /tmp/whisper.tar.gz https://github.com/ggml-org/whisper.cpp/releases/download/b4938/whisper-bin-ubuntu-x64.tar.gz && \
    echo "f4cfc1f969a13805908fb72043ce7cc896eb42e0b8afbe841dc8e7298923b061  /tmp/whisper.tar.gz" | sha256sum --check --strict && \
    tar --extract --gzip --file /tmp/whisper.tar.gz --directory /tmp/whisper && \
    find /tmp/whisper -type f -name whisper-cli -exec install -m 0555 '{}' /opt/whisper/bin/whisper-cli \; && \
    test -x /opt/whisper/bin/whisper-cli && \
    find /tmp/whisper -name '*.so*' -exec cp -L '{}' /opt/whisper/bin/ \; && \
    curl --fail --location --retry 3 --output /opt/whisper/models/ggml-tiny.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/5359861c739e955e79d9a303bcbc70fb988958b1/ggml-tiny.en.bin && \
    echo "921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f  /opt/whisper/models/ggml-tiny.en.bin" | sha256sum --check --strict && \
    BINARY_SHA="$(sha256sum /opt/whisper/bin/whisper-cli | cut -d ' ' -f 1)" && \
    printf '{"release":"b4938","archive_sha256":"f4cfc1f969a13805908fb72043ce7cc896eb42e0b8afbe841dc8e7298923b061","binary_sha256":"%s","model":"tiny.en","model_sha256":"921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f"}\n' "$BINARY_SHA" > /opt/whisper/manifest.json && \
    chmod -R a-w /opt/whisper

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV LD_LIBRARY_PATH=/opt/whisper/bin
WORKDIR /app
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg=7:5.1.9-0+deb12u1 tesseract-ocr=5.3.0-2 tesseract-ocr-eng=1:4.1.0-2 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 salus
COPY --from=whisper-assets /opt/whisper /opt/whisper
COPY . .
RUN python tools/reconstruct_v343_source.py && python tools/verify_v343_source.py
RUN python tools/reconstruct_salops_preparedness.py
RUN python tools/reconstruct_personnel_assessment.py
RUN python tools/reconstruct_salintel_relationships.py
RUN python tools/reconstruct_salintel_research.py
RUN python tools/reconstruct_salintel_handoffs.py
RUN python tools/reconstruct_facility_assessment.py
RUN python tools/reconstruct_salintel_monitoring.py
RUN python tools/reconstruct_salcapa_assurance.py
RUN python tools/reconstruct_salcapa_contextual_guidance.py
RUN python tools/reconstruct_salcapa_human_first_communications.py
RUN python tools/reconstruct_salops_plan_assembly.py
RUN python tools/reconstruct_salcapa_commercial.py
RUN python tools/reconstruct_salcapa_contextual_intake.py
RUN python tools/reconstruct_salcapa_material_processing.py
RUN python tools/reconstruct_salcapa_office_processing.py
RUN python tools/reconstruct_salcapa_pdf_processing.py
RUN python tools/reconstruct_salcapa_image_ocr_processing.py
RUN python tools/reconstruct_salcapa_audio_video_processing.py
RUN python tools/reconstruct_salcapa_visual_geospatial.py
RUN python tools/reconstruct_salcapa_visual_object_processing.py
RUN python tools/reconstruct_salcapa_handwriting_ocr_processing.py
RUN python tools/reconstruct_salcapa_demo_fixtures.py
RUN python -m py_compile salcapa_runtime.py salcapa_demo_fixtures.py salcapa_commercial.py salcapa_contextual_intake.py salcapa_material_processing.py salcapa_office_processing.py salcapa_pdf_processing.py salcapa_image_ocr_processing.py salcapa_audio_video_processing.py salcapa_visual_object_processing.py salcapa_handwriting_ocr_processing.py tools/salcapa_pdf_worker.py tools/salcapa_image_ocr_worker.py tools/salcapa_audio_video_worker.py tools/salcapa_visual_object_worker.py tools/salcapa_handwriting_ocr_worker.py salops_preparedness.py salops_plan_assembly.py personnel_assessment.py facility_assessment.py salintel_relationships.py salintel_research.py salintel_handoffs.py salintel_monitoring.py salcapa_assurance.py tools/ci_salcapa_demo_fixtures_smoke.py tools/ci_salcapa_commercial_smoke.py tools/ci_salcapa_contextual_intake_smoke.py tools/ci_salcapa_material_processing_smoke.py tools/ci_salcapa_office_processing_smoke.py tools/ci_salcapa_pdf_processing_smoke.py tools/ci_salcapa_image_ocr_processing_smoke.py tools/ci_salcapa_audio_video_processing_smoke.py tools/ci_salcapa_visual_object_processing_smoke.py tools/ci_salcapa_handwriting_ocr_processing_smoke.py tools/ci_salops_preparedness_smoke.py tools/ci_salops_plan_assembly_smoke.py tools/ci_salops_plan_assembly_ui_smoke.py tools/ci_personnel_assessment_smoke.py tools/ci_facility_assessment_smoke.py tools/ci_facility_assessment_ui_smoke.py tools/ci_salintel_relationships_smoke.py tools/ci_salintel_research_smoke.py tools/ci_salintel_handoffs_smoke.py tools/ci_salintel_monitoring_smoke.py tools/ci_salcapa_assurance_smoke.py tools/ci_salcapa_assurance_ui_smoke.py tools/ci_salcapa_contextual_guidance_smoke.py tools/ci_salcapa_human_first_communications_smoke.py
RUN mkdir -p /app/attachments /app/backups /app/data && chown -R salus:salus /app
USER salus
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"
CMD ["uvicorn","salcapa_runtime:app","--host","0.0.0.0","--port","8000","--proxy-headers"]
