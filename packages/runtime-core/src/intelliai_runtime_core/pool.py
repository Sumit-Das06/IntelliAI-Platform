"""Bounded inference execution — the runtime's concurrency, owned here.

Inference is blocking, CPU-bound work; the event loop must never run it.
The pool runs engine calls on a fixed thread pool sized to
``max_concurrency`` and admits at most ``max_concurrency + max_queue``
requests at once. Beyond that it answers ``overloaded`` immediately: a
fast honest no that the gateway can retry or surface (ADR-0016 — retry
policy is the gateway's, capacity truth is ours).

Threads, not processes: engines share one loaded model read-only, and the
libraries that matter release the GIL during inference (validated against
a real engine in M2 step 5's measurements).

``run_stream`` (M36) is the same admission law for PROGRESSIVE work: one
pool slot held for the whole production, items crossing to the event
loop through a BOUNDED buffer (a slow consumer blocks the producer —
backpressure, never unbounded memory), and consumer cancellation
propagated to the producer between items (a bounded stop: no orphaned
inference). It knows nothing about audio, engines, or models — items are
opaque; this module stays pure lifecycle machinery (ADR-0019).
"""

import asyncio
import queue
import threading
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core.failures import RuntimeServiceError


class StreamCancelled(Exception):  # noqa: N818 — a signal, not an error condition
    """Raised inside a producer's ``emit`` when the consumer is gone."""


class _End:
    """Sentinel: producer finished (optionally with its failure)."""

    def __init__(self, error: BaseException | None = None) -> None:
        self.error = error


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

    async def run_stream[R](
        self, produce: Callable[[Callable[[R], None]], None], buffer_items: int = 4
    ) -> AsyncIterator[R]:
        """Run ``produce(emit)`` on one pool slot; yield what it emits.

        Admission is identical to ``run`` — checked on entry, one slot
        for the stream's whole life. ``emit`` blocks when ``buffer_items``
        are unconsumed (backpressure) and raises ``StreamCancelled`` once
        the consumer has gone away, so a producer that emits regularly
        stops within one item of a disconnect. A producer exception ends
        the stream by re-raising HERE, after every already-emitted item
        has been delivered.
        """
        if self._admitted >= self._capacity:
            raise RuntimeServiceError(
                RuntimeErrorType.OVERLOADED,
                "runtime is at capacity; retry shortly",
            )
        self._admitted += 1
        handoff: queue.Queue[R | _End] = queue.Queue(maxsize=max(1, buffer_items))
        cancelled = threading.Event()

        def emit(item: R) -> None:
            while True:
                if cancelled.is_set():
                    raise StreamCancelled
                try:
                    handoff.put(item, timeout=0.1)
                    return
                except queue.Full:
                    continue

        def worker() -> None:
            try:
                produce(emit)
            except StreamCancelled:
                handoff.put(_End())
            except BaseException as exc:
                handoff.put(_End(exc))
            else:
                handoff.put(_End())

        try:
            async with self._semaphore:
                loop = asyncio.get_running_loop()
                future = loop.run_in_executor(self._executor, worker)
                try:
                    while True:
                        item = await loop.run_in_executor(None, handoff.get)
                        if isinstance(item, _End):
                            if item.error is not None:
                                raise item.error
                            break
                        yield item
                finally:
                    cancelled.set()
                    # Drain so a blocked emit() wakes, sees the flag, and
                    # the producer exits — the slot is never orphaned.
                    while not future.done():
                        try:
                            handoff.get_nowait()
                        except queue.Empty:
                            await asyncio.sleep(0.05)
                    await future
        finally:
            self._admitted -= 1

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
