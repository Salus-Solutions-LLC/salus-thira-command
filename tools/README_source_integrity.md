# Source integrity

After a fresh checkout of v1.15, run:

```bash
python tools/reconstruct_v115_source.py
python tools/verify_v115_source.py
```

The reconstruction entrypoint establishes the exact frozen v1.14 baseline through the versioned archive chain, applies the deterministic v1.15 delta, and verifies every archive chunk and reconstructed source file with SHA-256. The verification entrypoint independently checks the final `app.py` and `static/app.js` byte lengths and hashes against `source_archives/v1.15/manifest.json`.
