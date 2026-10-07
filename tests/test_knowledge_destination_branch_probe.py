"""Offline checks for the proposed read-only destination verification probe."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace


path = Path(__file__).resolve().parents[1] / "tools" / "knowledge_destination_branch_probe.py"
if not path.exists():
    path = Path(__file__).with_name("knowledge_destination_branch_probe_candidate.py")
spec = importlib.util.spec_from_file_location("branch_probe", path)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Response:
    def __init__(self, status, *, payload=None, content=b"", headers=None):
        self.status_code = status
        self.payload = payload or {}
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self.payload

    def iter_bytes(self, chunk_size):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset:offset + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Client:
    def __init__(self, original: bytes, mode: str):
        self.original = original
        self.mode = mode
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url))
        if url.endswith(".original.bin:"):
            return Response(200, payload={"id": "fallback123"})
        if url.endswith(":"):
            return Response(200, payload={"id": "primary123"})
        raise AssertionError(url)

    def stream(self, method, url, **kwargs):
        assert method == "GET"
        self.calls.append(("stream", url))
        if url.endswith("/items/primary123/content"):
            if self.mode == "rejected":
                return Response(503)
            if self.mode == "redirect":
                return Response(302, headers={"Location": "https://tenant.sharepoint.com/file"})
            return Response(200, content=self.original + b"modified")
        if url.endswith("/items/fallback123/content"):
            return Response(200, content=self.original)
        if url == "https://tenant.sharepoint.com/file":
            return Response(200, content=self.original)
        raise AssertionError(url)


def run():
    original = b"synthetic bytes"
    sha256 = hashlib.sha256(original).hexdigest()
    assert probe.names_for_hash("sample.docx", sha256)[0][1].endswith(".docx")
    assert probe.names_for_hash("sample.docx", sha256)[1][1].endswith(".original.bin")
    assert len(probe.names_for_hash("sample.pdf", sha256)) == 1
    assert probe.trusted_redirect("https://tenant.sharepoint.com/file")
    assert not probe.trusted_redirect("https://tenant.sharepoint.com.evil.test/file")
    assert not probe.trusted_redirect("http://tenant.sharepoint.com/file")

    for mode, expected_primary, expected_count in (
        ("rejected", 503, 2),
        ("mismatch", 200, 2),
        ("redirect", 302, 1),
    ):
        client = Client(original, mode)
        writer = SimpleNamespace(
            client=client,
            destination=SimpleNamespace(drive_id="drive12345"),
            _resolve_folder=lambda _: "folder12345",
            _headers=lambda: {"Authorization": "test-only"},
        )
        result = probe.inspect(writer, "05 Research and Reference", "sample.docx", sha256, len(original))
        assert result["candidate_count"] == 1
        assert len(result["observations"]) == expected_count
        assert result["observations"][0]["first_status"] == expected_primary
        assert result["observations"][-1]["hash_match"] is True
        assert all("Authorization" not in str(row) for row in result["observations"])
        assert all("sample" not in str(row) for row in result["observations"])
        assert all("drive12345" not in str(row) for row in result["observations"])
        assert all(method in {"get", "stream"} for method, _ in client.calls)
    print("DESTINATION_BRANCH_PROBE_CANDIDATE_PASS")


if __name__ == "__main__":
    run()
