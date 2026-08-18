"""M23: deterministic merge of frozen train manifests (the E3 composition).

A retention-mix corpus is a UNION of independently frozen parts — the
E2 corpus verbatim, an English retention slice, a bounded short-speech
slice — each already carrying its own provenance sidecar. The merge is
pure text: every part's pin is re-verified against its sidecar, global
id/path uniqueness is enforced, optional per-language share ceilings
guard the composition mechanically, and the output obeys the same
5-field byte law the freezer writes (fixed key order, compact
separators, LF, trailing newline, ascending id order).

Per-part validation (duration windows, eval disjointness, markup
policy, speaker roster) lives in each part's own sidecar; the merge
refuses to run without one and never re-litigates it. Content-hash
disjointness across parts is structural: within a part the freezer
deduplicates by hash, and across parts either the sources differ or
the duration windows are disjoint — the same audio bytes cannot
satisfy both a [2 s, 30 s] freeze and a [0.5 s, 2 s) freeze.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from intelliai_datasets.manifests import ManifestPin


class MergeError(RuntimeError):
    """A part drifted, collided, or broke a composition ceiling."""


class MergeRow(BaseModel):
    """One 5-field platform row, as frozen by ``write_train_jsonl``."""

    model_config = ConfigDict(frozen=True)

    id: str
    audio: str
    text: str
    language: str
    duration_seconds: float


class Part(BaseModel):
    """One frozen part: pin-verified rows plus the raw sidecar."""

    model_config = ConfigDict(frozen=True)

    pin: ManifestPin
    rows: tuple[MergeRow, ...]
    sidecar: dict[str, object]


def read_part(jsonl_path: Path, provenance_path: Path) -> Part:
    """Load one frozen part; refuse drift between bytes and sidecar pin."""
    sidecar = json.loads(provenance_path.read_text(encoding="utf-8"))
    pin = ManifestPin.model_validate(sidecar["manifest"])
    actual = hashlib.sha256(jsonl_path.read_bytes()).hexdigest()
    if actual != pin.sha256.lower():
        msg = (
            f"part {jsonl_path} does not match its sidecar pin: expected "
            f"{pin.sha256.lower()}, got {actual}. A frozen part never "
            "changes silently — refusing to merge."
        )
        raise MergeError(msg)
    rows = tuple(
        MergeRow.model_validate(json.loads(line))
        for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    if len(rows) != pin.samples:
        msg = f"part {jsonl_path} carries {len(rows)} rows but its pin records {pin.samples}"
        raise MergeError(msg)
    return Part(pin=pin, rows=rows, sidecar=sidecar)


def merge_rows(parts: Sequence[Part]) -> list[MergeRow]:
    """Union the parts; refuse any id or audio-path collision."""
    seen_ids: dict[str, str] = {}
    seen_audio: dict[str, str] = {}
    merged: list[MergeRow] = []
    for part in parts:
        for row in part.rows:
            if row.id in seen_ids:
                msg = f"id {row.id!r} appears in both {seen_ids[row.id]} and {part.pin.path}"
                raise MergeError(msg)
            if row.audio in seen_audio:
                msg = (
                    f"audio path {row.audio!r} appears in both "
                    f"{seen_audio[row.audio]} and {part.pin.path}"
                )
                raise MergeError(msg)
            seen_ids[row.id] = part.pin.path
            seen_audio[row.audio] = part.pin.path
            merged.append(row)
    return sorted(merged, key=lambda r: r.id)


def enforce_language_shares(rows: Sequence[MergeRow], ceilings: Mapping[str, float]) -> None:
    """Refuse a composition whose per-language ROW share exceeds a ceiling.

    The mechanical form of "do not let English dominate": a ceiling of
    ``{"en": 0.10}`` refuses any merge where English exceeds 10% of rows.
    """
    if not rows or not ceilings:
        return
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.language] = counts.get(row.language, 0) + 1
    for language, ceiling in ceilings.items():
        share = counts.get(language, 0) / len(rows)
        if share > ceiling:
            msg = (
                f"language {language!r} holds {share:.4f} of rows, above the "
                f"ceiling {ceiling:.4f} — the composition is refused, not trimmed"
            )
            raise MergeError(msg)


def write_merged_jsonl(rows: Sequence[MergeRow], target: Path) -> ManifestPin:
    """Write the merged manifest under the freezer's exact byte law."""
    ordered = sorted(rows, key=lambda r: r.id)
    lines = [
        json.dumps(
            {
                "id": row.id,
                "audio": row.audio,
                "text": row.text,
                "language": row.language,
                "duration_seconds": round(row.duration_seconds, 3),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for row in ordered
    ]
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return ManifestPin(
        path=target.as_posix(),
        sha256=hashlib.sha256(payload).hexdigest(),
        samples=len(ordered),
        duration_seconds=round(sum(r.duration_seconds for r in ordered), 3),
    )


def merged_statistics(rows: Sequence[MergeRow]) -> dict[str, dict[str, int]]:
    """Descriptive stats for the merged provenance — counted, never invented."""
    languages: dict[str, int] = {}
    durations: dict[str, int] = {}
    prefixes: dict[str, int] = {}
    for row in rows:
        languages[row.language] = languages.get(row.language, 0) + 1
        band = (
            "<2s"
            if row.duration_seconds < 2
            else "2-5s"
            if row.duration_seconds < 5
            else "5-15s"
            if row.duration_seconds < 15
            else "15-30s"
        )
        durations[band] = durations.get(band, 0) + 1
        prefix = row.id.split("-", 1)[0]
        prefixes[prefix] = prefixes.get(prefix, 0) + 1
    return {"language": languages, "duration_bands": durations, "id_prefix": prefixes}
