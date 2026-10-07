"""Synthetic no-write checks for the unactivated response-shape candidate."""

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / "tools" / "knowledge_destination_response_shape_probe.py"
spec = importlib.util.spec_from_file_location("response_shape_probe", path)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Response:
    def __init__(self, status, payload=None, raw=b"", headers=None):
        self.status_code = status
        self.payload = payload or {}
        self.raw = raw
        self.headers = headers or {}

    def json(self):
        return self.payload

    def iter_raw(self, chunk_size):
        for offset in range(0, len(self.raw), chunk_size):
            yield self.raw[offset:offset + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Client:
    def __init__(self, source: bytes, metadata_size: int, raw: bytes, encoding: str):
        self.source = source
        self.metadata_size = metadata_size
        self.raw = raw
        self.encoding = encoding
        self.methods = []

    def get(self, url, **kwargs):
        self.methods.append("get")
        assert url.endswith(":")
        return Response(200, payload={"id": "primary123", "size": self.metadata_size})

    def stream(self, method, url, **kwargs):
        self.methods.append("stream")
        assert method == "GET"
        if url.endswith("/content"):
            return Response(302, headers={"Location": "https://tenant.sharepoint.com/file"})
        assert url == "https://tenant.sharepoint.com/file"
        return Response(200, raw=self.raw, headers={
            "Content-Length": str(len(self.raw)),
            "Content-Encoding": self.encoding,
        })


def run():
    source = b"governed synthetic bytes"
    digest = hashlib.sha256(source).hexdigest()
    for metadata_size, raw, encoding, expected_metadata, expected_raw, matches in (
        (len(source), source, "gzip", "equal", "equal", True),
        (len(source) - 1, source[:-1], "", "below", "below", False),
        (len(source) + 1, source + b"x", "identity", "above", "above", False),
    ):
        client = Client(source, metadata_size, raw, encoding)
        writer = SimpleNamespace(
            client=client,
            destination=SimpleNamespace(drive_id="drive12345"),
            _resolve_folder=lambda _: "folder12345",
            _headers=lambda: {"Authorization": "synthetic-only"},
        )
        result = probe.inspect(writer, "05 Research and Reference", "sample.pdf", digest, len(source))
        assert result["candidate_count"] == 1
        assert len(result["observations"]) == 1
        item = result["observations"][0]
        assert item["metadata_size_relation"] == expected_metadata
        assert item["raw_size_relation"] == expected_raw
        assert item["raw_hash_match"] is matches
        assert item["content_encoding"] == ("compressed" if encoding == "gzip" else encoding or "absent")
        assert item["content_range_present"] is False
        assert set(client.methods) == {"get", "stream"}
        assert "Authorization" not in str(result)
        assert "sample" not in str(result)
        assert "drive12345" not in str(result)
    print("RESPONSE_SHAPE_CANDIDATE_PASS")


if __name__ == "__main__":
    run()

