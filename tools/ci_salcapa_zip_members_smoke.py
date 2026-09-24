"""ZIP members remain bounded and retain per-member source provenance."""

import io
import os
import sys
import zipfile

sys.path.insert(0,os.path.dirname(os.path.dirname(__file__)))
import salcapa_zip_members as members


def archive(values):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for name,body in values: z.writestr(name,body)
    return buffer.getvalue()


def check():
    source=archive([("nested/a.txt",b"one"),("nested/b.txt",b"two"),
                    ("../escape.txt",b"no"),("nested/a.txt",b"duplicate")])
    output=list(members.iter_zip_members(source))
    assert [(row["status"],row.get("reason")) for row in output]==[
        ("Ready",None),("Ready",None),("Retry","unsafe_member_path"),
        ("Retry","duplicate_member_path")],output
    assert output[0]["path"]=="nested/a.txt" and output[0]["content"]==b"one"
    old=members.MAX_TOTAL_BYTES
    try:
        members.MAX_TOTAL_BYTES=3
        try: list(members.iter_zip_members(source))
        except members.ArchiveLimitError as exc: assert exc.code=="archive_total_size_limit"
        else: raise AssertionError("unbounded archive accepted")
    finally: members.MAX_TOTAL_BYTES=old
    old=members.MAX_RATIO
    try:
        members.MAX_RATIO=1
        result=list(members.iter_zip_members(archive([("bomb.txt",b"x"*1000)])))
        assert result[0]["reason"]=="member_compression_limit"
    finally: members.MAX_RATIO=old
    print("zip member smoke passed")


if __name__=="__main__": check()
