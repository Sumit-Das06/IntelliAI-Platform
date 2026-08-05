"""What a benchmark record is made of — importable without a network stack.

Everything here is a *record part*: a vocabulary, an identity, or a
container that an evidence record nests. Both evidence roots import from
this module — recognition (`results.EvalRun`) and generation
(`speech_results.SpeechEvalRun`) stay two roots and converge through
these parts rather than through a merged schema.

**The import budget is the point.** This module may depend on nothing
beyond pydantic, stdlib, and `metrics`. Reading a five-year-old JSON
record must never require an HTTP client to be installable — and the
production-ladder record types used to live in `bench.py`, which imports
`httpx` at module scope and shells out to `docker stats`. They are here
now; the machinery that *produces* them stayed behind.

**Absence has exactly one representation.** A fact we could not obtain is
``None`` on its field plus a :class:`Determination` saying why. There is
deliberately no parallel `unknown_fields` list: two mechanisms for one
meaning is how a reader learns to check only the one they remember.

**Validity is computed, never asserted.** A record carries the facts; a
later pass reads them and decides whether the run was valid. That is why
:class:`Validity` has no member meaning "not yet computed" — absence is
``None``, and an absence that is spellable as a value is a value somebody
will eventually set by hand.
"""

from __future__ import annotations

import datetime
import json
import math
from enum import StrEnum, unique
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────────────────────────────
# Execution vocabularies — permanent, append-only, never renamed
# ─────────────────────────────────────────────────────────────────────


@unique
class MeasurementRoute(StrEnum):
    """How the measurement reached the model.

    A comparability blocker: two numbers taken by different routes may be
    read side by side and **never differenced**. A research shim measures
    a different system than the product does, and laundering the two
    together is how a shim's number becomes a product claim.
    """

    #: The path a customer request takes — the runtime's public binding at
    #: minimum, with the hosted artifact verified against live `/info`.
    PRODUCT_PATH = "product_path"
    #: A shim: in-process engine call, a branch-exported manifest, a route
    #: that was never shipped. Legitimate, and labelled rather than hidden.
    RESEARCH_HARNESS = "research_harness"


@unique
class LanguageMode(StrEnum):
    """Whether the request declared a language or the engine guessed.

    A first-order *cost* variable, not a detail: on our own hardware,
    declaring `hi` cost 13698 ms against 1462 ms for `en` on identical
    audio. It is also the live divergence between our two harnesses — the
    quality pass declares a language per clip and the production ladder
    sends none — so a record that cannot state its mode cannot be read
    against the other half of its own session.
    """

    EXPLICIT = "explicit"
    AUTO = "auto"


@unique
class EmittedUnit(StrEnum):
    """The granularity the model emits. Recorded, never used to select a metric.

    Metric primacy is fixed per (language, corpus version) and never per
    candidate: a rule that chose the headline metric from a candidate's
    own granularity would let ruler choice decide a switching test. This
    field exists so a reader can *interpret* a character-emitting model's
    word error rate, not so the harness can pick a kinder ruler for it.

    There is no ``token`` member and never will be: a token count is a
    property of one tokenizer and is not comparable across candidates.
    """

    WORD = "word"
    CHARACTER = "character"
    BYTE = "byte"


@unique
class VadOwner(StrEnum):
    """Which component decided there was speech.

    This changes what a probe measures. Our own zero-hallucination result
    was obtained *structurally* — the pipeline's VAD short-circuits before
    the engine runs — so a product-path silence probe measures the
    pipeline, not the engine. A candidate that bundles its own VAD is a
    different measured system wearing the same name.
    """

    PIPELINE = "pipeline"
    ENGINE = "engine"
    NONE = "none"


@unique
class TimestampSource(StrEnum):
    """Where timestamps came from, when the measured system produced any.

    This records what the *system emitted*, which is not the same as what
    the record kept. Our transcription engine emits native segment
    timestamps on every request and the harness currently reads only the
    text — so the honest value is ``NATIVE`` plus a :class:`Determination`
    recording that they were not measured. Writing ``NONE`` would say the
    engine produced nothing, which is false.

    Presence is recordable; *quality* is not. No alignment metric family
    exists, and this field is not a licence to invent one.
    """

    NONE = "none"
    NATIVE = "native"
    AUXILIARY_MODEL = "auxiliary_model"
    DERIVED = "derived"


