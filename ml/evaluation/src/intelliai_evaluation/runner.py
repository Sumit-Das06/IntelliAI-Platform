"""STT evaluation runner: measure a LIVE runtime, exactly as customers use it.

Deliberately end-to-end over the runtime's HTTP binding: the number we
record is the number the product produces — pipeline, VAD short-circuit,
and engine together. Per-clip inference time comes from the runtime's own
timing stages, so RTF is engine inference over audio duration, not network
time.

**Route-aware since M5 step 4.** A run measures one *slice*: one public
model, one language, and the artifact the registry resolved for that pair.
The runner is handed that resolution — it never chooses an artifact, and
it refuses to run against a runtime that is not actually hosting the one
it was told to measure. A record that misnames its subject is worse than
no record.

**An honest evidence writer since B4b.** Every value written into an
`ExecutionContext` is Observed, Derived, or accompanied by a
Determination — the classification law in `evidence`. Nothing is guessed,
and nothing is typed by an operator that the runtime already knows: the
build, the decode configuration, the granularity, the VAD owner and the
machine are all read from `/info`, and the CLI has no flag for any of
them.

**This module writes evidence and never interprets it.** It computes no
validity verdict. A run cannot: two of the ten conditions are
session-level and one has no field on any schema. Interpretation belongs
to a later pass, reading what is recorded here.

**Failures are evidence.** A clip that errors is recorded with whatever it
managed to measure, and the run continues. Before this the runner called
`raise_for_status()`, so one HTTP error aborted everything — which meant
the hypotheses whose expected outcome is "the candidate does not run at
all" were exactly the ones the harness could not record.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from intelliai_evaluation.accuracy import RulerFailureError, hallucinated_words, score, wer_ascii
from intelliai_evaluation.dataset import EvalClip, EvalDataset
from intelliai_evaluation.evidence import (
    Authorship,
    Basis,
    DeploymentIdentity,
    Determination,
    DeterminationState,
    EmittedUnit,
    EnvironmentIdentity,
    ExecutionContext,
    LanguageMode,
    MeasurementRoute,
    TimestampSource,
    VadOwner,
)
from intelliai_evaluation.fetch import materialize_clips
from intelliai_evaluation.identity import EvaluationIdentity, SliceCoverage
from intelliai_evaluation.normalization import NormalizationProfile, profile_for
from intelliai_evaluation.resolution import ResolvedServing
from intelliai_evaluation.results import ClipResult, EvalRun
from intelliai_evaluation.runtime_info import ModelInfo, RuntimeInfo
from intelliai_evaluation.wer import WerBreakdown
from intelliai_runtime_contract import RuntimeResponse, TranscriptionResult

_TRANSCRIBE_ROUTE = "/v1/transcribe"
_INFO_ROUTE = "/info"

#: "No linguistic content". A clip so labelled carries no language on the
#: request, which is what makes such a slice auto-detected rather than
#: explicitly declared.
_NO_LINGUISTIC_CONTENT = "zxx"

#: The English transition anchor. §4.1 records `wer_ascii` alongside the
#: Unicode ruler for English only, so the 2026-08-03 baseline stays
#: comparable while the primary metric moves.
_ASCII_ANCHOR_LANGUAGE = "en"


class ArtifactNotHostedError(RuntimeError):
    """The runtime is not serving the artifact this run is supposed to measure."""


class RuntimeNotDescribedError(RuntimeError):
    """`/info` did not describe the artifact well enough to record a benchmark.

    An under-specified execution context must be unconstructible rather
    than plausible: a record that cannot state its own build or decode
    configuration is not a benchmark, and writing one anyway would put an
    unfalsifiable number into an append-only ledger.
    """


def read_info(client: httpx.Client) -> RuntimeInfo:
    """The observation basis for the whole run, captured once.

    Once, deliberately: `/info` is lifetime-stable by law, so re-reading
    it per clip could only introduce disagreement between fields of one
    record without adding a single fact.
    """
    response = client.get(_INFO_ROUTE)
    response.raise_for_status()
    return RuntimeInfo.model_validate(response.json())


def require_hosted(info: RuntimeInfo, artifact: str) -> ModelInfo:
    """Reproducibility metadata comes from LIVE facts, never operator claims.

    If the runtime is not hosting what the registry resolved, the run
    would record a measurement of something else under this artifact's
    name.
    """
    hosted = info.model_for(artifact)
    if hosted is None:
        msg = (
            f"runtime hosts {sorted(info.hosted())}, not {artifact!r}; "
            "refusing to record a misnamed run"
        )
        raise ArtifactNotHostedError(msg)
    return hosted


def language_slice(dataset: EvalDataset, language: str) -> list[EvalClip]:
    """The clips this slice measures — exactly those declaring the language.

    No widening: a `hi` run does not silently include language-less
    probes, because the record's identity says `hi` and a reader is
    entitled to believe it.
    """
    return [clip for clip in dataset.clips if clip.language == language]


def slice_coverage(clips: list[EvalClip], breakdowns: list[ClipResult]) -> SliceCoverage:
    """What this slice contains, so the record cannot overstate itself."""
    natural = sum(1 for clip in clips if clip.synthetic is None and clip.reference_text)
    return SliceCoverage(
        clips=len(clips),
        natural_speech_clips=natural,
        probe_clips=sum(1 for clip in clips if clip.synthetic is not None),
        reference_words=sum(result.reference_words for result in breakdowns),
    )


@dataclass
class _Observation:
    """What one clip contributed, kept apart from the record it becomes.

    Aggregates are word- and duration-weighted, so they need the raw
    breakdowns rather than the per-clip ratios: a mean of ratios silently
    over-weights short clips — by 11-33% on our own committed records.
    """

    duration_seconds: float
    words: WerBreakdown | None = None
    characters: WerBreakdown | None = None
    ascii_words: WerBreakdown | None = None
    probe_words: int | None = None
    inference_seconds: float | None = None
    segments: int = 0
    produced_text: bool = False


@dataclass
class _Ledger:
    """Determinations accumulated while measuring, in the order they arose."""

    run_at: datetime.datetime
    entries: list[Determination] = field(default_factory=list)

    def record(self, *, code: str, subject: str, state: DeterminationState, detail: str) -> None:
        self.entries.append(
            Determination(
                code=code,
                subject=subject,
                state=state,
                # The instrument observed this, with no human in the loop.
                authored_by=Authorship.HARNESS,
                basis=Basis.FACT,
                detail=detail,
                verified_on=self.run_at.date(),
            )
        )


def run_stt_eval(
    dataset: EvalDataset,
    *,
    base_url: str,
    data_dir: Path,
    public_model: str,
    language: str,
    serving: ResolvedServing,
    engine: str,
    benchmark: str | None = None,
    session_id: str | None = None,
    notes: str = "",
    extra_determinations: tuple[Determination, ...] = (),
) -> EvalRun:
    """Measure one slice against the artifact the registry resolved for it.

    ``extra_determinations`` lets the SESSION layer contribute statements
    the instrument cannot make itself — the operator's idleness assertion
    is the canonical case: authored by a person, held as a claim. The
    runner appends them verbatim; it never authors on their behalf.
    """
    if serving.artifact is None or serving.artifact_version is None:  # pragma: no cover
        msg = "an unserved route has nothing to evaluate"
        raise ValueError(msg)
    clips = language_slice(dataset, language)
    if not clips:
        msg = f"dataset {dataset.name}@v{dataset.version} has no {language!r} clips"
        raise ValueError(msg)

    # Refuses rather than defaulting. A language with no ruler cannot be
    # measured, and borrowing another language's is exactly how a
    # Devanagari reference gets scored by an ASCII ruler and committed.
    profile = profile_for(language)

    run_at = datetime.datetime.now(tz=datetime.UTC)
    ledger = _Ledger(run_at=run_at)
    # The SLICE, not the dataset: a hi session must not download
    # English audio it will never send.
    paths = materialize_clips(clips, data_dir)

    with httpx.Client(base_url=base_url, timeout=300) as client:
        info = read_info(client)
        hosted = require_hosted(info, serving.artifact)
        results, observations = _measure(
            client, clips, serving.artifact, profile, language, paths, ledger
        )

    execution = _execution_context(
        info=info,
        hosted=hosted,
        profile=profile,
        language=language,
        public_model=public_model,
        observations=observations,
        ledger=ledger,
    )
    build = execution.environment.compute_type if execution.environment else None
    if build is None:  # pragma: no cover - _execution_context refuses first
        msg = "the runtime described no build"
        raise RuntimeNotDescribedError(msg)

    return EvalRun(
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        capability=dataset.capability,
        # Stamped once and reused: the record's two timestamps used to be
        # two separate `now()` calls, which could disagree.
        run_at=run_at,
        artifact=serving.artifact,
        engine=engine,
        engine_version=_engine_version(info, engine, ledger),
        compute=build,
        hardware=_hardware_line(info),
        notes=notes,
        clips=results,
        load_ms=hosted.load_ms,
        warmup_ms=hosted.warmup_ms,
        identity=EvaluationIdentity(
            public_model=public_model,
            language=language,
            artifact=serving.artifact,
            artifact_version=serving.artifact_version,
            build=build,
            deployment=serving.deployment or "unknown",
            dataset=dataset.name,
            dataset_version=dataset.version,
            benchmark=benchmark,
            # Transcription's judge is the dataset's own reference text,
            # which `dataset@version` already names — no model judged here.
            judge=None,
            run_at=run_at,
        ),
        coverage=slice_coverage(clips, results),
        execution=execution,
        determinations=tuple(ledger.entries) + extra_determinations,
        metrics=_aggregate(observations),
        # Evidence only. Validity is an interpretation, made later.
        validity=None,
        session_id=session_id,
        methodology_version=None,
    )


def _measure(
    client: httpx.Client,
    clips: list[EvalClip],
    artifact: str,
    profile: NormalizationProfile,
    language: str,
    paths: dict[str, Path],
    ledger: _Ledger,
) -> tuple[list[ClipResult], list[_Observation]]:
    """One pass over the slice, in fixed manifest order."""
    results: list[ClipResult] = []
    observations: list[_Observation] = []
    for clip in clips:
        observation = _Observation(duration_seconds=clip.duration_seconds)
        params: dict[str, str] = {"model": artifact}
        if clip.language != _NO_LINGUISTIC_CONTENT:
            params["language"] = clip.language

        audio_path = paths[clip.id]
        try:
            response = client.post(
                _TRANSCRIBE_ROUTE,
                files={"file": (audio_path.name, audio_path.read_bytes(), "audio/wav")},
                data={"params": json.dumps(params)},
            )
        except httpx.HTTPError as exc:
            results.append(_failed(clip, f"transport: {type(exc).__name__}"))
            observations.append(observation)
            continue
        if response.status_code != 200:
            results.append(_failed(clip, f"runtime: HTTP {response.status_code}"))
            observations.append(observation)
            continue

        envelope = RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
        observation.inference_seconds = _inference_seconds(envelope, clip, ledger)
        observation.segments = len(envelope.output.segments)
        observation.produced_text = bool(envelope.output.text.strip())
        results.append(_scored(clip, envelope, profile, language, observation, ledger))
        observations.append(observation)
    return results, observations


def _failed(clip: EvalClip, reason: str) -> ClipResult:
    """A clip that produced nothing, recorded rather than aborting the run."""
    return ClipResult(
        clip_id=clip.id,
        duration_seconds=clip.duration_seconds,
        inference_seconds=0.0,
        substitutions=0,
        insertions=0,
        deletions=0,
        reference_words=0,
        hypothesis_words=0,
        hypothesis_text="",
        failure=reason,
    )


def _inference_seconds(
    envelope: RuntimeResponse[TranscriptionResult], clip: EvalClip, ledger: _Ledger
) -> float | None:
    """The engine's own timing, or nothing — never a zero.

    A missing stage used to default to 0.0, which reads as infinite speed
    and would silently improve every real-time factor it touched.
    """
    stage = envelope.timing.stages.get("inference")
    if stage is None:
        ledger.record(
            code="inference_stage_missing",
            subject=f"clip {clip.id}",
            state=DeterminationState.NOT_MEASURED,
            detail="the runtime reported no `inference` timing stage; a zero here would "
            "read as infinite speed and distort recognition_rtf",
        )
        return None
    return float(stage) / 1000.0


def _scored(
    clip: EvalClip,
    envelope: RuntimeResponse[TranscriptionResult],
    profile: NormalizationProfile,
    language: str,
    observation: _Observation,
    ledger: _Ledger,
) -> ClipResult:
    """Score one clip under the slice's ruler."""
    hypothesis = envelope.output.text
    metrics: dict[str, float] = {}
    breakdown: WerBreakdown | None = None

    if clip.reference_text:
        try:
            scores = score(clip.reference_text, hypothesis, profile)
        except RulerFailureError as exc:
            ledger.record(
                code="ruler_erased_reference",
                subject=f"clip {clip.id}",
                state=DeterminationState.UNDETERMINABLE,
                detail=str(exc),
            )
        else:
            breakdown = scores.words
            observation.words = scores.words
            observation.characters = scores.characters
            metrics = {
                "wer_unicode": scores.wer,
                "cer_unicode": scores.cer,
                "substitution_rate": scores.substitution_rate,
                "insertion_rate": scores.insertion_rate,
                "deletion_rate": scores.deletion_rate,
                "excess_word_ratio": scores.excess_word_ratio,
            }
            if language == _ASCII_ANCHOR_LANGUAGE:
                anchor = wer_ascii(clip.reference_text, hypothesis)
                observation.ascii_words = anchor
                metrics["wer_ascii"] = anchor.wer
    else:
        emitted = hallucinated_words(
            declared_reference=clip.reference_text, hypothesis=hypothesis, profile=profile
        )
        observation.probe_words = emitted
        metrics = {"hallucinated_words": float(emitted)}

    if observation.inference_seconds is not None and clip.duration_seconds > 0:
        metrics["recognition_rtf"] = observation.inference_seconds / clip.duration_seconds

    return ClipResult(
        clip_id=clip.id,
        duration_seconds=clip.duration_seconds,
        inference_seconds=observation.inference_seconds or 0.0,
        substitutions=breakdown.substitutions if breakdown else 0,
        insertions=breakdown.insertions if breakdown else 0,
        deletions=breakdown.deletions if breakdown else 0,
        reference_words=breakdown.reference_words if breakdown else 0,
        hypothesis_words=breakdown.hypothesis_words
        if breakdown
        else len(profile.words(hypothesis)),
        hypothesis_text=hypothesis,
        metrics=metrics,
    )


