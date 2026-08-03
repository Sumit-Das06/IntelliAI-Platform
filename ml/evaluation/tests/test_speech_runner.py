"""The runner: orchestration only, failures preserved, deterministic."""

import datetime

from intelliai_evaluation.corpus import (
    CorpusProvenance,
    Difficulty,
    SpeechCorpus,
    SpeechTextCase,
    TextCategory,
)
from intelliai_evaluation.speech_results import (
    EvaluatedArtifact,
    JudgeIdentity,
    RuntimeIdentity,
)
from intelliai_evaluation.speech_runner import (
    JudgeError,
    SynthesisError,
    SynthesisOutcome,
    run_speech_eval,
)
from test_signal import tone, wav_of

EVALUATED = EvaluatedArtifact(artifact="fake-voice", version=1, lineage="fake")
RUNTIME = RuntimeIdentity(service="tts-runtime", service_version="0.0.0")


def corpus() -> SpeechCorpus:
    return SpeechCorpus(
        name="runner-test",
        version=1,
        provenance=CorpusProvenance(
            author="tests",
            created=datetime.date(2026, 8, 3),
            rationale="runner tests",
            source="synthetic",
            languages=("en",),
        ),
        cases=(
            SpeechTextCase(
                id="case-a",
                language="en",
                category=TextCategory.GENERAL,
                difficulty=Difficulty.EASY,
                text="hello evaluation world",
                trap_words=("evaluation",),
            ),
            SpeechTextCase(
                id="case-b",
                language="en",
                category=TextCategory.TECHNICAL,
                difficulty=Difficulty.MEDIUM,
                text="the api gateway",
                trap_words=("api",),
            ),
        ),
    )


class FakeSource:
    """Deterministic synthesis: same text, same tone, fixed latency."""

    def __init__(self, fail_ids: tuple[str, ...] = (), garbage_ids: tuple[str, ...] = ()) -> None:
        self._fail_texts = fail_ids
        self._garbage = garbage_ids
        self.calls: list[str] = []

    def synthesize(self, text: str, params: dict[str, str]) -> SynthesisOutcome:
        self.calls.append(text)
        if text in self._fail_texts:
            raise SynthesisError("timeout after 30s")
        if text in self._garbage:
            return SynthesisOutcome(wav_bytes=b"not a wav at all", latency_ms=5.0)
        return SynthesisOutcome(wav_bytes=wav_of(tone(1.0)), latency_ms=200.0)


class FakeJudge:
    """Echoes the text it was 'shown' via a canned map; knows who it is."""

    def __init__(self, name: str = "whisper-small", transcripts: dict[str, str] | None = None):
        self.identity = JudgeIdentity(
            capability="transcription", artifact=name, version=1, runtime_version="0.1.0"
        )
        self._transcripts = transcripts
        self._calls = 0

    def transcribe(self, wav_bytes: bytes, language: str | None) -> str:
        if self._transcripts is None:
            raise JudgeError("unavailable")
        self._calls += 1
        return list(self._transcripts.values())[self._calls - 1]


def run_with(source: FakeSource, judge: FakeJudge, **kwargs: object):  # type: ignore[no-untyped-def]
    return run_speech_eval(
        corpus=corpus(),
        source=source,
        judge=judge,
        evaluated=EVALUATED,
        runtime=RUNTIME,
        hardware="test machine",
        **kwargs,  # type: ignore[arg-type]
    )


class TestHappyPath:
    def test_full_record_with_scores_and_baseline_identity(self) -> None:
        judge = FakeJudge(transcripts={"a": "hello evaluation world", "b": "the api gateway"})
        record = run_with(FakeSource(), judge, baseline_name="2026-08-03-fake-cpu")
        assert record.baseline_name == "2026-08-03-fake-cpu"
        assert [c.case_id for c in record.cases] == ["case-a", "case-b"]  # manifest order
        assert record.aggregate_metrics["round_trip_wer"] == 0.0
        assert record.aggregate_metrics["pronunciation_accuracy"] == 1.0
        assert record.judge.artifact == "whisper-small"
        assert all(c.failure is None for c in record.cases)

    def test_rtf_and_latency_recorded(self) -> None:
        judge = FakeJudge(transcripts={"a": "hello evaluation world", "b": "the api gateway"})
        record = run_with(FakeSource(), judge)
        assert record.aggregate_metrics["synthesis_latency_ms"] == 200.0
        assert 0.15 <= record.aggregate_metrics["rtf"] <= 0.25  # 200ms for 1s audio


class TestFailuresAreEvidence:
    def test_synthesis_failure_recorded_run_continues(self) -> None:
        source = FakeSource(fail_ids=("hello evaluation world",))
        judge = FakeJudge(transcripts={"b": "the api gateway"})
        record = run_with(source, judge)
        failed, succeeded = record.cases
        assert failed.failure == "synthesis: timeout after 30s"
        assert failed.metrics == {}
        assert succeeded.failure is None
        assert succeeded.metrics["round_trip_wer"] == 0.0

    def test_invalid_audio_recorded_with_latency(self) -> None:
        source = FakeSource(garbage_ids=("hello evaluation world",))
        judge = FakeJudge(transcripts={"b": "the api gateway"})
        record = run_with(source, judge)
        assert record.cases[0].failure is not None
        assert record.cases[0].failure.startswith("invalid audio")
        assert record.cases[0].metrics == {"synthesis_latency_ms": 5.0}

    def test_judge_failure_preserves_signal_evidence(self) -> None:
        record = run_with(FakeSource(), FakeJudge(transcripts=None))
        for case in record.cases:
            assert case.failure == "judge: unavailable"
            # The waveform still proved what it proved.
            assert case.metrics["clipping_ratio"] == 0.0
            assert case.metrics["silence_ratio"] == 0.0
            assert "round_trip_wer" not in case.metrics

    def test_aggregates_average_only_what_measured(self) -> None:
        source = FakeSource(fail_ids=("hello evaluation world",))
        judge = FakeJudge(transcripts={"b": "the api gateway"})
        record = run_with(source, judge)
        assert record.aggregate_metrics["round_trip_wer"] == 0.0  # one sample, not zero-padded


class TestDeterminismAndReplaceability:
    def test_identical_runs_produce_identical_evidence_modulo_wall_clock(self) -> None:
        def one_run() -> dict[str, object]:
            judge = FakeJudge(transcripts={"a": "hello evaluation world", "b": "the api gateway"})
            record = run_with(FakeSource(), judge)
            dumped: dict[str, object] = record.model_dump()
            del dumped["run_at"]  # the only expected variance
            return dumped

        assert one_run() == one_run()

    def test_swapping_the_judge_changes_only_the_judge_identity(self) -> None:
        transcripts = {"a": "hello evaluation world", "b": "the api gateway"}
        first = run_with(FakeSource(), FakeJudge("whisper-small", dict(transcripts)))
        second = run_with(FakeSource(), FakeJudge("intelliai-stt-v1", dict(transcripts)))
        assert first.judge.artifact != second.judge.artifact
        assert first.aggregate_metrics == second.aggregate_metrics  # runner unchanged
