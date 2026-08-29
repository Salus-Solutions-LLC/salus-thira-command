# Source integrity

After a fresh checkout of v0.5, run:

```bash
python tools/reconstruct_v05_source.py
python tools/verify_v05_source.py
```

The first command reconstructs the two large tested source files from versioned archives. The second verifies their SHA-256 hashes against the v0.5 release record.
