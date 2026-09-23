#!/usr/bin/env python3
"""Run one bounded knowledge intake batch in a scheduled Container Apps job."""

from __future__ import annotations

import json

from salcapa_runtime import app


def main() -> None:
    process = app.state.process_knowledge_pending
    result = process("SalCAPA Scheduled Knowledge Processor")
    print("SALCAPA_KNOWLEDGE_BATCH=" + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
