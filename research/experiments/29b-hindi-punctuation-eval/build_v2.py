"""M29B — build the frozen hi-punct-eval@v2 benchmark (deterministic).

Two domains, one manifest:

  read-paragraph (88 rows) — the M29A derived probe PROMOTED to a frozen
      component: consecutive hi-punct-eval@v1 rows joined in groups of 3,
      dedup order, no randomness. Every paragraph records its member row
      ids; the member rows pin the FLEURS source revision, so each
      paragraph is reproducible byte-for-byte from pinned sources.

  spontaneous (60 rows) — the FIRST human-reviewable punctuated
      spontaneous Hindi references: stt-hi-public-eval@v1 natural clips
      (scenario Extempore/Conversation, ascending id, first 60), reference
      transcripts annotated per annotation-style-guide-v1.md. The builder
      REFUSES any annotation that changes words (depunct must match the
      source reference exactly).

v1 remains the frozen single-sentence component; v2 complements it and
replaces nothing. Run from the repo root:
  uv run --package intelliai-evaluation python \
      research/experiments/29b-hindi-punctuation-eval/build_v2.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from intelliai_evaluation.punctuation import (
    PUNCTUATION_RULER,
    SENTENCE_END_MARKS,
    SUPPORTED_MARKS,
    depunct,
    load_punctuation_dataset,
    strip_punctuation_for_input,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V1_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json"
ASR_EVAL_PATH = ROOT / "ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json"
V2_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v2.json"
PROVENANCE_PATH = ROOT / "ml/datasets/manifests/hi-punct-eval-v2.provenance.json"
GROUP = 3


def mark_stats(texts: list[str]) -> dict:
    return {
        "danda": sum(t.count("।") for t in texts),
        "comma": sum(t.count(",") for t in texts),
        "question_mark": sum(t.count("?") for t in texts),
        "exclamation": sum(t.count("!") for t in texts),
        "full_stop": sum(t.count(".") for t in texts),
        "sentence_boundaries": sum(sum(t.count(m) for m in SENTENCE_END_MARKS) for t in texts),
        "words": sum(len(t.split()) for t in texts),
    }


def main() -> None:
    v1 = load_punctuation_dataset(V1_PATH)
    v1_sha = hashlib.sha256(V1_PATH.read_bytes()).hexdigest()

    # ── read-paragraph component ─────────────────────────────────────────
    rows: list[dict] = []
    v1_rows = list(v1.rows)
    for start in range(0, len(v1_rows) - len(v1_rows) % GROUP, GROUP):
        group = v1_rows[start : start + GROUP]
        reference = " ".join(row.reference_text for row in group)
        rows.append(
            {
                "id": f"hi-punct-para-{start // GROUP:03d}",
                "language": "hi",
                "reference_text": reference,
                "domain": "read-paragraph",
                "members": [row.id for row in group],
                "source": {
                    "sentence_id": "+".join(row.source.sentence_id for row in group),
                    "files": [f for row in group for f in row.source.files],
                    "genders": [g for row in group for g in row.source.genders],
                    "duration_seconds": [d for row in group for d in row.source.duration_seconds],
                },
            }
        )
    paragraph_count = len(rows)

    # ── spontaneous component ────────────────────────────────────────────
    candidates = {
        c["clip_id"]: c
        for c in json.loads((HERE / "spontaneous-candidates.json").read_text(encoding="utf-8"))[
            "candidates"
        ]
    }
    annotations = json.loads((HERE / "spontaneous-annotations.json").read_text(encoding="utf-8"))
    uncertain_count = 0
    for entry in annotations["rows"]:
        clip = candidates[entry["clip_id"]]
        original = clip["reference_text"]
        punctuated_raw = entry["punctuated"]
        punctuated = " ".join(punctuated_raw.split()) if punctuated_raw else ""
        if depunct(punctuated) != depunct(original):
            msg = (
                f"annotation for {entry['clip_id']} changes words:\n"
                f"  source:    {depunct(original)}\n"
                f"  annotated: {depunct(punctuated)}"
            )
            raise SystemExit(msg)
        extra = set(punctuated) - set(original)
        if not extra <= set(SUPPORTED_MARKS):
            msg = f"annotation for {entry['clip_id']} adds unsupported characters: {extra}"
            raise SystemExit(msg)
        if entry.get("uncertain"):
            uncertain_count += 1
        gender = (
            "Female"
            if "gender='Female'" in clip["notes"]
            else ("Male" if "gender='Male'" in clip["notes"] else "unknown")
        )
        rows.append(
            {
                "id": f"hi-punct-spont-{entry['clip_id']}",
                "language": "hi",
                "reference_text": punctuated,
                "domain": "spontaneous",
                "members": [entry["clip_id"]],
                "source": {
                    "sentence_id": entry["clip_id"],
                    "files": [clip["path"]],
                    "genders": [gender],
                    "duration_seconds": [clip["duration_seconds"]],
                },
            }
        )
    spontaneous_count = len(rows) - paragraph_count

    dataset = {
        "name": "hi-punct-eval",
        "version": 2,
        "task": "punctuation-restoration",
        "description": (
            "Hindi punctuation-restoration benchmark v2 (Milestone 29B). Two "
            "domains, reported SEPARATELY, never averaged blindly: "
            "read-paragraph (88 rows) - deterministic 3-sentence paragraphs "
            "from consecutive hi-punct-eval@v1 rows (FLEURS hi_in test, "
            "pinned), promoting the M29A multi-sentence probe to a frozen "
            "component for mid-text boundary measurement; spontaneous (60 "
            "rows) - stt-hi-public-eval@v1 Extempore/Conversation reference "
            "transcripts punctuated per annotation-style-guide-v1 (single "
            "annotator, AI, text-only, PROVISIONAL pending founder "
            "native-speaker review - the style guide and its limitations are "
            "part of this benchmark's provenance). v1 remains the frozen "
            "single-sentence component; v2 complements, never replaces. "
            "Audio is not vendored; every row's source audio identity is "
            "recorded."
        ),
        "rows": rows,
    }
    V2_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_sha = hashlib.sha256(V2_PATH.read_bytes()).hexdigest()
    validated = load_punctuation_dataset(V2_PATH)

    para_texts = [r.reference_text for r in validated.rows if r.domain == "read-paragraph"]
    spont_texts = [r.reference_text for r in validated.rows if r.domain == "spontaneous"]

    provenance = {
        "manifest": {
            "path": "ml/evaluation/punctuation/datasets/hi-punct-eval-v2.json",
            "sha256": manifest_sha,
            "samples": len(validated.rows),
        },
        "created": "2026-08-19",
        "language": "hi",
        "task": "punctuation-restoration",
        "components": {
            "read-paragraph": {
                "rows": paragraph_count,
                "construction": (
                    f"deterministic: consecutive hi-punct-eval@v1 rows in groups of {GROUP}, "
                    "dedup order, joined with single spaces; member ids recorded per row"
                ),
                "derived_from": {"dataset": "hi-punct-eval@v1", "sha256": v1_sha},
                "statistics": mark_stats(para_texts),
            },
            "spontaneous": {
                "rows": spontaneous_count,
                "selection": (
                    "stt-hi-public-eval@v1 natural clips with scenario Extempore or "
                    "Conversation, ascending clip id, first 60"
                ),
                "annotation": {
                    "style_guide": (
                        "research/experiments/29b-hindi-punctuation-eval/"
                        "annotation-style-guide-v1.md"
                    ),
                    "style_guide_version": 1,
                    "annotator": (
                        "single annotator: automated research assistant (AI, non-native, "
                        "TEXT-ONLY); PROVISIONAL pending founder native-speaker review"
                    ),
                    "annotated_on": "2026-08-19",
                    "uncertain_rows": uncertain_count,
                    "word_law": (
                        "builder-verified: depunct(annotated) == depunct(source) for every row"
                    ),
                },
                "statistics": mark_stats(spont_texts),
            },
        },
        "normalization": PUNCTUATION_RULER,
        "primary_ruler": "punctuation_f1_micro (per domain; domains never blindly averaged)",
        "audio": "not vendored; identities recorded per row",
        "notes": "",
    }
    PROVENANCE_PATH.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    inputs = {
        "experiment": "29b-hindi-punctuation-eval",
        "dataset": f"{validated.name}@v{validated.version}",
        "dataset_sha256": manifest_sha,
        "rows": [
            {
                "id": row.id,
                "domain": row.domain,
                "input_text": strip_punctuation_for_input(row.reference_text),
            }
            for row in validated.rows
        ],
    }
    (HERE / "harness").mkdir(exist_ok=True)
    (HERE / "harness/v2-inputs.json").write_text(
        json.dumps(inputs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"v2: {len(validated.rows)} rows = {paragraph_count} read-paragraph "
        f"+ {spontaneous_count} spontaneous"
    )
    print(f"  sha256: {manifest_sha}")
    print(f"  paragraph stats: {mark_stats(para_texts)}")
    print(f"  spontaneous stats: {mark_stats(spont_texts)} (uncertain rows: {uncertain_count})")


if __name__ == "__main__":
    sys.exit(main())
