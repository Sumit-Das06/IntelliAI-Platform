"""M29A — build the frozen hi-punct-eval@v1 benchmark (deterministic).

Source: google/fleurs data/hi_in/test.tsv at the pinned revision — TEXT ONLY
(no audio is downloaded; the audio identity is recorded so a future
end-to-end phase can fetch it from the pinned source).

Curation, in order, all deterministic:
  1. fetch test.tsv; REFUSE unless its sha256 equals the pinned value
  2. per row: reference = NFC(raw_transcription) with whitespace collapsed
  3. dedup by reference text (FLEURS records the same sentence read by up
     to 3 speakers; a TEXT-level benchmark scores each sentence once):
     first TSV occurrence keeps the row id; every recording's audio
     identity (file, gender, duration) is retained on the kept row
  4. rows keep TSV order

Outputs:
  ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json   (the manifest)
  ml/datasets/manifests/hi-punct-eval-v1.provenance.json      (identity)
  research/experiments/29a-hindi-punctuation-eval/harness/inputs.json
      (id -> punctuation-stripped restorer input, via the punct_slots@v1
       input preparation)

Run from the repo root:
  uv run --package intelliai-evaluation python \
      research/experiments/29a-hindi-punctuation-eval/build_dataset.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import unicodedata
import urllib.request
from pathlib import Path

from intelliai_evaluation.punctuation import (
    PUNCTUATION_RULER,
    SUPPORTED_MARKS,
    load_punctuation_dataset,
    strip_punctuation_for_input,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

TSV_URL = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/hi_in/test.tsv"
SOURCE_REVISION = "70bb2e84b976b7e960aa89f1c648e09c59f894dd"
TSV_SHA256 = "889e82e2875490f9533ff59ab67326fcfa01cf828fc4412758aaaa1f442a729f"

DATASET_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json"
PROVENANCE_PATH = ROOT / "ml/datasets/manifests/hi-punct-eval-v1.provenance.json"
INPUTS_PATH = HERE / "harness/inputs.json"


def freeze(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def main() -> None:
    req = urllib.request.Request(TSV_URL, headers={"User-Agent": "intelliai-research/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:  # noqa: S310 — pinned https
        raw_bytes = response.read()
    actual = hashlib.sha256(raw_bytes).hexdigest()
    if actual != TSV_SHA256:
        msg = f"source drifted: test.tsv sha256 {actual} != pinned {TSV_SHA256}"
        raise SystemExit(msg)

    tsv_rows = [
        row
        for row in csv.reader(io.StringIO(raw_bytes.decode("utf-8")), delimiter="\t")
        if len(row) >= 7
    ]
    candidates = len(tsv_rows)

    by_text: dict[str, dict] = {}
    order: list[str] = []
    for sentence_id, filename, raw_transcription, _norm, _chars, num_samples, gender in tsv_rows:
        reference = freeze(raw_transcription)
        if not reference:
            continue
        if reference not in by_text:
            by_text[reference] = {
                "id": f"fleurs-hi_in-test-{int(sentence_id):06d}",
                "language": "hi",
                "reference_text": reference,
                "source": {
                    "sentence_id": sentence_id,
                    "files": [],
                    "genders": [],
                    "duration_seconds": [],
                },
            }
            order.append(reference)
        entry = by_text[reference]
        entry["source"]["files"].append(filename)
        entry["source"]["genders"].append(gender)
        entry["source"]["duration_seconds"].append(round(int(num_samples) / 16000, 3))

    rows = [by_text[text] for text in order]
    duplicates_merged = candidates - len(rows)
    punctuated = sum(
        1 for r in rows if any(mark in r["reference_text"] for mark in SUPPORTED_MARKS)
    )

    dataset = {
        "name": "hi-punct-eval",
        "version": 1,
        "task": "punctuation-restoration",
        "description": (
            "PRIMARY Hindi punctuation-restoration benchmark (Milestone 29A). "
            "TEXT-LEVEL: references are FLEURS hi_in TEST raw_transcription "
            f"(google/fleurs, CC-BY-4.0, revision {SOURCE_REVISION}), "
            "NFC-normalized, whitespace-collapsed, PUNCTUATION PRESERVED "
            "VERBATIM (FLEURS mixes danda and Latin full stop as sentence "
            "enders - the documented policy scores them per-mark separately "
            "and jointly as the sentence-boundary group). Deduplicated by "
            "reference text (multi-speaker re-reads of one sentence keep one "
            "row; every recording's audio identity is retained). Audio is "
            "NOT vendored: this benchmark scores punctuation restoration on "
            "text; the pinned source revision keeps the audio recoverable "
            "for a future end-to-end phase. Read speech - spontaneous-"
            "dictation punctuation quality is OUT of this benchmark's reach "
            "and stays a documented domain gap."
        ),
        "rows": rows,
    }
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATASET_PATH.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest_sha = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()

    # Self-check: the shipped manifest must satisfy its own schema.
    validated = load_punctuation_dataset(DATASET_PATH)

    provenance = {
        "manifest": {
            "path": "ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json",
            "sha256": manifest_sha,
            "samples": len(validated.rows),
        },
        "created": "2026-08-19",
        "language": "hi",
        "task": "punctuation-restoration",
        "sources": [
            {
                "name": "fleurs",
                "reference": "google/fleurs",
                "language": "multi",
                "license": "CC-BY-4.0",
                "license_verified_on": "2026-08-19",
                "license_source_url": "https://huggingface.co/datasets/google/fleurs",
                "commercial": "yes",
                "access": "open",
                "access_detail": "",
                "speaker_ids": False,
                "official_splits": True,
                "contamination_risk": "known_overlap",
                "notes": (
                    "Read speech (FLoRes sentences). raw_transcription is the "
                    "punctuation-bearing column; the normalized transcription "
                    "column already drops most punctuation and is unusable "
                    "here (verified M28). Sentence-ender style is MIXED "
                    "(danda and Latin full stop) - preserved verbatim, "
                    "policy documented in the manifest description."
                ),
            }
        ],
        "source_revision": SOURCE_REVISION,
        "source_file": {
            "path": "data/hi_in/test.tsv",
            "sha256": TSV_SHA256,
            "bytes": len(raw_bytes),
        },
        "source_splits": ["test"],
        "reference_field": "raw_transcription",
        "normalization": PUNCTUATION_RULER,
        "primary_ruler": "punctuation_f1_micro",
        "curation": (
            "deterministic: TSV order; NFC + whitespace collapse; dedup by "
            "reference text keeping the first occurrence's row id and every "
            "occurrence's audio identity"
        ),
        "validation": {
            "source": "fleurs",
            "language": "hi",
            "split": "test",
            "candidates": candidates,
            "accepted": len(validated.rows),
            "duplicates_merged": duplicates_merged,
            "rows_with_supported_punctuation": punctuated,
        },
        "audio": "not vendored (text-level benchmark); recoverable from the pinned revision",
        "notes": "",
    }
    PROVENANCE_PATH.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    INPUTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    INPUTS_PATH.write_text(
        json.dumps(
            {
                "experiment": "29a-hindi-punctuation-eval",
                "dataset": f"{validated.name}@v{validated.version}",
                "dataset_sha256": manifest_sha,
                "input_preparation": (
                    f"strip_punctuation_for_input ({PUNCTUATION_RULER}): NFC, "
                    "Cf deleted, category P -> space, whitespace collapsed, "
                    "case preserved"
                ),
                "rows": [
                    {"id": row.id, "input_text": strip_punctuation_for_input(row.reference_text)}
                    for row in validated.rows
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"dataset:    {DATASET_PATH.relative_to(ROOT)}")
    print(f"  rows={len(validated.rows)} (candidates={candidates}, merged={duplicates_merged})")
    print(f"  punctuated rows: {punctuated}/{len(validated.rows)}")
    print(f"  sha256: {manifest_sha}")
    print(f"provenance: {PROVENANCE_PATH.relative_to(ROOT)}")
    print(f"inputs:     {INPUTS_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
