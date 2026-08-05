"""Campaign and session execution — orchestration, never measurement.

A **campaign** names a measurement programme (`CAMP-STT-2026A`); a
**phase** names a stage of it with its own validity character (`PH0`
apparatus, `PH1` bridging, …); a **session** is the unit of reproducible
execution: one experiment, one language, preconditions checked at one
moment, emitting one or more evidence records that share one identity.

**Identity is permanent and names the experiment only** (founder ruling,
PH0 Amendment 1). Records cite their session forever in an append-only
ledger, so ids are validated at construction, never reused, and never
encode the artifact, deployment or route — those already live inside each
record's `ExecutionContext`, and an id that duplicated them would go
stale the day a session was re-pointed.

**This module decides whether measuring may START; the runner measures.**
Preconditions fail closed: a session that cannot prove its prerequisites
emits a refusal naming the precondition and produces nothing — never a
silent partial run. The runner underneath stays a dumb, honest sensor
that neither knows nor cares what a campaign is.

**Everything a session does is written down.** The session manifest
carries the spec verbatim, the runtime's `/info` verbatim (procedure
P-7), every precondition's outcome, the W1 warm-up timings (recorded and
excluded, never discarded — procedure §3), the operator's assertions, and
every record produced with its hash. "What happened in this session" is a
document, not a memory.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from intelliai_evaluation.dataset import EvalClip, find_dataset
from intelliai_evaluation.evidence import Authorship, Basis, Determination, DeterminationState
from intelliai_evaluation.fetch import materialize_clips
from intelliai_evaluation.metrics import METRICS, MetricNotRecordableError
from intelliai_evaluation.normalization import ProfileNotRegisteredError, profile_for
from intelliai_evaluation.resolution import UnservedError, load_manifest
from intelliai_evaluation.results import EvalRun
from intelliai_evaluation.runner import language_slice, run_stt_eval
from intelliai_evaluation.runtime_info import RuntimeInfo
from intelliai_runtime_contract import Capability

# ─────────────────────────────────────────────────────────────────────
# Identifier grammar — permanent once issued
# ─────────────────────────────────────────────────────────────────────

#: `CAMP-<discipline>-<year><series>`, e.g. CAMP-STT-2026A.
_CAMPAIGN = re.compile(r"^CAMP-[A-Z0-9]+-\d{4}[A-Z]$")
#: `PH<n>` — never bare `P<n>`, which collided with hardware profiles and
#: prerequisite items and was permanently disambiguated at Gate 4 v0.2.
_PHASE = re.compile(r"^PH\d+$")
#: `S<nn>-<slug>`: a two-digit ordinal and a concise experiment label.
#: The slug identifies the EXPERIMENT — never the artifact, deployment,
#: or route, which live in ExecutionContext.
_SESSION = re.compile(r"^S\d{2}-[a-z0-9][a-z0-9-]*$")


class SessionIdentityError(ValueError):
    """An identifier outside the permanent grammar. Refused at construction,
    because a malformed id that reaches a record is cited forever."""


@dataclass(frozen=True)
class SessionId:
    """One session's permanent identity: campaign / phase / session."""

    campaign: str
    phase: str
    session: str

    def __post_init__(self) -> None:
        for pattern, part, shape in (
            (_CAMPAIGN, self.campaign, "CAMP-<DISCIPLINE>-<year><series>"),
            (_PHASE, self.phase, "PH<n>"),
            (_SESSION, self.session, "S<nn>-<experiment-slug>"),
        ):
            if not pattern.match(part):
                raise SessionIdentityError(
                    f"{part!r} is outside the permanent identifier grammar ({shape}); "
                    "session ids are cited by append-only records and cannot be "
                    "corrected later"
                )

    @classmethod
    def parse(cls, text: str) -> SessionId:
        parts = text.split("/")
        if len(parts) != 3:
            raise SessionIdentityError(
                f"{text!r} is not <campaign>/<phase>/<session> (e.g. CAMP-STT-2026A/PH0/S01-en)"
            )
        return cls(campaign=parts[0], phase=parts[1], session=parts[2])

    def __str__(self) -> str:
        return f"{self.campaign}/{self.phase}/{self.session}"

    @property
    def file_stem(self) -> str:
        """The id as a filename component (slashes are path separators)."""
        return str(self).replace("/", "-")