@unique
class Validity(StrEnum):
    """Whether a record's numbers can mean what they claim.

    Computed from recorded facts by a later pass — never asserted by the
    thing being judged. Nobody "invalidates" a record: an invalid run is
    still written, with the failing condition named, because deleting
    evidence is worse than keeping evidence that says it is wrong.

    Deliberately **no** member for "not computed". That state is ``None``
    on the field. An absence spelled as a value is a value somebody sets.
    """

    VALID = "valid"
    #: Measured less than planned. Citable for what it contains, and it
    #: may never be named a baseline.
    INCOMPLETE = "incomplete"
    #: A validity condition is violated. Written anyway, and marked.
    INVALID = "invalid"


# ─────────────────────────────────────────────────────────────────────
# Determination — absence recorded as evidence
# ─────────────────────────────────────────────────────────────────────


@unique
class DeterminationState(StrEnum):
    """Why a fact is not a number."""

    #: The system cannot do this at all (a candidate that emits no timestamps).
    NOT_SUPPORTED = "not_supported"
    #: It could have been measured and was not (an instrument we lack today).
    NOT_MEASURED = "not_measured"
    #: It cannot be established from where we stand (a counter the device
    #: does not expose).
    UNDETERMINABLE = "undeterminable"


@unique
class Authorship(StrEnum):
    """What kind of author established this determination.

    **Roles, not teams.** An earlier draft used `engineering` / `research`
    — the groups that happen to exist today. A record outlives the org
    chart that produced it, and a reader in five years needs to know what
    *kind* of statement they are holding, not which department was called
    what in 2026. These three distinctions survive any reorganisation:
    a machine observed it, the person running the measurement stated it,
    or the person reading the evidence afterwards concluded it.

    Enumerated rather than free text because the separation is
    load-bearing: whoever reads evidence afterwards may **append**
    determinations and may never revoke a measurement. A field recording
    which kind of author spoke is what makes that checkable rather than
    procedural.
    """

    #: The instrument recorded it, without a human in the loop.
    HARNESS = "harness"
    #: Stated by whoever executed the run — facts about the machine and
    #: the session that no instrument could read.
    OPERATOR = "operator"
    #: Concluded by whoever read the evidence afterwards. May append; may
    #: never revoke a measurement.
    REVIEWER = "reviewer"


@unique
class Basis(StrEnum):
    """How strongly this determination is held.

    Three-valued, matching the labels the research framework already uses
    throughout its gates. A vendor's assertion is a CLAIM — not something
    we verified, and not our reasoning either. Two-valued would force
    every unverified external statement to be mislabelled as one or the
    other.
    """

    FACT = "fact"
    CLAIM = "claim"
    INFERENCE = "inference"


class Determination(BaseModel):
    """A dated statement that something is not a measurement.

    The mechanism for "the candidate emits no timestamps" or "this device
    exposes no memory counter": carried **with** the record, never as a
    missing field and never as a zero. A zero is a measurement of nothing;
    this says why there is no measurement at all.
    """

    model_config = ConfigDict(frozen=True)

    #: Stable identifier, e.g. "timestamps_not_retained". Free-form on
    #: purpose: the space of things that can be absent grows faster than
    #: any enum, and unlike a metric name this is read rather than joined.
    code: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    state: DeterminationState
    authored_by: Authorship
    basis: Basis
    detail: str = Field(min_length=1)
    source: str | None = None
    #: Determinations decay, exactly as licence verdicts do. A reader five
    #: years out needs to know when this was last true.
    verified_on: datetime.date


# ─────────────────────────────────────────────────────────────────────
# Identities — the machine, the deployment, the stack
# ─────────────────────────────────────────────────────────────────────


