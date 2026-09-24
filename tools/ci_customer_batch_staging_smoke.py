"""Boundary regression for shared customer batch staging (no Graph writes)."""

import hashlib
import sqlite3

from salcapa_customer_batches import (
    BatchBoundaryError, assign_batch, bind_hash, create_tables, record_item,
    register_batch, release_manifest, seal_inventory,
)


def denied(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except BatchBoundaryError:
        return
    raise AssertionError("A customer boundary was not enforced")


def main():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    batch = register_batch(conn, source_drive_id="drive_1234",
                           source_root_id="root_1234", source_folder_id="folder_1234",
                           verify_folder=lambda d, f, r: f == "folder_1234" and r == "root_1234")
    assert batch == register_batch(conn, source_drive_id="drive_1234",
                                   source_root_id="root_1234", source_folder_id="folder_1234",
                                   verify_folder=lambda *_: True)
    denied(register_batch, conn, source_drive_id="drive_1234",source_root_id="root_1234",
           source_folder_id="other_1234",verify_folder=lambda *_: False)
    denied(release_manifest, conn,batch,verify_route=lambda *_: True,
           verify_source=lambda *_: True,verify_complete_inventory=lambda *_: True)
    denied(record_item, conn,batch,source_item_id="item_1234",source_etag="e1",
           relative_path="../leak.txt",size_bytes=4,verify_ancestry=lambda *_: True)
    denied(record_item, conn,batch,source_item_id="item_1234",source_etag="e1",
           relative_path="a.txt",size_bytes=4,verify_ancestry=lambda *_: False)
    record_item(conn,batch,source_item_id="item_1234",source_etag="e1",
                relative_path="a/b.txt",size_bytes=4,verify_ancestry=lambda *_: True)
    digest = hashlib.sha256(b"test").hexdigest()
    bind_hash(conn,batch,"item_1234","e1",digest)
    denied(bind_hash,conn,batch,"item_1234","e1",hashlib.sha256(b"other").hexdigest())
    denied(assign_batch,conn,batch,member_id="PM_1234",engagement_id="ENG_1234",
           destination_drive_id="dest_1234",destination_folder_id="target_1234",
           actor="user_1234",verify_route=lambda *_: False)
    assign_batch(conn,batch,member_id="PM_1234",engagement_id="ENG_1234",
                 destination_drive_id="dest_1234",destination_folder_id="target_1234",
                 actor="user_1234",verify_route=lambda *_: True)
    denied(assign_batch,conn,batch,member_id="PM_9999",engagement_id="ENG_9999",
           destination_drive_id="dest_1234",destination_folder_id="target_1234",
           actor="user_1234",verify_route=lambda *_: True)
    denied(seal_inventory,conn,batch,checkpoint="delta-token",verify_complete_inventory=lambda *_: False)
    seal_inventory(conn,batch,checkpoint="delta-token",verify_complete_inventory=lambda *_: True)
    denied(release_manifest,conn,batch,verify_route=lambda *_: False,
           verify_source=lambda *_: True,verify_complete_inventory=lambda *_: True)
    denied(release_manifest,conn,batch,verify_route=lambda *_: True,
           verify_source=lambda *_: False,verify_complete_inventory=lambda *_: True)
    denied(release_manifest,conn,batch,verify_route=lambda *_: True,
           verify_source=lambda *_: True,verify_complete_inventory=lambda *_: False)
    manifest = release_manifest(conn,batch,verify_route=lambda *_: True,
                                verify_source=lambda *_: True,
                                verify_complete_inventory=lambda *_: True)
    assert manifest["member_id"] == "PM_1234"
    assert manifest["items"][0]["source_sha256"] == digest
    denied(record_item,conn,batch,source_item_id="item_5678",source_etag="e2",
           relative_path="late.txt",size_bytes=4,verify_ancestry=lambda *_: True)
    conn.close()


if __name__ == "__main__":
    main()
