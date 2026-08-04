"""Promotion: turning evidence into a decision, and the decision into a diff.

Promotion is where every plane meets. The one-way causal chain — serving
→ evidence → promotion → registry state → routing — becomes an operating
procedure here, and this module is the part of it a machine can check.

**What this module does not do.** It does not promote anything. It
computes verdicts from committed evidence and states, for one proposal,
whether the bar it claims to meet is actually met. A human reads that,
decides, and writes a diff. The evaluation plane never changes registry
state — it produces the evidence a promotion cites, and the diff is the
promotion record (V1.5; Registry V2 lifts this into a store).

**Three classes, because they answer different questions.**

| Class | Question | Bar |
|---|---|---|
| Language enablement | Is this good enough to *promise*? | absolute |
| Route replacement | Is B *at least as good as* A? | relative |
| Voice rebinding | Does it still *sound like* the voice? | relative + listening |

An absolute bar needs a number someone chose (F-M5-3). A relative bar
needs two runs that are actually comparable, which is a stricter
requirement than it sounds: same slice, same corpus version, same judge.
Comparing across corpus versions is not a strict comparison — it is a
category error with a plausible-looking delta.
"""

from __future__ import annotations

from enum import StrEnum, unique

from pydantic import BaseModel, ConfigDict, Field

from intelliai_evaluation.dataset import EvalDataset
from intelliai_evaluation.results import EvalRun


@unique
class PromotionClass(StrEnum):
    """What kind of change is being proposed."""

    LANGUAGE_ENABLEMENT = "language_enablement"  # a rung moves: absolute bar
    ROUTE_REPLACEMENT = "route_replacement"  # artifact A -> B behind a route
    VOICE_REBINDING = "voice_rebinding"  # a voice's artifact changes


@unique
class Verdict(StrEnum):
    BLOCKED = "blocked"  # a precondition fails; the comparison is not even valid
    REFUSED = "refused"  # comparable, and the bar is not met
    TRADE = "trade"  # comparable, mixed — a human must accept the trade in writing
    PASSED = "passed"  # comparable, and the bar is met


