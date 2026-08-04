"""Evaluation identity — what a measurement is *about*.

A number without an identity is not evidence. Before this module, a run
recorded which artifact it measured and against which dataset version;
that was sufficient while one public model meant one artifact and one
language. It stopped being sufficient the moment a public model could
resolve to different artifacts per language, because "WER 0.07 for
whisper-small" no longer says *which promise* was measured, *which
deployment* answered, or *which language slice* the number covers.

**Why identity lives here and not in the registry.** The registry is the
single source of *serving* truth: what serves a request, right now. An
evaluation record is a permanent statement about the past — it must stay
readable and reproducible long after the registry has been re-pointed,
the deployment renamed, and the artifact archived. Putting identity in
the registry would make history mutable by a promotion; putting it in the
record makes the record self-contained. The registry says what *is*; the
evidence ledger says what *was measured*, and neither may rewrite the
other.

Fields are additive-only, for the same reason as the run schema: a reader
written today must parse a record written in five years, and a record
written in 2026 must still be readable by a reader written in 2031.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvaluationJudge(BaseModel):
    """The model that decided whether an output was right.

    ``None`` on the identity means the dataset's own reference texts were
    the judge — the transcription case, where correctness is a comparison
    against a committed string rather than another model's opinion. When a
    model judges (the synthesis round-trip), it is itself an artifact with
    a version, and a judge upgrade re-baselines every incumbent.
    """

    model_config = ConfigDict(frozen=True)

    artifact: str = Field(min_length=1)
    artifact_version: int = Field(ge=1)
    runtime_version: str = Field(min_length=1)


class SliceCoverage(BaseModel):
    """What the measured slice actually contains.

    Present so a record cannot overstate itself. A language slice with no
    natural-speech clips can produce a hallucination measurement and
    cannot produce a word error rate — and a reader five years from now
    must be able to see that from the record, not infer it from prose.
    """

    model_config = ConfigDict(frozen=True)

    clips: int = Field(ge=0)
    natural_speech_clips: int = Field(ge=0)  # pinned recordings of real speech
    probe_clips: int = Field(ge=0)  # deterministic synthetic audio
    reference_words: int = Field(ge=0)

    @property
    def supports_word_error_rate(self) -> bool:
        """Whether this slice can produce a WER at all."""
        return self.reference_words > 0

    @property
    def is_quality_claim(self) -> bool:
        """Whether a promotion may cite this slice as a quality measurement.

        A slice with no natural speech measures the system's behaviour on
        audio nobody speaks. That is real evidence about hallucination and
        it is not a quality claim about a language.
        """
        return self.natural_speech_clips > 0 and self.supports_word_error_rate


class EvaluationIdentity(BaseModel):
    """Who and what one measurement is about — the evidence ledger's key.

    Every field answers a question a future reader will have and cannot
    reconstruct from anywhere else once the registry has moved on.
    """

    model_config = ConfigDict(frozen=True)

    #: The promise measured. Customers buy `intelliai-stt`, not an
    #: artifact; a baseline that cannot name the promise cannot be cited
    #: in a promotion of it.
    public_model: str = Field(min_length=1)
    #: The language slice. `zxx` means audio with no linguistic content.
    language: str = Field(min_length=1)
    #: What actually served, and at which version.
    artifact: str = Field(min_length=1)
    artifact_version: int = Field(ge=1)
    #: The build — precision, conversion, anything deterministic applied
    #: at load. Quality binds to (artifact, build), never to artifact
    #: alone: a quantized build is the same identity and not necessarily
    #: the same behaviour.
    build: str = Field(min_length=1)
    #: Which deployment of the capability service answered.
    deployment: str = Field(min_length=1)
    #: The versioned corpus. Two runs on different corpus versions are
    #: different evidence, and comparing them is a category error.
    dataset: str = Field(min_length=1)
    dataset_version: int = Field(ge=1)
    #: Set ONLY when this run is christened a named benchmark. A run is
    #: not a baseline because it was first; it is a baseline because it
    #: was named one.
    benchmark: str | None = None
    judge: EvaluationJudge | None = None
    run_at: datetime

    @property
    def slug(self) -> str:
        """The citation form: what a promotion diff quotes."""
        return (
            f"{self.public_model}/{self.language}/"
            f"{self.artifact}@{self.artifact_version}/{self.build}/"
            f"{self.dataset}@v{self.dataset_version}"
        )

    def reproduction(self) -> dict[str, str]:
        """Everything needed to run this measurement again, from records
        alone — no operator memory anywhere in the list.

        The registry contributes the artifact through the manifest, the
        dataset contributes the clips through its version, and this record
        contributes the rest. If any value here had to be remembered
        rather than read, the measurement would not be reproducible.
        """
        return {
            "model": self.public_model,
            "language": self.language,
            "dataset": f"{self.dataset}@v{self.dataset_version}",
            "artifact": f"{self.artifact}@v{self.artifact_version}",
            "build": self.build,
            "deployment": self.deployment,
        }
