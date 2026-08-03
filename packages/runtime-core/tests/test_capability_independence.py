"""The proof the extraction exists for: lifecycle is capability-agnostic.

Step 1 proved the move changed nothing for STT. THIS suite proves the
claim behind the move: engines with deliberately alien inference surfaces
— a synthesis-shaped fake whose only method is ``speak(text) -> bytes``,
a vision-shaped fake with ``describe(pixels) -> str`` — flow through
ModelManager, ArtifactStore, and WorkerPool without a single source
change. The fakes contain no AI logic; their entire job is to be shaped
wrong for transcription. The machinery must not notice.
"""

import hashlib
from pathlib import Path

import httpx
import pytest

from intelliai_runtime_core import (
    ArtifactFile,
    ArtifactSpec,
    ArtifactStore,
    ModelManager,
    SlotSpec,
    WorkerPool,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeSynthesisEngine:
    """Text in, bytes out — the inverse of transcription's shape."""

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.closed = 0

    def speak(self, text: str) -> bytes:
        self.spoken.append(text)
        return text.encode("utf-16-le")  # deterministic fake "audio"

    def close(self) -> None:
        self.closed += 1


class FakeVisionEngine:
    """Pixels in, text out — a third shape, sharing nothing with the others."""

    def __init__(self) -> None:
        self.described: list[bytes] = []
        self.closed = 0

    def describe(self, pixels: bytes) -> str:
        self.described.append(pixels)
        return f"{len(pixels)} bytes of image"

    def close(self) -> None:
        self.closed += 1


def synthesis_warm_up(engine: FakeSynthesisEngine) -> None:
    """What probing means is the capability's business — here, speaking."""
    engine.speak("warm-up")


def vision_warm_up(engine: FakeVisionEngine) -> None:
    engine.describe(b"\x00" * 16)


@pytest.mark.anyio
async def test_full_lifecycle_for_a_synthesis_shaped_engine() -> None:
    """ensure->load->warm->ready->serve->shutdown, no transcription anywhere."""
    manager = ModelManager(
        slots=(
            SlotSpec(slot="default", artifact="fake-tts", load=lambda _: FakeSynthesisEngine()),
        ),
        warm_up=synthesis_warm_up,
    )
    assert manager.started is False  # readiness: not before startup
    await manager.startup()
    assert manager.started is True

    loaded = manager.lookup(None)
    assert loaded.artifact == "fake-tts"
    assert loaded.engine.spoken == ["warm-up"]  # the injected probe, verbatim
    assert loaded.load_ms >= 0
    assert loaded.warmup_ms >= 0  # startup cost measured, capability unknown

    # Serving uses the engine's own alien surface; the manager never calls it.
    audio = loaded.engine.speak("hello world")
    assert audio == "hello world".encode("utf-16-le")

    engine = loaded.engine
    await manager.shutdown()
    assert engine.closed == 1  # close() is the ONLY method lifecycle touches
    assert manager.started is False


@pytest.mark.anyio
async def test_two_capabilities_run_side_by_side_on_the_same_machinery() -> None:
    """One ModelManager class, N capabilities: each with its own engine
    shape and its own probe meaning, zero shared state, zero source edits."""
    synthesis = ModelManager(
        slots=(
            SlotSpec(slot="default", artifact="fake-tts", load=lambda _: FakeSynthesisEngine()),
        ),
        warm_up=synthesis_warm_up,
    )
    vision = ModelManager(
        slots=(SlotSpec(slot="default", artifact="fake-ocr", load=lambda _: FakeVisionEngine()),),
        warm_up=vision_warm_up,
    )
    await synthesis.startup()
    await vision.startup()

    assert synthesis.lookup(None).engine.spoken == ["warm-up"]
    assert vision.lookup(None).engine.described == [b"\x00" * 16]

    await synthesis.shutdown()
    assert vision.started is True  # lifecycles are independent
    await vision.shutdown()


def test_store_verifies_voice_pack_shaped_artifacts_identically(tmp_path: Path) -> None:
    """A multi-file artifact (weights + a voice-pack-like asset) is just
    pinned bytes to the store — it verifies content, never meaning."""
    weights, voices = b"fake weights " * 50, b"fake voice pack " * 50

    class TwoFileTransport(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            body = weights if "model.bin" in str(request.url) else voices
            return httpx.Response(200, content=body)

    spec = ArtifactSpec(
        artifact="fake-tts",
        version=1,
        files=(
            ArtifactFile(
                filename="model.bin",
                url="https://x.example/model.bin",
                sha256=hashlib.sha256(weights).hexdigest(),
            ),
            ArtifactFile(
                filename="voices.bin",
                url="https://x.example/voices.bin",
                sha256=hashlib.sha256(voices).hexdigest(),
            ),
        ),
    )
    store = ArtifactStore(tmp_path, client=httpx.Client(transport=TwoFileTransport()))
    target = store.ensure(spec)
    assert (target / "model.bin").read_bytes() == weights
    assert (target / "voices.bin").read_bytes() == voices


@pytest.mark.anyio
async def test_pool_executes_synthesis_shaped_work_unchanged() -> None:
    """The pool runs opaque callables; bytes-producing work is no different."""
    engine = FakeSynthesisEngine()
    pool = WorkerPool(max_concurrency=1, max_queue=0)
    try:
        result = await pool.run(lambda: engine.speak("bounded admission"))
        assert result == "bounded admission".encode("utf-16-le")
    finally:
        pool.shutdown()
