"""Verify Graph cursor and worker leases on the production PostgreSQL adapter."""

import os
import sys

sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
from database import connect_database
from salcapa_bulk_delta import discover,claim_work,complete_work
from ci_salcapa_bulk_delta_smoke import Client,Intake,Response,BASE,file,DRIVE,PENDING


def check():
    assert os.getenv("SALUS_DB_BACKEND")=="postgres"
    client=Client()
    client.pages[BASE]=Response(200,{"value":[file(700001),file(700002)],
                                     "@odata.deltaLink":BASE+"?token=pg"})
    intake=Intake(client)
    assert discover(intake,connect_database,now=1000)["complete"]
    work=claim_work(connect_database,DRIVE,PENDING,limit=2,now=1001)
    assert len(work)==2
    assert complete_work(connect_database,DRIVE,PENDING,work[0],success=True,now=1002)
    assert complete_work(connect_database,DRIVE,PENDING,work[1],success=False,reason="retry",now=1002)
    conn=connect_database()
    try:
        rows=conn.execute("SELECT status FROM m365_bulk_items ORDER BY item_id").fetchall()
        assert [row["status"] for row in rows]==["Done","Retry"]
    finally:
        conn.execute("DROP TABLE IF EXISTS m365_bulk_items")
        conn.execute("DROP TABLE IF EXISTS m365_bulk_cursors")
        conn.commit()
        conn.close()
    print("PostgreSQL bulk delta smoke passed")


if __name__=="__main__": check()
