"""The campaign/session layer: orchestration that fails closed.

The runner measures; this layer decides whether measuring may start and
what belongs together. Every test here holds one of those two lines.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

from intelliai_evaluation.campaign import (
    QUALITY_CLAIM_MINIMUM_CLIPS,
    PreconditionError,
    SessionId,
    SessionIdentityError,
    SessionResult,
    SessionSpec,
    record_filename,
    run_session,
)
from intelliai_evaluation.evidence import Authorship, Basis
from intelliai_evaluation.results import EvalRun
from test_runner_evidence import INFO, FakeRuntime, envelope

DATASETS = Path("ml/evaluation/stt/datasets")


# ─────────────────────────────────────────────────────────────────────
# Identifier grammar
# ─────────────────────────────────────────────────────────────────────


class TestTheIdentifierGrammarIsPermanent:
    def test_the_ph0_session_ids_parse(self) -> None:
        # The grammar must accept exactly what the ledger already cites.
        for text in (
            "CAMP-STT-2026A/PH0/S01-en",
            "CAMP-STT-2026A/PH0/S02-en-replicate",
            "CAMP-STT-2026A/PH0/S03-hi",
            "CAMP-STT-2026A/PH0/S04-zxx",
        ):
            assert str(SessionId.parse(text)) == text

    @pytest.mark.parametrize(
        "malformed",
        [
            "CAMP-STT-2026A/P0/S01-en",  # bare P<n> collided; PH<n> is permanent
            "CAMP-STT-2026A/PH0/S1-en",  # ordinal is two digits
            "CAMP-STT-2026A/PH0/S01-EN",  # slugs are lowercase
            "camp-stt-2026a/PH0/S01-en",  # campaigns are uppercase
            "CAMP-STT-2026A/PH0",  # no session part
            "CAMP-STT-2026A/PH0/S01-en/extra",  # too deep
            "CAMP-STT-26A/PH0/S01-en",  # year is four digits
        ],
    )
    def test_a_malformed_id_is_refused_at_construction(self, malformed: str) -> None:
        # A malformed id that reached a record would be cited forever.
        with pytest.raises(SessionIdentityError):
            SessionId.parse(malformed)

    def test_the_file_stem_carries_no_path_separators(self) -> None:
        stem = SessionId.parse("CAMP-STT-2026A/PH0/S01-en").file_stem
        assert "/" not in stem and "\\" not in stem


# ─────────────────────────────────────────────────────────────────────
# Specs and preconditions — fail closed, each with its name
# ─────────────────────────────────────────────────────────────────────


def spec_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "session_id": "CAMP-STT-2026A/PH0/S90-smoke",
        "public_model": "intelliai-stt",
        "language": "en",
        "dataset": "stt-eval-seed@v2",
        "manifest": "ml/evaluation/manifests/resolution.json",
        "runtime_url": "http://runtime.test",
        "engine": "faster-whisper",
        "plan_reference": "gate4-benchmark-campaign.md (PROPOSED; apparatus scope)",
    }
    return document | overrides


def write_spec(tmp_path: Path, **overrides: Any) -> Path:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec_document(**overrides)), encoding="utf-8")
    return path


Wire = Callable[[FakeRuntime], FakeRuntime]


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch) -> Wire:
    """Install one fake runtime behind BOTH httpx client sites."""

    def install(runtime: FakeRuntime) -> FakeRuntime:
        transport = httpx.MockTransport(runtime.handle)
        real = httpx.Client

        def client(**kwargs: Any) -> httpx.Client:
            kwargs.pop("timeout", None)
            return real(transport=transport, **kwargs)

        monkeypatch.setattr("intelliai_evaluation.runner.httpx.Client", client)
        monkeypatch.setattr("intelliai_evaluation.campaign.httpx.Client", client)
        return runtime

    return install


def execute(tmp_path: Path, *, idle_by: str = "Test Operator", **overrides: Any) -> SessionResult:
    spec = SessionSpec.load(write_spec(tmp_path, **overrides))
    return run_session(
        spec,
        idle_asserted_by=idle_by,
        data_dir=tmp_path / "data",
        results_dir=tmp_path / "results",
        sessions_dir=tmp_path / "sessions",
    )


def enough_replies(count: int = 16) -> list[dict[str, Any]]:
    return [envelope("hello world") for _ in range(count)]


class TestPreconditionsFailClosed:
    def test_a_missing_plan_reference_refuses_as_p1(self, wired: Wire, tmp_path: Path) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError, match=r"\[P-1\]"):
            execute(tmp_path, plan_reference="   ")

    def test_an_unnamed_idle_assertion_refuses_as_p9(self, wired: Wire, tmp_path: Path) -> None:
        # Asserted, never assumed — and an assertion has an author.
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError, match=r"\[P-9\]"):
            execute(tmp_path, idle_by="  ")

    def test_an_unreleased_dataset_refuses_as_p2(self, wired: Wire, tmp_path: Path) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError, match=r"\[P-2\]"):
            execute(tmp_path, dataset="stt-eval-seed@v99")

    def test_a_dataset_cited_by_filename_is_refused(self, wired: Wire, tmp_path: Path) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError, match="by identity"):
            execute(tmp_path, dataset="stt-eval-v2.json")

    def test_an_empty_slice_refuses_as_p2(self, wired: Wire, tmp_path: Path) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError, match="no 'ta' clips"):
            execute(tmp_path, language="ta")

    def test_a_thin_corpus_cannot_carry_a_quality_claim_p3(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # The committed English slice has 2 referenced clips against a
        # floor of 100. The refusal names the only honest fixes: shrink
        # the claim or grow the corpus.
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError, match=str(QUALITY_CLAIM_MINIMUM_CLIPS)):
            execute(tmp_path, quality_claim=True)

    def test_a_language_with_no_clips_refuses_before_its_missing_ruler(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # `ar` resolves in the production manifest, has no ruler (P-5)
        # AND no clips (P-2). The corpus check fires first, which is the
        # right order: there is nothing to measure before there is
        # nothing to measure it with. P-5 becomes reachable the day a
        # corpus gains an unbound language.
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError, match=r"\[P-2\]"):
            execute(tmp_path, language="ar")

    def test_an_unresolvable_subject_refuses(self, wired: Wire, tmp_path: Path) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError, match=r"\[resolution\]"):
            execute(tmp_path, public_model="research:whisper-base")

    def test_an_unreachable_runtime_refuses_as_p7(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("nothing listening")

        transport = httpx.MockTransport(refuse)
        real = httpx.Client
        monkeypatch.setattr(
            "intelliai_evaluation.campaign.httpx.Client",
            lambda **kw: (kw.pop("timeout", None), real(transport=transport, **kw))[1],
        )
        with pytest.raises(PreconditionError, match=r"\[P-7\]"):
            execute(tmp_path)

    def test_an_undescribed_runtime_refuses_as_p7(self, wired: Wire, tmp_path: Path) -> None:
        # The PH0 stale-process lesson (F-1): a pre-B4a runtime answers
        # /info but cannot describe itself, and a session against it
        # cannot write a complete record.
        stale = {**INFO, "models": [{"slot": "default", "artifact": "whisper-small"}]}
        stale.pop("vad_owner")
        wired(FakeRuntime(info=stale))
        with pytest.raises(PreconditionError, match=r"\[P-7\]"):
            execute(tmp_path)

    def test_a_runtime_hosting_something_else_refuses_as_p6(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        other = {**INFO, "models": [{**INFO["models"][0], "artifact": "someone-else"}]}
        wired(FakeRuntime(info=other))
        with pytest.raises(PreconditionError, match=r"\[P-6\]"):
            execute(tmp_path)

    def test_nothing_is_written_when_a_precondition_fails(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # Fail closed means fail EMPTY: no manifest, no records, no
        # partial session for a later reader to mistake for evidence.
        wired(FakeRuntime(replies=enough_replies()))
        with pytest.raises(PreconditionError):
            execute(tmp_path, dataset="stt-eval-seed@v99")
        assert not (tmp_path / "sessions").exists()
        assert not (tmp_path / "results").exists()


# ─────────────────────────────────────────────────────────────────────
# Execution: identity, warm-up, manifest
# ─────────────────────────────────────────────────────────────────────


class TestSessionExecution:
    def test_every_record_carries_the_one_session_id(self, wired: Wire, tmp_path: Path) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        result = execute(tmp_path, language="zxx", runs=2)
        assert len(result.record_paths) == 2
        for path in result.record_paths:
            run = EvalRun.model_validate_json(path.read_text(encoding="utf-8"))
            assert run.session_id == "CAMP-STT-2026A/PH0/S90-smoke"

    def test_w1_is_recorded_in_the_manifest_and_excluded_from_records(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # Recorded, never discarded: our own data shows the first request
        # can be FASTER than steady state, and that residual is worth
        # keeping. Excluded: the zxx slice has 2 clips, so a record holds
        # exactly 2 results however many warm-up requests preceded them.
        runtime = wired(FakeRuntime(replies=enough_replies()))
        result = execute(tmp_path, language="zxx", warmup_requests=3, runs=1)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        assert len(manifest["w1_warm_up"]) == 3
        assert all("wall_ms" in probe for probe in manifest["w1_warm_up"])
        run = EvalRun.model_validate_json(result.record_paths[0].read_text(encoding="utf-8"))
        assert len(run.clips) == 2
        # 3 warm-up + 2 measured: the runtime saw every request the
        # session made, and the record kept only the measured ones.
        assert len(runtime.requests) == 5

    def test_the_manifest_lists_every_record_with_its_hash(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        result = execute(tmp_path, language="zxx", runs=2)
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        assert len(manifest["records"]) == 2
        for entry, path in zip(manifest["records"], result.record_paths, strict=True):
            assert entry["file"] == path.name
            assert len(entry["sha256"]) == 64
            assert entry["slice"].startswith("intelliai-stt/zxx/")

    def test_the_manifest_captures_info_verbatim_and_the_assertion(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        result = execute(tmp_path, language="zxx", idle_by="A Named Person")
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
        assert manifest["runtime_info"] == INFO  # P-7: verbatim
        assert manifest["operator_assertions"]["asserted_by"] == "A Named Person"
        assert set(manifest["preconditions"]) >= {"P-1", "P-2", "P-4", "P-5", "P-6", "P-7", "P-9"}

    def test_the_operator_assertion_enters_each_record_as_a_claim(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        # An assertion is a person's statement, held as a claim — exactly
        # what Authorship.OPERATOR and Basis.CLAIM exist to say.
        wired(FakeRuntime(replies=enough_replies()))
        result = execute(tmp_path, language="zxx", idle_by="A Named Person")
        run = EvalRun.model_validate_json(result.record_paths[0].read_text(encoding="utf-8"))
        (assertion,) = [d for d in run.determinations if d.code == "otherwise_idle_asserted"]
        assert assertion.authored_by is Authorship.OPERATOR
        assert assertion.basis is Basis.CLAIM
        assert "A Named Person" in assertion.detail

    def test_a_session_id_is_never_reused(self, wired: Wire, tmp_path: Path) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        execute(tmp_path, language="zxx")
        with pytest.raises(PreconditionError, match="already executed"):
            execute(tmp_path, language="zxx")

    def test_record_names_derive_from_identity_and_sanitise_research_subjects(
        self, wired: Wire, tmp_path: Path
    ) -> None:
        wired(FakeRuntime(replies=enough_replies()))
        result = execute(tmp_path, language="zxx", runs=2)
        run = EvalRun.model_validate_json(result.record_paths[0].read_text(encoding="utf-8"))
        session = SessionId.parse("CAMP-STT-2026A/PH0/S90-smoke")
        first = record_filename(run, session, 1)
        second = record_filename(run, session, 2)
        assert first.endswith("-s90-smoke.json")
        assert second.endswith("-s90-smoke-r2.json")
        assert result.record_paths[0].name == first
        # A research subject is a legal identity and an illegal Windows
        # filename; the colon never reaches the filesystem.
        assert run.identity is not None
        sanitised = run.model_copy(
            update={"identity": run.identity.model_copy(update={"public_model": "research:x"})}
        )
        assert ":" not in record_filename(sanitised, session, 1)
