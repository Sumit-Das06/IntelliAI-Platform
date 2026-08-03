"""The metric registry: pinned identities, never-inferred facts."""

from intelliai_evaluation.metrics import (
    SPEECH_METRICS,
    MetricConfidence,
    MetricDirection,
    MetricLayer,
)

LOWER = MetricDirection.LOWER_IS_BETTER
HIGHER = MetricDirection.HIGHER_IS_BETTER


def test_registry_is_exactly_the_documented_hierarchy() -> None:
    """Golden pin of SPEECH_EVALUATION.md §3 — any drift is a conscious act."""
    expected: dict[str, tuple[MetricLayer, MetricDirection, MetricConfidence]] = {
        "round_trip_wer": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.MEDIUM),
        "pronunciation_accuracy": (MetricLayer.CORRECTNESS, HIGHER, MetricConfidence.MEDIUM),
        "clipping_ratio": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.HIGH),
        "silence_ratio": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.MEDIUM),
        "duration_plausibility": (MetricLayer.CORRECTNESS, HIGHER, MetricConfidence.MEDIUM),
        "time_to_first_audio_ms": (MetricLayer.PERFORMANCE, LOWER, MetricConfidence.HIGH),
        "synthesis_latency_ms": (MetricLayer.PERFORMANCE, LOWER, MetricConfidence.HIGH),
        "rtf": (MetricLayer.PERFORMANCE, LOWER, MetricConfidence.HIGH),
        "peak_memory_mib": (MetricLayer.PERFORMANCE, LOWER, MetricConfidence.HIGH),
        "cpu_percent_max": (MetricLayer.PERFORMANCE, LOWER, MetricConfidence.MEDIUM),
        "listening_preference": (MetricLayer.QUALITY, HIGHER, MetricConfidence.HUMAN),
        "listening_naturalness": (MetricLayer.QUALITY, HIGHER, MetricConfidence.HUMAN),
        "predicted_mos": (MetricLayer.QUALITY, HIGHER, MetricConfidence.RESERVED),
        "speaker_similarity": (MetricLayer.QUALITY, HIGHER, MetricConfidence.RESERVED),
        "voice_consistency": (MetricLayer.QUALITY, HIGHER, MetricConfidence.RESERVED),
        "emotion_preservation": (MetricLayer.QUALITY, HIGHER, MetricConfidence.RESERVED),
    }
    actual = {
        name: (spec.layer, spec.direction, spec.confidence) for name, spec in SPEECH_METRICS.items()
    }
    assert actual == expected


def test_judged_metrics_name_their_judge() -> None:
    for name in ("round_trip_wer", "pronunciation_accuracy"):
        assert SPEECH_METRICS[name].judge == "transcription"


def test_every_spec_is_self_describing() -> None:
    for spec in SPEECH_METRICS.values():
        assert spec.description
        assert spec.unit
