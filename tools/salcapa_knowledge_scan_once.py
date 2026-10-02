#!/usr/bin/env python3
"""Run one bounded knowledge intake batch in a scheduled Container Apps job."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
print("SALCAPA_WORKER_PHASE=runtime_import_started", flush=True)
from salcapa_runtime import app
print("SALCAPA_WORKER_PHASE=runtime_import_done", flush=True)


def main() -> None:
    process = app.state.process_knowledge_pending
    print("SALCAPA_WORKER_PHASE=process_pending_started", flush=True)
    result = process("SalCAPA Scheduled Knowledge Processor")
    print("SALCAPA_KNOWLEDGE_BATCH=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
