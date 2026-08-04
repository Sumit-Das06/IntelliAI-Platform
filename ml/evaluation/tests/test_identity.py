"""Evaluation identity: what a measurement is about, and what it is not."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from intelliai_evaluation.identity import EvaluationIdentity, EvaluationJudge, SliceCoverage

RUN_AT = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def identity(**over: object) -> EvaluationIdentity:
    fields: dict[str, object] = {
        "public_model": "intelliai-stt",
        "language": "hi",
        "artifact": "whisper-small",
        "artifact_version": 1,
        "build": "cpu-int8",
        "deployment": "stt-runtime",
        "dataset": "stt-eval-seed",
        "dataset_version": 2,
        "run_at": RUN_AT,
    }
    fields.update(over)
    return EvaluationIdentity.model_validate(fields)


class TestIdentityCompleteness:
    def test_it_names_every_thing_a_future_reader_cannot_reconstruct(self) -> None:
        # The registry will have moved on; the record must not depend on it.
        required = {
            "public_model",
            "language",
            "artifact",
            "artifact_version",
            "build",
            "deployment",
            "dataset",
            "dataset_version",
            "benchmark",
            "judge",
            "run_at",
        }
        assert set(EvaluationIdentity.model_fields) == required

    def test_the_citation_form_is_the_full_slice(self) -> None:
        assert identity().slug == ("intelliai-stt/hi/whisper-small@1/cpu-int8/stt-eval-seed@v2")

    def test_quality_binds_to_artifact_and_build_not_artifact_alone(self) -> None:
        # A quantized build is the same identity and not necessarily the
        # same behaviour, so two builds are two slices.
        assert identity(build="cpu-int8").slug != identity(build="cpu-float32").slug

    def test_records_are_frozen(self) -> None:
        record = identity()
        with pytest.raises(ValidationError):
            record.language = "en"  # type: ignore[misc]

    def test_a_run_is_not_a_benchmark_unless_it_was_named_one(self) -> None:
        assert identity().benchmark is None
        assert identity(benchmark="2026-08-05-x").benchmark == "2026-08-05-x"

    def test_transcription_has_no_model_judge(self) -> None:
        # The dataset's reference text judged it; `dataset@version` says so.
        assert identity().judge is None

    def test_a_judging_model_is_itself_a_versioned_artifact(self) -> None:
        judged = identity(
            judge=EvaluationJudge(
                artifact="whisper-small", artifact_version=1, runtime_version="0.1.0"
            )
        )
        assert judged.judge is not None
        assert judged.judge.artifact_version == 1


class TestReproduction:
    def test_every_input_comes_from_a_record(self) -> None:
        inputs = identity().reproduction()
        assert inputs == {
            "model": "intelliai-stt",
            "language": "hi",
            "dataset": "stt-eval-seed@v2",
            "artifact": "whisper-small@v1",
            "build": "cpu-int8",
            "deployment": "stt-runtime",
        }

    def test_nothing_in_it_is_a_filename_or_a_url(self) -> None:
        # Paths move; identities do not. A reproduction that needs a path
        # needs someone to remember where the file went.
        for value in identity().reproduction().values():
            assert "/" not in value.replace("intelliai-stt/", "")
            assert "\\" not in value
            assert "http" not in value


class TestSliceCoverage:
    def test_a_slice_without_natural_speech_is_not_a_quality_claim(self) -> None:
        hindi = SliceCoverage(clips=2, natural_speech_clips=0, probe_clips=2, reference_words=0)
        assert hindi.supports_word_error_rate is False
        assert hindi.is_quality_claim is False

    def test_a_slice_with_natural_speech_and_references_is(self) -> None:
        english = SliceCoverage(clips=4, natural_speech_clips=2, probe_clips=2, reference_words=44)
        assert english.is_quality_claim is True

    def test_natural_speech_without_references_still_is_not(self) -> None:
        # Audio nobody transcribed cannot produce a word error rate.
        odd = SliceCoverage(clips=1, natural_speech_clips=1, probe_clips=0, reference_words=0)
        assert odd.is_quality_claim is False