class Finding(BaseModel):
    """One reason a verdict is what it is — quotable in a promotion diff."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class SwitchingVerdict(BaseModel):
    """The C3 switching test, per language route.

    ``comparable`` is the precondition and is reported separately from the
    outcome, because "the candidate lost" and "we cannot tell" are
    different answers and collapsing them is how bad promotions happen.
    """

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    comparable: bool
    findings: tuple[Finding, ...] = ()
    incumbent: str | None = None  # identity slug
    candidate: str | None = None
    wer_delta: float | None = None  # candidate - incumbent; negative is better
    hallucination_delta: int | None = None
    regressed_clips: tuple[str, ...] = ()

    @property
    def may_proceed(self) -> bool:
        """Only a clean pass proceeds without a human writing something down."""
        return self.verdict is Verdict.PASSED


def _comparability(incumbent: EvalRun, candidate: EvalRun) -> list[Finding]:
    """Everything that must match before a delta means anything."""
    findings: list[Finding] = []
    left, right = incumbent.identity, candidate.identity
    if left is None or right is None:
        findings.append(
            Finding(
                code="identity_missing",
                detail="a run without an evaluation identity cannot be compared: "
                "it does not say which promise, language, or build it measured",
            )
        )
        return findings
    if left.public_model != right.public_model:
        findings.append(
            Finding(
                code="different_promise",
                detail=f"{left.public_model} vs {right.public_model}",
            )
        )
    if left.language != right.language:
        findings.append(
            Finding(code="different_language", detail=f"{left.language} vs {right.language}")
        )
    if (left.dataset, left.dataset_version) != (right.dataset, right.dataset_version):
        findings.append(
            Finding(
                code="different_corpus_version",
                detail=f"{left.dataset}@v{left.dataset_version} vs "
                f"{right.dataset}@v{right.dataset_version}; a switching test is only "
                "valid within one corpus version",
            )
        )
    if left.judge != right.judge:
        findings.append(
            Finding(code="different_judge", detail="a judge upgrade re-baselines every incumbent")
        )
    if left.artifact == right.artifact and left.build == right.build:
        findings.append(
            Finding(
                code="not_a_replacement",
                detail=f"both runs measured {left.artifact}@{left.build}; "
                "there is nothing to switch to",
            )
        )
    return findings


def switching_test(incumbent: EvalRun, candidate: EvalRun) -> SwitchingVerdict:
    """Is the candidate at least as good as the incumbent, on this slice?

    The relative bar. A candidate wins on the quality layer, or it trades
    consciously — and a trade is never decided here: it is surfaced, and a
    human writes down why it is acceptable, in the diff that promotes it.
    """
    blockers = _comparability(incumbent, candidate)
    if blockers:
        return SwitchingVerdict(verdict=Verdict.BLOCKED, comparable=False, findings=tuple(blockers))
    assert incumbent.identity is not None and candidate.identity is not None  # noqa: S101

    findings: list[Finding] = []
    before = {clip.clip_id: clip for clip in incumbent.clips}
    after = {clip.clip_id: clip for clip in candidate.clips}
    if set(before) != set(after):
        missing = sorted(set(before) ^ set(after))
        return SwitchingVerdict(
            verdict=Verdict.BLOCKED,
            comparable=False,
            findings=(
                Finding(code="different_clips", detail=f"clips differ: {', '.join(missing)}"),
            ),
        )

    regressed = tuple(
        clip_id
        for clip_id in sorted(before)
        if after[clip_id].errors > before[clip_id].errors
        or after[clip_id].hallucinated_words > before[clip_id].hallucinated_words
    )
    wer_delta: float | None = None
    if incumbent.overall_wer is not None and candidate.overall_wer is not None:
        wer_delta = candidate.overall_wer - incumbent.overall_wer
    hallucination_delta = candidate.hallucinated_words_total - incumbent.hallucinated_words_total

    if wer_delta is None:
        findings.append(
            Finding(
                code="no_word_error_rate",
                detail="this slice has no references, so the comparison covers "
                "hallucination only — it is not a quality comparison",
            )
        )
    if hallucination_delta > 0:
        findings.append(
            Finding(
                code="hallucination_regression",
                detail=f"+{hallucination_delta} hallucinated words",
            )
        )
    if wer_delta is not None and wer_delta > 0:
        findings.append(Finding(code="wer_regression", detail=f"WER +{wer_delta:.4f}"))
    if regressed:
        findings.append(
            Finding(code="clip_regressions", detail=f"{len(regressed)} clip(s) got worse")
        )

    if hallucination_delta > 0 or (wer_delta is not None and wer_delta > 0):
        verdict = Verdict.REFUSED
    elif regressed or wer_delta is None:
        # Aggregates held (or do not exist) while something underneath
        # moved: exactly the case a human must look at rather than a
        # threshold decide.
        verdict = Verdict.TRADE
    else:
        verdict = Verdict.PASSED

    return SwitchingVerdict(
        verdict=verdict,
        comparable=True,
        findings=tuple(findings),
        incumbent=incumbent.identity.slug,
        candidate=candidate.identity.slug,
        wer_delta=wer_delta,
        hallucination_delta=hallucination_delta,
        regressed_clips=regressed,
    )


class EnablementVerdict(BaseModel):
    """The absolute bar: is this good enough to *promise*?"""

    model_config = ConfigDict(frozen=True)

    verdict: Verdict
    findings: tuple[Finding, ...] = ()
    slice_slug: str | None = None

    @property
    def may_proceed(self) -> bool:
        return self.verdict is Verdict.PASSED


def enablement_test(
    run: EvalRun,
    corpus: EvalDataset,
    *,
    max_word_error_rate: float | None = None,
    max_hallucinated_words: int = 0,
) -> EnablementVerdict:
    """May this language be promised, on this evidence?

    The corpus precondition (ADR-0027 Amendment 3) is checked first and
    is not a threshold: a corpus with no natural speech in the promoted
    language cannot support a promise however good its numbers look, and
    ``max_word_error_rate`` is the founder's per-language bar (F-M5-3),
    absent by default because guessing it here would be worse than
    refusing to.
    """
    findings: list[Finding] = []
    identity = run.identity
    if identity is None:
        return EnablementVerdict(
            verdict=Verdict.BLOCKED,
            findings=(
                Finding(
                    code="identity_missing",
                    detail="a run without an identity does not say what it measured",
                ),
            ),
        )
    if (corpus.name, corpus.version) != (identity.dataset, identity.dataset_version):
        findings.append(
            Finding(
                code="corpus_mismatch",
                detail=f"run cites {identity.dataset}@v{identity.dataset_version}, "
                f"checked against {corpus.name}@v{corpus.version}",
            )
        )
    natural = [
        clip
        for clip in corpus.clips
        if clip.language == identity.language and clip.synthetic is None and clip.reference_text
    ]
    if not natural:
        findings.append(
            Finding(
                code="no_natural_speech_in_corpus",
                detail=f"{corpus.name}@v{corpus.version} has no natural-speech clips in "
                f"{identity.language!r}; evidence quality is bounded by dataset quality, "
                "so this cannot support a promise (ADR-0027 Amendment 3)",
            )
        )
    if findings:
        return EnablementVerdict(
            verdict=Verdict.BLOCKED, findings=tuple(findings), slice_slug=identity.slug
        )

    if run.coverage is not None and not run.coverage.is_quality_claim:
        findings.append(
            Finding(
                code="not_a_quality_claim",
                detail="the measured slice contains no natural speech",
            )
        )
    if run.hallucinated_words_total > max_hallucinated_words:
        findings.append(
            Finding(
                code="hallucination",
                detail=f"{run.hallucinated_words_total} hallucinated words "
                f"(bar: {max_hallucinated_words})",
            )
        )
    if max_word_error_rate is None:
        findings.append(
            Finding(
                code="no_absolute_bar",
                detail="no per-language quality bar has been set (F-M5-3); a promise "
                "cannot be checked against a threshold nobody chose",
            )
        )
    elif run.overall_wer is None or run.overall_wer > max_word_error_rate:
        findings.append(
            Finding(
                code="wer_above_bar",
                detail=f"WER {run.overall_wer} vs bar {max_word_error_rate}",
            )
        )

    verdict = Verdict.REFUSED if findings else Verdict.PASSED
    return EnablementVerdict(verdict=verdict, findings=tuple(findings), slice_slug=identity.slug)
