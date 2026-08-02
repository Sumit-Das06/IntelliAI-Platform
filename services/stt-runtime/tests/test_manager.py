"""ModelManager lifecycle: load once, reuse always, unload once."""

import pytest

from intelliai_runtime_contract import RuntimeErrorType, TranscriptionRequest, TranscriptionResult
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.manager import ModelManager, SlotSpec
from intelliai_stt_runtime.pipeline import DecodedAudio


class RecordingEngine:
    """Counts constructions and closes so lifecycle claims are provable."""

    constructed = 0

    def __init__(self) -> None:
        type(self).constructed += 1
        self.closed = 0

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
        return TranscriptionResult(text="x", language="und", duration_seconds=0.0)

    def close(self) -> None:
        self.closed += 1


def make_manager() -> ModelManager:
    return ModelManager(slots=(SlotSpec(slot="default", artifact="rec", load=RecordingEngine),))


@pytest.mark.anyio
async def test_engines_load_once_and_are_reused_across_lookups() -> None:
    RecordingEngine.constructed = 0
    manager = make_manager()
    await manager.startup()
    first = manager.lookup(None)
    second = manager.lookup("rec")
    assert first.engine is second.engine  # no per-request construction
    assert RecordingEngine.constructed == 1
    assert first.artifact == "rec"


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
    spec = SlotSpec(slot="default", artifact="a", load=RecordingEngine)
    with pytest.raises(ValueError, match="at least one"):
        ModelManager(slots=())
    with pytest.raises(ValueError, match="unique"):
        ModelManager(slots=(spec, SlotSpec(slot="default", artifact="b", load=RecordingEngine)))
    with pytest.raises(ValueError, match="default"):
        ModelManager(slots=(SlotSpec(slot="premium", artifact="a", load=RecordingEngine),))
