"""Aggregation math: word-weighted WER, RTF, hallucination accounting."""

from datetime import UTC, datetime

import pytest

from intelliai_evaluation.results import ClipResult, EvalRun


def _clip(
    clip_id: str,
    *,
    reference_words: int,
    errors: int = 0,
    hypothesis_words: int = 0,
    duration: float = 10.0,
    inference: float = 5.0,
) -> ClipResult:
    return ClipResult(
        clip_id=clip_id,
        duration_seconds=duration,
        inference_seconds=inference,
        substitutions=errors,
        insertions=0,
        deletions=0,
        reference_words=reference_words,
        hypothesis_words=hypothesis_words,
        hypothesis_text="",
    )


def _run(clips: list[ClipResult]) -> EvalRun:
    return EvalRun(
        dataset_name="stt-eval-seed",
        dataset_version=1,
        capability="transcription",
        run_at=datetime(2026, 8, 1, tzinfo=UTC),
        artifact="whisper-small",
        engine="faster-whisper",
        engine_version="1.2.1",
        compute="cpu-int8",
        hardware="test",
        clips=clips,
    )


class TestAggregation:
    def test_overall_wer_is_word_weighted(self) -> None:
        # 2 errors over 10 words + 2 errors over 40 words = 4/50, NOT mean(0.2, 0.05)
        run = _run(
            [
                _clip("a", reference_words=10, errors=2, hypothesis_words=10),
                _clip("b", reference_words=40, errors=2, hypothesis_words=40),
            ]
        )
        assert run.overall_wer == pytest.approx(0.08)

    def test_empty_reference_clips_do_not_pollute_wer(self) -> None:
        run = _run(
            [
                _clip("speech", reference_words=20, errors=1, hypothesis_words=20),
                _clip("silence", reference_words=0, hypothesis_words=7),
            ]
        )
        assert run.overall_wer == pytest.approx(1 / 20)
        assert run.hallucinated_words_total == 7

    def test_all_probe_dataset_has_no_wer(self) -> None:
        run = _run([_clip("silence", reference_words=0, hypothesis_words=0)])
        assert run.overall_wer is None

    def test_rtf(self) -> None:
        clip = _clip("a", reference_words=1, duration=10.0, inference=5.0)
        assert clip.rtf == pytest.approx(0.5)
        run = _run(
            [
                _clip("a", reference_words=1, duration=10.0, inference=5.0),
                _clip("b", reference_words=1, duration=10.0, inference=15.0),
            ]
        )
        assert run.mean_rtf == pytest.approx(1.0)

    def test_clip_wer_none_for_probes(self) -> None:
        probe = _clip("silence", reference_words=0, hypothesis_words=3)
        assert probe.wer is None
        assert probe.hallucinated_words == 3
        speech = _clip("speech", reference_words=10, errors=1, hypothesis_words=10)
        assert speech.wer == pytest.approx(0.1)
        assert speech.hallucinated_words == 0

    def test_summary_shape(self) -> None:
        run = _run([_clip("a", reference_words=10, errors=1, hypothesis_words=10)])
        summary = run.summary()
        assert summary["dataset"] == "stt-eval-seed@v1"
        assert summary["clips"] == 1
        assert summary["overall_wer"] == pytest.approx(0.1)

    def test_run_serializes_to_json(self) -> None:
        run = _run([_clip("a", reference_words=10, errors=1, hypothesis_words=10)])
        payload = run.model_dump_json()
        restored = EvalRun.model_validate_json(payload)
        assert restored == run
