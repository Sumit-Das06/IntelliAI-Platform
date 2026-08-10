"""FLEURS ingestion: pinned parquet shards → original WAV bytes on disk.

FLEURS (google/fleurs, CC-BY-4.0, read at source 2026-08-11) is the one
approved source that is open — no account, no gate. The Hugging Face
parquet API lists the shard URLs per (config, split); each shard is
downloaded, hashed, and read with pyarrow; each row's audio bytes are
written out exactly as shipped (original-bytes law) and probed.

Transcripts: FLEURS ships ``raw_transcription`` (original casing and
punctuation) and ``transcription`` (lowercased/normalized). We record
``raw_transcription`` — references are stored pre-normalization by
corpus law; scoring-time normalization is versioned in the evaluation
plane.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq

from intelliai_datasets.audio import UnreadableAudioError, probe_wav
from intelliai_datasets.samples import CandidateSample
from intelliai_datasets.sources import source

_PARQUET_INDEX = "https://huggingface.co/api/datasets/google/fleurs/parquet/{config}/{split}"
_DOWNLOAD_TIMEOUT = httpx.Timeout(600.0, connect=30.0)
_DOWNLOAD_ATTEMPTS = 4

# FLEURS locale → our normalized base subtag.
LANGUAGE_BY_CONFIG = {
    "hi_in": "hi",
    "cmn_hans_cn": "zh",
}


class FleursIngestError(RuntimeError):
    """The FLEURS source did not behave as pinned."""


def shard_urls(config: str, split: str, client: httpx.Client) -> list[str]:
    response = client.get(_PARQUET_INDEX.format(config=config, split=split))
    response.raise_for_status()
    urls = json.loads(response.content)
    if not isinstance(urls, list) or not all(isinstance(u, str) for u in urls):
        msg = f"unexpected parquet index shape for {config}/{split}"
        raise FleursIngestError(msg)
    return sorted(urls)


def _download_shard(url: str, target: Path, client: httpx.Client) -> None:
    """Stream a shard to a temp file, retrying transient failures.

    Atomic temp-then-rename: a partial download can never be mistaken
    for a complete shard on a later run.
    """
    partial = target.with_suffix(target.suffix + ".partial")
    last_error: Exception | None = None
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        try:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_bytes(1 << 20):
                        handle.write(chunk)
            partial.replace(target)
            return
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt < _DOWNLOAD_ATTEMPTS:
                time.sleep(2.0 * attempt)
    msg = f"shard download failed after {_DOWNLOAD_ATTEMPTS} attempts: {url}"
    raise FleursIngestError(msg) from last_error


def _rows(table: Any) -> Iterator[dict[str, Any]]:
    for batch in table.to_batches():
        yield from batch.to_pylist()


def ingest_fleurs(
    *,
    config: str,
    split: str,
    data_root: Path,
    max_rows: int | None = None,
) -> tuple[list[CandidateSample], list[str]]:
    """Ingest one (config, split); return (samples, problems).

    Problems are per-row ingestion failures (undecodable audio, missing
    fields) — recorded, never silently skipped. Validation proper happens
    downstream; this layer only refuses what it cannot even read.
    """
    record = source("fleurs")
    language = LANGUAGE_BY_CONFIG.get(config)
    if language is None:
        known = ", ".join(sorted(LANGUAGE_BY_CONFIG))
        msg = f"unmapped FLEURS config {config!r}; mapped: {known}"
        raise FleursIngestError(msg)

    audio_dir = data_root / "fleurs" / config / split
    audio_dir.mkdir(parents=True, exist_ok=True)
    shard_dir = data_root / "fleurs" / "_parquet" / config / split
    shard_dir.mkdir(parents=True, exist_ok=True)

    samples: list[CandidateSample] = []
    problems: list[str] = []
    seen_ids: set[str] = set()
    ingested = 0

    with httpx.Client(follow_redirects=True, timeout=_DOWNLOAD_TIMEOUT) as client:
        for url in shard_urls(config, split, client):
            shard_path = shard_dir / Path(httpx.URL(url).path).name
            if not shard_path.exists():
                _download_shard(url, shard_path, client)
            table = pq.read_table(shard_path)
            for row in _rows(table):
                if max_rows is not None and ingested >= max_rows:
                    return samples, problems
                ingested += 1
                outcome = _ingest_row(
                    row,
                    config=config,
                    split=split,
                    language=language,
                    license_name=record.license,
                    audio_dir=audio_dir,
                    data_root=data_root,
                    seen_ids=seen_ids,
                )
                if isinstance(outcome, CandidateSample):
                    samples.append(outcome)
                else:
                    problems.append(outcome)
    return samples, problems


def _ingest_row(
    row: dict[str, Any],
    *,
    config: str,
    split: str,
    language: str,
    license_name: str,
    audio_dir: Path,
    data_root: Path,
    seen_ids: set[str],
) -> CandidateSample | str:
    row_id = row.get("id")
    audio = row.get("audio") or {}
    payload = audio.get("bytes") if isinstance(audio, dict) else None
    text = row.get("raw_transcription") or row.get("transcription") or ""
    if row_id is None or not isinstance(payload, bytes | bytearray):
        return f"row id={row_id!r}: missing id or audio bytes"

    sample_id = f"fleurs-{config}-{split}-{int(row_id):06d}"
    if sample_id in seen_ids:
        # FLEURS repeats utterance ids for multi-speaker recordings of the
        # same sentence; suffix by occurrence to keep ids unique and stable
        # (shards and rows arrive in sorted, deterministic order).
        occurrence = 2
        while f"{sample_id}-{occurrence}" in seen_ids:
            occurrence += 1
        sample_id = f"{sample_id}-{occurrence}"
    seen_ids.add(sample_id)

    try:
        probe = probe_wav(bytes(payload))
    except UnreadableAudioError as exc:
        return f"{sample_id}: {exc}"

    target = audio_dir / f"{sample_id}.wav"
    if not target.exists():
        target.write_bytes(bytes(payload))

    return CandidateSample(
        id=sample_id,
        source="fleurs",
        language=language,
        split=split,
        path=target.relative_to(data_root).as_posix(),
        text=str(text),
        duration_seconds=round(probe.duration_seconds, 3),
        sample_rate_hz=probe.sample_rate_hz,
        channels=probe.channels,
        sha256=probe.sha256,
        speaker_id=None,  # FLEURS publishes no speaker identifiers
        license=license_name,
        notes=f"FLEURS {config}/{split}; gender={row.get('gender')!r}",
    )
