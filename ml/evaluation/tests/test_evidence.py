"""Evidence record v2: permanent vocabularies, and history that still loads."""

import ast
import datetime
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from intelliai_evaluation import bench, bench_tts, evidence
from intelliai_evaluation.evidence import (
    AcceleratorIdentity,
    ArtifactRef,
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
    StackIdentity,
    TimestampSource,
    VadOwner,
    Validity,
)
from intelliai_evaluation.results import ClipResult, EvalRun
from intelliai_evaluation.speech_results import SpeechEvalRun

STT_RESULTS = Path("ml/evaluation/stt/results")
TTS_RESULTS = Path("ml/evaluation/tts/results")
LADDERS = (Path("ml/evaluation/stt/benchmarks"), Path("ml/evaluation/tts/benchmarks"))
EVIDENCE_SOURCE = Path("ml/evaluation/src/intelliai_evaluation/evidence.py")


def _context(**overrides: object) -> ExecutionContext:
    fields: dict[str, object] = {
        "route": MeasurementRoute.PRODUCT_PATH,
        "normalization": "unicode_generic@v2",
        "declared_language": "hi",
        "language_mode": LanguageMode.EXPLICIT,
        "emitted_unit": EmittedUnit.WORD,
        "vad_owner": VadOwner.PIPELINE,
        "timestamp_source": TimestampSource.NATIVE,
        "decode_params": {"beam_size": "5", "task": "transcribe"},
    }
    return ExecutionContext.model_validate(fields | overrides)


def _determination(**overrides: object) -> Determination:
    fields: dict[str, object] = {
        "code": "timestamps_not_retained",
        "subject": "transcription segments",
        "state": DeterminationState.NOT_MEASURED,
        "authored_by": Authorship.HARNESS,
        "basis": Basis.FACT,
        "detail": "the engine emitted native segments; the harness reads text only",
        "verified_on": datetime.date(2026, 8, 5),
    }
    return Determination.model_validate(fields | overrides)


# ─────────────────────────────────────────────────────────────────────
# The permanent vocabularies — golden pins
# ─────────────────────────────────────────────────────────────────────


class TestVocabulariesArePinned:
    """First landing is permanent; a change here must be a conscious act."""

    def test_measurement_route(self) -> None:
        assert [m.value for m in MeasurementRoute] == ["product_path", "research_harness"]

    def test_language_mode(self) -> None:
        assert [m.value for m in LanguageMode] == ["explicit", "auto"]

    def test_emitted_unit(self) -> None:
        assert [m.value for m in EmittedUnit] == ["word", "character", "byte"]

    def test_vad_owner(self) -> None:
        assert [m.value for m in VadOwner] == ["pipeline", "engine", "none"]

    def test_timestamp_source(self) -> None:
        assert [m.value for m in TimestampSource] == [
            "none",
            "native",
            "auxiliary_model",
            "derived",
        ]

    def test_validity(self) -> None:
        assert [m.value for m in Validity] == ["valid", "incomplete", "invalid"]

    def test_validity_has_no_member_for_not_computed(self) -> None:
        # An absence spelled as a value is a value somebody eventually
        # sets by hand. "Not computed" is `None` on the field.
        assert not {"not_computed", "unassessed", "pending", "unknown"} & {
            m.value for m in Validity
        }

    def test_determination_axes(self) -> None:
        assert [m.value for m in DeterminationState] == [
            "not_supported",
            "not_measured",
            "undeterminable",
        ]
        assert [m.value for m in Authorship] == ["harness", "operator", "reviewer"]
        assert [m.value for m in Basis] == ["fact", "claim", "inference"]

    def test_basis_can_hold_an_unverified_external_statement(self) -> None:
        # Two-valued fact|inference would force a vendor's assertion to be
        # mislabelled as one or the other. The research gates already use
        # three labels; the record uses the same three.
        assert Basis.CLAIM.value == "claim"

    def test_no_token_unit_is_ever_registered(self) -> None:
        # A token count is a property of one tokenizer and is not
        # comparable across candidates.
        assert "token" not in {m.value for m in EmittedUnit}

    def test_the_deferred_vocabularies_do_not_exist(self) -> None:
        # AudioCondition has no producer (no robustness corpus exists) and
        # duration_bands exists to band a performance metric that has not
        # landed. Each arrives with the thing that uses it.
        assert not hasattr(evidence, "AudioCondition")
        assert not hasattr(evidence, "DurationBands")

    def test_production_evidence_is_not_in_this_milestone(self) -> None:
        # A record carries exactly one ExecutionContext, while our own
        # ladder ran under WSL2 and our quality records ran native.
        # Nesting production evidence would require mis-stating one
        # environment: an architecture decision, not a build.
        assert not hasattr(evidence, "ProductionEvidence")
        assert "production" not in EvalRun.model_fields


