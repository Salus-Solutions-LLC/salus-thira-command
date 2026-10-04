"""One-use, read-only classifier for the held 4 October fictional Clean event.

Never run for a Protected Member. Output only bounded booleans and categories.
No queue acknowledgement, blob read, byte access, or database mutation.
"""
import base64
import binascii
import json
import os
import re


def one_unquote(value):
    if not isinstance(value, str):
        return None
    return value[1:-1] if len(value) > 2 and value[0] == value[-1] == '"' else value


def load_events(content):
    if not isinstance(content, str) or len(content) > 65536:
        return []
    try:
        value = json.loads(content)
    except (TypeError, ValueError):
        try:
            value = json.loads(base64.b64decode(content, validate=True).decode("utf-8"))
        except (ValueError, UnicodeError, binascii.Error):
            return []
    if isinstance(value, dict):
        value = [value]
    return value if isinstance(value, list) and len(value) <= 10 else []


def main():
    required = {
        "SALUS_ENV": "dev",
        "SALUS_DB_BACKEND": "postgres",
        "SALUS_PACKAGE_SCAN_MODE": "defender",
    }
    if any(os.getenv(key) != expected for key, expected in required.items()):
        raise RuntimeError("Fictional scope guard failed")
    identity = os.getenv("SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID", "")
    queue_url = os.getenv("SALUS_SCAN_RESULTS_QUEUE_URL", "")
    topic = os.getenv("SALUS_SCAN_RESULT_TOPIC_ID", "")
    if (not identity or not queue_url.endswith("/scan-results")
            or not topic.startswith("/subscriptions/")):
        raise RuntimeError("Scanner identity or queue guard failed")

    import app
    from salus_scan_results import (
        same_blob_etag, defender_event_matches_pending, defender_result_for_pending,
    )
    from azure.identity import ManagedIdentityCredential
    from azure.storage.queue import QueueClient

    conn = app.db()
    try:
        tenants = list(conn.execute(
            "SELECT id FROM tenants WHERE slug LIKE 'fictional-scanner-%' "
            "AND created_at >= ? AND created_at < ?",
            ("2026-10-04T03:00:00", "2026-10-04T03:06:00")))
        if len(tenants) != 1:
            print(json.dumps({"fictional_clean_shape": "inconclusive",
                              "fictional_scope_count": len(tenants)}))
            return
        rows = [dict(row) for row in conn.execute(
            "SELECT id,original_name,status,blob_uri,etag,content_sha256,scan_event_id "
            "FROM package_intake_pending_scans WHERE tenant_id=?", (tenants[0]["id"],))]
        if len(rows) != 2 or {row["original_name"] for row in rows} != {"clean.txt", "eicar.txt"}:
            print(json.dumps({"fictional_clean_shape": "inconclusive",
                              "fictional_pending_count": len(rows)}))
            return
        clean = next(row for row in rows if row["original_name"] == "clean.txt")
        candidate_rows = [dict(row) for row in conn.execute(
            "SELECT id,etag FROM package_intake_pending_scans WHERE blob_uri=?",
            (clean["blob_uri"],))]
    finally:
        conn.close()

    queue = QueueClient.from_queue_url(
        queue_url, credential=ManagedIdentityCredential(client_id=identity))
    messages = list(queue.peek_messages(max_messages=16))
    matched = []
    for message in messages:
        for event in load_events(message.content):
            if isinstance(event, dict) and isinstance(event.get("data"), dict):
                if event["data"].get("blobUri") == clean["blob_uri"]:
                    matched.append(event)
    if len(matched) != 1:
        print(json.dumps({"fictional_clean_shape": "inconclusive",
                          "peeked_messages": len(messages),
                          "visible_clean_events": len(matched)}))
        return

    event = matched[0]
    data = event["data"]
    observed = data.get("eTag")
    recorded = clean["etag"]
    recorded_unquoted = one_unquote(recorded)
    observed_unquoted = one_unquote(observed)
    hex_etag = re.compile(r"0x[0-9A-Fa-f]+\Z")
    strict_matches = sum(
        1 for candidate in candidate_rows
        if same_blob_etag(candidate["etag"], observed))
    details = data.get("scanResultDetails")
    digest = details.get("sha256") if isinstance(details, dict) else None
    recorded_sha_valid = isinstance(clean["content_sha256"], str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", clean["content_sha256"]))
    details_is_object = isinstance(details, dict)
    event_digest_valid = isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-fA-F]{64}", digest))
    malware_names_is_array = details_is_object and isinstance(details.get("malwareNamesFound"), list)
    matched_pending = defender_event_matches_pending(
        event, topic=topic, blob_uri=clean["blob_uri"],
        etag=recorded, sha256=clean["content_sha256"])
    result = defender_result_for_pending(
        event, topic=topic, blob_uri=clean["blob_uri"],
        etag=recorded, sha256=clean["content_sha256"])
    print(json.dumps({
        "fictional_clean_shape": "read_only",
        "details_is_object": details_is_object,
        "recorded_sha_valid": recorded_sha_valid,
        "event_digest_valid": event_digest_valid,
        "malware_names_is_array": malware_names_is_array,
        "peeked_messages": len(messages),
        "visible_clean_events": len(matched),
        "clean_still_pending": clean["status"] == "Pending",
        "clean_has_result_event": bool(clean["scan_event_id"]),
        "candidate_rows_for_uri": len(candidate_rows),
        "strict_etag_candidate_count": strict_matches,
        "recorded_etag_is_hex": bool(isinstance(recorded_unquoted, str)
                                     and hex_etag.fullmatch(recorded_unquoted)),
        "event_etag_is_hex": bool(isinstance(observed_unquoted, str)
                                  and hex_etag.fullmatch(observed_unquoted)),
        "etag_equal_after_one_quote_pair": recorded_unquoted == observed_unquoted,
        "same_blob_etag": same_blob_etag(recorded, observed),
        "topic_matches": event.get("topic") == topic,
        "event_type_matches": event.get("eventType") == "Microsoft.Security.MalwareScanningResult",
        "result_type_is_clean": data.get("scanResultType") == "No threats found",
        "event_digest_absent": digest is None or digest == "",
        "defender_event_matches_pending": matched_pending,
        "defender_result": result if result in ("Clean", "Malicious", "Unscanned") else "Other",
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"fictional_clean_shape": "failed",
                          "error_type": type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
