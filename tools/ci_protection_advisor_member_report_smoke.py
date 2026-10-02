"""Dependency-free contract check for the candidate exact-original PDF store."""

from __future__ import annotations

import hashlib
import importlib
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ReportError(RuntimeError):
    pass


class Response:
    def __init__(self, status_code: int, content: bytes = b"", payload: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self.content = content
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


class Config:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def from_environment(cls):
        return cls(managed_identity_client_id="managed-identity", drive_id="advisor-drive",
                   folder_item_id="review-folder", max_file_bytes=1024, retries=1)


class Client:
    items: dict[str, bytes] = {}

    def __init__(self, config):
        self.config = config
        self.client = self

    def _content_url(self, name):
        return "https://graph.microsoft.com/folder/" + name

    def _request(self, method, url, **kwargs):
        if method == "PUT":
            content = kwargs["content"]
            item_id = "ITEM-" + hashlib.sha256(content).hexdigest()[:16]
            self.items[item_id] = content
            return Response(201, payload={"id": item_id})
        item_id = url.rsplit("/", 2)[-2] if url.endswith("/content") else url.rsplit("/", 1)[-1]
        if method == "GET":
            return Response(200, content=self.items[item_id])
        if method == "DELETE":
            self.items.pop(item_id, None)
            return Response(204)
        raise AssertionError(method)

    def get(self, location, **kwargs):
        raise AssertionError("No redirect expected in this fixture")


storage = types.ModuleType("salcapa_m365_reports")
storage.GovernedM365ReportConfig = Config
storage.GovernedM365Reports = Client
storage.M365ReportError = ReportError
sys.modules[storage.__name__] = storage
advisor = types.ModuleType("salcapa_m365_advisor_reports")
advisor._trusted_pdf_conversion_url = lambda location: location.startswith("https://salussolutions.sharepoint.com/")
sys.modules[advisor.__name__] = advisor

module = importlib.import_module("protection_advisor_member_reports")
os.environ["SALUS_M365_ADVISOR_MEMBER_REPORT_FOLDER_ITEM_ID"] = "member-folder"
content = b"%PDF-1.4\nfictional test report\n%%EOF"
stored = module.store_member_pdf("SPA-REPORT-TEST-001", 2, content)
assert stored["sha256"] == hashlib.sha256(content).hexdigest()
assert stored["filename"].endswith(stored["sha256"] + ".pdf")
assert module.read_member_pdf(stored["item_id"], stored["sha256"], stored["size"]) == content
receipt = module.store_member_pdf("SPA-RECEIPT-TEST-001", 2, content + b" receipt")
assert receipt["filename"].startswith("SPA-RECEIPT-TEST-001-R2-")
assert module.read_member_pdf(receipt["item_id"], receipt["sha256"], receipt["size"]) == content + b" receipt"
try:
    module.read_member_pdf(stored["item_id"], "0" * 64, stored["size"])
except ReportError:
    pass
else:
    raise AssertionError("Changed content digest was accepted")
try:
    module.store_member_pdf("../../escape", 1, content)
except ReportError:
    pass
else:
    raise AssertionError("Invalid report reference was accepted")
module.delete_member_pdf(stored["item_id"])
assert stored["item_id"] not in Client.items
module.delete_member_pdf(receipt["item_id"])
assert receipt["item_id"] not in Client.items
print("Protection Advisor exact-original store contract passed")
