"""WorkerPool: bounded admission, honest overload, off-loop execution.

(Moved verbatim from the stt-runtime suite at extraction, M3 step 1 —
imports only.)
"""

import asyncio
import threading
from collections.abc import AsyncGenerator

import pytest

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError, WorkerPool


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_runs_blocking_work_and_returns_result() -> None:
    pool = WorkerPool(max_concurrency=1, max_queue=0)
    try:
        assert await pool.run(lambda: 21 * 2) == 42
    finally:
        pool.shutdown()


@pytest.mark.anyio
async def test_saturation_answers_overloaded_immediately() -> None:
    release = threading.Event()
    pool = WorkerPool(max_concurrency=1, max_queue=1)

    def blocking() -> str:
        release.wait(timeout=10)
        return "done"

    try:
        running = asyncio.create_task(pool.run(blocking))  # occupies the slot
        queued = asyncio.create_task(pool.run(blocking))  # fills the queue
        await asyncio.sleep(0.05)  # let both tasks be admitted
        assert pool.admitted == 2

        with pytest.raises(RuntimeServiceError) as exc_info:
            await pool.run(blocking)  # over capacity: refuse, don't wait
        assert exc_info.value.error_type is RuntimeErrorType.OVERLOADED

        release.set()
        assert await running == "done"
        assert await queued == "done"
        assert pool.admitted == 0
    finally:
        release.set()
        pool.shutdown()


# ── run_stream (M36): the admission law, applied to progressive work ──


@pytest.mark.anyio
class TestRunStream:
    async def test_items_arrive_in_order_and_the_slot_is_released(self) -> None:
        pool = WorkerPool(max_concurrency=1, max_queue=0)

        def produce(emit):  # type: ignore[no-untyped-def]
            for index in range(5):
                emit(index)

        received = [item async for item in pool.run_stream(produce)]
        assert received == [0, 1, 2, 3, 4]
        assert pool.admitted == 0

    async def test_admission_refuses_when_streams_hold_the_capacity(self) -> None:

        pool = WorkerPool(max_concurrency=1, max_queue=0)
        release = threading.Event()

        def slow_produce(emit):  # type: ignore[no-untyped-def]
            emit(b"first")
            release.wait(timeout=5)

        stream: AsyncGenerator[bytes] = pool.run_stream(slow_produce)  # type: ignore[assignment]
        assert await anext(stream) == b"first"  # slot now held by the stream
        with pytest.raises(RuntimeServiceError) as refused:
            await pool.run(lambda: 42)
        assert refused.value.error_type is RuntimeErrorType.OVERLOADED
        release.set()
        await stream.aclose()
        assert pool.admitted == 0

    async def test_consumer_departure_cancels_the_producer_boundedly(self) -> None:
        pool = WorkerPool(max_concurrency=1, max_queue=0)
        emitted = []
        stopped = threading.Event()

        def produce(emit):  # type: ignore[no-untyped-def]
            try:
                for index in range(10_000):
                    emit(index)
                    emitted.append(index)
            finally:
                stopped.set()

        stream: AsyncGenerator[int] = pool.run_stream(produce, buffer_items=2)  # type: ignore[assignment]
        assert await anext(stream) == 0
        await stream.aclose()  # the consumer walks away
        assert stopped.wait(timeout=5), "producer must stop after consumer departure"
        # Bounded stop: the producer got at most a buffer's worth further.
        assert len(emitted) < 20
        assert pool.admitted == 0

    async def test_producer_failure_surfaces_after_delivered_items(self) -> None:
        pool = WorkerPool(max_concurrency=1, max_queue=0)

        def produce(emit):  # type: ignore[no-untyped-def]
            emit("delivered")
            raise ValueError("engine broke mid-stream")

        stream = pool.run_stream(produce)
        assert await anext(stream) == "delivered"
        with pytest.raises(ValueError, match="engine broke"):
            await anext(stream)
        assert pool.admitted == 0

    async def test_backpressure_blocks_the_producer_not_memory(self) -> None:
        import asyncio

        pool = WorkerPool(max_concurrency=1, max_queue=0)
        produced = []

        def produce(emit):  # type: ignore[no-untyped-def]
            for index in range(100):
                emit(index)
                produced.append(index)

        stream = pool.run_stream(produce, buffer_items=2)
        assert await anext(stream) == 0
        await asyncio.sleep(0.3)  # consumer stalls; producer must too
        assert len(produced) <= 5  # bounded by the buffer, not by 100
        remaining = [item async for item in stream]
        assert remaining == list(range(1, 100))
