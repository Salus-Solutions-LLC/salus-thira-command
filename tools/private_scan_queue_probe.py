"""One-use, read-only probe for the 4 October fictional scanner acceptance.

This file is encoded into one reviewed Container Apps job execution template.
Never invoke for a Protected Member. It prints only bounded categories, never
queue payloads, URIs, file names, hashes, tenant IDs, or file bytes.
"""
import base64
import collections
import json
import os

def main():
    required = {
        "SALUS_ENV": "dev",
        "SALUS_DB_BACKEND": "postgres",
        "SALUS_PACKAGE_SCAN_MODE": "defender",
    }
    if any(os.getenv(key) != value for key, value in required.items()):
        raise SystemExit("fictional_queue_probe_guard_failed")
    if not os.getenv("SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID"):
        raise SystemExit("fictional_queue_probe_identity_missing")
    import app
    conn = app.db()
    try:
        tenants = list(conn.execute(
            "SELECT id FROM tenants WHERE slug LIKE 'fictional-scanner-%' "
            "AND created_at >= ? AND created_at < ?",
            ("2026-10-04T03:00:00", "2026-10-04T03:06:00")))
        if len(tenants) != 1:
            print(json.dumps({"fictional_queue_probe": "inconclusive",
                              "fictional_scope_count": len(tenants)}))
            return
        rows = [dict(row) for row in conn.execute(
            "SELECT original_name,status,scan_result,blob_uri,blob_version_id,"
            "etag,content_sha256,scan_event_id FROM package_intake_pending_scans "
            "WHERE tenant_id=?", (tenants[0]["id"],))]
    finally:
        conn.close()
    if len(rows) != 2 or {row["original_name"] for row in rows} != {"clean.txt", "eicar.txt"}:
        print(json.dumps({"fictional_queue_probe": "inconclusive",
                          "fictional_pending_count": len(rows)}))
        return
    by_uri = {row["blob_uri"]: row for row in rows}
    queue_url = os.getenv("SALUS_SCAN_RESULTS_QUEUE_URL", "")
    expected_topic = os.getenv("SALUS_SCAN_RESULT_TOPIC_ID", "")
    if not queue_url.endswith("/scan-results") or not expected_topic.startswith("/subscriptions/"):
        raise SystemExit("fictional_queue_probe_queue_guard_failed")
    from azure.identity import ManagedIdentityCredential
    from azure.storage.queue import QueueClient
    credential = ManagedIdentityCredential(
        client_id=os.environ["SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID"])
    queue = QueueClient.from_queue_url(queue_url, credential=credential)
    messages = list(queue.peek_messages(max_messages=16))
    counts = collections.Counter()
    for message in messages:
        raw = message.content
        if not isinstance(raw, str) or len(raw) > 65536:
            counts["invalid_content"] += 1
            continue
        try:
            events = json.loads(raw)
        except (TypeError, ValueError):
            try:
                events = json.loads(base64.b64decode(raw, validate=True).decode("utf-8"))
                counts["base64_wrapped"] += 1
            except (ValueError, UnicodeError):
                counts["invalid_json"] += 1
                continue
        if isinstance(events, dict):
            events = [events]
        if not isinstance(events, list) or not 1 <= len(events) <= 10:
            counts["invalid_event_shape"] += 1
            continue
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("data"), dict):
                counts["invalid_event_shape"] += 1
                continue
            data = event["data"]
            row = by_uri.get(data.get("blobUri"))
            if row is None:
                counts["other_scope_or_uri_mismatch"] += 1
                continue
            counts["fictional_event"] += 1
            if event.get("eventType") != "Microsoft.Security.MalwareScanningResult":
                counts["event_type_mismatch"] += 1
            if event.get("topic") != expected_topic:
                counts["topic_mismatch"] += 1
            if data.get("eTag") != row["etag"]:
                counts["etag_mismatch"] += 1
            details = data.get("scanResultDetails")
            digest = details.get("sha256") if isinstance(details, dict) else None
            if not isinstance(digest, str) or digest.lower() != row["content_sha256"].lower():
                counts["digest_mismatch_or_absent"] += 1
            result = data.get("scanResultType")
            if result in ("Malicious", "No threats found", "Not scanned", "Error"):
                counts["result_" + result.replace(" ", "_")] += 1
            else:
                counts["result_other"] += 1
    statuses = {}
    for row in rows:
        label = "clean" if row["original_name"] == "clean.txt" else "eicar"
        status = row["status"]
        if status not in ("Pending", "Promoted", "Malicious", "Unscanned", "Reconcile"):
            status = "Other"
        statuses[label] = {
            "status": status,
            "has_result_event": bool(row["scan_event_id"]),
            "has_exact_version": bool(row["blob_version_id"]),
        }
    allowed = (
        "invalid_content", "invalid_json", "base64_wrapped", "invalid_event_shape",
        "other_scope_or_uri_mismatch", "fictional_event", "event_type_mismatch",
        "topic_mismatch", "etag_mismatch", "digest_mismatch_or_absent",
        "result_Malicious", "result_No_threats_found", "result_Not_scanned",
        "result_Error", "result_other",
    )
    print(json.dumps({
        "fictional_queue_probe": "read_only",
        "peeked_messages": len(messages),
        "fictional_status": statuses,
        "event_categories": {key: counts[key] for key in allowed},
    }, sort_keys=True))

if __name__ == "__main__":
    main()
