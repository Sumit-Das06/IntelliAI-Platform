"""The media pipeline: six stages, one responsibility each, every one timed.

    validate -> detect -> decode -> normalize -> vad -> (handoff)

Handoff is the caller's stage: the pipeline returns `PipelineOutput` and
the capability layer decides what meets the engine — which is what keeps
this subsystem reusable by any future speech capability (translation,
diarization, keyword spotting, voice agents): none of its stages know
what a transcript is.

Failure philosophy (decided before implementation, ADR-0016 taxonomy):
- empty/oversized/overlong input, unrecognized container, corrupted file,
  unsupported codec, decode timeout -> ``invalid_input`` (the request's
  fault; identical retries fail identically).
- missing/broken ffmpeg -> ``internal`` — and startup verification makes
  this a deploy failure, not a request failure.
- no speech after VAD -> NOT an error: the caller returns an empty
  transcript without invoking an engine. Silence has a correct answer.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError
from intelliai_stt_runtime.pipeline.audio import DecodedAudio, canonical_audio
from intelliai_stt_runtime.pipeline.detect import MediaFormat, detect_format
from intelliai_stt_runtime.pipeline.ffmpeg import FfmpegDecoder
from intelliai_stt_runtime.pipeline.vad import SpeechAnalysis, VoiceActivityDetector


@dataclass(frozen=True)
class PipelineOutput:
    """Everything ingestion learned: canonical audio, speech facts, evidence."""

    audio: DecodedAudio
    speech: SpeechAnalysis
    media_format: MediaFormat
    timings_ms: dict[str, float]


class MediaPipeline:
    """Permanent, engine-independent ingestion subsystem."""

    def __init__(
        self,
        decoder: FfmpegDecoder,
        vad: VoiceActivityDetector,
        *,
        max_upload_bytes: int,
        max_audio_seconds: float,
    ) -> None:
        self._decoder = decoder
        self._vad = vad
        self._max_upload_bytes = max_upload_bytes
        self._max_audio_seconds = max_audio_seconds

    def verify(self) -> None:
        """Startup gate: refuse to serve without a working decoder."""
        self._decoder.verify()

    def process(self, payload: bytes) -> PipelineOutput:
        """Run stages 1-5. Blocking by design — callers run it off the loop."""
        timings: dict[str, float] = {}

        def timed[T](stage: str, run: Callable[[], T]) -> T:
            started = time.perf_counter()
            result = run()
            timings[stage] = (time.perf_counter() - started) * 1000.0
            return result

        timed("validate", lambda: self._validate(payload))
        media_format = timed("detect", lambda: detect_format(payload))
        pcm = timed("decode", lambda: self._decoder.decode_to_canonical(payload))
        audio = timed("normalize", lambda: self._normalize(pcm))
        speech = timed("vad", lambda: self._vad.analyze(audio))
        return PipelineOutput(
            audio=audio, speech=speech, media_format=media_format, timings_ms=timings
        )

    def _validate(self, payload: bytes) -> None:
        if not payload:
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT, "audio file is empty", param="file"
            )
        if len(payload) > self._max_upload_bytes:
            limit_mb = self._max_upload_bytes / (1024 * 1024)
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                f"audio file exceeds the {limit_mb:.0f} MB limit",
                param="file",
            )

    def _normalize(self, pcm: bytes) -> DecodedAudio:
        audio = canonical_audio(pcm)
        if audio.duration_seconds > self._max_audio_seconds:
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                f"audio exceeds the {self._max_audio_seconds:.0f}s duration limit",
                param="file",
            )
        return audio