# ─────────────────────────────────────────────────────────────────────
# ExecutionContext
# ─────────────────────────────────────────────────────────────────────


class TestExecutionContextIsUnconstructibleWhenUnderspecified:
    """An underspecified benchmark must be impossible, not merely unusual."""

    @pytest.mark.parametrize(
        "missing",
        [
            "route",
            "normalization",
            "declared_language",
            "language_mode",
            "emitted_unit",
            "vad_owner",
            "timestamp_source",
            "decode_params",
        ],
    )
    def test_every_known_fact_must_be_stated(self, missing: str) -> None:
        fields = _context().model_dump()
        del fields[missing]
        with pytest.raises(ValidationError):
            ExecutionContext.model_validate(fields)

    def test_decode_params_has_no_default_because_defaults_were_active(self) -> None:
        # Our engine runs under a beam search, a best-of, a temperature
        # ladder and previous-text conditioning that we never set. An
        # omitted dict would assert no decode configuration was in force.
        assert ExecutionContext.model_fields["decode_params"].is_required()

    def test_timestamp_source_has_no_default_so_none_is_never_implied(self) -> None:
        # The engine emits native segments on every request; the harness
        # discards them. Defaulting to NONE would say the engine produced
        # nothing, which is false.
        assert ExecutionContext.model_fields["timestamp_source"].is_required()

    def test_non_retention_is_a_determination_not_a_second_field(self) -> None:
        # One mechanism for absence, per the founder ruling.
        context = _context(timestamp_source=TimestampSource.NATIVE)
        run = _minimal_run(execution=context, determinations=(_determination(),))
        assert run.execution is not None
        assert run.execution.timestamp_source is TimestampSource.NATIVE
        assert run.determinations[0].code == "timestamps_not_retained"
        assert "timestamps_retained" not in ExecutionContext.model_fields


class TestExecutionContextRecordsIncompletenessRatherThanRefusingIt:
    """Validity is computed from recorded facts, never by a constructor."""

    @pytest.mark.parametrize("field", ["environment", "deployment", "stack"])
    def test_a_block_with_no_capture_path_may_be_absent(self, field: str) -> None:
        assert getattr(_context(), field) is None

    def test_such_a_context_is_still_constructible(self) -> None:
        # The schema permits it; the validity pass judges it. Refusing to
        # build it would mean no record could be written until every
        # capture path existed.
        assert _context().environment is None


# ─────────────────────────────────────────────────────────────────────
# EnvironmentIdentity
# ─────────────────────────────────────────────────────────────────────


