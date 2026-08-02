"""Bounded inference execution — the runtime's concurrency, owned here.

Inference is blocking, CPU-bound work; the event loop must never run it.
The pool runs engine calls on a fixed thread pool sized to
``max_concurrency`` and admits at most ``max_concurrency + max_queue``
requests at once. Beyond that it answers ``overloaded`` immediately: a
fast honest no that the gateway can retry or surface (ADR-0016 — retry
policy is the gateway's, capacity truth is ours).

Threads, not processes: engines share one loaded model read-only, and the
libraries that matter release the GIL during inference (validated against
a real engine in step 5's measurements).
"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.failures import RuntimeServiceError


class WorkerPool:
    def __init__(self, max_concurrency: int, max_queue: int) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrency, thread_name_prefix="inference"
        )
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._capacity = max_concurrency + max_queue
        self._admitted = 0

    @property
    def admitted(self) -> int:
        """Requests currently executing or waiting (operational signal)."""
        return self._admitted

    async def run[R](self, fn: Callable[[], R]) -> R:
        """Execute a blocking callable on the pool, or refuse honestly."""
        if self._admitted >= self._capacity:
            raise RuntimeServiceError(
                RuntimeErrorType.OVERLOADED,
                "runtime is at capacity; retry shortly",
            )
        self._admitted += 1
        try:
            async with self._semaphore:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(self._executor, fn)
        finally:
            self._admitted -= 1

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
