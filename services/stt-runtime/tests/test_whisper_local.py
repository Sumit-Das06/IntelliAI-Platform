"""Local real-model tier: the actual whisper-small, end to end.

Opt-in (INTELLIAI_RUN_LOCAL_MODEL_TESTS=1): downloads/verifies ~480 MB of
weights and needs the `whisper` extra installed. CI never runs this —
CI proves the architecture with the ReferenceEngine; THIS tier proves the
foundation model, on demand, on real hardware.
"""

import os
from pathlib import Path

import pytest

from intelliai_runtime_contract import TranscriptionRequest

pytestmark = pytest.mark.skipif(
    os.environ.get("INTELLIAI_RUN_LOCAL_MODEL_TESTS") != "1",
    reason="local model tier: set INTELLIAI_RUN_LOCAL_MODEL_TESTS=1 (downloads weights)",
)


def test_whisper_small_transcribes_real_speech() -> None:
    import httpx

    from intelliai_runtime_core import ArtifactStore
    from intelliai_stt_runtime.engines.whisper import WHISPER_SMALL_FILES, load_faster_whisper
    from intelliai_stt_runtime.pipeline import EnergyVad, FfmpegDecoder, MediaPipeline

    store = ArtifactStore(Path("models"))
    local_dir = store.ensure(WHISPER_SMALL_FILES)
    engine = load_faster_whisper(local_dir)

    jfk = httpx.get(
        "https://github.com/openai/whisper/raw/v20250625/tests/jfk.flac",
        follow_redirects=True,
        timeout=60,
    ).content
    pipeline = MediaPipeline(
        FfmpegDecoder("ffmpeg", 30.0),
        EnergyVad(),
        max_upload_bytes=25 * 1024 * 1024,
        max_audio_seconds=600.0,
    )
    output = pipeline.process(jfk)
    result = engine.transcribe(output.audio, TranscriptionRequest(language="en"))
    engine.close()

    lowered = result.text.lower()
    assert "ask not what your country can do for you" in lowered
    assert result.language == "en"
    assert result.segments
