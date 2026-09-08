#!/usr/bin/env python3
"""Run archived regression smokes against the current SalCAPA candidate version.

Frozen source archives intentionally preserve the exact release expectation that
was current when each capability was accepted. Current-candidate PR validation
must preserve all substantive archived assertions while adapting only explicit
release-version assertions to the candidate under test.

This runner copies each smoke beside the original, changes version literals only
on lines that explicitly reference ``version`` or ``SALCAPA_RELEASE_VERSION``,
executes that temporary copy, and then removes it. The archived reconstruction and
its digest remain unchanged and independently verifiable.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "salcapa_runtime.py"
VERSION_DECLARATION = re.compile(r'^SALCAPA_RELEASE_VERSION\s*=\s*["\'](?P<version>\d+\.\d+)["\']', re.MULTILINE)
QUOTED_VERSION = re.compile(r'(?P<quote>["\'])(?P<version>\d+\.\d+)(?P=quote)')


def candidate_version() -> str:
    match = VERSION_DECLARATION.search(RUNTIME.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("Current SalCAPA release version declaration was not found")
    return match.group("version")


def normalized_source(path: Path, current: str) -> tuple[str, list[tuple[int, str, str]]]:
    original = path.read_text(encoding="utf-8")
    output: list[str] = []
    changes: list[tuple[int, str, str]] = []

    for number, line in enumerate(original.splitlines(keepends=True), start=1):
        lower = line.lower()
        if "version" not in lower and "salcapa_release_version" not in lower:
            output.append(line)
            continue

        def replace(match: re.Match[str]) -> str:
            old = match.group("version")
            if old == current:
                return match.group(0)
            quote = match.group("quote")
            changes.append((number, old, current))
            return f"{quote}{current}{quote}"

        output.append(QUOTED_VERSION.sub(replace, line))

    normalized = "".join(output)
    if normalized != original:
        original_lines = original.splitlines()
        normalized_lines = normalized.splitlines()
        for index, (before, after) in enumerate(zip(original_lines, normalized_lines), start=1):
            if before == after:
                continue
            marker = before.lower()
            if "version" not in marker and "salcapa_release_version" not in marker:
                raise SystemExit(f"Refusing unscoped smoke normalization at {path}:{index}")
    return normalized, changes


def run_smoke(path: Path, current: str) -> None:
    if not path.is_file():
        raise SystemExit(f"Smoke file not found: {path}")
    source, changes = normalized_source(path, current)
    if changes:
        detail = ", ".join(f"line {line}: {old}->{new}" for line, old, new in changes)
        print(f"CURRENT_RELEASE_SMOKE_NORMALIZATION {path.relative_to(ROOT)}: {detail}")
    else:
        print(f"CURRENT_RELEASE_SMOKE_NO_NORMALIZATION {path.relative_to(ROOT)}")

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".py", prefix=f".{path.stem}-current-",
        dir=path.parent, delete=False,
    ) as handle:
        handle.write(source)
        temporary = Path(handle.name)
    try:
        subprocess.run([sys.executable, str(temporary)], cwd=ROOT, check=True)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: run_current_release_smoke.py <smoke.py> [<smoke.py> ...]", file=sys.stderr)
        return 2
    current = candidate_version()
    print(f"CURRENT_SALCAPA_CANDIDATE_VERSION {current}")
    for raw in argv[1:]:
        candidate = (ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError as exc:
            raise SystemExit(f"Smoke path must remain inside repository: {candidate}") from exc
        run_smoke(candidate, current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