def _aggregate(observations: list[_Observation]) -> dict[str, float]:
    """Slice-level numbers, weighted by their own denominators.

    Word-weighted for the accuracy family and duration-weighted for the
    real-time factor, never a mean of per-clip ratios: mean-of-rates
    destroys additivity and over-weights short clips.
    """
    metrics: dict[str, float] = {}

    words = [o.words for o in observations if o.words is not None]
    reference_total = sum(b.reference_words for b in words)
    if reference_total:
        metrics["wer_unicode"] = sum(b.errors for b in words) / reference_total
        metrics["substitution_rate"] = sum(b.substitutions for b in words) / reference_total
        metrics["insertion_rate"] = sum(b.insertions for b in words) / reference_total
        metrics["deletion_rate"] = sum(b.deletions for b in words) / reference_total
        excess = sum(max(0, b.hypothesis_words - b.reference_words) for b in words)
        metrics["excess_word_ratio"] = excess / reference_total

    ascii_words = [o.ascii_words for o in observations if o.ascii_words is not None]
    ascii_total = sum(b.reference_words for b in ascii_words)
    if ascii_total:
        metrics["wer_ascii"] = sum(b.errors for b in ascii_words) / ascii_total

    characters = [o.characters for o in observations if o.characters is not None]
    character_total = sum(b.reference_words for b in characters)
    if character_total:
        metrics["cer_unicode"] = sum(b.errors for b in characters) / character_total

    probes = [o.probe_words for o in observations if o.probe_words is not None]
    if probes:
        metrics["hallucinated_words"] = float(sum(probes))

    timed = [o for o in observations if o.inference_seconds is not None]
    audio = sum(o.duration_seconds for o in timed)
    if timed and audio > 0:
        metrics["recognition_rtf"] = sum(o.inference_seconds or 0.0 for o in timed) / audio
    return metrics


