"""Fail-closed processing loop for approved assessment task adapters.

This does not publish reports or authorize source, model, or paid-service access.
Production execution needs the PostgreSQL queue adapter, governed evidence-store
adapter, approved cost envelope and dedicated supervised deployment in issue #588.
"""

from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from typing import Callable

from assessment_worker_state import AssessmentQueue, ClaimedItem


class TaskGate(Exception):
    def __init__(self, state: str, reason_code: str):
        super().__init__(reason_code)
        self.state = state
        self.reason_code = reason_code


@dataclass(frozen=True)
class TaskResult:
    output_ref: str
    output_sha256: str
    review_required: bool = False


Handler = Callable[[ClaimedItem, Callable[[dict], None]], TaskResult]


def run_one(queue: AssessmentQueue, tenant_id: str, worker_id: str,
            handlers: dict[str, Handler], *, lease_seconds: int = 120) -> bool:
    item = queue.claim(tenant_id, worker_id, lease_seconds)
    if item is None:
        return False
    handler = handlers.get(item.stage)
    if handler is None:
        queue.block(item, worker_id, 'blocked_expertise', 'NO_APPROVED_STAGE_ADAPTER')
        return True

    def checkpoint(data: dict):
        # The handler passes only stable offsets, hashes and opaque references.
        queue.checkpoint(item, worker_id, data, lease_seconds)

    try:
        result = handler(item, checkpoint)
        queue.finish(item, worker_id, result.output_ref, result.output_sha256,
                     review_required=result.review_required)
    except TaskGate as gate:
        queue.block(item, worker_id, gate.state, gate.reason_code)
    except Exception as exc:
        # Exception text can contain Protected Member data; only its type is logged.
        queue.fail_retryable(item, worker_id, type(exc).__name__)
    return True


def run_forever(queue: AssessmentQueue, tenant_id: str, worker_id: str,
                handlers: dict[str, Handler], *, idle_poll_seconds: float = 2.0,
                stop_requested: Callable[[], bool] | None = None):
    """Keep processing eligible work until supervisor shutdown; never claim package completion."""
    stop_requested = stop_requested or (lambda: False)
    while not stop_requested():
        if not run_one(queue, tenant_id, worker_id, handlers):
            time.sleep(idle_poll_seconds)


def install_shutdown_handler():
    state = {'stop': False}

    def request_stop(_signum, _frame):
        state['stop'] = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    return lambda: state['stop']

