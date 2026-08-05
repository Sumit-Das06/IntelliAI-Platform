"""Benchmark result records — the format every model measurement is kept in.

One EvalRun per measured slice — (public model, language, artifact,
build, dataset version) — serialized to JSON and committed under the
capability's results/ directory (append-only, never edited —
Constitution P13). The schema is additive-only: consumers written today
must parse results written in five years, and readers written in five
years must parse the records written today. That is why ``identity`` is
optional on the model and mandatory in the runner: records that predate
it must still load, and every record written from now on carries it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from intelliai_evaluation.evidence import Determination, ExecutionContext, Validity
from intelliai_evaluation.identity import EvaluationIdentity, SliceCoverage
from intelliai_evaluation.metrics import MEASURED_CONFIDENCES, require_registered
from intelliai_runtime_contract import Capability


class ClipResult(BaseModel):
    """Measurement for one clip within a run."""

    model_config = ConfigDict(frozen=True)

    clip_id: str
    duration_seconds: float
    inference_seconds: float
    substitutions: int
    insertions: int
    deletions: int
    reference_words: int
    hypothesis_words: int
    hypothesis_text: str
    # ── Additive (B3) ───────────────────────────────────────────────
    #: Registry-validated numbers for this clip. The alignment counts
    #: above are the raw facts; this is where named metrics computed from
    #: them live, so a reader never has to guess which ruler produced a
    #: number that has no name.
    metrics: dict[str, float] = {}
    #: **Failures are evidence.** A clip that errored keeps whatever
    #: partial metrics were obtained and says what went wrong, verbatim.
    #: Until this existed the recognition runner could only abort the
    #: whole run — so the hypotheses whose expected outcome is "the
    #: candidate does not run at all" were the ones it could not record.
    failure: str | None = None

    @field_validator("metrics")
    @classmethod
    def _measured_only(cls, value: dict[str, float]) -> dict[str, float]:
        require_registered(value, MEASURED_CONFIDENCES)
        return value

    @property
    def errors(self) -> int:
        return self.substitutions + self.insertions + self.deletions

    @property
    def wer(self) -> float | None:
        """None for empty-reference probes (their metric is hallucination)."""
        if self.reference_words == 0:
            return None
        return self.errors / self.reference_words

    @property
    def hallucinated_words(self) -> int:
        """Words emitted where the correct output was silence."""
        return self.hypothesis_words if self.reference_words == 0 else 0

    @property
    def rtf(self) -> float:
        """Real-time factor: inference time / audio duration (lower is better)."""
        return self.inference_seconds / self.duration_seconds


class EvalRun(BaseModel):
    """One complete measurement of one model against one dataset version."""

    model_config = ConfigDict(frozen=True)

    dataset_name: str
    dataset_version: int
    capability: Capability
    run_at: datetime
    artifact: str  # registry model id (e.g. "whisper-small")
    engine: str
    engine_version: str
    compute: str  # e.g. "cpu-int8"
    hardware: str  # human description of the machine
    notes: str = ""
    clips: list[ClipResult]
    # Startup economics (additive, M2 step 5): from the runtime's /info.
    load_ms: float | None = None
    warmup_ms: float | None = None
    # Evaluation identity (additive, M5 step 4). Optional on the schema so
    # the M2 records still parse; mandatory in the runner, so every record
    # written from now on says which promise, language, build, and
    # deployment it measured.
    identity: EvaluationIdentity | None = None
    coverage: SliceCoverage | None = None

    # ── Evidence record v2 (additive, B3) ───────────────────────────
    #
    # Every field below is optional in the schema and mandatory in the
    # runner. Optional because a required field would break
    # `model_validate` on all three committed recognition records — which
    # breaks `find_dataset`, which breaks `switching_test` against the
    # incumbent baseline, silently. Each default is not merely safe but
    # TRUE of what those records contain.

    #: How the run was executed: route, ruler, language, decode
    #: configuration, and the machine. One container rather than a dozen
    #: loose fields, so the bare name `conditions` stays unclaimed on this
    #: root and a four-way collision cannot recur.
    #:
    #: `None` means no execution context was recorded — true of every
    #: committed record, and honestly so: the oldest of them mixes `en`
    #: and `zxx` clips in one run, so no single `declared_language` would
    #: be a fact about it.
    execution: ExecutionContext | None = None

    #: Absence recorded as evidence: what could not be measured, why, who
    #: says so, and when they last checked. Never a missing field, never a
    #: zero. This is also where a ruler failure lands — a declared
    #: reference that a profile normalises to nothing is a Determination,
    #: not a number.
    determinations: tuple[Determination, ...] = ()

    #: Registry-validated aggregates. The properties below stayed as they
    #: were: they are the M2-era computed view, and changing what they
    #: return would change what a committed record means.
    metrics: dict[str, float] = {}

    #: Whether these numbers can mean what they claim — computed from the
    #: recorded facts by a later pass, never asserted by the run itself.
    #: `None` is "not computed", which is true of every record we hold:
    #: validity is computed at the end of a session, and no session has
    #: ever run under this methodology. There is no enum member for this
    #: state on purpose.
    validity: Validity | None = None

    #: One session emits several records — a quality record and a
    #: production record per language. A shared id makes "which production
    #: benchmark accompanies this quality benchmark" a query rather than
    #: something a human has to remember. `None` means unlinked; it does
    #: not mean the run belonged to no session.
    session_id: str | None = None

    #: Which recognition methodology produced this record. `None` means it
    #: predates the methodology entirely — true of all three committed
    #: records, and more honest than stamping them as conforming to a
    #: document written after them.
    methodology_version: int | None = None

    @field_validator("metrics")
    @classmethod
    def _measured_only(cls, value: dict[str, float]) -> dict[str, float]:
        require_registered(value, MEASURED_CONFIDENCES)
        return value

    @property
    def overall_wer(self) -> float | None:
        """Word-weighted WER across clips with non-empty references."""
        reference_total = sum(c.reference_words for c in self.clips)
        if reference_total == 0:
            return None
        error_total = sum(c.errors for c in self.clips if c.reference_words > 0)
        return error_total / reference_total

    @property
    def mean_rtf(self) -> float | None:
        if not self.clips:
            return None
        return sum(c.rtf for c in self.clips) / len(self.clips)

    @property
    def hallucinated_words_total(self) -> int:
        return sum(c.hallucinated_words for c in self.clips)

    def summary(self) -> dict[str, object]:
        """Compact aggregate view for logs and review tables."""
        view: dict[str, object] = {
            "dataset": f"{self.dataset_name}@v{self.dataset_version}",
            "artifact": self.artifact,
            "engine": f"{self.engine} {self.engine_version}",
            "compute": self.compute,
            "overall_wer": self.overall_wer,
            "mean_rtf": self.mean_rtf,
            "hallucinated_words_total": self.hallucinated_words_total,
            "clips": len(self.clips),
        }
        if self.identity is not None:
            view["slice"] = self.identity.slug
            view["public_model"] = self.identity.public_model
            view["language"] = self.identity.language
            view["deployment"] = self.identity.deployment
        if self.coverage is not None:
            view["natural_speech_clips"] = self.coverage.natural_speech_clips
            # Stated rather than implied: a slice with no natural speech
            # measures hallucination, and is not a quality claim.
            view["is_quality_claim"] = self.coverage.is_quality_claim
        return view
