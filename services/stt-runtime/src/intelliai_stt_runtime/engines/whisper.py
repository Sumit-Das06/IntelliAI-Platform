"""FasterWhisperEngine — the platform's FIRST foundation model, not its last.

Everything model-specific lives in this one module: the pinned artifact
files, the faster-whisper import (lazy — the library is an optional
extra, absent from CI and from every non-engine module), the PCM->float32
conversion, and the segment-shape adaptation. Replacing this engine with
a fine-tuned IntelliAI STT artifact means: new pinned spec + new loader
behind the same `TranscriptionEngine` protocol. Nothing else on the
platform changes — that is the design being proven here.

Precision is a BUILD concern (ADR-0015): the artifact is float32 weights;
int8 is applied at load time via compute_type, configured by deployment,
never part of identity.

License verdict for this artifact version: MIT, verified 2026-07-31 at the
served distribution (registry catalog carries the normative record). The
model.bin SHA-256 below was verified against Hugging Face's own LFS
object metadata at pin time (2026-08-02).
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from intelliai_runtime_contract import (
    RuntimeErrorType,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
)
from intelliai_runtime_core import ArtifactFile, ArtifactSpec, RuntimeServiceError
from intelliai_stt_runtime.pipeline import DecodedAudio

if TYPE_CHECKING:
    from collections.abc import Iterable

ARTIFACT_ID: Final = "whisper-small"

_HF_BASE: Final = "https://huggingface.co/Systran/faster-whisper-small/resolve/main"

WHISPER_SMALL_FILES: Final = ArtifactSpec(
    artifact=ARTIFACT_ID,
    version=1,
    files=(
        ArtifactFile(
            filename="model.bin",
            url=f"{_HF_BASE}/model.bin",
            sha256="3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
        ),
        ArtifactFile(
            filename="config.json",
            url=f"{_HF_BASE}/config.json",
            sha256="b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828",
        ),
        ArtifactFile(
            filename="tokenizer.json",
            url=f"{_HF_BASE}/tokenizer.json",
            sha256="fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
        ),
        ArtifactFile(
            filename="vocabulary.txt",
            url=f"{_HF_BASE}/vocabulary.txt",
            sha256="34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
        ),
    ),
)


def _to_float32(audio: DecodedAudio) -> Any:
    """Canonical s16le PCM -> the float32 waveform faster-whisper expects."""
    import numpy  # engine-only dependency, via the `whisper` extra

    samples = numpy.frombuffer(audio.pcm, dtype=numpy.int16)
    return samples.astype(numpy.float32) / 32768.0


def convert_segments(
    segments: "Iterable[Any]",
    detected_language: str | None,
    audio: DecodedAudio,
) -> TranscriptionResult:
    """Engine-shape -> contract-shape. Pure adaptation, unit-testable
    without the library (segments only need .start/.end/.text)."""
    converted: list[TranscriptionSegment] = []
    texts: list[str] = []
    for segment in segments:
        text = str(segment.text).strip()
        if not text:
            continue
        converted.append(
            TranscriptionSegment(
                start_seconds=max(0.0, float(segment.start)),
                end_seconds=max(0.0, float(segment.end)),
                text=text,
            )
        )
        texts.append(text)
    return TranscriptionResult(
        text=" ".join(texts),
        language=detected_language or "und",
        duration_seconds=audio.duration_seconds,
        segments=tuple(converted),
    )


class FasterWhisperEngine:
    """Thin adapter: one loaded WhisperModel, stateless beyond it."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
        try:
            segments, info = self._model.transcribe(
                _to_float32(audio),
                language=request.language,
                task="transcribe",
                vad_filter=False,  # VAD is the pipeline's job, never the engine's
            )
        except ValueError as exc:
            # An adapter's job is contract-shaped params in, contract-shaped
            # results out — including when the engine says no. A language
            # this model does not have is the caller's mistake, and letting
            # the library's ValueError escape turned it into a 500 (found
            # in M5 step 7 production validation, on `hi-IN`).
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                f"language {request.language!r} is not served by this artifact",
                param="language",
            ) from exc
        return convert_segments(segments, getattr(info, "language", None), audio)

    def close(self) -> None:
        self._model = None  # CTranslate2 frees on release


def load_faster_whisper(
    local_dir: Path | None, *, compute_type: str = "int8"
) -> FasterWhisperEngine:
    """Slot loader: verified artifact directory -> a loaded engine.

    The faster-whisper import lives here and only here. compute_type is
    the deployment's precision choice (ADR-0015) applied to the float32
    artifact at load time.
    """
    if local_dir is None:
        msg = "faster-whisper requires a verified artifact directory"
        raise ValueError(msg)
    # The ONE import site (untyped optional extra; mypy override in the
    # root pyproject — absent in CI, installed where the engine runs).
    from faster_whisper import WhisperModel

    model = WhisperModel(str(local_dir), device="cpu", compute_type=compute_type)
    return FasterWhisperEngine(model)