class TestEnvironmentIdentityIsStructureOnly:
    def test_every_field_is_optional(self) -> None:
        # This milestone lands the structure; nothing populates it. A
        # field that cannot be obtained honestly stays None.
        assert EnvironmentIdentity().model_dump(exclude_defaults=True) == {}

    def test_hardware_class_is_none_until_the_reference_machine_is_ruled(self) -> None:
        # The one machine we own is already spelled four ways across
        # committed records; a default here would make a fifth canonical.
        assert EnvironmentIdentity().hardware_class is None

    def test_there_is_no_unknown_fields_list(self) -> None:
        # One mechanism for absence: None plus a Determination.
        assert "unknown_fields" not in EnvironmentIdentity.model_fields

    def test_observed_from_is_a_controlled_vocabulary(self) -> None:
        # The harness talks to a runtime over HTTP, so facts read from its
        # own process describe the harness host — right only when the
        # runtime is local and native. That is a correctness question, so
        # the answer must not be a sentence somebody has to parse.
        assert EnvironmentIdentity(observed_from="harness").observed_from == "harness"
        assert EnvironmentIdentity(observed_from="runtime").observed_from == "runtime"

    def test_prose_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            EnvironmentIdentity.model_validate({"observed_from": "the harness host, probably"})

    def test_it_is_a_literal_rather_than_a_new_permanent_enum(self) -> None:
        # The distinction is local to one field. A Literal keeps it
        # controlled without adding a type to the vocabulary namespace —
        # and widening a Literal later is purely additive, while renaming
        # an enum member is forbidden outright.
        assert not hasattr(evidence, "EnvironmentScope")
        assert not hasattr(evidence, "ObservedFrom")

    def test_an_accelerator_that_has_no_memory_is_expressible(self) -> None:
        # not_applicable is not the same as unreadable. A unified-memory
        # device must not be structurally excluded by a CUDA-shaped field.
        unified = AcceleratorIdentity(
            device_class="npu", device_model="unified-memory part", device_count=1
        )
        assert unified.device_memory_mib is None

    def test_deployment_and_stack_are_structure_only_too(self) -> None:
        assert DeploymentIdentity().model_dump(exclude_defaults=True) == {}
        assert StackIdentity().model_dump(exclude_defaults=True) == {}

    def test_no_detection_is_shipped_in_this_milestone(self) -> None:
        # Environment detection is B4's, and it needs the runtime to
        # report its own environment first.
        assert not hasattr(evidence, "detect")
        assert not hasattr(EnvironmentIdentity, "detect")

    def test_no_new_runtime_dependency_was_added(self) -> None:
        source = EVIDENCE_SOURCE.read_text(encoding="utf-8")
        for banned in ("psutil", "cpuinfo", "GPUtil", "pynvml"):
            assert banned not in source


# ─────────────────────────────────────────────────────────────────────
# Historical compatibility — checked against the ledger, not asserted
# ─────────────────────────────────────────────────────────────────────


def _records() -> list[Path]:
    return sorted(STT_RESULTS.glob("*.json")) + sorted(TTS_RESULTS.glob("*.json"))


def _minimal_run(**overrides: object) -> EvalRun:
    fields: dict[str, object] = {
        "dataset_name": "t",
        "dataset_version": 1,
        "capability": "transcription",
        "run_at": datetime.datetime(2026, 8, 5, tzinfo=datetime.UTC),
        "artifact": "a",
        "engine": "e",
        "engine_version": "1",
        "compute": "cpu-int8",
        "hardware": "test machine",
        "clips": [],
    }
    return EvalRun.model_validate(fields | overrides)


def test_there_are_records_to_check() -> None:
    assert len(_records()) == 5


