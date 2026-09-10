#!/usr/bin/env python3
"""Governance smoke checks for bounded local audio and video transcription."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.chdir(ROOT)
os.environ.update({
    "SALUS_AUTH_MODE": "prototype", "SALUS_SEED_DEMO": "1",
    "SALUS_DB_BACKEND": os.environ.get("SALUS_DB_BACKEND", "sqlite"),
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "media.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
import salcapa_audio_video_processing as media_processing  # noqa: E402
from salcapa_audio_video_processing import register_salcapa_audio_video_processing  # noqa: E402

register_salcapa_audio_video_processing(core.app, core.__dict__)


def command(arguments: list[str]) -> None:
    subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def component_diagnostic(wav_data: bytes) -> str:
    """Return bounded technical detail for this fictional CI fixture only."""
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "diagnostic.wav"
        prefix = Path(directory) / "diagnostic"
        source.write_bytes(wav_data)
        result = subprocess.run(
            [
                "/opt/whisper/bin/whisper-cli", "-m", "/opt/whisper/models/ggml-tiny.en.bin",
                "-f", str(source), "-l", "en", "-t", "1", "-bs", "1", "-bo", "1",
                "-np", "-nt", "-osrt", "-of", str(prefix), "--no-gpu",
            ],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=120, check=False,
        )
        detail = (result.stderr + result.stdout).decode("utf-8", errors="replace")[-2000:]
        return f"exit={result.returncode}; output={detail}"


def fixtures(directory: Path) -> dict[str, bytes]:
    wav = directory / "briefing.wav"
    mp3 = directory / "briefing.mp3"
    mp4 = directory / "briefing.mp4"
    phrase = "Assembly point alpha seven. This is a fictional demonstration recording."
    command(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"flite=text='{phrase}'", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)])
    command(["ffmpeg", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "64k", str(mp3)])
    command(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=1", "-i", str(wav), "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", str(mp4)])
    return {"wav": wav.read_bytes(), "mp3": mp3.read_bytes(), "mp4": mp4.read_bytes()}


def upload(client: TestClient, name: str, content_type: str, data: bytes):
    material_kind = "Video" if name.lower().endswith(".mp4") else "Audio"
    response = client.post(
        "/api/materials/upload", headers=HEADERS,
        files={"file": (name, data, content_type)},
        data={"title": f"Fictional {name}", "material_kind": material_kind, "source_origin": "Authorized fictional demonstration", "sensitivity": "Restricted"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def process(client: TestClient, source: dict):
    return client.post(
        f"/api/materials/{source['id']}/safe-text-processing", headers=HEADERS,
        json={"reason": "Prepare a bounded spoken-word review aid for independent human review."},
    )


def expect_failure(client: TestClient, name: str, content_type: str, data: bytes, code: str) -> None:
    source = upload(client, name, content_type, data)
    response = process(client, source)
    assert response.status_code == 422, response.text
    conn = core.db()
    job = conn.execute("SELECT * FROM material_processing_jobs WHERE source_material_id=? ORDER BY id DESC LIMIT 1", (source["id"],)).fetchone()
    conn.close()
    assert job["status"] == "Failed" and job["failure_code"] == code, dict(job)


conn = core.db()
if not conn.execute("SELECT id FROM tenants WHERE id=5").fetchone():
    conn.execute("INSERT INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?)", (5, "Media Test Tenant", "media-test", "Active", core.now()))
conn.commit()
conn.close()
HEADERS = {"X-Salus-User": "Information Review Lead", "X-Salus-Tenant": "5", "X-Salus-Role": "Assessment Director"}

with tempfile.TemporaryDirectory() as fixture_dir, TestClient(core.app) as client:
    material = fixtures(Path(fixture_dir))
    for extension, content_type in (("wav", "audio/wav"), ("mp3", "audio/mpeg"), ("mp4", "video/mp4")):
        original = material[extension]
        response = process(client, upload(client, f"briefing.{extension}", content_type, original))
        if response.status_code != 200:
            raise AssertionError(f"{response.text}; {component_diagnostic(material['wav'])}")
        record = response.json()["derivative"]
        assert record["review_status"] == "Awaiting Human Review"
        assert record["confidence_status"] == "Derived — Unverified"
        assert "ASSEMBLY" in record["content_preview"].upper()
        assert "normalized-sha256=" in record["extraction_method"]
        assert "model-sha256=" in record["extraction_method"]
        assert "no video-frame analysis" in record["extraction_method"]
        assert record["processor"] == "SalCAPA Isolated Audio and Video Transcript Preparer"
        conn = core.db()
        source = conn.execute("SELECT * FROM materials WHERE id=?", (record["source_material_id"],)).fetchone()
        conn.close()
        assert core.storage.get_bytes(source["stored_name"]) == original

    expect_failure(client, "wrong.mp3", "video/mp4", material["mp3"], "MEDIA_FORMAT_MISMATCH")
    expect_failure(client, "false.wav", "audio/wav", b"not a recording", "MEDIA_HEADER_INVALID")

    original_limit = media_processing.MAX_SOURCE_BYTES
    media_processing.MAX_SOURCE_BYTES = 8
    try:
        expect_failure(client, "large.wav", "audio/wav", material["wav"], "MEDIA_RESOURCE_LIMIT")
    finally:
        media_processing.MAX_SOURCE_BYTES = original_limit

print("SALCAPA_AUDIO_VIDEO_PROCESSING_SMOKE_PASS")
