"""Read-only, bounded probes of the governed Microsoft 365 source boundary."""

from __future__ import annotations

import re
from collections import deque
from urllib.parse import urlparse

from salcapa_m365_intake import GRAPH_ROOT, GovernedM365Config, GovernedM365Intake


MAX_BOUNDARY_ITEMS = 50000
MAX_BOUNDARY_FOLDERS = 5000
MAX_BOUNDARY_PAGES = 1000
EXPECTED_TOP_LEVEL_FOLDERS = {
    "10 Pending Classification",
    "20 Ready for Intake Review",
    "30 Exceptions and Manual Review",
    "40 Customer Batch Staging - Unassigned",
    "90 Migration Hold",
    "90 Processed Intake",
    "Does Not Upload",
}


def _children_endpoint(intake: GovernedM365Intake, folder_id: str) -> str:
    return f"{GRAPH_ROOT}/drives/{intake.config.drive_id}/items/{folder_id}/children"


def _scoped_children_link(link: object, endpoint: str) -> str:
    if not isinstance(link, str) or not link or len(link) > 8192:
        raise RuntimeError("Boundary continuation invalid")
    parsed = urlparse(link)
    expected = urlparse(endpoint)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "graph.microsoft.com"
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.path != expected.path
        or not parsed.query
    ):
        raise RuntimeError("Boundary continuation invalid")
    return link


def census(intake: GovernedM365Intake) -> dict[str, int]:
    """Count every in-boundary item without downloading source bytes."""
    root_id = intake.config.folder_item_id
    queue = deque([(root_id, "")])
    seen_folders = set()
    seen_items = set()
    top_level = set()
    totals = {"files": 0, "folders": 0, "bytes": 0, "oversize": 0, "pages": 0}
    select = "id,name,size,file,folder,remoteItem,lastModifiedDateTime,eTag,parentReference"

    while queue:
        folder_id, first_level = queue.popleft()
        if folder_id in seen_folders:
            raise RuntimeError("Boundary folder cycle")
        seen_folders.add(folder_id)
        if len(seen_folders) > MAX_BOUNDARY_FOLDERS:
            raise RuntimeError("Boundary folder limit exceeded")
        endpoint = _children_endpoint(intake, folder_id)
        page = endpoint
        params = {"$select": select, "$top": "200"}
        seen_pages = set()
        while page:
            if page in seen_pages or totals["pages"] >= MAX_BOUNDARY_PAGES:
                raise RuntimeError("Boundary page limit exceeded")
            seen_pages.add(page)
            totals["pages"] += 1
            response = intake.client.get(page, headers=intake._headers(), params=params)
            if response.status_code != 200:
                raise RuntimeError("Boundary folder unavailable")
            payload = response.json()
            values = payload.get("value")
            if not isinstance(values, list) or len(values) > 1000:
                raise RuntimeError("Boundary response incomplete")
            for item in values:
                if not isinstance(item, dict) or "remoteItem" in item:
                    raise RuntimeError("Boundary item invalid")
                item_id = str(item.get("id", ""))
                if not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", item_id):
                    raise RuntimeError("Boundary item identity invalid")
                if item_id in seen_items:
                    continue
                seen_items.add(item_id)
                if len(seen_items) > MAX_BOUNDARY_ITEMS:
                    raise RuntimeError("Boundary item limit exceeded")
                name = str(item.get("name", ""))
                if not name or name in {".", ".."} or "/" in name or "\\" in name:
                    raise RuntimeError("Boundary item name invalid")
                parent = str((item.get("parentReference") or {}).get("id", ""))
                if parent != folder_id:
                    raise RuntimeError("Boundary parent mismatch")
                item_first_level = first_level or name
                if folder_id == root_id:
                    top_level.add(name)
                is_folder = isinstance(item.get("folder"), dict)
                is_file = isinstance(item.get("file"), dict)
                if is_folder == is_file:
                    raise RuntimeError("Boundary item kind invalid")
                if is_folder:
                    totals["folders"] += 1
                    queue.append((item_id, item_first_level))
                    continue
                size = item.get("size")
                if not isinstance(size, int) or size < 0:
                    raise RuntimeError("Boundary file size invalid")
                if not item.get("eTag") or not item.get("lastModifiedDateTime"):
                    raise RuntimeError("Boundary file provenance incomplete")
                totals["files"] += 1
                totals["bytes"] += size
                if size > intake.config.max_file_bytes:
                    totals["oversize"] += 1
            next_page = payload.get("@odata.nextLink")
            page = _scoped_children_link(next_page, endpoint) if next_page else ""
            params = None

    if top_level != EXPECTED_TOP_LEVEL_FOLDERS:
        raise RuntimeError("Boundary top-level folders changed")
    totals["complete"] = 1
    return totals


