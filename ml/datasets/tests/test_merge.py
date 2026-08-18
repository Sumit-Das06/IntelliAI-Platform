"""M23 merge: pins re-verified, collisions refused, composition guarded."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelliai_datasets.merge import (
    MergeError,
    enforce_language_shares,
    merge_rows,
    merged_statistics,
    read_part,
    write_merged_jsonl,
)


def freeze_part(tmp_path: Path, name: str, rows: list[dict[str, object]]) -> tuple[Path, Path]:
    """Write a tiny frozen part + sidecar the way the freezer would."""
    import hashlib

    lines = [json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in rows]
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    jsonl = tmp_path / f"{name}.jsonl"
    jsonl.write_bytes(payload)
    sidecar = tmp_path / f"{name}.provenance.json"
    sidecar.write_text(
        json.dumps(
            {
                "manifest": {
                    "path": jsonl.as_posix(),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "samples": len(rows),
                    "duration_seconds": round(
                        sum(float(str(r["duration_seconds"])) for r in rows), 3
                    ),
                },
                "speaker_ids_available": True,
                "sources": [],
                "source_splits": ["train"],
            }
        ),
        encoding="utf-8",
    )
    return jsonl, sidecar


def row(id_: str, *, language: str = "hi", duration: float = 3.0) -> dict[str, object]:
    return {
        "id": id_,
        "audio": f"src/{id_}.wav",
        "text": "" if language == "zxx" else "नमस्ते" if language == "hi" else "hello",
        "language": language,
        "duration_seconds": duration,
    }


class TestReadPart:
    def test_pin_verified_part_loads(self, tmp_path: Path) -> None:
        jsonl, sidecar = freeze_part(tmp_path, "a", [row("a-1"), row("a-2")])
        part = read_part(jsonl, sidecar)
        assert len(part.rows) == 2

    def test_drifted_part_is_refused(self, tmp_path: Path) -> None:
        jsonl, sidecar = freeze_part(tmp_path, "a", [row("a-1")])
        jsonl.write_text(jsonl.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with pytest.raises(MergeError, match="does not match its sidecar pin"):
            read_part(jsonl, sidecar)


class TestMergeRows:
    def test_union_is_sorted_by_id(self, tmp_path: Path) -> None:
        a = read_part(*freeze_part(tmp_path, "a", [row("z-late"), row("b-mid")]))
        b = read_part(*freeze_part(tmp_path, "b", [row("a-early")]))
        merged = merge_rows([a, b])
        assert [r.id for r in merged] == ["a-early", "b-mid", "z-late"]

    def test_id_collision_is_refused(self, tmp_path: Path) -> None:
        a = read_part(*freeze_part(tmp_path, "a", [row("same")]))
        b_rows = [row("same")]
        b_rows[0]["audio"] = "src/other.wav"
        b = read_part(*freeze_part(tmp_path, "b", b_rows))
        with pytest.raises(MergeError, match="id 'same'"):
            merge_rows([a, b])

    def test_audio_path_collision_is_refused(self, tmp_path: Path) -> None:
        a = read_part(*freeze_part(tmp_path, "a", [row("one")]))
        b_rows = [row("two")]
        b_rows[0]["audio"] = "src/one.wav"
        b = read_part(*freeze_part(tmp_path, "b", b_rows))
        with pytest.raises(MergeError, match="audio path"):
            merge_rows([a, b])


class TestLanguageShares:
    def test_composition_inside_the_ceiling_passes(self, tmp_path: Path) -> None:
        part = read_part(
            *freeze_part(
                tmp_path,
                "a",
                [row("h-1"), row("h-2"), row("h-3"), row("e-1", language="en")],
            )
        )
        merged = merge_rows([part])
        enforce_language_shares(merged, {"en": 0.30})  # 25% <= 30%

    def test_a_dominating_language_is_refused_not_trimmed(self, tmp_path: Path) -> None:
        part = read_part(
            *freeze_part(
                tmp_path, "a", [row("h-1"), row("e-1", language="en"), row("e-2", language="en")]
            )
        )
        merged = merge_rows([part])
        with pytest.raises(MergeError, match="above the ceiling"):
            enforce_language_shares(merged, {"en": 0.10})


class TestWriteMerged:
    def test_byte_determinism_and_pin(self, tmp_path: Path) -> None:
        part = read_part(*freeze_part(tmp_path, "a", [row("a-1"), row("b-1", duration=1.5)]))
        merged = merge_rows([part])
        first = write_merged_jsonl(merged, tmp_path / "one.jsonl")
        second = write_merged_jsonl(merged, tmp_path / "two.jsonl")
        assert first.sha256 == second.sha256
        assert first.samples == 2
        assert first.duration_seconds == 4.5
        assert (tmp_path / "one.jsonl").read_bytes() == (tmp_path / "two.jsonl").read_bytes()

    def test_statistics_are_counted_by_language_and_band(self, tmp_path: Path) -> None:
        part = read_part(
            *freeze_part(
                tmp_path,
                "a",
                [row("iv-1", duration=1.0), row("iv-2", duration=6.0), row("fl-1", language="en")],
            )
        )
        stats = merged_statistics(merge_rows([part]))
        assert stats["language"] == {"hi": 2, "en": 1}
        assert stats["duration_bands"] == {"<2s": 1, "5-15s": 1, "2-5s": 1}
