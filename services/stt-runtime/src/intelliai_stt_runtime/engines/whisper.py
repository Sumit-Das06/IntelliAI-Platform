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

import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from intelliai_runtime_contract import (
    RuntimeErrorType,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
)
from intelliai_runtime_core import (
    ArtifactFile,
    ArtifactSpec,
    EngineDescription,
    RuntimeServiceError,
    effective_parameters,
)
from intelliai_stt_runtime.pipeline import DecodedAudio

if TYPE_CHECKING:
    from collections.abc import Iterable

ARTIFACT_ID: Final = "whisper-small"

#: The decode knobs that describe *this engine's* behaviour for the
#: process's lifetime. `language` is excluded deliberately: it varies per
#: request, and a lifetime-stable endpoint must not report it.
#:
#: Most of these are never passed by this adapter — they are the library's
#: own defaults, and they are in force on every measurement we have ever
#: taken. Recording them is the difference between describing the measured
#: system and describing the two lines of it we happened to write.
_DECODE_KNOBS: Final = (
    "task",
    "beam_size",
    "best_of",
    "patience",
    "length_penalty",
    "temperature",
    "condition_on_previous_text",
    "compression_ratio_threshold",
    "log_prob_threshold",
    "no_speech_threshold",
    "without_timestamps",
    "word_timestamps",
    "vad_filter",
)

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

_HF_BASE_CHALLENGER: Final = "https://huggingface.co/Systran/faster-whisper-base/resolve/main"

#: The first admitted challenger (B6). Same engine family, same loader,
#: same adapter — a different checkpoint under different pinned bytes.
#: Research-hosted only: no production route resolves to it, and the
#: gateway's catalog has never heard its name. Licence: MIT, read at the
#: Systran distribution 2026-08-06 (hosting-only verification; the full
#: per-version re-verification is owed before any adoption citation).
#: model.bin sha256 is Hugging Face's own LFS object id; the small files
#: were downloaded and hashed locally at pin time.
WHISPER_BASE_FILES: Final = ArtifactSpec(
    artifact="whisper-base",
    version=1,
    files=(
        ArtifactFile(
            filename="model.bin",
            url=f"{_HF_BASE_CHALLENGER}/model.bin",
            sha256="d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9",
        ),
        ArtifactFile(
            filename="config.json",
            url=f"{_HF_BASE_CHALLENGER}/config.json",
            sha256="56a6d8110d311f19c8f0471e562832c7527f146b567275bfca59fcf7c184da9a",
        ),
        ArtifactFile(
            filename="tokenizer.json",
            url=f"{_HF_BASE_CHALLENGER}/tokenizer.json",
            sha256="fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
        ),
        ArtifactFile(
            filename="vocabulary.txt",
            url=f"{_HF_BASE_CHALLENGER}/vocabulary.txt",
            sha256="34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
        ),
    ),
)

_HF_BASE_LARGE_V3: Final = "https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main"

#: The lineage's quality-ceiling checkpoint (Stage 1, Whisper family
#: benchmark). Research-hosted only, same rules as whisper-base.
#: Licence: MIT, read at the Systran distribution 2026-08-06
#: (hosting-only verification; full re-verification owed before any
#: adoption citation). model.bin sha256 is Hugging Face's own LFS object
#: id; the small files were downloaded and hashed locally at pin time.
#: Unlike small/base, large-v3 ships `vocabulary.json` (a different
#: tokenizer generation) and `preprocessor_config.json` — the latter is
#: load-bearing: it declares feature_size=128 mel bins where earlier
#: checkpoints use 80, so omitting it would silently extract the wrong
#: features.
WHISPER_LARGE_V3_FILES: Final = ArtifactSpec(
    artifact="whisper-large-v3",
    version=1,
    files=(
        ArtifactFile(
            filename="model.bin",
            url=f"{_HF_BASE_LARGE_V3}/model.bin",
            sha256="69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1",
        ),
        ArtifactFile(
            filename="config.json",
            url=f"{_HF_BASE_LARGE_V3}/config.json",
            sha256="a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9",
        ),
        ArtifactFile(
            filename="preprocessor_config.json",
            url=f"{_HF_BASE_LARGE_V3}/preprocessor_config.json",
            sha256="7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711",
        ),
        ArtifactFile(
            filename="tokenizer.json",
            url=f"{_HF_BASE_LARGE_V3}/tokenizer.json",
            sha256="6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca",
        ),
        ArtifactFile(
            filename="vocabulary.json",
            url=f"{_HF_BASE_LARGE_V3}/vocabulary.json",
            sha256="c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1",
        ),
    ),
)

_RESEARCH_E1: Final = "https://research-artifacts.intelliai.invalid/e1/whisper-small-hi-lora-e1"

