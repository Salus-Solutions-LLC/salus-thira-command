from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath


FORBIDDEN_SUFFIXES = {
    ".backup", ".db", ".doc", ".docm", ".docx", ".dump", ".key", ".log",
    ".ndjson", ".p12", ".pdf", ".pem", ".pfx", ".ppt", ".pptm", ".pptx",
    ".sqlite", ".sqlite3", ".xls", ".xlsm", ".xlsx",
}
FORBIDDEN_PARTS = {
    "attachments", "backups", "case-files", "client-evidence", "controlled-documents",
    "exports", "logs", "person-records", "uploads",
}
ALLOWED_PATHS = {".env.example"}
MAX_SCAN_BYTES = 2 * 1024 * 1024
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Azure storage account key": re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}"),
    "credentialed database URL": re.compile(r"postgres(?:ql)?://[^\s:@/]+:[^\s@/]+@"),
    "assigned client secret": re.compile(r"(?i)client[_-]?secret\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}"),
}


def tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return [Path(p.decode("utf-8")) for p in result.stdout.split(b"\0") if p]


def main() -> int:
    violation_found = False
    scanned = 0
    for path in tracked_paths():
        posix = PurePosixPath(path.as_posix())
        if path.as_posix() in ALLOWED_PATHS:
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or FORBIDDEN_PARTS.intersection(posix.parts):
            violation_found = True
            continue
        try:
            if not path.is_file() or path.stat().st_size > MAX_SCAN_BYTES:
                continue
            data = path.read_bytes()
            if b"\0" in data:
                continue
            text = data.decode("utf-8", errors="strict")
        except (OSError, UnicodeError):
            continue
        scanned += 1
        # A line-level exception must be explicit and reviewable. Use only for
        # non-secret test fixtures, never for a real credential.
        text = "\n".join(
            line for line in text.splitlines() if "repo-hygiene: allow" not in line
        )
        for pattern in SECRET_PATTERNS.values():
            if pattern.search(text):
                violation_found = True

    if violation_found:
        print("REPOSITORY_HYGIENE_FAIL")
        print("Review the proposed files locally; sensitive details are not printed in CI logs.")
        return 1
    print(f"REPOSITORY_HYGIENE_PASS scanned_text_files={scanned}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
