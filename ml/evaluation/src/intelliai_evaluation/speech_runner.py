"""The speech evaluation runner — orchestration ONLY.

    Corpus -> SynthesisSource -> Judge -> scoring -> SpeechEvalRun

Every stage is an interface: the runner knows no engine, no transport,
no metric formula. It loops the corpus in manifest order (determinism),
survives per-case failures (failures are evidence), and assembles the
immutable record. Replacing any component — a new TTS engine, a
different judge (IntelliAI-STT, external ASR, human transcription), a
future capability's synthesis call — changes an adapter, never this
loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx

from intelliai_evaluation.corpus import SpeechCorpus
from intelliai_evaluation.signal import analyze_wav
from intelliai_evaluation.speech_results import (
    METHODOLOGY_VERSION,
    CaseResult,
    EvaluatedArtifact,
    JudgeIdentity,
    RuntimeIdentity,
    SpeechEvalRun,
)
from intelliai_evaluation.speech_scoring import aggregate_cases, score_case, signal_metrics


class SynthesisError(Exception):
    """Sources raise this for any failure to produce audio (incl. timeout)."""


class JudgeError(Exception):
    """Judges raise this for any failure to transcribe."""


@dataclass(frozen=True)
class SynthesisOutcome:
    """What a source returns: audio plus what it cost."""

    wav_bytes: bytes
    latency_ms: float


class SynthesisSource(Protocol):
    """Anything that turns text into a WAV: an HTTP runtime client today,
    an in-process engine or future capability tomorrow."""

    def synthesize(self, text: str, params: dict[str, str]) -> SynthesisOutcome:
        """Produce audio for the text; raise SynthesisError on any failure."""
        ...


class Judge(Protocol):
    """Anything that turns audio into a transcript — and KNOWS WHO IT IS
    (multi-judge future: run once per judge, no runner change)."""

    @property
    def identity(self) -> JudgeIdentity: ...

    def transcribe(self, wav_bytes: bytes, language: str | None) -> str:
        """Transcribe the audio; raise JudgeError on any failure."""
        ...


def run_speech_eval(
    *,
    corpus: SpeechCorpus,
    source: SynthesisSource,
    judge: Judge,
    evaluated: EvaluatedArtifact,
    runtime: RuntimeIdentity,
    hardware: str,
    synthesis_params: dict[str, str] | None = None,
    baseline_name: str | None = None,
    notes: str = "",
) -> SpeechEvalRun:
    """One command's engine: corpus in, permanent evidence out."""
    params = synthesis_params or {}
    case_results: list[CaseResult] = []

    for case in corpus.cases:  # manifest order — deterministic by rule
        try:
            outcome = source.synthesize(case.text, params)
        except SynthesisError as exc:
            case_results.append(
                CaseResult(case_id=case.id, transcript="", metrics={}, failure=f"synthesis: {exc}")
            )
            continue

        try:
            analysis = analyze_wav(outcome.wav_bytes)
        except (ValueError, EOFError) as exc:
            case_results.append(
                CaseResult(
                    case_id=case.id,
                    transcript="",
                    metrics={"synthesis_latency_ms": outcome.latency_ms},
                    failure=f"invalid audio: {exc}",
                )
            )
            continue

        language = None if case.language == "mixed" else case.language
        try:
            transcript = judge.transcribe(outcome.wav_bytes, language)
        except JudgeError as exc:
            # Partial evidence: the waveform still proved what it proved.
            metrics = signal_metrics(case.text, analysis)
            metrics["synthesis_latency_ms"] = outcome.latency_ms
            case_results.append(
                CaseResult(case_id=case.id, transcript="", metrics=metrics, failure=f"judge: {exc}")
            )
            continue

        case_results.append(score_case(case, analysis, transcript, outcome.latency_ms))

    return SpeechEvalRun(
        corpus_name=corpus.name,
        corpus_version=corpus.version,
        methodology_version=METHODOLOGY_VERSION,
        evaluated=evaluated,
        judge=judge.identity,
        runtime=runtime,
        hardware=hardware,
        run_at=datetime.now(tz=UTC),
        synthesis_params=params,
        cases=tuple(case_results),
        aggregate_metrics=aggregate_cases(case_results),
        baseline_name=baseline_name,
        notes=notes,
    )


class HttpSttJudge:
    """The platform's own ears as the judge, over the STT runtime's HTTP
    binding. The first (and today only) Judge implementation."""

    def __init__(
        self,
        base_url: str,
        judge_artifact: str,
        judge_artifact_version: int,
        runtime_version: str,
        timeout_seconds: float = 300.0,
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout_seconds)
        self._artifact = judge_artifact
        self._identity = JudgeIdentity(
            capability="transcription",
            artifact=judge_artifact,
            version=judge_artifact_version,
            runtime_version=runtime_version,
        )

    @property
    def identity(self) -> JudgeIdentity:
        return self._identity

    def transcribe(self, wav_bytes: bytes, language: str | None) -> str:
        import json

        params: dict[str, str] = {"model": self._artifact}
        if language is not None:
            params["language"] = language
        try:
            response = self._client.post(
                "/v1/transcribe",
                files={"file": ("case.wav", wav_bytes, "audio/wav")},
                data={"params": json.dumps(params)},
            )
        except httpx.HTTPError as exc:
            raise JudgeError(f"judge unreachable: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise JudgeError(f"judge refused: HTTP {response.status_code}")
        try:
            text = response.json()["output"]["text"]
        except (ValueError, KeyError) as exc:
            raise JudgeError("malformed judge envelope") from exc
        return str(text)

    def close(self) -> None:
        self._client.close()
