"""Future capabilities plug into the UNCHANGED runner (M3 step 6 demo).

Three sources with deliberately different internal shapes — a future TTS
engine, a voice-cloning engine (renders through a per-org reference
speaker), and a speech-to-speech engine (renders from an internal source
utterance) — all meet the same SynthesisSource seam. The runner, schema,
metrics, and judge are byte-identical for every one of them: evaluation
grows by ADDING adapters, never by editing the framework
(SPEECH_EVALUATION.md — evaluators are only ever added).
"""

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
    SpeechEvalRun,
)
from intelliai_evaluation.speech_runner import SynthesisError, SynthesisOutcome, run_speech_eval
from test_signal import tone, wav_of

RUNTIME = RuntimeIdentity(service="tts-runtime", service_version="0.0.0")


def corpus() -> SpeechCorpus:
    return SpeechCorpus(
        name="extension-demo",
        version=1,
        provenance=CorpusProvenance(
            author="tests",
            created=datetime.date(2026, 8, 3),
            rationale="capability-extension demonstration",
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
            ),
        ),
    )


class OrderedJudge:
    """Canned transcripts by call order; knows who it is (§4 discipline)."""

    def __init__(self, transcripts: tuple[str, ...]) -> None:
        self.identity = JudgeIdentity(
            capability="transcription", artifact="whisper-small", version=1, runtime_version="0.1.0"
        )
        self._transcripts = transcripts
        self._calls = 0

    def transcribe(self, wav_bytes: bytes, language: str | None) -> str:
        self._calls += 1
        return self._transcripts[self._calls - 1]


class FutureTtsEngineSource:
    """A successor TTS engine: text in, audio out — the plain shape."""

    def synthesize(self, text: str, params: dict[str, str]) -> SynthesisOutcome:
        return SynthesisOutcome(wav_bytes=wav_of(tone(1.0)), latency_ms=150.0)


class VoiceCloningSource:
    """A cloning engine: renders through a per-organization reference
    speaker. The governance requirement (a consent-bound reference) rides
    the params — and its absence is a synthesis FAILURE, recorded as
    evidence, exactly how the consent gate should surface in evaluation."""

    def synthesize(self, text: str, params: dict[str, str]) -> SynthesisOutcome:
        reference = params.get("reference_speaker")
        if reference is None:
            raise SynthesisError("no consent-bound reference speaker supplied")
        return SynthesisOutcome(wav_bytes=wav_of(tone(0.8)), latency_ms=420.0)


class SpeechToSpeechSource:
    """An S2S engine: internally renders a SOURCE utterance first, then
    converts — two model passes behind the same one-method seam."""

    def synthesize(self, text: str, params: dict[str, str]) -> SynthesisOutcome:
        source_utterance = wav_of(tone(0.5))  # internal first pass
        assert source_utterance  # the seam never sees this intermediate
        return SynthesisOutcome(wav_bytes=wav_of(tone(1.2)), latency_ms=800.0)


def run_with(source: object, artifact: str, lineage: str, params: dict[str, str]) -> SpeechEvalRun:
    return run_speech_eval(
        corpus=corpus(),
        source=source,  # type: ignore[arg-type]
        judge=OrderedJudge(("hello evaluation world",)),
        evaluated=EvaluatedArtifact(artifact=artifact, version=1, lineage=lineage),
        runtime=RUNTIME,
        hardware="test machine",
        synthesis_params=params,
    )


def test_three_capability_shapes_one_unchanged_runner() -> None:
    records = [
        run_with(FutureTtsEngineSource(), "successor-tts", "successor", {}),
        run_with(
            VoiceCloningSource(),
            "cloning-v1",
            "chatterbox",
            {"reference_speaker": "org_123/consented-voice-7"},
        ),
        run_with(SpeechToSpeechSource(), "s2s-v1", "s2s", {"source_language": "hi"}),
    ]
    for record in records:
        assert isinstance(record, SpeechEvalRun)  # schema holds for every shape
        assert record.aggregate_metrics["round_trip_wer"] == 0.0
        assert record.cases[0].failure is None
    # Reproducibility metadata is capability-specific and recorded verbatim.
    assert records[1].synthesis_params == {"reference_speaker": "org_123/consented-voice-7"}
    assert records[2].synthesis_params == {"source_language": "hi"}
    # The three evaluated identities are distinct evidence subjects.
    assert [r.evaluated.lineage for r in records] == ["successor", "chatterbox", "s2s"]


def test_cloning_governance_failure_is_evidence_not_a_crash() -> None:
    record = run_with(VoiceCloningSource(), "cloning-v1", "chatterbox", {})
    (case,) = record.cases
    assert case.failure is not None
    assert "consent" in case.failure  # graduated honesty, preserved verbatim
    assert "round_trip_wer" not in record.aggregate_metrics  # nothing judged