def _execution_context(
    *,
    info: RuntimeInfo,
    hosted: ModelInfo,
    profile: NormalizationProfile,
    language: str,
    public_model: str,
    observations: list[_Observation],
    ledger: _Ledger,
) -> ExecutionContext:
    """Assemble what the run can honestly say about how it executed."""
    if hosted.decode_params is None or hosted.compute_type is None:
        msg = (
            f"the runtime does not describe {hosted.artifact!r}: a record that cannot "
            "state its own build or decode configuration is not a benchmark"
        )
        raise RuntimeNotDescribedError(msg)

    # Manifest provenance is a real question and it is NOT the route. The
    # exported manifest carries no identity metadata, so whether this
    # registry state was ever shipped cannot be established from the
    # record — and deriving it by comparing bytes against a file on disk
    # would depend on current filesystem state, which a Derived value may
    # never do.
    ledger.record(
        code="manifest_provenance_unverified",
        subject="resolution manifest",
        state=DeterminationState.UNDETERMINABLE,
        detail="the exported manifest carries no provenance metadata, so a reader cannot "
        "distinguish shipped registry state from a branch export",
    )
    ledger.record(
        code="stack_not_reported",
        subject="serving stack",
        state=DeterminationState.NOT_MEASURED,
        detail="the runtime reports no serving_stack or engine_module; a flag here would "
        "reintroduce the operator memory this milestone exists to remove",
    )

    return ExecutionContext(
        # Derived from evidence this run holds: the subject it resolved.
        # The research manifest namespaces every subject `research:` so no
        # entry can be mistaken for a product promise (B6) — the namespace
        # IS the manifest identity metadata, carried on the record itself,
        # so the derivation depends on no filesystem or registry state.
        # (The pre-B6 rationale here — "a research shim would have no
        # socket and no /info" — described a research route that no longer
        # exists: B6's research runtime has both, and hardcoding
        # PRODUCT_PATH mislabeled its evidence. Found by Stage 1 execution.)
        route=(
            MeasurementRoute.RESEARCH_HARNESS
            if public_model.startswith("research:")
            else MeasurementRoute.PRODUCT_PATH
        ),
        normalization=profile.id,
        declared_language=language,
        language_mode=_language_mode(language),
        emitted_unit=EmittedUnit(hosted.emitted_unit or EmittedUnit.WORD),
        vad_owner=VadOwner(info.vad_owner) if info.vad_owner else VadOwner.NONE,
        timestamp_source=_timestamp_source(observations, ledger),
        decode_params=dict(hosted.decode_params),
        environment=_environment(info, hosted, ledger),
        deployment=DeploymentIdentity(
            max_concurrency=info.pool.max_concurrency,
            max_queue=info.pool.max_queue,
            # Derived: this runner posts straight to the runtime binding.
            gateway_present=False,
        ),
        # Recorded above as a Determination rather than guessed.
        stack=None,
    )


