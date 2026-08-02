"""Media ingestion — a permanent subsystem, independent of every engine.

Any supported container in, canonical audio (16 kHz mono s16le PCM) +
speech analysis out, with per-stage timing evidence. Engines receive only
`DecodedAudio`; they never learn what a format, codec, or VAD is. The
subsystem is capability-agnostic by design — future speech capabilities
(translation, diarization, keyword spotting, voice agents) reuse it as
is; it extracts to a shared package when a second speech runtime exists.
"""

from intelliai_stt_runtime.pipeline.audio import (
    CANONICAL_SAMPLE_RATE_HZ,
    DecodedAudio,
    canonical_audio,
)
from intelliai_stt_runtime.pipeline.detect import MediaFormat, detect_format
from intelliai_stt_runtime.pipeline.ffmpeg import FfmpegDecoder
from intelliai_stt_runtime.pipeline.pipeline import MediaPipeline, PipelineOutput
from intelliai_stt_runtime.pipeline.vad import (
    EnergyVad,
    SpeechAnalysis,
    SpeechRegion,
    VoiceActivityDetector,
)

__all__ = [
    "CANONICAL_SAMPLE_RATE_HZ",
    "DecodedAudio",
    "EnergyVad",
    "FfmpegDecoder",
    "MediaFormat",
    "MediaPipeline",
    "PipelineOutput",
    "SpeechAnalysis",
    "SpeechRegion",
    "VoiceActivityDetector",
    "canonical_audio",
    "detect_format",
]