class ArtifactRef(BaseModel):
    """An artifact that is part of the measured system but is not the subject.

    An auxiliary alignment model is measured whether or not anyone meant
    to measure it, so it is identified, pinned and licence-verified like
    any other artifact rather than living in a footnote.
    """

    model_config = ConfigDict(frozen=True)

    artifact: str = Field(min_length=1)
    version: int = Field(ge=1)
    role: str = Field(min_length=1)  # e.g. "forced_alignment"
    sha256: str | None = None


class AcceleratorIdentity(BaseModel):
    """A GPU, NPU, ASIC — or nothing.

    Deliberately not CUDA-shaped. An all-required block of `vram_mib` /
    `compute_capability` / `driver_version` cannot be filled honestly by a
    device with unified memory or no compute-capability analogue, and
    under such a schema every measurement on one would be automatically
    incomplete **because of a field shape rather than anything about the
    measurement**.
    """

    model_config = ConfigDict(frozen=True)

    device_class: str = Field(min_length=1)  # gpu | npu | asic | none
    device_model: str = Field(min_length=1)
    device_count: int = Field(ge=0)
    #: ``None`` where memory is unified — genuinely not applicable, which
    #: is different from unreadable and does not degrade completeness.
    device_memory_mib: int | None = None
    driver_or_runtime: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)


class EnvironmentIdentity(BaseModel):
    """The machine a measurement was taken on.

    **Every field is optional, and that is not laziness.** This milestone
    lands the structure; nothing populates it. A field that cannot be
    obtained honestly stays ``None`` and is explained by a
    :class:`Determination` on the record — which is why there is no
    `unknown_fields` list here.

    **Whose machine?** The harness talks to a runtime over HTTP, so facts
    read from the harness's own process describe the *harness host*, which
    is the right answer only when the runtime is local and native. Our own
    committed evidence already spans both cases: the quality records were
    taken "native" and the production ladder under Docker Desktop/WSL2, on
    one physical machine. ``observed_from`` records which, in prose,
    because the honest fix is the runtime reporting its own environment
    and that is a runtime change rather than a vocabulary.
    """

    model_config = ConfigDict(frozen=True)

    # ── Compute ─────────────────────────────────────────────────────
    cpu_model: str | None = None
    #: Physical cores, never logical threads: SMT siblings share execution
    #: units and inflate the count without adding throughput, and on a
    #: hybrid part the efficiency cores are a straggler class inside
    #: barrier-synchronised regions.
    cpu_physical_cores: int | None = None
    cpu_logical_threads: int | None = None
    cpu_base_clock_mhz: int | None = None
    cpu_boost_clock_mhz: int | None = None

    # ── Memory and storage ──────────────────────────────────────────
    ram_total_mib: int | None = None
    ram_type: str | None = None
    storage_class: str | None = None  # nvme_ssd | sata_ssd | hdd | network

    # ── Accelerator ─────────────────────────────────────────────────
    accelerator: AcceleratorIdentity | None = None

    # ── Threading and numerics ──────────────────────────────────────
    #: The field most often forgotten. CPU recognition throughput is
    #: strongly thread-sensitive, so a CPU benchmark without it is not
    #: reproducible — and the numbers that matter are the *runtime's*,
    #: which the harness cannot read from its own environment.
    thread_config: dict[str, int] = Field(default_factory=dict)
    blas_backend: str | None = None
    #: Declared, not read: the runtime does not surface it at `/info`
    #: today. That is a Rule LF violation with a scheduled fix, recorded
    #: here rather than papered over.
    compute_type: str | None = None

    # ── Machine state ───────────────────────────────────────────────
    virtualisation: str | None = None  # bare_metal | vm | container | cloud
    power_profile: str | None = None
    #: Asserted by an operator, never assumed. A machine that was busy
    #: produces real numbers about a machine that was busy.
    otherwise_idle: bool | None = None

    # ── Era ─────────────────────────────────────────────────────────
    #: The coarse label a comparability check blocks on, e.g.
    #: `cpu-x86-consumer-2026`. Left ``None`` until the founder ratifies
    #: the reference machine: the one machine we own is already spelled
    #: four ways across committed records, and a default here would make a
    #: fifth canonical by accident.
    hardware_class: str | None = None

    #: Whose machine these facts describe.
    #:
    #: A controlled vocabulary rather than prose, because it is the answer
    #: to a correctness question and a reader must not have to parse a
    #: sentence to get it. A `Literal` rather than a new enum, because the
    #: distinction is local to this one field and does not deserve a
    #: permanent type in the vocabulary namespace — and because widening a
    #: Literal later is purely additive, while renaming an enum member is
    #: forbidden.
    #:
    #: - ``harness``  — read from the harness's own process. Correct only
    #:   when the runtime is local and native; under a container the CPU
    #:   count reflects a cgroup and the thread variables are the wrong
    #:   process's.
    #: - ``runtime``  — reported by the runtime about itself. The honest
    #:   answer, and not yet available: `/info` does not expose it.
    observed_from: Literal["harness", "runtime"] | None = None