def _language_mode(language: str) -> LanguageMode:
    """Derived from what the runner actually sends, not from intent.

    The language parameter goes on every clip whose language is not "no
    linguistic content", and `language_slice` matches exactly — so a slice
    is homogeneous by construction and this is a fact about the requests
    that were issued.
    """
    return LanguageMode.AUTO if language == _NO_LINGUISTIC_CONTENT else LanguageMode.EXPLICIT


def _timestamp_source(observations: list[_Observation], ledger: _Ledger) -> TimestampSource:
    """What the measured system emitted — three-way, because two would lie.

    "No segments" is ambiguous: an engine that emits none looks exactly
    like a clip that had nothing to segment. Our `hi` slice is precisely
    that case — two synthetic probes, both returning empty text — so
    writing NONE there would claim a capability absence on evidence that
    shows only silence.
    """
    if any(o.segments for o in observations):
        return TimestampSource.NATIVE
    if any(o.produced_text for o in observations):
        # It produced words and no timings: that is a real absence.
        return TimestampSource.NONE
    ledger.record(
        code="timestamp_source_undeterminable",
        subject="timestamps",
        state=DeterminationState.UNDETERMINABLE,
        detail="no clip in this slice produced any text, so an absence of segments cannot "
        "distinguish an engine that emits no timestamps from audio with nothing to segment",
    )
    return TimestampSource.NONE


