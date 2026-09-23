# SalCAPA 3.171 Release Notes

## Outcome

SalCAPA 3.171 activates the automatic Microsoft 365 knowledge processor in the production runtime.

## Correction

- Imports `register_knowledge_promotion` into `salcapa_runtime.py`.
- Registers the knowledge routes and scheduled startup processor with the live FastAPI application.
- Adds regression checks that fail if runtime composition omits the processor.

## Retained controls

- PostgreSQL candidate creation uses explicit `RETURNING id`.
- Every pending file is processed automatically without a human ingestion exception queue.
- Originals are retained and moved only after SHA-256 destination verification.
- Citation metadata remains hash-bound to the exact source.
