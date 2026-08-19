"""M29C — build hi-punct-eval@v3: the founder-review-ratified benchmark.

Released manifests are immutable, so applying the founder-supplied review
(spontaneous-annotations-review.json) creates the NEXT version — v2 stays
frozen as the pre-review record, and every piece of committed v2 evidence
keeps pointing at the bytes it measured.

v3 = v2 with:
  - the 2 REVISE rows' references replaced (comma-only insertions; the
    word law is re-verified against the frozen ASR eval references)
  - the review recorded in provenance: 49 APPROVE / 2 REVISE /
    9 AUDIO_REVIEW_REQUIRED, plus the review's own stated limit
    ("text-only linguistic review, not a native-speaker/audio review")
  - read-paragraph rows copied verbatim (untouched by the review)

Because the revisions add only punctuation, the punctuation-stripped
restorer INPUTS are byte-identical to v2's — the builder ASSERTS this, so
the committed v2 predictions remain valid for v3 scoring (deterministic;
nothing needs re-predicting).

Run: uv run --package intelliai-evaluation python .../build_v3.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from intelliai_evaluation.punctuation import (
    PUNCTUATION_RULER,
    SUPPORTED_MARKS,
    depunct,
    load_punctuation_dataset,
    strip_punctuation_for_input,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V2_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v2.json"
V3_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v3.json"
PROVENANCE_PATH = ROOT / "ml/datasets/manifests/hi-punct-eval-v3.provenance.json"
ASR_EVAL_PATH = ROOT / "ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json"
REVIEW_PATH = HERE / "spontaneous-annotations-review.json"


def main() -> None:
    v2 = load_punctuation_dataset(V2_PATH)
    v2_sha = hashlib.sha256(V2_PATH.read_bytes()).hexdigest()
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    revisions = {r["clip_id"]: r for r in review["revisions"]}
    audio_flagged = set(review["audio_review_required_ids"])
    asr_references = {
        clip["id"]: clip["reference_text"]
        for clip in json.loads(ASR_EVAL_PATH.read_text(encoding="utf-8"))["clips"]
    }

    rows: list[dict] = []
    revised_count = 0
    for row in v2.rows:
        record = json.loads(row.model_dump_json())
        record["source"]["files"] = list(row.source.files)
        record["source"]["genders"] = list(row.source.genders)
        record["source"]["duration_seconds"] = list(row.source.duration_seconds)
        record["members"] = list(row.members)
        if row.domain == "spontaneous":
            (clip_id,) = row.members
            if clip_id in revisions:
                revised = " ".join(revisions[clip_id]["revised_punctuated"].split())
                original_reference = asr_references[clip_id]
                if depunct(revised) != depunct(original_reference):
                    msg = f"revision for {clip_id} changes words — refused"
                    raise SystemExit(msg)
                extra = set(revised) - set(original_reference)
                if not extra <= set(SUPPORTED_MARKS):
                    msg = f"revision for {clip_id} adds unsupported characters: {extra}"
                    raise SystemExit(msg)
                if strip_punctuation_for_input(revised) != strip_punctuation_for_input(
                    row.reference_text
                ):
                    msg = f"revision for {clip_id} changes the restorer input — refused"
                    raise SystemExit(msg)
                record["reference_text"] = revised
                revised_count += 1
        rows.append(record)
    if revised_count != len(revisions):
        msg = f"applied {revised_count} revisions, review carries {len(revisions)}"
        raise SystemExit(msg)

    dataset = {
        "name": "hi-punct-eval",
        "version": 3,
        "task": "punctuation-restoration",
        "description": (
            "Hindi punctuation-restoration benchmark v3 (Milestone 29C): "
            "hi-punct-eval@v2 with the founder-supplied review applied to the "
            "spontaneous domain (49 rows approved unchanged, 2 revised with "
            "comma-only insertions, 9 flagged AUDIO_REVIEW_REQUIRED - their "
            "text unchanged and their ids recorded in provenance so scoring "
            "can split text-ratified rows from audio-pending rows). The "
            "review is a TEXT-ONLY linguistic review, not a native-speaker/"
            "audio review - that limit is part of this benchmark's "
            "provenance. read-paragraph rows are copied verbatim from v2. "
            "v1 and v2 remain frozen as the single-sentence component and "
            "the pre-review record."
        ),
        "rows": rows,
    }
    V3_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_sha = hashlib.sha256(V3_PATH.read_bytes()).hexdigest()
    validated = load_punctuation_dataset(V3_PATH)

    # The committed v2 predictions stay valid only if inputs are identical:
    v2_inputs = json.loads((HERE / "harness/v2-inputs.json").read_text(encoding="utf-8"))
    v3_inputs_by_id = {
        row.id: strip_punctuation_for_input(row.reference_text) for row in validated.rows
    }
    for entry in v2_inputs["rows"]:
        if v3_inputs_by_id[entry["id"]] != entry["input_text"]:
            msg = f"input drift at {entry['id']} — v2 predictions would be invalid"
            raise SystemExit(msg)

    text_ratified = [
        row.id
        for row in validated.rows
        if row.domain == "spontaneous" and row.members[0] not in audio_flagged
    ]
    provenance = {
        "manifest": {
            "path": "ml/evaluation/punctuation/datasets/hi-punct-eval-v3.json",
            "sha256": manifest_sha,
            "samples": len(validated.rows),
        },
        "created": "2026-08-19",
        "language": "hi",
        "task": "punctuation-restoration",
        "derived_from": {"dataset": "hi-punct-eval@v2", "sha256": v2_sha},
        "review": {
            "record": (
                "research/experiments/29b-hindi-punctuation-eval/"
                "spontaneous-annotations-review.json"
            ),
            "review_type": review["review_type"],
            "important_limit": review["important_limit"],
            "counts": review["counts"],
            "revised_rows": sorted(revisions),
            "audio_review_required_rows": sorted(audio_flagged),
            "text_ratified_spontaneous_rows": len(text_ratified),
        },
        "input_compatibility": (
            "builder-verified: punctuation-stripped inputs are byte-identical "
            "to hi-punct-eval@v2's, so v2 harness predictions remain valid"
        ),
        "normalization": PUNCTUATION_RULER,
        "primary_ruler": "punctuation_f1_micro (per domain; domains never blindly averaged)",
        "audio": "not vendored; identities recorded per row",
        "notes": "",
    }
    PROVENANCE_PATH.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"v3: {len(validated.rows)} rows, sha256 {manifest_sha}")
    print(f"  revisions applied: {revised_count}; audio-flagged: {len(audio_flagged)}")
    print(f"  text-ratified spontaneous rows: {len(text_ratified)}/60")
    print("  input compatibility with v2 predictions: VERIFIED")


if __name__ == "__main__":
    sys.exit(main())