@pytest.mark.parametrize("path", _records(), ids=lambda p: p.name)
def test_every_committed_record_still_parses(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    root = SpeechEvalRun if "cases" in document else EvalRun
    assert root.model_validate(document)


@pytest.mark.parametrize("path", _records(), ids=lambda p: p.name)
def test_no_committed_record_carries_any_new_key(path: Path) -> None:
    """The defaults are not merely safe — they are TRUE of the ledger.

    A default that contradicted a committed record would silently rewrite
    what that record says the next time anything read it.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    added = {
        "execution",
        "determinations",
        "metrics",
        "validity",
        "session_id",
        "methodology_version",
        "normalization",
    }
    if "cases" in document:  # the generation root already has its own
        added.discard("methodology_version")
    assert not added & set(document)


@pytest.mark.parametrize("path", sorted(STT_RESULTS.glob("*.json")), ids=lambda p: p.name)
def test_no_committed_clip_carries_a_new_key(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    for clip in document["clips"]:
        assert not {"metrics", "failure"} & set(clip)


@pytest.mark.parametrize("path", _records(), ids=lambda p: p.name)
def test_history_reads_as_not_computed_never_as_a_claim(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    if "cases" in document:
        record = SpeechEvalRun.model_validate(document)
        assert record.normalization is None
        assert record.determinations == ()
        return
    run = EvalRun.model_validate(document)
    # Not `valid`, not `complete`, not `0` — a record that never had
    # validity computed says exactly that.
    assert run.validity is None
    assert run.execution is None
    assert run.methodology_version is None
    assert run.determinations == ()
    assert run.metrics == {}


@pytest.mark.parametrize(
    "path", [p for tree in LADDERS for p in sorted(tree.glob("*.json"))], ids=lambda p: p.name
)
def test_every_committed_ladder_still_parses_after_relocation(path: Path) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    root = evidence.BenchReport if "clip" in document else evidence.TtsBenchReport
    assert root.model_validate(document).levels


# ─────────────────────────────────────────────────────────────────────
# Schema unification and the import budget
# ─────────────────────────────────────────────────────────────────────


class TestTheImportBudget:
    """Reading a five-year-old record must never need a network stack."""

    def test_evidence_imports_nothing_beyond_pydantic_metrics_and_stdlib(self) -> None:
        tree = ast.parse(EVIDENCE_SOURCE.read_text(encoding="utf-8"))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
        assert "httpx" not in roots
        assert "subprocess" not in roots
        assert roots <= {"datetime", "json", "math", "enum", "typing", "pydantic", "__future__"}

    def test_the_relocated_symbols_are_still_importable_from_their_old_homes(self) -> None:
        # Every existing import site keeps working; the move is a
        # behaviour-preserving relocation, not a rename.
        assert bench.BenchReport is evidence.BenchReport
        assert bench.LevelResult is evidence.LevelResult
        assert bench.OverheadResult is evidence.OverheadResult
        assert bench.RequestSample is evidence.RequestSample
        assert bench.nearest_rank is evidence.nearest_rank
        assert bench_tts.TtsBenchReport is evidence.TtsBenchReport
        assert bench_tts.TtsSample is evidence.TtsSample
        assert bench_tts.sample_from_response is evidence.sample_from_response

    def test_metrics_never_imports_a_record_module(self) -> None:
        # The registry guard moved into metrics.py; if metrics imported a
        # record root in return the two would be a cycle.
        source = Path("ml/evaluation/src/intelliai_evaluation/metrics.py").read_text(
            encoding="utf-8"
        )
        for record_module in ("results", "speech_results", "evidence"):
            assert f"import {record_module}" not in source


class TestBothRootsShareOneGuard:
    def test_an_unregistered_metric_is_refused_on_the_recognition_root(self) -> None:
        with pytest.raises(ValidationError, match="unknown metric"):
            _minimal_run(metrics={"recognition_rtf": 0.5})

    def test_a_human_metric_may_not_enter_the_measured_map(self) -> None:
        with pytest.raises(ValidationError, match="does not belong in this section"):
            _minimal_run(metrics={"listening_preference": 0.5})

    def test_the_accuracy_family_is_accepted(self) -> None:
        run = _minimal_run(metrics={"wer_unicode": 0.07, "cer_unicode": 0.03})
        assert run.metrics["wer_unicode"] == 0.07

    def test_a_clip_carries_its_own_registry_validated_metrics(self) -> None:
        clip = ClipResult(
            clip_id="c",
            duration_seconds=1.0,
            inference_seconds=0.5,
            substitutions=0,
            insertions=0,
            deletions=0,
            reference_words=4,
            hypothesis_words=4,
            hypothesis_text="x",
            metrics={"wer_unicode": 0.0},
        )
        assert clip.failure is None
        assert clip.metrics == {"wer_unicode": 0.0}

    def test_a_failed_clip_keeps_whatever_it_measured(self) -> None:
        # Failures are evidence. Before this field the runner could only
        # abort the whole run.
        clip = ClipResult(
            clip_id="c",
            duration_seconds=1.0,
            inference_seconds=0.0,
            substitutions=0,
            insertions=0,
            deletions=0,
            reference_words=0,
            hypothesis_words=0,
            hypothesis_text="",
            failure="runtime: HTTP 503 overloaded",
        )
        assert clip.failure == "runtime: HTTP 503 overloaded"


class TestDeterminationRecordsAbsenceWithProvenance:
    def test_it_says_who_established_it_and_how_strongly(self) -> None:
        stated = _determination(authored_by=Authorship.REVIEWER, basis=Basis.CLAIM)
        assert stated.authored_by is Authorship.REVIEWER
        assert stated.basis is Basis.CLAIM

    def test_it_decays_like_every_other_verdict(self) -> None:
        assert _determination().verified_on == datetime.date(2026, 8, 5)

    def test_it_is_frozen(self) -> None:
        with pytest.raises(ValidationError):
            _determination().code = "changed"  # type: ignore[misc]

    def test_an_auxiliary_artifact_is_identified_not_footnoted(self) -> None:
        context = _context(
            auxiliary_artifacts=(
                ArtifactRef(artifact="aligner", version=1, role="forced_alignment"),
            )
        )
        assert context.auxiliary_artifacts[0].role == "forced_alignment"
