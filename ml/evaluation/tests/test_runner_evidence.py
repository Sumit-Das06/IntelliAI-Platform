"""The runner as an honest evidence writer.

Every value it puts into an `ExecutionContext` must be Observed, Derived,
or accompanied by a Determination. These tests hold that line field by
field, and hold the harder line behind it: a Derived value may never
depend on state outside the record.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from intelliai_evaluation.cli import main
from intelliai_evaluation.dataset import EvalClip, EvalDataset, SyntheticSpec
from intelliai_evaluation.evidence import (
    Authorship,
    Basis,
    EmittedUnit,
    LanguageMode,
    MeasurementRoute,
    TimestampSource,
    VadOwner,
)
from intelliai_evaluation.metrics import METRICS
from intelliai_evaluation.normalization import ProfileNotRegisteredError
from intelliai_evaluation.resolution import ResolvedServing
from intelliai_evaluation.results import EvalRun
from intelliai_evaluation.runner import (
    ArtifactNotHostedError,
    RuntimeNotDescribedError,
    run_stt_eval,
)

ARTIFACT = "whisper-small"

INFO: dict[str, Any] = {
    "pool": {"admitted": 0, "max_concurrency": 4, "max_queue": 8},
    "service": "stt-runtime",
    "service_version": "0.1.0",
    "contract_version": 1,
    "capability": "transcription",
    "vad_owner": "pipeline",
    "environment": {
        "os_name": "Linux",
        "os_release": "6.1.0",
        "machine": "x86_64",
        "python_version": "3.12.10",
        "cpu_model": "A Test CPU",
        "cpu_logical_threads": 8,
        "thread_env": {"OMP_NUM_THREADS": "4"},
        "hardware_class": None,
        "package_versions": {"faster-whisper": "1.2.1"},
    },
    "models": [
        {
            "slot": "default",
            "artifact": ARTIFACT,
            "load_ms": 100.0,
            "warmup_ms": 20.0,
            "compute_type": "int8",
            "emitted_unit": "word",
            "decode_params": {"beam_size": "5", "task": "transcribe"},
        }
    ],
}

SERVING = ResolvedServing(
    language="en",
    status="supported",
    artifact=ARTIFACT,
    artifact_version=1,
    deployment="stt-runtime",
)


def dataset(*clips: EvalClip, name: str = "runner-test") -> EvalDataset:
    return EvalDataset(name=name, version=1, capability="transcription", clips=list(clips))


def spoken(clip_id: str, language: str, reference: str, seconds: float = 2.0) -> EvalClip:
    """A clip with a declared reference, generated deterministically."""
    return EvalClip(
        id=clip_id,
        language=language,
        reference_text=reference,
        duration_seconds=seconds,
        license="test",
        synthetic=SyntheticSpec(kind="tone", duration_seconds=seconds),
    )


def probe(clip_id: str, language: str, seconds: float = 1.0) -> EvalClip:
    """A clip whose manifest declares an EMPTY reference."""
    return EvalClip(
        id=clip_id,
        language=language,
        reference_text="",
        duration_seconds=seconds,
        license="test",
        synthetic=SyntheticSpec(kind="silence", duration_seconds=seconds),
    )


def envelope(
    text: str, *, inference_ms: float | None = 500.0, segments: bool = True
) -> dict[str, Any]:
    timing: dict[str, Any] = {"total_ms": 600.0, "stages": {}}
    if inference_ms is not None:
        timing["stages"]["inference"] = inference_ms
    output: dict[str, Any] = {"text": text, "language": "en", "duration_seconds": 2.0}
    if segments and text:
        output["segments"] = [{"start_seconds": 0.0, "end_seconds": 2.0, "text": text}]
    return {
        "output": output,
        "model": ARTIFACT,
        "usage": [],
        "timing": timing,
        "runtime": {"service": "stt-runtime", "service_version": "0.1.0", "contract_version": 1},
    }


class FakeRuntime:
    """A runtime over a real httpx transport: real JSON, real status codes."""

    def __init__(
        self,
        *,
        info: dict[str, Any] | None = None,
        replies: list[dict[str, Any]] | None = None,
        statuses: list[int] | None = None,
    ) -> None:
        self.info = info if info is not None else INFO
        self.replies = replies or []
        self.statuses = statuses or []
        self.requests: list[dict[str, str]] = []
        self._served = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/info":
            return httpx.Response(200, json=self.info)
        index = self._served
        self._served += 1
        # The params part is multipart-encoded; recovering it is how these
        # tests check what the runner actually SENT rather than intended.
        body = request.content.decode("utf-8", errors="replace")
        marker = '"model"'
        start = body.find(marker)
        if start != -1:
            end = body.find("}", start)
            self.requests.append(json.loads("{" + body[start : end + 1]))
        status = self.statuses[index] if index < len(self.statuses) else 200
        if status != 200:
            return httpx.Response(status, json={"type": "overloaded", "message": "busy"})
        reply = self.replies[index] if index < len(self.replies) else envelope("hello world")
        return httpx.Response(200, json=reply)


#: Installs a fake runtime behind the runner's own client and returns it.
Wire = Callable[["FakeRuntime"], "FakeRuntime"]


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> Wire:
    """Install a fake runtime behind the runner's own httpx client."""

    def install(runtime: FakeRuntime) -> FakeRuntime:
        transport = httpx.MockTransport(runtime.handle)
        # Bound BEFORE patching: `runner.httpx` is the httpx module itself,
        # so patching its Client would otherwise make this factory call
        # itself.
        real = httpx.Client

        def client(**kwargs: Any) -> httpx.Client:
            kwargs.pop("timeout", None)
            return real(transport=transport, **kwargs)

        monkeypatch.setattr("intelliai_evaluation.runner.httpx.Client", client)
        return runtime

    return install


