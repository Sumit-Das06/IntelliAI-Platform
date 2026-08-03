"""Aggregation semantics: declared, and provably word-weighted (C1)."""

from intelliai_evaluation.speech_results import CaseResult
from intelliai_evaluation.speech_scoring import aggregate_cases


def test_round_trip_wer_is_word_weighted_not_mean_of_means() -> None:
    long_clean = CaseResult(
        case_id="long",
        transcript="ten perfect words here" + " x" * 6,
        metrics={"round_trip_wer": 0.0},
        reference_words=10,
        word_errors=0,
    )
    short_bad = CaseResult(
        case_id="short",
        transcript="wrong words",
        metrics={"round_trip_wer": 0.5},
        reference_words=2,
        word_errors=1,
    )
    aggregates = aggregate_cases([long_clean, short_bad])
    # Word-weighted: 1 error / 12 words — NOT the mean of (0.0, 0.5) = 0.25.
    assert aggregates["round_trip_wer"] == 1 / 12
    assert aggregates["round_trip_wer"] != 0.25


def test_other_metrics_average_only_over_measuring_cases() -> None:
    measured = CaseResult(
        case_id="a", transcript="x", metrics={"clipping_ratio": 0.2, "silence_ratio": 0.0}
    )
    failed = CaseResult(case_id="b", transcript="", metrics={}, failure="synthesis: boom")
    aggregates = aggregate_cases([measured, failed])
    assert aggregates["clipping_ratio"] == 0.2  # one sample, never zero-padded


def test_no_judged_cases_means_no_round_trip_aggregate() -> None:
    unjudged = CaseResult(
        case_id="a", transcript="", metrics={"clipping_ratio": 0.0}, failure="judge: down"
    )
    assert "round_trip_wer" not in aggregate_cases([unjudged])
