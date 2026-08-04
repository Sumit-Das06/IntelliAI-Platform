"""The promotion bars: what evidence has to show before a route may move."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from intelliai_evaluation.dataset import find_dataset, load_dataset
from intelliai_evaluation.identity import EvaluationIdentity, EvaluationJudge, SliceCoverage
from intelliai_evaluation.promotion import (
    PromotionClass,
    Verdict,
    enablement_test,
    switching_test,
)
from intelliai_evaluation.results import ClipResult, EvalRun

DATASETS = Path("ml/evaluation/stt/datasets")
RESULTS = Path("ml/evaluation/stt/results")
RUN_AT = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)


def identity(**over: object) -> EvaluationIdentity:
    fields: dict[str, object] = {
        "public_model": "intelliai-stt",
        "language": "en",
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


def clip(
    clip_id: str, *, errors: int = 0, hallucinated: int = 0, references: int = 10
) -> ClipResult:
    return ClipResult(
        clip_id=clip_id,
        duration_seconds=1.0,
        inference_seconds=0.1,
        substitutions=errors,
        insertions=0,
        deletions=0,
        reference_words=references,
        hypothesis_words=hallucinated if references == 0 else references,
        hypothesis_text="x",
    )


def run(*clips: ClipResult, **over: object) -> EvalRun:
    fields: dict[str, object] = {
        "dataset_name": "stt-eval-seed",
        "dataset_version": 2,
        "capability": "transcription",
        "run_at": RUN_AT,
        "artifact": "whisper-small",
        "engine": "faster-whisper",
        "engine_version": "1.2.1",
        "compute": "cpu-int8",
        "hardware": "test",
        "clips": list(clips),
        "identity": identity(),
        "coverage": SliceCoverage(
            clips=len(clips), natural_speech_clips=len(clips), probe_clips=0, reference_words=10
        ),
    }
    fields.update(over)
    return EvalRun.model_validate(fields)


def candidate(*clips: ClipResult, **over: object) -> EvalRun:
    over.setdefault("identity", identity(artifact="future-en-v1"))
    over.setdefault("artifact", "future-en-v1")
    return run(*clips, **over)


class TestPromotionClasses:
    def test_there_are_exactly_three_and_they_are_named(self) -> None:
        assert {member.value for member in PromotionClass} == {
            "language_enablement",
            "route_replacement",
            "voice_rebinding",
        }


class TestComparability:
    """ "The candidate lost" and "we cannot tell" are different answers."""

    def test_a_different_corpus_version_is_not_a_comparison(self) -> None:
        verdict = switching_test(
            run(clip("a")),
            candidate(clip("a"), identity=identity(artifact="future-en-v1", dataset_version=3)),
        )
        assert verdict.verdict is Verdict.BLOCKED
        assert verdict.comparable is False
        assert {finding.code for finding in verdict.findings} == {"different_corpus_version"}

    def test_a_different_language_slice_is_not_a_comparison(self) -> None:
        verdict = switching_test(
            run(clip("a")),
            candidate(clip("a"), identity=identity(artifact="future-en-v1", language="hi")),
        )
        assert verdict.verdict is Verdict.BLOCKED
        assert "different_language" in {finding.code for finding in verdict.findings}

    def test_a_different_judge_re_baselines_every_incumbent(self) -> None:
        judged = identity(
            artifact="future-en-v1",
            judge=EvaluationJudge(
                artifact="whisper-small", artifact_version=2, runtime_version="0.1.0"
            ),
        )
        verdict = switching_test(run(clip("a")), candidate(clip("a"), identity=judged))
        assert "different_judge" in {finding.code for finding in verdict.findings}

    def test_a_run_without_identity_cannot_be_compared_at_all(self) -> None:
        verdict = switching_test(run(clip("a"), identity=None), candidate(clip("a")))
        assert verdict.verdict is Verdict.BLOCKED
        assert "identity_missing" in {finding.code for finding in verdict.findings}

    def test_the_same_artifact_and_build_is_not_a_replacement(self) -> None:
        verdict = switching_test(run(clip("a")), run(clip("a")))
        assert "not_a_replacement" in {finding.code for finding in verdict.findings}

    def test_different_clips_cannot_be_compared(self) -> None:
        verdict = switching_test(run(clip("a")), candidate(clip("b")))
        assert verdict.verdict is Verdict.BLOCKED
        assert "different_clips" in {finding.code for finding in verdict.findings}


class TestSwitchingTest:
    def test_an_equal_candidate_passes(self) -> None:
        verdict = switching_test(run(clip("a")), candidate(clip("a")))
        assert verdict.verdict is Verdict.PASSED
        assert verdict.may_proceed is True
        assert verdict.wer_delta == 0.0

    def test_a_better_candidate_passes(self) -> None:
        verdict = switching_test(run(clip("a", errors=2)), candidate(clip("a")))
        assert verdict.verdict is Verdict.PASSED
        assert verdict.wer_delta is not None and verdict.wer_delta < 0

    def test_a_worse_candidate_is_refused(self) -> None:
        verdict = switching_test(run(clip("a")), candidate(clip("a", errors=3)))
        assert verdict.verdict is Verdict.REFUSED
        assert verdict.may_proceed is False
        assert "wer_regression" in {finding.code for finding in verdict.findings}

    def test_new_hallucination_is_refused_even_when_wer_holds(self) -> None:
        verdict = switching_test(
            run(clip("a"), clip("p", references=0)),
            candidate(clip("a"), clip("p", references=0, hallucinated=4)),
        )
        assert verdict.verdict is Verdict.REFUSED
        assert verdict.hallucination_delta == 4

    def test_a_wash_on_aggregate_with_movement_underneath_is_a_trade(self) -> None:
        # Two clips, one better and one worse, same total: a human must
        # look at this, not a threshold.
        verdict = switching_test(
            run(clip("a", errors=2), clip("b")),
            candidate(clip("a"), clip("b", errors=2)),
        )
        assert verdict.verdict is Verdict.TRADE
        assert verdict.may_proceed is False
        assert verdict.regressed_clips == ("b",)

    def test_a_reference_free_slice_can_never_be_a_quality_comparison(self) -> None:
        verdict = switching_test(run(clip("p", references=0)), candidate(clip("p", references=0)))
        assert verdict.verdict is Verdict.TRADE
        assert "no_word_error_rate" in {finding.code for finding in verdict.findings}

    def test_the_verdict_names_both_slices_it_compared(self) -> None:
        verdict = switching_test(run(clip("a")), candidate(clip("a")))
        assert verdict.incumbent == "intelliai-stt/en/whisper-small@1/cpu-int8/stt-eval-seed@v2"
        assert verdict.candidate == "intelliai-stt/en/future-en-v1@1/cpu-int8/stt-eval-seed@v2"


class TestEnablementBar:
    def _committed(self, name: str) -> EvalRun:
        return EvalRun.model_validate_json((RESULTS / name).read_text(encoding="utf-8"))

    def test_hindi_cannot_be_promoted_because_the_corpus_has_no_hindi_speech(self) -> None:
        # ADR-0027 Amendment 3, live. This is the rule working.
        verdict = enablement_test(
            self._committed("2026-08-05-intelliai-stt-hi.json"),
            find_dataset(DATASETS, "stt-eval-seed", 2),
            max_word_error_rate=0.15,
        )
        assert verdict.verdict is Verdict.BLOCKED
        assert "no_natural_speech_in_corpus" in {finding.code for finding in verdict.findings}

    def test_english_clears_the_corpus_precondition(self) -> None:
        verdict = enablement_test(
            self._committed("2026-08-05-intelliai-stt-en.json"),
            find_dataset(DATASETS, "stt-eval-seed", 2),
            max_word_error_rate=0.15,
        )
        assert verdict.verdict is Verdict.PASSED
        assert verdict.slice_slug is not None and "/en/" in verdict.slice_slug

    def test_without_a_founder_bar_nothing_can_be_promised(self) -> None:
        # F-M5-3 is not optional: a promise cannot be checked against a
        # threshold nobody chose, so the absence of one refuses.
        verdict = enablement_test(
            self._committed("2026-08-05-intelliai-stt-en.json"),
            find_dataset(DATASETS, "stt-eval-seed", 2),
        )
        assert verdict.verdict is Verdict.REFUSED
        assert "no_absolute_bar" in {finding.code for finding in verdict.findings}

    def test_a_bar_the_evidence_misses_refuses(self) -> None:
        verdict = enablement_test(
            self._committed("2026-08-05-intelliai-stt-en.json"),
            find_dataset(DATASETS, "stt-eval-seed", 2),
            max_word_error_rate=-0.01,
        )
        assert verdict.verdict is Verdict.REFUSED
        assert "wer_above_bar" in {finding.code for finding in verdict.findings}

    def test_a_corpus_that_is_not_the_one_the_run_cited_blocks(self) -> None:
        with pytest.raises(FileNotFoundError):
            find_dataset(DATASETS, "stt-eval-seed", 99)
        verdict = enablement_test(
            self._committed("2026-08-05-intelliai-stt-en.json"),
            load_dataset(DATASETS / "stt-eval-v1.json"),
            max_word_error_rate=0.15,
        )
        assert verdict.verdict is Verdict.BLOCKED
        assert "corpus_mismatch" in {finding.code for finding in verdict.findings}
