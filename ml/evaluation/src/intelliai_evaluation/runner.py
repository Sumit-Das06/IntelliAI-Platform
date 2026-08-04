"""STT evaluation runner: measure a LIVE runtime, exactly as customers use it.

Deliberately end-to-end over the runtime's HTTP binding: the number we
record is the number the product produces — pipeline, VAD short-circuit,
and engine together. (Silence probes therefore measure the SYSTEM's
hallucination behavior; after M2 step 4 the pipeline guarantees zero
hallucinated words for pure silence — the tone probe still exercises the
engine path.) Per-clip inference time comes from the runtime's own timing
stages, so RTF is engine inference over audio duration, not network time.

**Route-aware since M5 step 4.** A run measures one *slice*: one public
model, one language, and the artifact the registry resolved for that
pair. The runner is handed that resolution — it never chooses an
artifact, and it refuses to run against a runtime that is not actually
hosting the one it was told to measure. A record that misnames its
subject is worse than no record.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from intelliai_evaluation.dataset import EvalClip, EvalDataset
from intelliai_evaluation.fetch import materialize
from intelliai_evaluation.identity import EvaluationIdentity, SliceCoverage
from intelliai_evaluation.resolution import ResolvedServing
from intelliai_evaluation.results import ClipResult, EvalRun
from intelliai_evaluation.wer import word_error_rate
from intelliai_runtime_contract import RuntimeResponse, TranscriptionResult

_TRANSCRIBE_ROUTE = "/v1/transcribe"
_INFO_ROUTE = "/info"


class ArtifactNotHostedError(RuntimeError):
    """The runtime is not serving the artifact this run is supposed to measure."""


def _runtime_startup_stats(
    client: httpx.Client, artifact: str
) -> tuple[float | None, float | None]:
    """Best-effort read of the serving model's load/warm-up cost from /info."""
    try:
        info = client.get(_INFO_ROUTE).json()
        for model in info.get("models", []):
            if model.get("artifact") == artifact:
                return model.get("load_ms"), model.get("warmup_ms")
    except (httpx.HTTPError, ValueError):
        return None, None
    return None, None


def _require_hosted(client: httpx.Client, artifact: str) -> None:
    """Reproducibility metadata comes from LIVE facts, never operator claims.

    The same discipline the synthesis evaluator has had since M2.5: if the
    runtime is not hosting what the registry resolved, the run would
    record a measurement of something else under this artifact's name.
    """
    info = client.get(_INFO_ROUTE).json()
    hosted = {model["artifact"] for model in info.get("models", [])}
    if artifact not in hosted:
        msg = f"runtime hosts {sorted(hosted)}, not {artifact!r}; refusing to record a misnamed run"
        raise ArtifactNotHostedError(msg)


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


def run_stt_eval(
    dataset: EvalDataset,
    *,
    base_url: str,
    data_dir: Path,
    public_model: str,
    language: str,
    serving: ResolvedServing,
    build: str,
    engine: str,
    engine_version: str,
    hardware: str,
    benchmark: str | None = None,
    notes: str = "",
) -> EvalRun:
    """Measure one slice against the artifact the registry resolved for it."""
    if serving.artifact is None or serving.artifact_version is None:  # pragma: no cover
        msg = "an unserved route has nothing to evaluate"
        raise ValueError(msg)
    clips = language_slice(dataset, language)
    if not clips:
        msg = f"dataset {dataset.name}@v{dataset.version} has no {language!r} clips"
        raise ValueError(msg)

    paths = materialize(dataset, data_dir)
    clip_results: list[ClipResult] = []
    with httpx.Client(base_url=base_url, timeout=300) as client:
        _require_hosted(client, serving.artifact)
        load_ms, warmup_ms = _runtime_startup_stats(client, serving.artifact)
        for clip in clips:
            audio_path = paths[clip.id]
            params: dict[str, str] = {"model": serving.artifact}
            if clip.language != "zxx":
                params["language"] = clip.language
            response = client.post(
                _TRANSCRIBE_ROUTE,
                files={"file": (audio_path.name, audio_path.read_bytes(), "audio/wav")},
                data={"params": json.dumps(params)},
            )
            response.raise_for_status()
            envelope = RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
            breakdown = word_error_rate(clip.reference_text, envelope.output.text)
            clip_results.append(
                ClipResult(
                    clip_id=clip.id,
                    duration_seconds=clip.duration_seconds,
                    inference_seconds=envelope.timing.stages.get("inference", 0.0) / 1000.0,
                    substitutions=breakdown.substitutions,
                    insertions=breakdown.insertions,
                    deletions=breakdown.deletions,
                    reference_words=breakdown.reference_words,
                    hypothesis_words=breakdown.hypothesis_words,
                    hypothesis_text=envelope.output.text,
                )
            )
    return EvalRun(
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        capability=dataset.capability,
        run_at=datetime.now(tz=UTC),
        artifact=serving.artifact,
        engine=engine,
        engine_version=engine_version,
        compute=build,
        hardware=hardware,
        notes=notes,
        clips=clip_results,
        load_ms=load_ms,
        warmup_ms=warmup_ms,
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
            run_at=datetime.now(tz=UTC),
        ),
        coverage=slice_coverage(clips, clip_results),
    )
