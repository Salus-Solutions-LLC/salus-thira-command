"""Read-only, bounded probe of folder-scoped Microsoft Graph delta."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from salcapa_m365_intake import GRAPH_ROOT, GovernedM365Config, GovernedM365Intake


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
        status, kind, scoped = probe(GovernedM365Intake(GovernedM365Config.from_environment()))
        print(f"BULK_DELTA_HTTP={status}", flush=True)
        print(f"BULK_DELTA_LINK_KIND={kind}", flush=True)
        print(f"BULK_DELTA_SCOPED_LINK={scoped}", flush=True)
        if status != 200 or not scoped:
            raise SystemExit(1)
    except Exception as exc:
        print(f"BULK_DELTA_SAFE_ERROR_TYPE={type(exc).__name__}", flush=True)
        raise SystemExit(1) from None