def _environment(info: RuntimeInfo, hosted: ModelInfo, ledger: _Ledger) -> EnvironmentIdentity:
    """The machine, as the RUNTIME described it.

    `observed_from="runtime"` is the point of the whole B4a milestone:
    facts read from the harness's own process describe the harness's host,
    which is the right answer only when the runtime is local and native.
    """
    reported = info.environment
    for absent, why in _UNREPORTED_ENVIRONMENT:
        if absent not in reported:
            ledger.record(
                code=f"{absent}_unavailable",
                subject=f"environment.{absent}",
                state=DeterminationState.UNDETERMINABLE,
                detail=why,
            )
    if reported.get("hardware_class") is None:
        ledger.record(
            code="hardware_class_unruled",
            subject="environment.hardware_class",
            state=DeterminationState.NOT_MEASURED,
            detail="the reference machine has not been ratified, so no era label is "
            "recorded; performance comparability across machines stays ungated",
        )

    thread_env = reported.get("thread_env")
    return EnvironmentIdentity(
        cpu_model=_text(reported.get("cpu_model")),
        cpu_logical_threads=_whole(reported.get("cpu_logical_threads")),
        ram_total_mib=_whole(reported.get("ram_total_mib")),
        thread_config={k: int(v) for k, v in thread_env.items()}
        if isinstance(thread_env, dict)
        else {},
        compute_type=hosted.compute_type,
        hardware_class=_text(reported.get("hardware_class")),
        observed_from="runtime",
    )


