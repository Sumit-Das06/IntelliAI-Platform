"""SpeechEvalRun — permanent evidence, not transient output.

An evaluation record is the auditable artifact that justified a model
decision (SPEECH_EVALUATION.md §5). Three laws are enforced here in
code, not just prose:

1. **Self-contained** — the five-year question: every record carries the
   full reproducibility set as REQUIRED fields (corpus version, evaluated
   artifact + lineage, judge identity, runtime, hardware, methodology
   version, synthesis parameters) plus per-case transcripts, so what
   happened is understandable from the record and the versioned repo.
2. **Immutable** — every model is frozen; the ledger is append-only.
   Corrections and re-runs create NEW records, never edits.
3. **Measured and human evidence never mix** — measured metric maps
   refuse human/reserved metric names; the human structure refuses
   measured ones. Both validate against the metric registry: free-form
   identifiers never enter the ledger, exactly as capabilities validate
   against the Capability enum.

The evidence principle: measurements describe reality; promotion
decisions interpret measurements. This module records evidence — it
never decides whether a model ships.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator

from intelliai_evaluation.evidence import Determination
from intelliai_evaluation.metrics import MEASURED_CONFIDENCES, MetricConfidence, require_registered

# Pinned from SPEECH_EVALUATION.md's header; recorded in every run so a
# record always names the methodology it was produced under. Note that
# `EvalRun.methodology_version` on the recognition root names a DIFFERENT
# document — the two roots are measured under two methodologies, and a
# reader of any single record is never ambiguous about which.
METHODOLOGY_VERSION: Final = 1

_MEASURED = MEASURED_CONFIDENCES
_require_registered = require_registered


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True)


class EvaluatedArtifact(_Record):
    """What was measured — registry identity plus lineage, never an engine."""

    artifact: str = Field(min_length=1)  # e.g. "kokoro-82m"
    version: int = Field(ge=1)
    lineage: str = Field(min_length=1)  # model family, e.g. "kokoro"


class JudgeIdentity(_Record):
    """Who judged the round trip — comparisons are valid only within one
    judge (SPEECH_EVALUATION.md §4)."""

    capability: str = Field(min_length=1)  # e.g. "transcription"
    artifact: str = Field(min_length=1)  # e.g. "whisper-small"
    version: int = Field(ge=1)
    runtime_version: str = Field(min_length=1)


class RuntimeIdentity(_Record):
    """Which serving process synthesized the audio."""

    service: str = Field(min_length=1)
    service_version: str = Field(min_length=1)


class CaseResult(_Record):
    """One corpus case's measured outcome — transcript kept verbatim so
    the record explains itself years later.

    Failures are evidence too: when a stage failed, ``failure`` names it
    and whatever metrics DID measure before the failure are preserved —
    partial evidence beats discarded evidence."""

    case_id: str = Field(min_length=1)
    transcript: str  # the judge's transcript, unedited ("" is valid evidence)
    metrics: dict[str, float]
    failure: str | None = None  # e.g. "synthesis: timeout", "judge: unavailable"
    # Round-trip alignment counts (evidence facts, and the inputs to the
    # word-weighted round_trip_wer aggregate — SPEECH_EVALUATION.md §5).
    reference_words: int | None = None
    word_errors: int | None = None

    @field_validator("metrics")
    @classmethod
    def _measured_only(cls, value: dict[str, float]) -> dict[str, float]:
        _require_registered(value, _MEASURED)
        return value


class HumanEvaluation(_Record):
    """Subjective evidence — separate from measurement by design."""

    protocol: str = Field(min_length=1)  # e.g. "founder-listening-v1"
    listeners: int = Field(ge=1)  # honesty about n
    scores: dict[str, float]
    notes: str = ""

    @field_validator("scores")
    @classmethod
    def _human_only(cls, value: dict[str, float]) -> dict[str, float]:
        _require_registered(value, (MetricConfidence.HUMAN,))
        return value


class ComparisonContext(_Record):
    """Reserved for future promotion workflows — recorded, never acted on
    by the evaluation system itself."""

    compared_against: str | None = None  # another run's identity
    promotion_candidate: bool | None = None
    benchmark_group: str | None = None


class SpeechEvalRun(_Record):
    """One complete, immutable, self-contained evaluation record."""

    # ── Reproducibility set: ALL required (an under-specified benchmark
    #    is impossible to construct) ──────────────────────────────────
    corpus_name: str = Field(min_length=1)
    corpus_version: int = Field(ge=1)
    methodology_version: int = Field(ge=1)
    evaluated: EvaluatedArtifact
    judge: JudgeIdentity
    runtime: RuntimeIdentity
    hardware: str = Field(min_length=1)
    run_at: datetime
    # Pinned synthesis parameters (voice, speed, seed …): part of what
    # "the same evaluation" means.
    synthesis_params: dict[str, str] = Field(default_factory=dict)

    # ── Schema unification (B3): additive, optional, mandatory in the
    #    runner from now on ─────────────────────────────────────────
    #
    # The ruler, as a record cites it: `name@vN`. Every committed
    # `round_trip_wer` was computed with `unicode_generic@v1` and says so
    # nowhere, which makes those records incomplete evidence by the
    # platform's own rule — a benchmark that cannot state which profile
    # produced its metric cannot be reproduced. Optional so they still
    # parse; stated from now on so no new record joins them.
    normalization: str | None = None
    #: Absence recorded as evidence, on this root too. One mechanism,
    #: both disciplines.
    determinations: tuple[Determination, ...] = ()

    # ── Evidence ────────────────────────────────────────────────────
    cases: tuple[CaseResult, ...] = Field(min_length=1)
    aggregate_metrics: dict[str, float]
    human: HumanEvaluation | None = None  # subjective evidence, separated
    comparison: ComparisonContext | None = None  # reserved
    # When set, this run IS a named baseline — the reference future
    # documents cite ("compared against baseline <name>"), never a filename.
    baseline_name: str | None = None
    notes: str = ""

    @field_validator("aggregate_metrics")
    @classmethod
    def _measured_only(cls, value: dict[str, float]) -> dict[str, float]:
        _require_registered(value, _MEASURED)
        return value
