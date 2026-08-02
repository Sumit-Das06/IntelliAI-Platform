"""Voice activity detection — a pipeline stage, never an engine feature.

The seam is the Protocol: today's implementation is a deterministic
energy detector (stdlib, no weights, byte-stable results on any machine);
a model-based detector (Silero-class) slots in behind the same Protocol
once the ModelManager owns weight distribution (step 5+) — zero pipeline
restructuring. Detection errs toward "speech": sending noise to an engine
costs compute; dropping speech costs a customer's words.
"""

import math
from array import array
from dataclasses import dataclass
from typing import Protocol

from intelliai_stt_runtime.pipeline.audio import CANONICAL_SAMPLE_RATE_HZ, DecodedAudio


@dataclass(frozen=True)
class SpeechRegion:
    start_seconds: float
    end_seconds: float


@dataclass(frozen=True)
class SpeechAnalysis:
    """What the pipeline learned about voice activity — annotation only;
    the pipeline never cuts audio (timestamps must stay truthful)."""

    has_speech: bool
    speech_seconds: float
    total_seconds: float
    regions: tuple[SpeechRegion, ...]

    @property
    def speech_ratio(self) -> float:
        if self.total_seconds == 0:
            return 0.0
        return self.speech_seconds / self.total_seconds


class VoiceActivityDetector(Protocol):
    def analyze(self, audio: DecodedAudio) -> SpeechAnalysis: ...


class EnergyVad:
    """Frame-energy detection over canonical PCM.

    A frame is active when its RMS clears BOTH an absolute floor (~-40
    dBFS — rejects digital silence and faint hum) and a fraction of the
    clip's own peak energy (adapts to recording level). Deterministic by
    construction: pure integer/float math over the samples.
    """

    FRAME_SECONDS = 0.03
    ABSOLUTE_RMS_FLOOR = 330.0  # ~1% of int16 full scale
    RELATIVE_TO_PEAK = 0.1
    MIN_SPEECH_SECONDS = 0.09  # three active frames

    def analyze(self, audio: DecodedAudio) -> SpeechAnalysis:
        samples = array("h")
        usable = len(audio.pcm) - (len(audio.pcm) % 2)
        samples.frombytes(audio.pcm[:usable])
        frame_length = int(CANONICAL_SAMPLE_RATE_HZ * self.FRAME_SECONDS)
        if frame_length == 0 or not samples:
            return SpeechAnalysis(
                has_speech=False,
                speech_seconds=0.0,
                total_seconds=audio.duration_seconds,
                regions=(),
            )

        rms_per_frame = [
            math.sqrt(
                sum(sample * sample for sample in samples[start : start + frame_length])
                / len(samples[start : start + frame_length])
            )
            for start in range(0, len(samples), frame_length)
        ]
        threshold = max(self.ABSOLUTE_RMS_FLOOR, self.RELATIVE_TO_PEAK * max(rms_per_frame))
        active = [rms >= threshold for rms in rms_per_frame]

        regions: list[SpeechRegion] = []
        region_start: int | None = None
        for index, is_active in enumerate([*active, False]):  # sentinel closes a trailing region
            if is_active and region_start is None:
                region_start = index
            elif not is_active and region_start is not None:
                regions.append(
                    SpeechRegion(
                        start_seconds=region_start * self.FRAME_SECONDS,
                        end_seconds=index * self.FRAME_SECONDS,
                    )
                )
                region_start = None

        speech_seconds = sum(region.end_seconds - region.start_seconds for region in regions)
        return SpeechAnalysis(
            has_speech=speech_seconds >= self.MIN_SPEECH_SECONDS,
            speech_seconds=speech_seconds,
            total_seconds=audio.duration_seconds,
            regions=tuple(regions),
        )