def run(
    wired: Wire,
    runtime: FakeRuntime,
    clips: list[EvalClip],
    tmp_path: Path,
    *,
    language: str = "en",
    **kwargs: Any,
) -> EvalRun:
    wired(runtime)
    return run_stt_eval(
        dataset(*clips),
        base_url="http://runtime.test",
        data_dir=tmp_path,
        public_model="intelliai-stt",
        language=language,
        serving=SERVING,
        engine="faster-whisper",
        **kwargs,
    )


class TestObservedValues:
    """Read from what the system reported, never from a flag."""

    def test_the_build_decode_config_and_granularity_come_from_info(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.execution is not None
        assert record.execution.decode_params == {"beam_size": "5", "task": "transcribe"}
        assert record.execution.emitted_unit is EmittedUnit.WORD
        assert record.execution.vad_owner is VadOwner.PIPELINE
        assert record.compute == "int8"

    def test_the_environment_is_the_runtimes_own(self, wired: Wire, tmp_path: Path) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.execution is not None
        environment = record.execution.environment
        assert environment is not None
        # The whole point of B4a: these describe the measured process, not
        # the harness's own host.
        assert environment.observed_from == "runtime"
        assert environment.cpu_model == "A Test CPU"
        assert environment.cpu_logical_threads == 8
        assert environment.thread_config == {"OMP_NUM_THREADS": 4}
        assert environment.compute_type == "int8"

    def test_the_engine_version_is_read_not_typed(self, wired: Wire, tmp_path: Path) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.engine_version == "1.2.1"

    def test_the_hardware_line_is_generated_from_observed_facts(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # This is what finally fixes one machine being spelled four ways:
        # nobody spells it. The structured truth is in the environment.
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.hardware == "A Test CPU · Linux 6.1.0"


class TestDerivedValues:
    """Deterministic from evidence the run itself holds."""

    def test_route_is_derived_from_the_evidence_the_run_holds(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # It received /info and transcription responses over a socket with
        # the hosted artifact verified. Not derived by byte-comparing a
        # file on disk: a Derived value may never depend on current
        # filesystem state, because a reader could not check it later.
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.execution is not None
        assert record.execution.route is MeasurementRoute.PRODUCT_PATH

    def test_manifest_provenance_is_a_determination_not_the_route(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # Whether this registry state was ever shipped is a real question
        # and a different one. The manifest carries no provenance, so it
        # is recorded as unestablished rather than folded into `route`.
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert "manifest_provenance_unverified" in {d.code for d in record.determinations}

    def test_language_mode_reflects_what_was_actually_sent(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        runtime = FakeRuntime()
        record = run(wired, runtime, [spoken("a", "en", "hello world")], tmp_path)
        assert record.execution is not None
        assert record.execution.language_mode is LanguageMode.EXPLICIT
        assert runtime.requests[0]["language"] == "en"

    def test_the_ruler_is_derived_from_the_slice(self, wired: Wire, tmp_path: Path) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.execution is not None
        assert record.execution.normalization == "unicode_generic@v2"
        assert record.execution.declared_language == "en"

    def test_the_declared_language_never_disagrees_with_the_records_subject(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.identity is not None
        assert record.execution is not None
        assert record.execution.declared_language == record.identity.language


class TestTimestampSourceIsThreeWay:
    """Two values would lie about a slice that had nothing to segment."""

    def test_segments_present_is_native(self, wired: Wire, tmp_path: Path) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.execution is not None
        assert record.execution.timestamp_source is TimestampSource.NATIVE

    def test_text_without_segments_is_a_real_absence(self, wired: Wire, tmp_path: Path) -> None:
        runtime = FakeRuntime(replies=[envelope("hello world", segments=False)])
        record = run(wired, runtime, [spoken("a", "en", "hello world")], tmp_path)
        assert record.execution is not None
        assert record.execution.timestamp_source is TimestampSource.NONE
        assert "timestamp_source_undeterminable" not in {d.code for d in record.determinations}

    def test_no_text_at_all_cannot_distinguish_and_says_so(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # Our own `hi` slice is exactly this: two synthetic probes that
        # return nothing. Writing NONE would claim a capability absence on
        # evidence that shows only silence.
        runtime = FakeRuntime(replies=[envelope("", segments=False)])
        record = run(wired, runtime, [probe("p", "en")], tmp_path)
        assert "timestamp_source_undeterminable" in {d.code for d in record.determinations}


class TestFailuresAreEvidence:
    def test_a_refused_clip_is_recorded_and_the_run_continues(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        runtime = FakeRuntime(statuses=[503, 200], replies=[{}, envelope("hello world")])
        record = run(
            wired,
            runtime,
            [spoken("a", "en", "hello world"), spoken("b", "en", "hello world")],
            tmp_path,
        )
        assert record.clips[0].failure == "runtime: HTTP 503"
        assert record.clips[0].metrics == {}
        assert record.clips[1].failure is None
        assert record.clips[1].metrics["wer_unicode"] == 0.0

    def test_a_missing_inference_stage_is_a_determination_never_a_zero(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # A zero here reads as infinite speed and would silently improve
        # every real-time factor it touched.
        runtime = FakeRuntime(replies=[envelope("hello world", inference_ms=None)])
        record = run(wired, runtime, [spoken("a", "en", "hello world")], tmp_path)
        assert "inference_stage_missing" in {d.code for d in record.determinations}
        assert "recognition_rtf" not in record.metrics


class TestMetricEmission:
    def test_every_emitted_name_resolves_in_the_registry(self, wired: Wire, tmp_path: Path) -> None:
        record = run(
            wired,
            FakeRuntime(),
            [spoken("a", "en", "hello world"), probe("p", "en")],
            tmp_path,
        )
        for name in record.metrics:
            assert name in METRICS
        for clip in record.clips:
            for name in clip.metrics:
                assert name in METRICS

    def test_english_carries_the_ascii_transition_anchor(self, wired: Wire, tmp_path: Path) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.metrics["wer_ascii"] == 0.0
        assert record.metrics["wer_unicode"] == 0.0

    def test_hindi_carries_no_ascii_anchor(self, wired: Wire, tmp_path: Path) -> None:
        # The ASCII ruler erases Devanagari; the anchor exists only to keep
        # the English baseline comparable.
        hindi = "मुझे हिंदी आती है"
        record = run(
            wired,
            FakeRuntime(replies=[envelope(hindi)]),
            [spoken("a", "hi", hindi)],
            tmp_path,
            language="hi",
        )
        assert "wer_ascii" not in record.metrics
        assert record.metrics["wer_unicode"] == 0.0

    def test_a_probe_only_slice_yields_hallucination_and_no_word_error_rate(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # Today's `hi` slice. It supports exactly this and nothing more.
        runtime = FakeRuntime(replies=[envelope("subscribe to the channel", segments=False)])
        record = run(wired, runtime, [probe("p", "en")], tmp_path)
        assert record.metrics["hallucinated_words"] == 4.0
        assert "wer_unicode" not in record.metrics

    def test_recognition_rtf_is_duration_weighted_not_a_mean_of_ratios(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # 500 ms over a 2 s clip and 500 ms over an 8 s clip.
        # duration-weighted = 1.0/10.0 = 0.10; mean-of-ratios = 0.15625.
        runtime = FakeRuntime(replies=[envelope("hello world"), envelope("hello world")])
        record = run(
            wired,
            runtime,
            [
                spoken("a", "en", "hello world", seconds=2.0),
                spoken("b", "en", "hello world", seconds=8.0),
            ],
            tmp_path,
        )
        assert record.metrics["recognition_rtf"] == pytest.approx(0.10)


class TestRefusals:
    def test_a_language_with_no_ruler_refuses_before_measuring(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        with pytest.raises(ProfileNotRegisteredError):
            run(wired, FakeRuntime(), [spoken("a", "ar", "x")], tmp_path, language="ar")

    def test_an_undescribed_runtime_cannot_produce_a_benchmark(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # A record that cannot state its own build or decode configuration
        # is not a benchmark; writing one anyway would put an unfalsifiable
        # number into an append-only ledger.
        stale = {**INFO, "models": [{"slot": "default", "artifact": ARTIFACT}]}
        with pytest.raises(RuntimeNotDescribedError):
            run(wired, FakeRuntime(info=stale), [spoken("a", "en", "x")], tmp_path)

    def test_a_runtime_hosting_something_else_refuses(self, wired: Wire, tmp_path: Path) -> None:
        other = {**INFO, "models": [{**INFO["models"][0], "artifact": "someone-else"}]}
        with pytest.raises(ArtifactNotHostedError):
            run(wired, FakeRuntime(info=other), [spoken("a", "en", "x")], tmp_path)


class TestDeterminationsCarryProvenance:
    def test_the_harness_authors_what_it_observed(self, wired: Wire, tmp_path: Path) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.determinations
        for determination in record.determinations:
            assert determination.authored_by is Authorship.HARNESS
            assert determination.basis is Basis.FACT
            assert determination.detail

    def test_the_unruled_reference_machine_is_stated_not_guessed(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert "hardware_class_unruled" in {d.code for d in record.determinations}
        assert record.execution is not None
        assert record.execution.environment is not None
        assert record.execution.environment.hardware_class is None


class TestEvidenceIsNeverInterpreted:
    def test_the_runner_computes_no_validity_verdict(self, wired: Wire, tmp_path: Path) -> None:
        # A run cannot: two of the ten conditions are session-level and one
        # has no field on any schema. Interpretation is a later pass.
        record = run(wired, FakeRuntime(), [spoken("a", "en", "hello world")], tmp_path)
        assert record.validity is None
        assert record.methodology_version is None

    def test_a_session_id_links_records_when_given(self, wired: Wire, tmp_path: Path) -> None:
        record = run(
            wired,
            FakeRuntime(),
            [spoken("a", "en", "hello world")],
            tmp_path,
            session_id="CAMP-STT-2026A/PH0/S01",
        )
        assert record.session_id == "CAMP-STT-2026A/PH0/S01"


class TestNoFlagDuplicatesAnObservableFact:
    """Rule LF, asserted against the argument surface itself.

    *If a fact is observable at /info, the harness must have no flag for
    it.* A hand-typed value the system already knows is a transcription
    error waiting to be committed — and `--hardware` is precisely how one
    machine came to be spelled four different ways across our records.
    """

    @pytest.mark.parametrize(
        "flag", ["--compute", "--hardware", "--engine-version", "--decode", "--vad", "--emitted"]
    )
    def test_the_run_command_offers_no_such_flag(
        self, flag: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            main(["run", "--help"])
        assert flag not in capsys.readouterr().out

    def test_the_facts_it_still_asks_for_are_the_ones_info_does_not_report(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # `--engine` survives because /info reports no engine_module; its
        # VERSION does not, because the runtime knows which library build
        # it loaded.
        with pytest.raises(SystemExit):
            main(["run", "--help"])
        surface = capsys.readouterr().out
        assert "--engine " in surface or "--engine\n" in surface
        assert "--engine-version" not in surface


def test_every_historical_record_still_parses() -> None:
    # B4b changes no schema: it fills fields B3 already defined.
    committed = sorted(Path("ml/evaluation/stt/results").glob("*.json"))
    assert (
        len(committed) == 26
    )  # 3 pre-methodology + 4 PH0 + 7 Stage 1 + 1 15B + 2 15C + 3 15D (E1 hi/replicate/en)
    # + 6 E1b (3 checkpoint-sweep hi + candidate hi/replicate/en)
    for path in committed:
        assert EvalRun.model_validate_json(path.read_text(encoding="utf-8"))
