"""The metric registry: pinned identities, never-inferred facts."""

import json
from pathlib import Path

import pytest

from intelliai_evaluation.bench import BenchReport
from intelliai_evaluation.bench_tts import TtsBenchReport
from intelliai_evaluation.metrics import (
    MEASURED_CONFIDENCES,
    METRIC_REGISTRY_VERSION,
    METRICS,
    DuplicateMetricError,
    MetricConfidence,
    MetricDirection,
    MetricLayer,
    MetricNotRecordableError,
    MetricNotRegisteredError,
    MetricRegistry,
    MetricSpec,
    MetricStatus,
)
from intelliai_evaluation.results import EvalRun
from intelliai_evaluation.speech_results import SpeechEvalRun
from intelliai_runtime_contract import Capability

LOWER = MetricDirection.LOWER_IS_BETTER
HIGHER = MetricDirection.HIGHER_IS_BETTER

TREES = (Path("ml/evaluation/stt"), Path("ml/evaluation/tts"))


def _spec(name: str, **overrides: object) -> MetricSpec:
    fields: dict[str, object] = {
        "name": name,
        "layer": MetricLayer.CORRECTNESS,
        "direction": LOWER,
        "unit": "ratio",
        "confidence": MetricConfidence.HIGH,
        "description": "a metric that exists only in this test",
    }
    return MetricSpec.model_validate(fields | overrides)


def test_registry_is_exactly_the_documented_hierarchy() -> None:
    """Golden pin of SPEECH_EVALUATION.md §3 — any drift is a conscious act.

    The version is pinned alongside the contents on purpose: changing what
    the registry holds means editing a test that shows you both, so a
    vocabulary change cannot be made without noticing that it is one.
    """
    assert METRIC_REGISTRY_VERSION == 2

    expected: dict[str, tuple[MetricLayer, MetricDirection, MetricConfidence]] = {
        # ── Recognition accuracy (B2, methodology §3.1) ──────────────
        "wer_ascii": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.HIGH),
        "wer_unicode": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.HIGH),
        "cer_unicode": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.HIGH),
        "substitution_rate": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.MEDIUM),
        "insertion_rate": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.MEDIUM),
        "deletion_rate": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.MEDIUM),
        "excess_word_ratio": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.MEDIUM),
        "hallucinated_words": (MetricLayer.CORRECTNESS, LOWER, MetricConfidence.HIGH),
        # ── Generation (B1, migrated unchanged from M2.5) ────────────
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
    actual = {spec.name: (spec.layer, spec.direction, spec.confidence) for spec in METRICS}
    assert actual == expected


def test_only_the_accuracy_family_has_landed() -> None:
    """B2 landed §3.1. The rest wait for the milestones that can hold them.

    None of the performance, latency, startup or resource names is
    language-aware, several are unrecordable today (the artifact store is
    untimed, no accelerator sampling exists, the contract has no streaming
    method), and `recognition_rtf` is additionally gated on
    `duration_bands@v1`. A name is permanent on first landing, so each one
    lands with the field that holds it. This test fails the day they
    arrive, which is the reminder to arrive at them deliberately.
    """
    not_yet = {
        "recognition_rtf",
        "end_to_end_latency_ms",
        "time_to_first_text_ms",
        "output_chars_per_second",
        "partial_revision_rate",
        "cold_start_ready_ms",
        "warm_restart_ready_ms",
        "model_load_ms",
        "model_warmup_ms",
        "artifact_ensure_download_ms",
        "artifact_ensure_verify_ms",
        "accelerator_memory_peak_mib",
    }
    assert not not_yet & set(METRICS.names())


def test_the_accuracy_family_is_recognition_scoped() -> None:
    # One namespace, applicability per spec. `rtf` (generation) and the
    # recognition family coexist without either being able to claim the
    # other's numbers.
    for name in ("wer_ascii", "wer_unicode", "cer_unicode", "hallucinated_words"):
        spec = METRICS.require(name)
        assert spec.applies_to(Capability.TRANSCRIPTION)
        assert not spec.applies_to(Capability.SPEECH_SYNTHESIS)


