"""The metric registry — every metric's identity card, declared not inferred.

SPEECH_EVALUATION.md §3 made the rule; this module makes it mechanical:
a metric exists only as a registered `MetricSpec` carrying its layer,
direction, unit, confidence, and judge dependency. Dashboards, promotion
gates, and result records read these facts — they never guess. Reserved
(future) metrics are registered too: the architecture holds their place,
and a golden test pins the whole registry so any change is a conscious,
reviewed act.
"""

from enum import StrEnum, unique

from pydantic import BaseModel, ConfigDict, Field


@unique
class MetricLayer(StrEnum):
    CORRECTNESS = "correctness"  # did it produce the requested speech?
    PERFORMANCE = "performance"  # fast and cheap enough to serve?
    QUALITY = "quality"  # did it sound like high-quality speech?


@unique
class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


@unique
class MetricConfidence(StrEnum):
    HIGH = "high"  # objective, deterministic
    MEDIUM = "medium"  # objective but approximate (heuristics, judge-dependent)
    HUMAN = "human"  # structured subjective judgment
    RESERVED = "reserved"  # future capability; place held, nothing implemented


class MetricSpec(BaseModel):
    """One metric's permanent identity."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    layer: MetricLayer
    direction: MetricDirection
    unit: str = Field(min_length=1)
    confidence: MetricConfidence
    judge: str | None = None  # capability that judges it (e.g. "transcription")
    description: str = Field(min_length=1)


_HIGHER = MetricDirection.HIGHER_IS_BETTER
_LOWER = MetricDirection.LOWER_IS_BETTER

SPEECH_METRICS: dict[str, MetricSpec] = {
    spec.name: spec
    for spec in (
        # ── Correctness (automated) ─────────────────────────────────────
        MetricSpec(
            name="round_trip_wer",
            layer=MetricLayer.CORRECTNESS,
            direction=_LOWER,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            judge="transcription",
            description="WER of the judge STT's transcript against the input text.",
        ),
        MetricSpec(
            name="pronunciation_accuracy",
            layer=MetricLayer.CORRECTNESS,
            direction=_HIGHER,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            judge="transcription",
            description="Fraction of trap words surviving the round trip.",
        ),
        MetricSpec(
            name="clipping_ratio",
            layer=MetricLayer.CORRECTNESS,
            direction=_LOWER,
            unit="ratio",
            confidence=MetricConfidence.HIGH,
            description="Samples at digital full scale over total samples.",
        ),
        MetricSpec(
            name="silence_ratio",
            layer=MetricLayer.CORRECTNESS,
            direction=_LOWER,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            description="Low-energy frames over total frames (threshold heuristic).",
        ),
        MetricSpec(
            name="duration_plausibility",
            layer=MetricLayer.CORRECTNESS,
            direction=_HIGHER,
            unit="score",
            confidence=MetricConfidence.MEDIUM,
            description="1.0 when speaking rate falls in a plausible band, else 0.0.",
        ),
        # ── Performance (automated; measured by the runner/bench) ───────
        MetricSpec(
            name="time_to_first_audio_ms",
            layer=MetricLayer.PERFORMANCE,
            direction=_LOWER,
            unit="ms",
            confidence=MetricConfidence.HIGH,
            description="Request start to first audio byte on the serving path.",
        ),
        MetricSpec(
            name="synthesis_latency_ms",
            layer=MetricLayer.PERFORMANCE,
            direction=_LOWER,
            unit="ms",
            confidence=MetricConfidence.HIGH,
            description="Total synthesis request wall time.",
        ),
        MetricSpec(
            name="rtf",
            layer=MetricLayer.PERFORMANCE,
            direction=_LOWER,
            unit="ratio",
            confidence=MetricConfidence.HIGH,
            description="Synthesis time over produced audio duration.",
        ),
        MetricSpec(
            name="peak_memory_mib",
            layer=MetricLayer.PERFORMANCE,
            direction=_LOWER,
            unit="MiB",
            confidence=MetricConfidence.HIGH,
            description="Peak container memory during evaluation.",
        ),
        MetricSpec(
            name="cpu_percent_max",
            layer=MetricLayer.PERFORMANCE,
            direction=_LOWER,
            unit="percent",
            confidence=MetricConfidence.MEDIUM,
            description="Max sampled container CPU (docker stats lag applies).",
        ),
        # ── Quality (human) ─────────────────────────────────────────────
        MetricSpec(
            name="listening_preference",
            layer=MetricLayer.QUALITY,
            direction=_HIGHER,
            unit="win_rate",
            confidence=MetricConfidence.HUMAN,
            description="Anchored A/B win rate from the listening protocol.",
        ),
        MetricSpec(
            name="listening_naturalness",
            layer=MetricLayer.QUALITY,
            direction=_HIGHER,
            unit="score_1_5",
            confidence=MetricConfidence.HUMAN,
            description="Naturalness on the fixed 1-5 sheet; n recorded.",
        ),
        # ── Reserved (architecture holds the slot; nothing implemented) ──
        MetricSpec(
            name="predicted_mos",
            layer=MetricLayer.QUALITY,
            direction=_HIGHER,
            unit="score_1_5",
            confidence=MetricConfidence.RESERVED,
            description="Model-based naturalness prediction (adoption-gated).",
        ),
        MetricSpec(
            name="speaker_similarity",
            layer=MetricLayer.QUALITY,
            direction=_HIGHER,
            unit="ratio",
            confidence=MetricConfidence.RESERVED,
            description="Cloned-voice similarity to reference (cloning capability).",
        ),
        MetricSpec(
            name="voice_consistency",
            layer=MetricLayer.QUALITY,
            direction=_HIGHER,
            unit="ratio",
            confidence=MetricConfidence.RESERVED,
            description="Voice identity stability across utterances.",
        ),
        MetricSpec(
            name="emotion_preservation",
            layer=MetricLayer.QUALITY,
            direction=_HIGHER,
            unit="ratio",
            confidence=MetricConfidence.RESERVED,
            description="Expressive/emotional fidelity (S2ST, expressive TTS).",
        ),
    )
}
