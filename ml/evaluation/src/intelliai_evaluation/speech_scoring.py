"""Speech evaluation logic — ALL of it, so the runner can have none.

The runner orchestrates (corpus -> synthesis -> judge -> scoring ->
record); this module decides what the numbers are. Pure and
deterministic: same inputs, same scores, forever.
"""

from __future__ import annotations

from intelliai_evaluation.corpus import SpeechTextCase
from intelliai_evaluation.roundtrip import pronunciation_accuracy, round_trip_wer
from intelliai_evaluation.signal import SignalAnalysis, duration_plausibility
from intelliai_evaluation.speech_results import CaseResult


def signal_metrics(text: str, analysis: SignalAnalysis) -> dict[str, float]:
    """What the waveform alone proves — computable even if the judge fails."""
    return {
        "clipping_ratio": analysis.clipping_ratio,
        "silence_ratio": analysis.silence_ratio,
        "duration_plausibility": duration_plausibility(text, analysis.duration_seconds),
    }


def score_case(
    case: SpeechTextCase,
    analysis: SignalAnalysis,
    transcript: str,
    synthesis_latency_ms: float,
) -> CaseResult:
    """A fully judged case: signal + round-trip + performance metrics."""
    metrics = signal_metrics(case.text, analysis)
    metrics["synthesis_latency_ms"] = synthesis_latency_ms
    if analysis.duration_seconds > 0:
        metrics["rtf"] = (synthesis_latency_ms / 1000.0) / analysis.duration_seconds
    breakdown = round_trip_wer(case.text, transcript)
    metrics["round_trip_wer"] = breakdown.wer
    accuracy = pronunciation_accuracy(case.trap_words, transcript)
    if accuracy is not None:
        metrics["pronunciation_accuracy"] = accuracy
    return CaseResult(
        case_id=case.id,
        transcript=transcript,
        metrics=metrics,
        reference_words=breakdown.reference_words,
        word_errors=breakdown.errors,
    )


def aggregate_cases(cases: list[CaseResult]) -> dict[str, float]:
    """Aggregation semantics per SPEECH_EVALUATION.md §5, declared not assumed:

    - ``round_trip_wer``: WORD-WEIGHTED — total errors over total reference
      words (matches the STT ledger; short cases must not outvote long ones).
    - everything else: arithmetic mean over the cases that measured it
      (failed stages contributed fewer samples — never zeros)."""
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for case in cases:
        for name, value in case.metrics.items():
            if name == "round_trip_wer":
                continue
            sums[name] = sums.get(name, 0.0) + value
            counts[name] = counts.get(name, 0) + 1
    aggregates = {name: sums[name] / counts[name] for name in sums}

    total_reference = sum(c.reference_words or 0 for c in cases if "round_trip_wer" in c.metrics)
    total_errors = sum(c.word_errors or 0 for c in cases if "round_trip_wer" in c.metrics)
    if total_reference > 0:
        aggregates["round_trip_wer"] = total_errors / total_reference
    return aggregates
