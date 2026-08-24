"""M44 — freeze the governed research dataset qwen-en-public-train@v1.

Source: LJSpeech-1.1 (public domain; single English speaker; 13,100
clips @ 22.05 kHz). This instrument validates every candidate row,
selects deterministic utterance-level splits, picks ONE pinned
reference clip (the official recipe wants the same ref_audio on every
row), and writes:

  - manifest (v1, frozen): provenance + per-row id/text/duration/sha256
    /split + rejection counts — the identity every later artifact cites
  - train_raw.jsonl / pilot_raw.jsonl / tiny_raw.jsonl in the OFFICIAL
    input format ({audio, text, ref_audio})
  - eval text lists (val / held-out test) for the frozen benchmark

Deterministic: seed 44, sorted inputs — same archive, same manifest,
forever. Research instrument only; nothing here is an evaluation-plane
corpus.

Run in WSL (data lives there):
  python m44_dataset_freeze.py --lj-dir ~/m44/data/LJSpeech-1.1 \
    --out-dir ~/m44/dataset --manifest-out <repo evidence path>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import wave
from pathlib import Path

TRAIN_ROWS = 1000
VAL_ROWS = 50
TEST_ROWS = 100
PILOT_ROWS = 100
TINY_ROWS = 5
MIN_SECONDS = 1.0
MAX_SECONDS = 15.0
REF_MIN_SECONDS = 5.0
REF_MAX_SECONDS = 8.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def wav_facts(path: Path) -> tuple[float, int, int] | None:
    try:
        with wave.open(str(path), "rb") as fh:
            frames, rate, channels = fh.getnframes(), fh.getframerate(), fh.getnchannels()
        return frames / float(rate), rate, channels
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lj-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--archive", default=None, help="tar.bz2 path for the archive sha256")
    args = parser.parse_args()

    lj_dir = Path(args.lj_dir).expanduser()
    out_dir = Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    rejections: dict[str, int] = {}

    def reject(reason: str) -> None:
        rejections[reason] = rejections.get(reason, 0) + 1

    rows: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    for line in (lj_dir / "metadata.csv").read_text(encoding="utf-8").splitlines():
        parts = line.split("|")
        if len(parts) != 3:
            reject("malformed_metadata_row")
            continue
        clip_id, _raw, normalized = parts
        text = normalized.strip()
        wav_path = lj_dir / "wavs" / f"{clip_id}.wav"
        if not text:
            reject("empty_transcript")
            continue
        if clip_id in seen_ids:
            reject("duplicate_id")
            continue
        if text.lower() in seen_texts:
            reject("duplicate_text")
            continue
        if not wav_path.exists():
            reject("missing_audio")
            continue
        facts = wav_facts(wav_path)
        if facts is None:
            reject("audio_does_not_decode")
            continue
        seconds, rate, channels = facts
        if rate != 22050 or channels != 1:
            reject("unexpected_format")
            continue
        if not (MIN_SECONDS <= seconds <= MAX_SECONDS):
            reject("duration_out_of_bounds")
            continue
        # ~11 chars/second is loose; catches text/audio mismatches
        # without punishing normal reading speed.
        if len(text) / seconds > 30 or len(text) / seconds < 3:
            reject("text_audio_ratio_implausible")
            continue
        seen_ids.add(clip_id)
        seen_texts.add(text.lower())
        rows.append({"id": clip_id, "text": text, "seconds": round(seconds, 3)})

    rows.sort(key=lambda row: str(row["id"]))
    rng = random.Random(44)  # noqa: S311 - deterministic split shuffle, not cryptography

    # The pinned reference clip: deterministic first candidate in the
    # 5-8 s band whose transcript has no digits (a clean read sentence).
    reference = next(
        row
        for row in rows
        if REF_MIN_SECONDS <= float(str(row["seconds"])) <= REF_MAX_SECONDS
        and not any(ch.isdigit() for ch in str(row["text"]))
    )
    pool = [row for row in rows if row["id"] != reference["id"]]
    rng.shuffle(pool)

    need = TRAIN_ROWS + VAL_ROWS + TEST_ROWS
    if len(pool) < need:
        msg = f"only {len(pool)} valid rows; need {need}"
        raise SystemExit(msg)
    split_of: dict[str, str] = {}
    for row in pool[:TRAIN_ROWS]:
        split_of[str(row["id"])] = "train"
    for row in pool[TRAIN_ROWS : TRAIN_ROWS + VAL_ROWS]:
        split_of[str(row["id"])] = "val"
    for row in pool[TRAIN_ROWS + VAL_ROWS : need]:
        split_of[str(row["id"])] = "test"

    ref_wav = lj_dir / "wavs" / f"{reference['id']}.wav"
    manifest_rows = []
    jsonl = {"train": [], "val": [], "test": []}  # type: dict[str, list[dict[str, str]]]
    for row in pool[:need]:
        clip_id = str(row["id"])
        wav_path = lj_dir / "wavs" / f"{clip_id}.wav"
        split = split_of[clip_id]
        manifest_rows.append(
            {
                "id": clip_id,
                "split": split,
                "text": row["text"],
                "seconds": row["seconds"],
                "sha256": sha256_file(wav_path),
            }
        )
        jsonl[split].append(
            {"audio": str(wav_path), "text": str(row["text"]), "ref_audio": str(ref_wav)}
        )

    train = jsonl["train"]
    for name, subset in (
        ("train_raw.jsonl", train),
        ("pilot_raw.jsonl", train[:PILOT_ROWS]),
        ("tiny_raw.jsonl", train[:TINY_ROWS]),
        ("val_raw.jsonl", jsonl["val"]),
    ):
        with (out_dir / name).open("w", encoding="utf-8") as fh:
            for entry in subset:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Frozen evaluation texts: the held-out test transcripts (in-domain)
    # and the val transcripts (checkpoint selection only, never test).
    for name, split in (("eval-test-texts.json", "test"), ("eval-val-texts.json", "val")):
        cases = [
            {"id": r["id"], "language": "en", "category": "lj_heldout", "text": r["text"]}
            for r in manifest_rows
            if r["split"] == split
        ]
        (out_dir / name).write_text(
            json.dumps({"name": f"qwen-en-public-{split}@v1", "cases": cases}, indent=2),
            encoding="utf-8",
        )

    manifest = {
        "dataset": "qwen-en-public-train@v1",
        "source": {
            "name": "LJSpeech-1.1",
            "url": "https://keithito.com/LJ-Speech-Dataset/",
            "license": "Public domain (LibriVox recordings of public-domain texts; "
            "dataset page: 'This data is in the public domain')",
            "archive_sha256": sha256_file(Path(args.archive).expanduser())
            if args.archive
            else None,
        },
        "policy": {
            "speaker_strategy": "single speaker (the corpus's only speaker); one pinned "
            "ref_audio on every row per the official recipe",
            "transcripts": "LJSpeech normalized transcription field",
            "splits": f"seed 44, utterance-level: train {TRAIN_ROWS} / val {VAL_ROWS} / "
            f"test {TEST_ROWS}; held-out test never trains",
            "validation": "decode + 22050Hz mono + 1-15s + non-empty unique transcript "
            "+ chars/sec plausibility",
        },
        "reference_clip": {
            "id": reference["id"],
            "text": reference["text"],
            "seconds": reference["seconds"],
            "sha256": sha256_file(ref_wav),
        },
        "counts": {
            "source_rows": 13100,
            "valid_rows": len(rows),
            "frozen_rows": need,
            "rejections": rejections,
        },
        "hours_frozen": round(sum(float(str(r["seconds"])) for r in manifest_rows) / 3600, 2),
        "rows": manifest_rows,
    }
    manifest_path = Path(args.manifest_out)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "valid": len(rows),
                "frozen": need,
                "hours": manifest["hours_frozen"],
                "reference": reference["id"],
                "rejections": rejections,
            }
        )
    )


if __name__ == "__main__":
    main()
