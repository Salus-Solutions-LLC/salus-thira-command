"""Fail-closed exact-original fallback after a destination changes source bytes."""

import hashlib
from types import SimpleNamespace
from urllib.parse import unquote, urlparse

import httpx
import pytest

from salcapa_knowledge_promotion import GraphKnowledgeWriter, KnowledgePromotionError


def _writer(content: bytes, *, fallback_content: bytes, primary_content: bytes = b"destination changed these bytes"):
    requests = []
    primary_id = "01PRIMARYITEM12345678"
    fallback_id = "01FALLBACKITEM1234567"

    def handler(request):
        requests.append(request)
        path = unquote(str(request.url))
        if request.method == "PUT" and path.endswith(":/content"):
            item_id = fallback_id if ".original.bin:/content" in path else primary_id
            return httpx.Response(
                201,
                json={"id": item_id, "webUrl": "https://salus.sharepoint.com/sites/knowledge/item"},
            )
        if request.method == "GET" and path.endswith(f"/items/{primary_id}/content"):
            return httpx.Response(200, content=primary_content)
        if request.method == "GET" and path.endswith(f"/items/{fallback_id}/content"):
            return httpx.Response(200, content=fallback_content)
        raise AssertionError(f"Unexpected request: {request.method}")

    writer = GraphKnowledgeWriter.__new__(GraphKnowledgeWriter)
    writer.client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    writer.destination = SimpleNamespace(drive_id="b!TESTDRIVE0123456789")
    writer._headers = lambda: {"Authorization": "Bearer test"}
    writer._resolve_folder = lambda folder: "01TESTFOLDERITEM1234567890"
    sha = hashlib.sha256(content).hexdigest()
    return writer, requests, sha


def test_non_office_mismatch_uses_bounded_exact_original():
    content = b"the exact governed source"
    writer, requests, sha = _writer(content, fallback_content=content)
    result = writer.put_verified("05 Research and Reference", "z" * 235 + ".zip", content, sha)
    assert result["item_id"] == "01FALLBACKITEM1234567"
    puts = [unquote(str(request.url)) for request in requests if request.method == "PUT"]
    assert len(puts) == 2
    original_name = unquote(urlparse(puts[1]).path).split(":/", 1)[1].rsplit(":/content", 1)[0]
    assert original_name.endswith(f".{sha}.original.bin")
    assert len(original_name) <= 240


def test_changed_exact_original_remains_unverified():
    content = b"the exact governed source"
    writer, requests, sha = _writer(content, fallback_content=b"also changed")
    with pytest.raises(KnowledgePromotionError, match="destination verification failed"):
        writer.put_verified("05 Research and Reference", "example.zip", content, sha)
    assert len([request for request in requests if request.method == "PUT"]) == 2


def test_primary_exact_bytes_need_no_fallback():
    content = b"the exact governed source"
    writer, requests, sha = _writer(content, fallback_content=content, primary_content=content)
    result = writer.put_verified("05 Research and Reference", "example.pdf", content, sha)
    assert result["item_id"] == "01PRIMARYITEM12345678"
    assert len([request for request in requests if request.method == "PUT"]) == 1