#: Milestone 15D candidate: whisper-small + Hindi LoRA (E1), merged and
#: converted to CTranslate2 float32 on this machine. Research-hosted
#: only, same rules as whisper-base. THIS ARTIFACT IS NOT DISTRIBUTED:
#: the URL uses the RFC-reserved .invalid TLD, which can never resolve
#: — by design. The store serves it from the pre-placed local cache
#: (hash-verified at every boot, like any artifact); a fresh machine
#: reproduces the bytes from the run record (base revision 973afd24 +
#: train manifest a4748dee + config + seed), never by download.
#: Provenance: ml/training run record weights/e1-hi-lora/run-record.json
#: (git 8883fa0); adapter sha256 b0b12ea9c2936020...
WHISPER_SMALL_HI_LORA_E1_FILES: Final = ArtifactSpec(
    artifact="whisper-small-hi-lora-e1",
    version=1,
    files=(
        ArtifactFile(
            filename="model.bin",
            url=f"{_RESEARCH_E1}/model.bin",
            sha256="6c0e999cc3267d58b2a38c7382cd3dd1750ffa416d3d474622548522950b0c54",
        ),
        ArtifactFile(
            filename="config.json",
            url=f"{_RESEARCH_E1}/config.json",
            sha256="364e66f09ce360358f61e549786419eedc8e6ab709186304dc77f84a3c4966c8",
        ),
        ArtifactFile(
            filename="preprocessor_config.json",
            url=f"{_RESEARCH_E1}/preprocessor_config.json",
            sha256="3e4dc53c73e7e3954fc4435034f5027733c61d7c123b38bbd1461598fd8503ef",
        ),
        ArtifactFile(
            filename="tokenizer.json",
            url=f"{_RESEARCH_E1}/tokenizer.json",
            sha256="7b469ff15eb7816315aa45eec391f5943d639b9d73d110f5c003df5192fd54e3",
        ),
        ArtifactFile(
            filename="vocabulary.json",
            url=f"{_RESEARCH_E1}/vocabulary.json",
            sha256="aa4e6188766a36f6a7f3e44db3f74823c6fee0bf33a9559247e18fedb3bc8d55",
        ),
    ),
)

#: Every artifact this engine family can host, keyed by identity. This
#: table IS the admission surface for the CTranslate2 stack: admitting
#: another checkpoint of this family is one pinned entry here — no new
#: module, no adapter change, no gateway-vocabulary edit. An artifact's
#: identity is determined by its pinned weights, which is why the table
#: maps identities to specs rather than letting a declaration invent one.
ARTIFACT_SPECS: Final[dict[str, ArtifactSpec]] = {
    spec.artifact: spec
    for spec in (
        WHISPER_SMALL_FILES,
        WHISPER_BASE_FILES,
        WHISPER_LARGE_V3_FILES,
        WHISPER_SMALL_HI_LORA_E1_FILES,
    )
}


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

    #: What this adapter explicitly passes. Everything else in
    #: `_DECODE_KNOBS` comes from the library's own signature.
    _OVERRIDES: Final = {"task": "transcribe", "vad_filter": False}

    def __init__(self, model: Any, *, compute_type: str) -> None:
        self._model = model
        self._compute_type = compute_type

    def describe(self) -> EngineDescription:
        """The configuration this engine really runs under.

        `decode_params` is read from the signature of the method about to
        be called, overlaid with this adapter's explicit overrides —
        never from a hand-maintained list of constants. That is the point:
        a faster-whisper upgrade that changes `beam_size` changes the
        measured system, and a constant would keep reporting the old value
        with no diff anywhere in this repository.
        """
        return EngineDescription(
            compute_type=self._compute_type,
            emitted_unit="word",
            decode_params=effective_parameters(
                _signature_defaults(self._model.transcribe), _DECODE_KNOBS, self._OVERRIDES
            ),
        )

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
        try:
            segments, info = self._model.transcribe(
                _to_float32(audio),
                language=request.language,
                **self._OVERRIDES,
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
    # The engine carries its own build label: a harness measuring this
    # runtime over HTTP cannot see how it was loaded, and quality binds to
    # (artifact, build) rather than to artifact alone.
    return FasterWhisperEngine(model, compute_type=compute_type)


def _signature_defaults(method: Any) -> dict[str, Any]:
    """The library's own defaults for the call we are about to make.

    Best effort by design: a future engine library that hides its
    signature behind a C extension should degrade to reporting only what
    the adapter explicitly passes, not crash a runtime at `/info`.
    """
    try:
        parameters = inspect.signature(method).parameters
    except (TypeError, ValueError):  # pragma: no cover - C-extension callables
        return {}
    return {
        name: parameter.default
        for name, parameter in parameters.items()
        if parameter.default is not inspect.Parameter.empty
    }