def probe(intake: GovernedM365Intake) -> tuple[int, str, bool]:
    root = (
        f"{GRAPH_ROOT}/drives/{intake.config.drive_id}/items/"
        f"{intake.config.folder_item_id}/children"
    )
    page = root
    params = {"$select": "id,name,folder", "$top": "200"}
    seen = set()
    pending = []
    for _ in range(20):
        if page in seen:
            raise RuntimeError("Delta probe folder pagination cycle")
        seen.add(page)
        response = intake.client.get(page, headers=intake._headers(), params=params)
        if response.status_code != 200:
            raise RuntimeError("Delta probe intake root unavailable")
        payload = response.json()
        for item in payload.get("value", []):
            if item.get("name") == "10 Pending Classification" and isinstance(item.get("folder"), dict):
                pending.append(str(item.get("id", "")))
        next_page = payload.get("@odata.nextLink")
        if not next_page:
            break
        parsed = urlparse(next_page)
        if (
            len(next_page) > 8192 or parsed.scheme != "https"
            or parsed.hostname != "graph.microsoft.com"
            or parsed.username or parsed.password or parsed.fragment
            or not next_page.startswith(root + "?")
        ):
            raise RuntimeError("Delta probe folder continuation invalid")
        page, params = next_page, None
    else:
        raise RuntimeError("Delta probe root pagination limit")
    if len(pending) != 1 or not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", pending[0]):
        raise RuntimeError("Delta probe pending folder unresolved")
    endpoint = f"{GRAPH_ROOT}/drives/{intake.config.drive_id}/items/{pending[0]}/delta"
    response = intake.client.get(
        endpoint, headers=intake._headers(), params={"$top": "1"},
    )
    if response.status_code != 200:
        try:
            code = str(response.json().get("error", {}).get("code", "unavailable"))[:80]
        except (ValueError, TypeError, AttributeError):
            code = "unavailable"
        return response.status_code, code if re.fullmatch(r"[A-Za-z0-9_.-]+", code) else "unavailable", False
    payload = response.json()
    link = payload.get("@odata.nextLink") or payload.get("@odata.deltaLink") or ""
    parsed = urlparse(link)
    scoped = bool(
        link and len(link) <= 8192 and parsed.scheme == "https"
        and parsed.hostname == "graph.microsoft.com"
        and not parsed.username and not parsed.password and not parsed.fragment
        and parsed.path.startswith(
            f"/v1.0/drives/{intake.config.drive_id}/items/{pending[0]}/delta"
        )
    )
    kind = "next" if "@odata.nextLink" in payload else "delta" if "@odata.deltaLink" in payload else "none"
    return response.status_code, kind, scoped


if __name__ == "__main__":
    try:
        intake = GovernedM365Intake(GovernedM365Config.from_environment())
        status, kind, scoped = probe(intake)
        print(f"BULK_DELTA_HTTP={status}", flush=True)
        print(f"BULK_DELTA_LINK_KIND={kind}", flush=True)
        print(f"BULK_DELTA_SCOPED_LINK={scoped}", flush=True)
        if status != 200 or not scoped:
            raise SystemExit(1)
        counts = census(intake)
        print(f"BOUNDARY_FILES={counts['files']}", flush=True)
        print(f"BOUNDARY_FOLDERS={counts['folders']}", flush=True)
        print(f"BOUNDARY_BYTES={counts['bytes']}", flush=True)
        print(f"BOUNDARY_OVERSIZE={counts['oversize']}", flush=True)
        print(f"BOUNDARY_PAGES={counts['pages']}", flush=True)
        print(f"BOUNDARY_COMPLETE={counts['complete']}", flush=True)
    except Exception as exc:
        print(f"BULK_DELTA_SAFE_ERROR_TYPE={type(exc).__name__}", flush=True)
        raise SystemExit(1) from None