def test_bare_wer_and_cer_are_never_registered() -> None:
    # The ruler is part of a metric's identity. A bare name would be a
    # permanent invitation to average two rulers.
    assert "wer" not in METRICS
    assert "cer" not in METRICS


def test_judged_metrics_name_their_judge() -> None:
    for name in ("round_trip_wer", "pronunciation_accuracy"):
        assert METRICS.require(name).judge == "transcription"


def test_every_spec_is_self_describing() -> None:
    for spec in METRICS:
        assert spec.description
        assert spec.unit


def test_every_registered_metric_is_active() -> None:
    # Nothing has been withdrawn yet. When something is, this test is the
    # place that says so out loud rather than letting it pass unnoticed.
    assert all(spec.status is MetricStatus.ACTIVE for spec in METRICS)
    assert all(spec.superseded_by is None for spec in METRICS)


class TestNamesArePermanent:
    """Registration refuses a collision instead of resolving it silently."""

    def test_a_duplicate_name_raises_at_registration(self) -> None:
        registry = MetricRegistry(version=1)
        registry.register(_spec("wer_like"))
        with pytest.raises(DuplicateMetricError, match="already registered"):
            registry.register(_spec("wer_like", unit="percent"))

    def test_the_first_registration_survives_the_attempt(self) -> None:
        # The old dict comprehension resolved a duplicate by keeping the
        # LAST spec, silently. Whatever the policy, the failure mode was
        # that nobody found out; here the loser never lands.
        registry = MetricRegistry(version=1)
        registry.register(_spec("wer_like", unit="ratio"))
        with pytest.raises(DuplicateMetricError):
            registry.register(_spec("wer_like", unit="percent"))
        assert registry.require("wer_like").unit == "ratio"

    def test_a_live_metric_may_not_name_a_successor(self) -> None:
        registry = MetricRegistry(version=1)
        with pytest.raises(ValueError, match="supersession is what withdrawal means"):
            registry.register(_spec("still_live", superseded_by="something_else"))


class TestWithdrawnMetricsStayReadable:
    """The whole point: correcting a mistake must not break the ledger.

    `_require_registered` is a pydantic field validator, so it runs on
    every `model_validate` — every read of every committed record. If
    withdrawal deleted the name, the day we admitted a metric was wrong
    would be the day its historical evidence stopped loading.
    """

    def test_a_withdrawn_metric_is_still_registered(self) -> None:
        registry = MetricRegistry(version=1)
        registry.register(
            _spec("old_ruler", status=MetricStatus.WITHDRAWN, superseded_by="new_ruler")
        )
        assert "old_ruler" in registry
        assert registry.require("old_ruler").superseded_by == "new_ruler"

    def test_a_withdrawn_metric_cannot_be_written(self) -> None:
        registry = MetricRegistry(version=1)
        registry.register(
            _spec("old_ruler", status=MetricStatus.WITHDRAWN, superseded_by="new_ruler")
        )
        with pytest.raises(MetricNotRecordableError, match="use 'new_ruler' instead"):
            registry.assert_recordable("old_ruler")

    def test_the_read_path_never_consults_status(self) -> None:
        # Read-side questions are exactly those whose answer cannot change
        # after a record is written. Status can change; membership cannot.
        registry = MetricRegistry(version=1)
        withdrawn = registry.register(_spec("old_ruler", status=MetricStatus.WITHDRAWN))
        assert registry.get("old_ruler") is withdrawn
        assert registry.require("old_ruler") is withdrawn
        assert withdrawn.confidence in MEASURED_CONFIDENCES  # still loads into a record


