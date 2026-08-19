"""M30 Phase 20 — the HARD gate: punctuation ON must not change ASR words.

Compares the two frozen-eval runs (stage OFF vs stage ON, same runtime
build, same pinned artifacts):

  1. corpus CER/WER byte-identical (the ruler strips punctuation, so any
     drift means WORDS changed);
  2. per clip: depunct(hyp_ON) == depunct(hyp_OFF) — the word streams are
     equal, and the ON hypothesis differs only by v1 marks;
  3. every ON clip's punctuation additions counted.

Any word-stream mismatch is attributed honestly: the stage is word-safe
by construction (word-copy + in-process invariant, fail-open), so a
mismatch would indicate decoder nondeterminism between runs — reported,
never hidden.

Run: uv run --package intelliai-evaluation python .../m30_asr_nonregression.py
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent

V1_MARKS = ("।", ",", "?")


def depunct(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).casefold()
    kept: list[str] = []
    for ch in folded:
        category = unicodedata.category(ch)
        if category == "Cf":
            continue
        kept.append(" " if category.startswith("P") else ch)
    return " ".join("".join(kept).split())


def main() -> None:
    off = json.loads((HERE / "asr-punct-off.json").read_text(encoding="utf-8"))
    on = json.loads((HERE / "asr-punct-on.json").read_text(encoding="utf-8"))

    # The HARD gate is about WORDS: every accuracy metric must be
    # byte-identical (the ruler strips punctuation, so any drift means
    # words changed). recognition_rtf is a wall-clock measurement — it
    # legitimately includes the stage's own ~1% time and run-to-run
    # scheduling noise, and is reported separately, never gated on.
    accuracy_keys = [k for k in off["metrics"] if k != "recognition_rtf"]
    metrics_identical = all(off["metrics"][k] == on["metrics"][k] for k in accuracy_keys)
    rtf_delta = round(on["metrics"]["recognition_rtf"] - off["metrics"]["recognition_rtf"], 5)
    off_clips = {c["clip_id"]: c for c in off["clips"]}
    on_clips = {c["clip_id"]: c for c in on["clips"]}

    word_mismatches: list[str] = []
    non_mark_changes: list[str] = []
    marks_added = 0
    punctuated_clips = 0
    for clip_id, off_clip in off_clips.items():
        on_clip = on_clips[clip_id]
        off_hyp = off_clip.get("hypothesis_text") or ""
        on_hyp = on_clip.get("hypothesis_text") or ""
        if depunct(off_hyp) != depunct(on_hyp):
            word_mismatches.append(clip_id)
            continue
        extra = [ch for ch in on_hyp if ch not in off_hyp or on_hyp.count(ch) > off_hyp.count(ch)]
        added = {ch for ch in extra if unicodedata.category(ch).startswith("P")}
        if not added <= set(V1_MARKS):
            non_mark_changes.append(clip_id)
        added_count = sum(on_hyp.count(m) - off_hyp.count(m) for m in V1_MARKS)
        if added_count > 0:
            punctuated_clips += 1
            marks_added += added_count

    verdict = (
        "PASS" if metrics_identical and not word_mismatches and not non_mark_changes else "FAIL"
    )
    evidence = {
        "experiment": "30-punctuation-runtime",
        "phase": "asr-non-regression (HARD gate)",
        "corpus_metrics_off": off["metrics"],
        "corpus_metrics_on": on["metrics"],
        "accuracy_metrics_byte_identical": metrics_identical,
        "accuracy_metrics_compared": accuracy_keys,
        "recognition_rtf_delta_not_gated": rtf_delta,
        "clips": len(off_clips),
        "word_stream_mismatches": word_mismatches,
        "non_v1_mark_changes": non_mark_changes,
        "clips_with_marks_added": punctuated_clips,
        "total_v1_marks_added": marks_added,
        "verdict": verdict,
    }
    (HERE / "asr-nonregression.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"metrics byte-identical: {metrics_identical}")
    print(
        f"word-stream mismatches: {len(word_mismatches)}; "
        f"non-v1 mark changes: {len(non_mark_changes)}"
    )
    print(f"clips punctuated: {punctuated_clips}/{len(off_clips)}; marks added: {marks_added}")
    print(f"VERDICT: {verdict}")


if __name__ == "__main__":
    sys.exit(main())
