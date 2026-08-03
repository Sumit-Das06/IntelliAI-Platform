"""ModelManager lifecycle: ensure once, load once, warm once, reuse always.

The engine here is deliberately capability-free — a bare object with
``close()`` — and warm-up is an injected probe. The lifecycle guarantees
this suite pins are exactly the ones the first runtime shipped with; only
the capability content moved out to its runtime (moved from the
stt-runtime suite at extraction, M3 step 1).
"""

from pathlib import Path

import pytest

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import ModelManager, RuntimeServiceError, SlotSpec


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RecordingEngine:
    """Counts constructions, warm-ups, and closes: lifecycle is provable."""

    constructed = 0

    def __init__(self) -> None:
        type(self).constructed += 1
        self.warm_ups = 0
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def load_recording(_: Path | None) -> RecordingEngine:
    return RecordingEngine()


def warm_recording(engine: RecordingEngine) -> None:
    engine.warm_ups += 1


def make_manager() -> ModelManager[RecordingEngine]:
    return ModelManager(
        slots=(SlotSpec(slot="default", artifact="rec", load=load_recording),),
        warm_up=warm_recording,
    )


@pytest.mark.anyio
async def test_engines_load_once_warm_once_and_are_reused() -> None:
    RecordingEngine.constructed = 0
    manager = make_manager()
    await manager.startup()
    first = manager.lookup(None)
    second = manager.lookup("rec")
    assert first.engine is second.engine  # no per-request construction
    assert RecordingEngine.constructed == 1
    assert isinstance(first.engine, RecordingEngine)
    # The injected probe ran exactly once, before any request could arrive.
    assert first.engine.warm_ups == 1
    assert first.load_ms >= 0
    assert first.warmup_ms >= 0


@pytest.mark.anyio
async def test_lookup_before_startup_is_not_ready() -> None:
    manager = make_manager()
    with pytest.raises(RuntimeServiceError) as exc_info:
        manager.lookup(None)
    assert exc_info.value.error_type is RuntimeErrorType.NOT_READY


@pytest.mark.anyio
async def test_unknown_artifact_is_invalid_input_with_param() -> None:
    manager = make_manager()
    await manager.startup()
    with pytest.raises(RuntimeServiceError) as exc_info:
        manager.lookup("whisper-small")
    assert exc_info.value.error_type is RuntimeErrorType.INVALID_INPUT
    assert exc_info.value.param == "model"


@pytest.mark.anyio
async def test_shutdown_closes_each_engine_exactly_once() -> None:
    manager = make_manager()
    await manager.startup()
    engine = manager.lookup(None).engine
    await manager.shutdown()
    assert isinstance(engine, RecordingEngine)
    assert engine.closed == 1
    assert manager.started is False


def test_slot_configuration_is_validated() -> None:
    spec = SlotSpec(slot="default", artifact="a", load=load_recording)
    with pytest.raises(ValueError, match="at least one"):
        ModelManager(slots=(), warm_up=warm_recording)
    with pytest.raises(ValueError, match="unique"):
        ModelManager(
            slots=(spec, SlotSpec(slot="default", artifact="b", load=load_recording)),
            warm_up=warm_recording,
        )
    with pytest.raises(ValueError, match="default"):
        ModelManager(
            slots=(SlotSpec(slot="premium", artifact="a", load=load_recording),),
            warm_up=warm_recording,
        )


def test_slots_with_files_require_a_store() -> None:
    from intelliai_runtime_core import ArtifactFile, ArtifactSpec

    files = ArtifactSpec(
        artifact="a",
        version=1,
        files=(ArtifactFile(filename="m.bin", url="https://x.example/m.bin", sha256="0" * 64),),
    )
    with pytest.raises(ValueError, match="ArtifactStore"):
        ModelManager(
            slots=(SlotSpec(slot="default", artifact="a", load=load_recording, files=files),),
            warm_up=warm_recording,
        )