class TestRecordability:
    def test_an_unregistered_name_is_refused(self) -> None:
        # `recognition_rtf` is designed and not landed: exactly the shape of
        # a name a runner might reach for before its milestone.
        with pytest.raises(MetricNotRegisteredError, match="unknown metric"):
            METRICS.assert_recordable("recognition_rtf")

    def test_a_reserved_metric_cannot_be_written(self) -> None:
        # The architecture holds its place; nothing implements it, so a
        # number under it would be a claim rather than a measurement.
        with pytest.raises(MetricNotRecordableError, match="RESERVED"):
            METRICS.assert_recordable("predicted_mos")

    def test_an_active_implemented_metric_is_writable(self) -> None:
        assert METRICS.assert_recordable("round_trip_wer").name == "round_trip_wer"

    def test_recordable_composes_the_two_axes(self) -> None:
        assert METRICS.require("round_trip_wer").recordable
        assert not METRICS.require("predicted_mos").recordable  # RESERVED
        assert not _spec("x", status=MetricStatus.WITHDRAWN).recordable


class TestCapabilityScoping:
    """One namespace, with applicability declared per spec (methodology A-0).

    Separate per-capability registries would make a name collision
    undetectable rather than merely awkward — two rulers called `rtf` in
    two namespaces never meet.
    """

    def test_a_synthesis_metric_is_refused_for_transcription(self) -> None:
        with pytest.raises(MetricNotRecordableError, match="speech_synthesis"):
            METRICS.assert_recordable("round_trip_wer", capability=Capability.TRANSCRIPTION)

    def test_a_synthesis_metric_is_accepted_for_synthesis(self) -> None:
        METRICS.assert_recordable("round_trip_wer", capability=Capability.SPEECH_SYNTHESIS)

    def test_resource_metrics_are_capability_generic(self) -> None:
        # They measure a process, not a modality, so every future family
        # reuses them unchanged rather than minting a parallel name.
        for name in ("peak_memory_mib", "cpu_percent_max"):
            spec = METRICS.require(name)
            assert spec.capabilities == ()
            for capability in Capability:
                assert spec.applies_to(capability)

    def test_capability_is_optional_so_existing_callers_are_unaffected(self) -> None:
        METRICS.assert_recordable("round_trip_wer")


def _committed_records() -> list[Path]:
    return sorted(
        path
        for tree in TREES
        for directory in ("results", "benchmarks")
        for path in (tree / directory).glob("*.json")
    )


def test_there_are_committed_records_to_check() -> None:
    # A guard on the guard: the checks below would pass vacuously if the
    # ledger were ever empty or moved.
    assert _committed_records()


@pytest.mark.parametrize("path", _committed_records(), ids=lambda p: p.name)
def test_every_metric_name_in_the_ledger_still_resolves(path: Path) -> None:
    """The append-only ledger stays readable, checked against the ledger.

    Records cite metric names by string. If a name ever leaves the
    registry, the record that cites it becomes unloadable — so this walks
    what we actually committed rather than trusting that nobody will.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    cited: set[str] = set()
    for key in ("aggregate_metrics", "metrics"):
        section = document.get(key)
        if isinstance(section, dict):
            cited |= set(section)
    for case in document.get("cases") or []:
        if isinstance(case.get("metrics"), dict):
            cited |= set(case["metrics"])

    unknown = sorted(name for name in cited if name not in METRICS)
    assert not unknown, (
        f"{path.name} cites {unknown}, which the registry no longer holds. "
        "Metrics are WITHDRAWN, never deleted — a deleted name makes every "
        "record citing it permanently unloadable."
    )


@pytest.mark.parametrize("path", _committed_records(), ids=lambda p: p.name)
def test_every_committed_record_still_parses(path: Path) -> None:
    """Both evidence roots, read through the validators that gate them.

    This is the check the whole withdrawal design exists to keep true:
    `_require_registered` is a field validator, so loading a record runs
    the registry over every metric name it cites. If a name ever stopped
    resolving, this is where it would surface — before a reader who needed
    that evidence found out the hard way.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    if "cases" in document:  # generation evidence
        assert SpeechEvalRun.model_validate(document).cases
    elif "clips" in document:  # recognition evidence
        assert EvalRun.model_validate(document).clips
    elif "clip" in document:  # recognition production ladder
        assert BenchReport.model_validate(document).levels
    else:  # generation production ladder
        assert TtsBenchReport.model_validate(document).levels