# ─────────────────────────────────────────────────────────────────────
# Session specification — what research specifies, engineering executes
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SessionSpec:
    """The reviewable plan for one session. Data, not code.

    A spec is committed and reviewed before it is executed, which is what
    makes "research specifies, engineering executes" a file boundary
    rather than a habit.
    """

    session_id: SessionId
    #: The subject as the manifest names it: a product promise
    #: (`intelliai-stt`) against the production manifest, or a research
    #: subject (`research:whisper-base`) against the research one.
    public_model: str
    language: str
    dataset: str  # by IDENTITY, `name@vN` — never a filename
    manifest_path: Path
    runtime_url: str
    engine: str
    #: Procedure P-1: a session runs under a founder-approved plan. The
    #: reference is recorded verbatim; its truth is the founder's, not
    #: this module's — but a session that cannot even name its plan does
    #: not start.
    plan_reference: str
    #: Whether this session's evidence will be offered as a quality claim.
    #: Gates the §7.1 corpus-size floor (P-3). A smoke or apparatus
    #: session says false and is never citable as quality.
    quality_claim: bool = False
    #: Deterministic-correctness repetition (§5): 1 for a plain run, 2 to
    #: produce the same-identity replicate in the same session.
    runs: int = 1
    #: W1 session warm-up: requests over corpus-representative audio,
    #: recorded and excluded (§3). Zero is allowed only when the spec
    #: says so explicitly — silence is not a policy.
    warmup_requests: int = 3
    benchmark: str | None = None  # set ONLY when a run IS a named baseline
    notes: str = ""

    @classmethod
    def load(cls, path: Path) -> SessionSpec:
        document = json.loads(path.read_text(encoding="utf-8"))
        try:
            return cls(
                session_id=SessionId.parse(document["session_id"]),
                public_model=document["public_model"],
                language=document["language"],
                dataset=document["dataset"],
                manifest_path=Path(document["manifest"]),
                runtime_url=document["runtime_url"],
                engine=document["engine"],
                plan_reference=document["plan_reference"],
                quality_claim=bool(document.get("quality_claim", False)),
                runs=int(document.get("runs", 1)),
                warmup_requests=int(document.get("warmup_requests", 3)),
                benchmark=document.get("benchmark"),
                notes=document.get("notes", ""),
            )
        except KeyError as exc:
            raise PreconditionError(
                "spec", f"session spec {path} is missing required field {exc}"
            ) from exc

    @property
    def dataset_identity(self) -> tuple[str, int]:
        name, _, version = self.dataset.partition("@v")
        if not name or not version.isdigit():
            raise PreconditionError(
                "spec", f"dataset must be cited by identity `name@vN`, not {self.dataset!r}"
            )
        return name, int(version)


# ─────────────────────────────────────────────────────────────────────
# Fail-closed preconditions (procedure §2)
# ─────────────────────────────────────────────────────────────────────