class DeploymentIdentity(BaseModel):
    """How the measured service was configured to accept work.

    Pool configuration is self-described at `/info`, so a harness reads it
    rather than accepting it as a flag: a hand-typed value the system
    already knows is a transcription error waiting to be committed.
    """

    model_config = ConfigDict(frozen=True)

    topology: str | None = None  # container | native | gateway_fronted
    max_concurrency: int | None = None
    max_queue: int | None = None
    resource_limits: dict[str, str] = Field(default_factory=dict)
    gateway_present: bool | None = None


class StackIdentity(BaseModel):
    """The serving software the artifact ran under.

    Free strings, deliberately. The candidate universe already spans
    CTranslate2, GGUF, ONNX Runtime, transformers, PEFT, NeMo, vLLM,
    fairseq2 and MLX; three fixed fields cannot describe that space and an
    enum would be obsolete within a year. The ban on free-form identifiers
    protects *metric names*, whose comparability depends on exact
    matching. A stack label is metadata a human reads.
    """

    model_config = ConfigDict(frozen=True)

    serving_stack: str | None = None
    engine_module: str | None = None
    quantization: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────
# ExecutionContext — one container, not four loose fields
# ─────────────────────────────────────────────────────────────────────


class ExecutionContext(BaseModel):
    """Everything about *how* a run was executed, in one place.

    One container rather than a dozen fields scattered across the record,
    because four independent designs each wanted to claim the bare name
    ``conditions`` on the run — and a collision in a permanent schema
    cannot be cleaned up later.

    **The required fields have no defaults on purpose.** A run's route,
    ruler, language, granularity, VAD ownership, timestamp source and
    decode configuration are all known to whatever is writing the record.
    A default would let a half-stated context be constructed silently, and
    an underspecified benchmark must be unconstructible rather than
    quietly plausible.

    **The nullable fields are nullable because nothing can fill them yet.**
    A context whose ``environment`` is ``None`` is real and recordable; it
    is simply *incomplete*, and the validity pass says so. The schema
    permits it and the verdict judges it — validity is computed from
    recorded facts, never enforced by a constructor.
    """

    model_config = ConfigDict(frozen=True)

    # ── Required: facts the writer always knows ─────────────────────
    route: MeasurementRoute
    #: The ruler, as a record cites it: ``name@vN``. A metric name says how
    #: two token sequences were compared; this says what a token was.
    normalization: str = Field(min_length=1)
    declared_language: str = Field(min_length=1)
    language_mode: LanguageMode
    emitted_unit: EmittedUnit
    vad_owner: VadOwner
    #: What the system emitted — never ``NONE`` merely because the harness
    #: discarded them. Non-retention is a Determination.
    timestamp_source: TimestampSource
    #: The decode configuration actually in force, **including values that
    #: came from library defaults**. An empty dict asserts that no decode
    #: configuration was active, which has never once been true: our
    #: engine runs under a beam search, a best-of, a temperature ladder and
    #: previous-text conditioning that we never set and could be changed by
    #: a dependency upgrade with no diff anywhere in this repository.
    decode_params: dict[str, str]

    # ── Nullable: no capture path exists yet ────────────────────────
    environment: EnvironmentIdentity | None = None
    deployment: DeploymentIdentity | None = None
    stack: StackIdentity | None = None

    # ── Additive ────────────────────────────────────────────────────
    auxiliary_artifacts: tuple[ArtifactRef, ...] = ()
    seed: int | None = None


