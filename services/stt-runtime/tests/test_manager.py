"""ModelManager lifecycle: ensure once, load once, warm once, reuse always."""

from pathlib import Path

import pytest

from intelliai_runtime_contract import RuntimeErrorType, TranscriptionRequest, TranscriptionResult
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.manager import ModelManager, SlotSpec
from intelliai_stt_runtime.pipeline import DecodedAudio


class RecordingEngine:
    """Counts constructions, transcriptions, and closes: lifecycle is provable."""

    constructed = 0

    def __init__(self) -> None:
        type(self).constructed += 1
        self.transcribe_calls = 0
        self.closed = 0

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
        self.transcribe_calls += 1
        return TranscriptionResult(text="x", language="und", duration_seconds=0.0)

    def close(self) -> None:
        self.closed += 1


def load_recording(_: Path | None) -> RecordingEngine:
    return RecordingEngine()


def make_manager() -> ModelManager:
    return ModelManager(slots=(SlotSpec(slot="default", artifact="rec", load=load_recording),))


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
    # Warm-up ran exactly one inference before any request could.
    assert first.engine.transcribe_calls == 1
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
        ModelManager(slots=())
    with pytest.raises(ValueError, match="unique"):
        ModelManager(slots=(spec, SlotSpec(slot="default", artifact="b", load=load_recording)))
    with pytest.raises(ValueError, match="default"):
        ModelManager(slots=(SlotSpec(slot="premium", artifact="a", load=load_recording),))


def test_slots_with_files_require_a_store() -> None:
    from intelliai_stt_runtime.manager import ArtifactFile, ArtifactSpec

    files = ArtifactSpec(
        artifact="a",
        version=1,
        files=(ArtifactFile(filename="m.bin", url="https://x.example/m.bin", sha256="0" * 64),),
    )
    with pytest.raises(ValueError, match="ArtifactStore"):
        ModelManager(
            slots=(SlotSpec(slot="default", artifact="a", load=load_recording, files=files),)
        )
