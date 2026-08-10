"""Generic authenticated HF-parquet ingestion: one adapter, per-dataset maps.

The FLEURS lesson generalized: every HF dataset ships the same parquet
transport with different column names. A ``ColumnMap`` names where the
audio bytes, transcript, speaker id, and row identity live; everything
downstream (validation, curation, manifests) stays source-agnostic.

Original bytes are stored exactly as shipped; WAV (PCM/IEEE float) and
FLAC are probed natively (the probe refuses anything else, and every
refusal is a recorded problem, never a silent skip — a dataset shipping
M4A, like Kathbath, is a recorded adapter gap, not a partial ingest).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq
from pydantic import BaseModel, ConfigDict

from intelliai_datasets import hf
from intelliai_datasets.audio import UnreadableAudioError, probe_audio
from intelliai_datasets.samples import CandidateSample
from intelliai_datasets.sources import source


class ColumnMap(BaseModel):
    """Where this dataset keeps each fact we need."""

    model_config = ConfigDict(frozen=True)

    audio: str  # struct column holding {bytes, path}
    text: str  # the transcript used as reference
    speaker: str | None = None  # None = source publishes no speaker ids
    row_id: str | None = None  # stable per-row name; None = positional
    note_fields: tuple[str, ...] = ()  # carried into CandidateSample.notes


class HfDatasetSpec(BaseModel):
    """One ingestable (dataset, config, split) with its column map."""

    model_config = ConfigDict(frozen=True)

    source_name: str  # sources.SourceRecord.name
    hf_id: str
    config: str
    split: str
    language: str
    columns: ColumnMap
    text_note: str  # WHY this text column is the reference (documented choice)


# The 15C presets. IndicVoices reference = `normalized` (orthographic
# ground truth; `verbatim` respells words phonetically — e.g. इस्थानीय for
# स्थानीय — which would penalize an engine for transcribing correct
# orthography). The decision is recorded here and in every provenance
# sidecar via `text_note`.
INDICVOICES_HI_VALID = HfDatasetSpec(
    source_name="indicvoices",
    hf_id="ai4bharat/IndicVoices",
    config="hindi",
    split="valid",
    language="hi",
    columns=ColumnMap(
        audio="audio_filepath",
        text="normalized",
        speaker="speaker_id",
        row_id=None,
        note_fields=("scenario", "gender", "age_group", "district"),
    ),
    text_note=(
        "reference = `normalized` (orthographic); `verbatim` captures "
        "phonetic respellings and would penalize orthographically correct "
        "transcription"
    ),
)

LAHAJA_TEST = HfDatasetSpec(
    source_name="lahaja",
    hf_id="ai4bharat/Lahaja",
    config="default",
    split="test",
    language="hi",
    columns=ColumnMap(
        audio="audio_filepath",
        text="normalized",
        speaker="sp_id",
        row_id="fname",
        note_fields=("scenario", "gender", "native_district"),
    ),
    text_note="reference = `normalized` (same rationale as IndicVoices)",
)

SPECS: dict[str, HfDatasetSpec] = {
    "indicvoices-hindi-valid": INDICVOICES_HI_VALID,
    "lahaja-test": LAHAJA_TEST,
}


class IngestResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    revision: str  # dataset repo sha at retrieval time
    samples: tuple[CandidateSample, ...]
    problems: tuple[str, ...]


def _rows(table: Any) -> Iterator[dict[str, Any]]:
    for batch in table.to_batches():
        yield from batch.to_pylist()


def ingest_hf(
    spec: HfDatasetSpec,
    *,
    data_root: Path,
    max_rows: int | None = None,
) -> IngestResult:
    record = source(spec.source_name)  # refuses unregistered sources loudly
    token = hf.discover_token()
    audio_dir = data_root / spec.source_name / spec.config / spec.split
    audio_dir.mkdir(parents=True, exist_ok=True)
    shard_dir = data_root / spec.source_name / "_parquet" / spec.config / spec.split
    shard_dir.mkdir(parents=True, exist_ok=True)

    samples: list[CandidateSample] = []
    problems: list[str] = []
    seen_ids: set[str] = set()
    ingested = 0

    with hf.client(token) as http:
        revision = hf.dataset_revision(spec.hf_id, http)
        for url in hf.shard_urls(spec.hf_id, spec.config, spec.split, http):
            shard_path = shard_dir / Path(httpx.URL(url).path).name
            if not shard_path.exists():
                hf.download_shard(url, shard_path, http)
            table = pq.read_table(shard_path)
            for index, row in enumerate(_rows(table)):
                if max_rows is not None and ingested >= max_rows:
                    return IngestResult(
                        revision=revision,
                        samples=tuple(samples),
                        problems=tuple(problems),
                    )
                ingested += 1
                outcome = _ingest_row(
                    row,
                    spec=spec,
                    license_name=record.license,
                    audio_dir=audio_dir,
                    data_root=data_root,
                    seen_ids=seen_ids,
                    positional=ingested - 1,
                    shard=shard_path.stem,
                    shard_index=index,
                )
                if isinstance(outcome, CandidateSample):
                    samples.append(outcome)
                else:
                    problems.append(outcome)
    return IngestResult(revision=revision, samples=tuple(samples), problems=tuple(problems))


def _ingest_row(
    row: dict[str, Any],
    *,
    spec: HfDatasetSpec,
    license_name: str,
    audio_dir: Path,
    data_root: Path,
    seen_ids: set[str],
    positional: int,
    shard: str,
    shard_index: int,
) -> CandidateSample | str:
    columns = spec.columns
    audio = row.get(columns.audio) or {}
    payload = audio.get("bytes") if isinstance(audio, dict) else None
    text = row.get(columns.text) or ""
    raw_name = str(row.get(columns.row_id) or "") if columns.row_id else ""
    stem = Path(raw_name).stem if raw_name else f"{shard}-{shard_index:06d}"
    sample_id = f"{spec.source_name}-{spec.config}-{spec.split}-{stem}"

    if not isinstance(payload, bytes | bytearray):
        return f"{sample_id}: missing audio bytes (row {positional})"
    if sample_id in seen_ids:
        occurrence = 2
        while f"{sample_id}-{occurrence}" in seen_ids:
            occurrence += 1
        sample_id = f"{sample_id}-{occurrence}"
    seen_ids.add(sample_id)

    try:
        probe = probe_audio(bytes(payload))
    except UnreadableAudioError as exc:
        return f"{sample_id}: {exc}"

    target = audio_dir / f"{sample_id}.{probe.container}"
    if not target.exists():
        target.write_bytes(bytes(payload))

    speaker: str | None = None
    if columns.speaker is not None:
        value = row.get(columns.speaker)
        speaker = str(value) if value not in (None, "") else None

    notes = " ".join(
        f"{field}={row.get(field)!r}" for field in columns.note_fields if row.get(field)
    )
    return CandidateSample(
        id=sample_id,
        source=spec.source_name,
        language=spec.language,
        split=spec.split,
        path=target.relative_to(data_root).as_posix(),
        text=str(text),
        duration_seconds=round(probe.duration_seconds, 3),
        sample_rate_hz=probe.sample_rate_hz,
        channels=probe.channels,
        sha256=probe.sha256,
        speaker_id=speaker,
        license=license_name,
        notes=f"{spec.hf_id}/{spec.config}/{spec.split} {notes}".strip(),
    )
