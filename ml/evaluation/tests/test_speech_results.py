"""SpeechEvalRun: the evidence laws, enforced by the schema itself."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from intelliai_evaluation.speech_results import (
    METHODOLOGY_VERSION,
    CaseResult,
    ComparisonContext,
    EvaluatedArtifact,
    HumanEvaluation,
    JudgeIdentity,
    RuntimeIdentity,
    SpeechEvalRun,
)

EVALUATED = EvaluatedArtifact(artifact="test-voice", version=1, lineage="test-family")
JUDGE = JudgeIdentity(
    capability="transcription", artifact="whisper-small", version=1, runtime_version="0.1.0"
)
RUNTIME = RuntimeIdentity(service="tts-runtime", service_version="0.1.0")


def case_result(**overrides: object) -> CaseResult:
    fields: dict[str, object] = {
        "case_id": "en-general-01",
        "transcript": "the quick brown fox",
        "metrics": {"round_trip_wer": 0.0, "pronunciation_accuracy": 1.0},
    }
    fields.update(overrides)
    return CaseResult.model_validate(fields)


def run(**overrides: object) -> SpeechEvalRun:
    fields: dict[str, object] = {
        "corpus_name": "tts-eval-seed",
        "corpus_version": 1,
        "methodology_version": METHODOLOGY_VERSION,
        "evaluated": EVALUATED,
        "judge": JUDGE,
        "runtime": RUNTIME,
        "hardware": "test machine",
        "run_at": datetime(2026, 8, 3, tzinfo=UTC),
        "cases": (case_result(),),
        "aggregate_metrics": {"round_trip_wer": 0.0, "rtf": 0.2},
    }
    fields.update(overrides)
    return SpeechEvalRun.model_validate(fields)


class TestRegistryIntegration:
    def test_free_form_metric_names_never_enter_the_ledger(self) -> None:
        with pytest.raises(ValidationError, match="unknown metric"):
            case_result(metrics={"vibes": 10.0})
        with pytest.raises(ValidationError, match="unknown metric"):
            run(aggregate_metrics={"speed_feeling": 1.0})

    def test_reserved_metrics_cannot_be_recorded(self) -> None:
        with pytest.raises(ValidationError, match="does not belong"):
            run(aggregate_metrics={"predicted_mos": 4.2})


class TestEvidenceSeparation:
    def test_human_metrics_rejected_from_measured_sections(self) -> None:
        with pytest.raises(ValidationError, match="does not belong"):
            case_result(metrics={"listening_naturalness": 4.0})

    def test_measured_metrics_rejected_from_human_scores(self) -> None:
        with pytest.raises(ValidationError, match="does not belong"):
            HumanEvaluation(
                protocol="founder-listening-v1",
                listeners=1,
                scores={"round_trip_wer": 0.1},
            )

    def test_human_evidence_is_welcome_in_its_own_structure(self) -> None:
        human = HumanEvaluation(
            protocol="founder-listening-v1",
            listeners=1,
            scores={"listening_naturalness": 4.0, "listening_preference": 0.75},
            notes="slight robotic prosody on long sentences",
        )
        assert run(human=human).human is not None


class TestReproducibilityCompleteness:
    @pytest.mark.parametrize(
        "missing",
        ["corpus_version", "methodology_version", "evaluated", "judge", "runtime", "hardware"],
    )
    def test_underspecified_benchmarks_are_unconstructible(self, missing: str) -> None:
        fields = {
            "corpus_name": "tts-eval-seed",
            "corpus_version": 1,
            "methodology_version": METHODOLOGY_VERSION,
            "evaluated": EVALUATED,
            "judge": JUDGE,
            "runtime": RUNTIME,
            "hardware": "test machine",
            "run_at": datetime(2026, 8, 3, tzinfo=UTC),
            "cases": (case_result(),),
            "aggregate_metrics": {},
        }
        del fields[missing]
        with pytest.raises(ValidationError):
            SpeechEvalRun.model_validate(fields)

    def test_at_least_one_case_required(self) -> None:
        with pytest.raises(ValidationError):
            run(cases=())


class TestImmutabilityAndSelfContainment:
    def test_records_are_frozen(self) -> None:
        record = run()
        with pytest.raises(ValidationError):
            record.hardware = "different machine"  # type: ignore[misc]

    def test_transcripts_are_kept_verbatim_including_empty(self) -> None:
        assert case_result(transcript="").transcript == ""

    def test_json_round_trip(self) -> None:
        record = run(
            synthesis_params={"voice": "test-voice-a", "speed": "1.0"},
            comparison=ComparisonContext(benchmark_group="tts-baselines"),
        )
        parsed = SpeechEvalRun.model_validate_json(record.model_dump_json())
        assert parsed == record
        assert parsed.comparison is not None
        assert parsed.comparison.compared_against is None  # reserved, unused


def test_methodology_version_is_pinned() -> None:
    assert METHODOLOGY_VERSION == 1