class PreconditionError(RuntimeError):
    """A session prerequisite does not hold. Nothing is measured."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"[{code}] {detail}")
        self.code = code
        self.detail = detail


#: The metric names the recognition runner can emit. Checked recordable
#: BEFORE measuring (P-4): a withdrawal landing mid-campaign must stop
#: the next session at its gate, not crash it halfway through a slice.
_RUNNER_METRICS = (
    "wer_unicode",
    "cer_unicode",
    "substitution_rate",
    "insertion_rate",
    "deletion_rate",
    "excess_word_ratio",
    "wer_ascii",
    "hallucinated_words",
    "recognition_rtf",
)

#: §7.1: a quality claim for a language requires at least this many cases.
QUALITY_CLAIM_MINIMUM_CLIPS = 100


def check_preconditions(
    spec: SessionSpec, *, idle_asserted_by: str | None
) -> tuple[dict[str, str], Any, list[EvalClip], dict[str, Any]]:
    """Every prerequisite, or a refusal naming the first that fails.

    Returns the check log, the resolved serving, the slice, and the
    verbatim `/info` capture — everything execution needs, gathered once.
    """
    log: dict[str, str] = {}

    # P-1 — a session runs under a named, founder-approved plan.
    if not spec.plan_reference.strip():
        raise PreconditionError("P-1", "no plan_reference: a session runs under an approved plan")
    log["P-1"] = f"plan: {spec.plan_reference}"

    # P-9 — the machine is otherwise idle, asserted by a person, never
    # assumed (founder ruling: an operator assertion at session level).
    if not idle_asserted_by or not idle_asserted_by.strip():
        raise PreconditionError(
            "P-9",
            "machine idleness must be ASSERTED by a named operator "
            "(--assert-idle-by); it is never assumed",
        )
    log["P-9"] = f"otherwise idle, asserted by {idle_asserted_by}"

    # P-2 — the corpus, by identity, released and immutable; the slice
    # is real. Hash verification happens at materialization (every url
    # clip is sha256-pinned by schema).
    name, version = spec.dataset_identity
    try:
        dataset = find_dataset(Path("ml/evaluation/stt/datasets"), name, version)
    except FileNotFoundError as exc:
        raise PreconditionError("P-2", str(exc)) from exc
    if dataset.capability is not Capability.TRANSCRIPTION:
        raise PreconditionError("P-2", f"{spec.dataset} is not a transcription corpus")
    slice_clips = language_slice(dataset, spec.language)
    if not slice_clips:
        raise PreconditionError(
            "P-2", f"{spec.dataset} holds no {spec.language!r} clips; there is nothing to measure"
        )
    log["P-2"] = f"{spec.dataset} resolved by identity; slice has {len(slice_clips)} clip(s)"

    # P-3 — the corpus meets the floor for the claim being made.
    if spec.quality_claim:
        referenced = sum(1 for clip in slice_clips if clip.reference_text)
        if referenced < QUALITY_CLAIM_MINIMUM_CLIPS:
            raise PreconditionError(
                "P-3",
                f"a quality claim requires >= {QUALITY_CLAIM_MINIMUM_CLIPS} referenced "
                f"cases; this slice has {referenced}. Run it as a non-quality session "
                "or grow the corpus — never the claim.",
            )
        log["P-3"] = f"quality claim: {referenced} referenced clips"
    else:
        log["P-3"] = "no quality claim made; C1 floor (any size) applies"

    # P-4 — every metric this session can emit is registered and ACTIVE.
    try:
        for metric in _RUNNER_METRICS:
            METRICS.assert_recordable(metric, capability=Capability.TRANSCRIPTION)
    except MetricNotRecordableError as exc:
        raise PreconditionError("P-4", str(exc)) from exc
    log["P-4"] = f"{len(_RUNNER_METRICS)} runner metrics registered and ACTIVE"

    # P-5 — the language's ruler is registered. (Its control-string
    # round-trip is enforced by CI on every commit; a session executes on
    # a green tree.)
    try:
        profile = profile_for(spec.language)
    except ProfileNotRegisteredError as exc:
        raise PreconditionError("P-5", str(exc)) from exc
    log["P-5"] = f"ruler {profile.id} registered for {spec.language!r}"

    # Resolution — the subject must resolve in the DECLARED manifest
    # (production or research), under the same no-fallback law. A `zxx`
    # slice declares nothing per clip, so it resolves via the default
    # route, exactly as declaration-less requests do (PH0 F-2).
    routing_language = None if spec.language == "zxx" else spec.language
    try:
        serving = load_manifest(spec.manifest_path).resolve(spec.public_model, routing_language)
    except (UnservedError, FileNotFoundError) as exc:
        raise PreconditionError("resolution", str(exc)) from exc
    log["resolution"] = f"{spec.public_model} -> {serving.artifact}@v{serving.artifact_version}"

    # P-6 + P-7 + P-8 — the runtime is ready, self-describing, hosting
    # the resolved artifact with verified files, and its /info is
    # captured VERBATIM into the session manifest. A runtime without
    # self-description is refused — the PH0 stale-process lesson (F-1).
    try:
        with httpx.Client(base_url=spec.runtime_url, timeout=30) as client:
            ready = client.get("/health/ready")
            if ready.status_code != 200:
                raise PreconditionError(
                    "P-7", f"runtime not ready: HTTP {ready.status_code} from /health/ready"
                )
            info_verbatim: dict[str, Any] = client.get("/info").json()
    except httpx.HTTPError as exc:
        raise PreconditionError(
            "P-7", f"runtime unreachable at {spec.runtime_url}: {type(exc).__name__}"
        ) from exc

    info = RuntimeInfo.model_validate(info_verbatim)
    hosted = info.model_for(serving.artifact or "")
    if hosted is None:
        raise PreconditionError(
            "P-6",
            f"runtime hosts {sorted(info.hosted())}, not {serving.artifact!r}; artifacts "
            "are downloaded and hash-verified by the runtime at startup, so an unhosted "
            "artifact is an unverified artifact",
        )
    if hosted.compute_type is None or hosted.decode_params is None or info.vad_owner is None:
        raise PreconditionError(
            "P-7",
            "the runtime does not describe itself (pre-B4a process?); a session "
            "against an undescribed runtime cannot write a complete record",
        )
    log["P-6"] = f"{serving.artifact} hosted; files verified at runtime startup"
    log["P-7"] = "runtime ready; /info captured verbatim into the session manifest"

    if not info.environment:
        raise PreconditionError(
            "P-8", "the runtime reports no environment block; the record would be blind"
        )
    log["P-8"] = "environment reported by the runtime; absences become Determinations"

    return log, serving, slice_clips, info_verbatim


# ─────────────────────────────────────────────────────────────────────
# Execution
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SessionResult:
    """What one session produced: the manifest path and its records."""

    manifest_path: Path
    record_paths: tuple[Path, ...]


def record_filename(run: EvalRun, session_id: SessionId, run_index: int) -> str:
    """A record's filename, derived from its own identity — never typed.

    `YYYY-MM-DD-<public-model>-<language>-<artifact>-<build>-<session>.json`
    with a `-rN` suffix from the second run of a session onward. Colons
    are sanitised: research subjects (`research:whisper-base`) are legal
    identities and illegal Windows filenames.
    """
    identity = run.identity
    assert identity is not None  # noqa: S101 — the runner always writes one
    stamp = run.run_at.strftime("%Y-%m-%d")
    subject = identity.public_model.replace(":", "-")
    parts = f"{stamp}-{subject}-{identity.language}-{identity.artifact}-{identity.build}"
    session_part = session_id.session.lower()
    suffix = "" if run_index == 1 else f"-r{run_index}"
    return f"{parts}-{session_part}{suffix}.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _w1_warm_up(
    spec: SessionSpec, clips: list[EvalClip], paths: dict[str, Path], artifact: str
) -> list[dict[str, float]]:
    """W1 session warm-up: recorded and excluded, never discarded (§3).

    Requests over corpus-representative audio — the slice's own first
    clip — through the same HTTP path measurement will use. The timings
    go into the session manifest because our own data shows the first
    request can be FASTER than steady state, and a residual worth keeping
    is not noise to throw away. They never enter an evidence record.
    """
    if spec.warmup_requests == 0:
        return []
    representative = clips[0]
    audio = paths[representative.id].read_bytes()
    params: dict[str, str] = {"model": artifact}
    if representative.language != "zxx":
        params["language"] = representative.language
    timings: list[dict[str, float]] = []
    with httpx.Client(base_url=spec.runtime_url, timeout=300) as client:
        for _ in range(spec.warmup_requests):
            started = time.perf_counter()
            response = client.post(
                "/v1/transcribe",
                files={"file": (paths[representative.id].name, audio, "audio/wav")},
                data={"params": json.dumps(params)},
            )
            wall_ms = (time.perf_counter() - started) * 1000.0
            entry: dict[str, float] = {"wall_ms": round(wall_ms, 1), "status": response.status_code}
            if response.status_code == 200:
                stages = response.json().get("timing", {}).get("stages", {})
                if "inference" in stages:
                    entry["inference_ms"] = float(stages["inference"])
            timings.append(entry)
    return timings


def run_session(
    spec: SessionSpec,
    *,
    idle_asserted_by: str,
    data_dir: Path = Path("ml/evaluation/data"),
    results_dir: Path = Path("ml/evaluation/stt/results"),
    sessions_dir: Path = Path("ml/evaluation/stt/sessions"),
) -> SessionResult:
    """Execute one session: preconditions → W1 → runs → manifest.

    Fail closed at every step. The manifest and the records are
    append-only: a path that already exists is a refusal, because
    re-execution is a NEW session under a NEW id, never an overwrite.
    """
    manifest_path = sessions_dir / f"{spec.session_id.file_stem}.json"
    if manifest_path.exists():
        raise PreconditionError(
            "identity",
            f"session {spec.session_id} has already executed ({manifest_path}); "
            "session ids are permanent — re-execution is a new session id",
        )

    started = datetime.datetime.now(tz=datetime.UTC)
    log, serving, clips, info_verbatim = check_preconditions(
        spec, idle_asserted_by=idle_asserted_by
    )

    name, version = spec.dataset_identity
    dataset = find_dataset(Path("ml/evaluation/stt/datasets"), name, version)
    # The slice only: sessions pay for the audio they will send.
    paths = materialize_clips(clips, data_dir)

    warmup = _w1_warm_up(spec, clips, paths, serving.artifact or "")

    # The operator's assertion travels INTO each record as evidence with
    # its provenance: authored by a person, held as a claim — exactly
    # what an assertion is.
    idle_assertion = Determination(
        code="otherwise_idle_asserted",
        subject="measurement host",
        state=DeterminationState.NOT_MEASURED,
        authored_by=Authorship.OPERATOR,
        basis=Basis.CLAIM,
        detail=f"machine asserted otherwise idle by {idle_asserted_by} at session start",
        verified_on=started.date(),
    )

    record_paths: list[Path] = []
    record_entries: list[dict[str, Any]] = []
    for run_index in range(1, spec.runs + 1):
        run = run_stt_eval(
            dataset,
            base_url=spec.runtime_url,
            data_dir=data_dir,
            public_model=spec.public_model,
            language=spec.language,
            serving=serving,
            engine=spec.engine,
            benchmark=spec.benchmark,
            session_id=str(spec.session_id),
            notes=spec.notes,
            extra_determinations=(idle_assertion,),
        )
        filename = record_filename(run, spec.session_id, run_index)
        record_path = results_dir / filename
        if record_path.exists():
            raise PreconditionError(
                "identity", f"{record_path} already exists; records are append-only"
            )
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
        record_paths.append(record_path)
        assert run.identity is not None  # noqa: S101
        record_entries.append(
            {
                "file": filename,
                "sha256": _sha256(record_path),
                "slice": run.identity.slug,
                "run": run_index,
            }
        )

    manifest = {
        "session_id": str(spec.session_id),
        "campaign": spec.session_id.campaign,
        "phase": spec.session_id.phase,
        "started_at": started.isoformat(),
        "finished_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "spec": {
            "public_model": spec.public_model,
            "language": spec.language,
            "dataset": spec.dataset,
            "manifest": str(spec.manifest_path),
            "runtime_url": spec.runtime_url,
            "engine": spec.engine,
            "plan_reference": spec.plan_reference,
            "quality_claim": spec.quality_claim,
            "runs": spec.runs,
            "warmup_requests": spec.warmup_requests,
            "benchmark": spec.benchmark,
            "notes": spec.notes,
        },
        "preconditions": log,
        "operator_assertions": {
            "otherwise_idle": True,
            "asserted_by": idle_asserted_by,
        },
        # W1: recorded here, excluded from every evidence record.
        "w1_warm_up": warmup,
        # P-7: the runtime's own words, verbatim, at session start.
        "runtime_info": info_verbatim,
        "records": record_entries,
    }
    sessions_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return SessionResult(manifest_path=manifest_path, record_paths=tuple(record_paths))
