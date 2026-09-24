"""Bounded, in-memory ZIP member enumeration with explicit skipped-member reasons."""

from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from pathlib import PurePosixPath

MAX_MEMBERS = 10000
MAX_MEMBER_BYTES = 100 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_RATIO = 200


class ArchiveLimitError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _safe_name(name):
    if (not name or len(name) > 512 or "\\" in name or name.startswith("/") or "\x00" in name
            or any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))
            or ":" in name.split("/")[0]):
        return False
    return str(PurePosixPath(name)) == name.rstrip("/")


def _open_checked(source):
    if len(source) > MAX_MEMBER_BYTES:
        raise ArchiveLimitError("archive_source_limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(source))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ArchiveLimitError("archive_invalid") from exc
    infos = archive.infolist()
    if len(infos) > MAX_MEMBERS:
        archive.close()
        raise ArchiveLimitError("archive_member_count_limit")
    if sum(info.file_size for info in infos) > MAX_TOTAL_BYTES:
        archive.close()
        raise ArchiveLimitError("archive_total_size_limit")
    return archive, infos


def zip_entry_count(source):
    archive, infos = _open_checked(source)
    archive.close()
    return len(infos)


def iter_zip_members(source, *, start=0, limit=None):
    """Yield records with bytes, hash and member path, or a visible failure.

    Central-directory totals are checked before any decompression; actual bytes
    are bounded again while streaming. The caller must consume the iterator.
    """
    if not isinstance(start,int) or start < 0 or (limit is not None and
            (not isinstance(limit,int) or not 1 <= limit <= MAX_MEMBERS)):
        raise ValueError("Archive page range is invalid")
    archive, infos = _open_checked(source)
    with archive:
        seen = set()
        remaining = MAX_TOTAL_BYTES
        stop = len(infos) if limit is None else min(len(infos),start + limit)
        for ordinal,info in enumerate(infos):
            path = info.filename
            duplicate = path.casefold() in seen
            seen.add(path.casefold())
            if ordinal < start:
                remaining -= info.file_size
                continue
            if ordinal >= stop:
                break
            if info.is_dir():
                continue
            reason = ""
            mode = info.external_attr >> 16
            if not _safe_name(path): reason = "unsafe_member_path"
            elif duplicate: reason = "duplicate_member_path"
            elif mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG): reason = "unsupported_member_type"
            elif info.flag_bits & 1: reason = "encrypted_member"
            elif info.file_size > MAX_MEMBER_BYTES: reason = "member_size_limit"
            elif info.file_size > max(1, info.compress_size) * MAX_RATIO: reason = "member_compression_limit"
            elif path.lower().endswith((".zip", ".jar", ".7z", ".rar", ".tar", ".gz")):
                reason = "nested_archive_requires_review"
            if reason:
                yield {"ordinal":ordinal,"path":path[:512],"path_sha256":hashlib.sha256(path.encode()).hexdigest(),
                       "status":"Retry","reason":reason,"size":info.file_size}
                continue
            buffer = io.BytesIO()
            try:
                with archive.open(info) as member:
                    while True:
                        chunk = member.read(1024 * 1024)
                        if not chunk: break
                        if buffer.tell() + len(chunk) > min(MAX_MEMBER_BYTES, remaining, info.file_size):
                            raise ArchiveLimitError("member_actual_size_limit")
                        buffer.write(chunk)
                data = buffer.getvalue()
            except (zipfile.BadZipFile, RuntimeError, OSError, ArchiveLimitError):
                yield {"ordinal":ordinal,"path":path[:512],"path_sha256":hashlib.sha256(path.encode()).hexdigest(),
                       "status":"Retry","reason":"member_read_failed","size":info.file_size}
                continue
            remaining -= len(data)
            yield {"ordinal":ordinal,"path":path[:512],"path_sha256":hashlib.sha256(path.encode()).hexdigest(),
                   "status":"Ready","size":len(data),
                   "sha256":hashlib.sha256(data).hexdigest(),"content":data}