# ─────────────────────────────────────────────────────────────────────
# Production ladder records — relocated, unchanged
# ─────────────────────────────────────────────────────────────────────
#
# These moved here from bench.py and bench_tts.py so that reading a
# committed ladder does not require httpx to be installable. Only the pure
# record types and the pure percentile function moved; the async request
# machinery and the docker sampler stayed with the code that runs them.


def nearest_rank(sorted_values: list[float], percentile: float) -> float:
    """Deterministic nearest-rank percentile over a pre-sorted sample.

    Ceiling-based with no interpolation, so two runs over the same data
    agree to the digit — and so that at n=3 or n=10 the "p95" **is the
    maximum**. Below 20 successful samples, report the maximum and call it
    the maximum.
    """
    if not sorted_values:
        raise ValueError("empty sample")
    rank = max(1, math.ceil(percentile * len(sorted_values)))
    return sorted_values[rank - 1]


class RequestSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    status: int
    client_ms: float
    runtime_total_ms: float | None = None
    stages_ms: dict[str, float] = {}


class LevelResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    concurrency: int
    requests: int
    succeeded: int
    overloaded: int
    other_errors: int
    wall_seconds: float
    p50_ms: float | None
    p95_ms: float | None
    throughput_rps: float
    mean_rtf: float | None
    max_pool_admitted: int | None = None
    docker_cpu_percent_max: float | None = None
    docker_memory_mib_max: float | None = None


class OverheadResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    direct_p50_ms: float
    via_gateway_p50_ms: float
    gateway_overhead_ms: float
    inference_p50_ms: float
    overhead_fraction_of_inference: float


class BenchReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    clip: str
    clip_seconds: float
    repetitions_per_worker: int
    hardware: str
    notes: str = ""
    levels: list[LevelResult]
    overhead: OverheadResult | None = None
    prd_p95_target_ms: float
    #: A known misnomer in the committed records: it was populated from a
    #: p50 of an n=10 probe. Kept verbatim rather than renamed, because a
    #: released record's fields mean what they meant when it was written.
    #: Fixed forward in new records, never by editing old ones.
    prd_p95_actual_ms: float | None
    prd_verdict: str


class TtsSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    status: int
    client_ms: float
    synthesis_ms: float | None = None
    audio_seconds: float | None = None


def sample_from_response(status: int, envelope_header: str | None, client_ms: float) -> TtsSample:
    """Pure parser: HTTP facts -> one sample (testable without a socket)."""
    if status != 200:
        return TtsSample(ok=False, status=status, client_ms=client_ms)
    synthesis_ms: float | None = None
    audio_seconds: float | None = None
    if envelope_header is not None:
        try:
            envelope = json.loads(envelope_header)
            stages = envelope.get("timing", {}).get("stages", {})
            raw = stages.get("synthesis")
            synthesis_ms = float(raw) if raw is not None else None
            audio_seconds = float(envelope["output"]["duration_seconds"])
        except (ValueError, KeyError, TypeError):
            synthesis_ms = None
            audio_seconds = None
    return TtsSample(
        ok=True,
        status=200,
        client_ms=client_ms,
        synthesis_ms=synthesis_ms,
        audio_seconds=audio_seconds,
    )


class TtsBenchReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    characters: int
    audio_seconds: float | None
    repetitions_per_worker: int
    hardware: str
    notes: str = ""
    levels: list[LevelResult]
    overhead: OverheadResult | None = None
    prd_ttfb_target_ms: float
    prd_ttfb_actual_ms: float | None
    prd_verdict: str
