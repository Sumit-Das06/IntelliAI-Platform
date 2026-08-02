"""WorkerPool: bounded admission, honest overload, off-loop execution."""

import asyncio
import threading

import pytest

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.pool import WorkerPool


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