#: Environment facts the runtime cannot read with the standard library, and
#: the reason each is absent. Recorded as Determinations rather than as
#: zeroes: a quietly wrong number is worse than a stated absence.
_UNREPORTED_ENVIRONMENT: tuple[tuple[str, str], ...] = (
    (
        "cpu_physical_cores",
        "physical core count needs a dependency the runtime deliberately does not carry; "
        "logical threads are reported instead and are not a substitute",
    ),
    (
        "ram_total_mib",
        "total memory is POSIX-only through the standard library; the Windows path would "
        "need a pointer cast that has already produced one silent zero here",
    ),
    (
        "thread_env",
        "no thread-pool variable is set in the runtime's environment, so the engine "
        "libraries defaulted internally - which is not the same as one thread",
    ),
)


def _engine_version(info: RuntimeInfo, engine: str, ledger: _Ledger) -> str:
    """Derived from the runtime's own installed packages, never typed.

    The engine *name* is still an argument — `/info` reports no
    engine_module — but its version is a fact the runtime holds, so an
    operator is never asked for it.
    """
    versions = info.environment.get("package_versions")
    if isinstance(versions, dict) and isinstance(versions.get(engine), str):
        return str(versions[engine])
    ledger.record(
        code="engine_version_unreported",
        subject=f"package {engine}",
        state=DeterminationState.NOT_MEASURED,
        detail=f"the runtime reports no installed version for {engine!r}, so the record "
        "cannot name the library build that produced these numbers",
    )
    return "unreported"


def _hardware_line(info: RuntimeInfo) -> str:
    """The legacy free-text machine description, now GENERATED.

    `EvalRun.hardware` predates structured environments and is required,
    so it cannot simply go. It is rendered from the observed facts instead
    of typed — which is what finally fixes the four different spellings of
    one machine across our committed records: nobody spells it any more.
    The structured truth lives in `execution.environment`.
    """
    reported = info.environment
    machine = _text(reported.get("cpu_model")) or _text(reported.get("machine")) or "unknown cpu"
    system = _text(reported.get("os_name")) or "unknown os"
    release = _text(reported.get("os_release")) or ""
    return f"{machine} · {system} {release}".strip()


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _whole(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
