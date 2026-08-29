from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "source_parts"

TARGETS = {
    ROOT / "app.py": ("app.py.part*", "c8a01088fb152fda095b17cd8911b910c3cf4b2c6e3e2c874dbcb93218bcd641"),
    ROOT / "static" / "app.js": ("static_app.js.part*", "941f8655c388cc4e3b44c4e41145d08c0699df03651143502d501a63d3177be8"),
}

for target, (pattern, expected) in TARGETS.items():
    parts = sorted(PARTS.glob(pattern))
    if not parts:
        raise SystemExit(f"No source parts found for {target.name}")
    data = b"".join(p.read_bytes() for p in parts)
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise SystemExit(
            f"Integrity check failed for {target}: expected {expected}, got {digest}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print(f"Reconstructed {target.relative_to(ROOT)} ({digest})")
