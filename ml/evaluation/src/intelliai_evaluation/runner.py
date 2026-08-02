"""STT evaluation runner: measure a LIVE runtime, exactly as customers use it.

Deliberately end-to-end over the runtime's HTTP binding: the number we
record is the number the product produces — pipeline, VAD short-circuit,
and engine together. (Silence probes therefore measure the SYSTEM's
hallucination behavior; after M2 step 4 the pipeline guarantees zero
hallucinated words for pure silence — the tone probe still exercises the
engine path.) Per-clip inference time comes from the runtime's own timing
stages, so RTF is engine inference over audio duration, not network time.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from intelliai_evaluation.dataset import EvalDataset
from intelliai_evaluation.fetch import materialize
from intelliai_evaluation.results import ClipResult, EvalRun
from intelliai_evaluation.wer import word_error_rate
from intelliai_runtime_contract import RuntimeResponse, TranscriptionResult

_TRANSCRIBE_ROUTE = "/v1/transcribe"
_INFO_ROUTE = "/info"


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


def run_stt_eval(
    dataset: EvalDataset,
    *,
    base_url: str,
    data_dir: Path,
    artifact: str,
    engine: str,
    engine_version: str,
    compute: str,
    hardware: str,
    notes: str = "",
) -> EvalRun:
    """Materialize every clip, transcribe each through the live runtime,
    score against references, and assemble the immutable run record."""
    paths = materialize(dataset, data_dir)
    clip_results: list[ClipResult] = []
    with httpx.Client(base_url=base_url, timeout=300) as client:
        load_ms, warmup_ms = _runtime_startup_stats(client, artifact)
        for clip in dataset.clips:
            audio_path = paths[clip.id]
            params: dict[str, str] = {"model": artifact}
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
        artifact=artifact,
        engine=engine,
        engine_version=engine_version,
        compute=compute,
        hardware=hardware,
        notes=notes,
        clips=clip_results,
        load_ms=load_ms,
        warmup_ms=warmup_ms,
    )
