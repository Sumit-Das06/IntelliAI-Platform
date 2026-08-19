"""M29A — real-E3-output sanity check (research instrument, scratch venv).

Runs the pinned lead model over the 153 REAL E3 hypotheses from the frozen
ASR eval result (M23). These transcripts have NO human punctuation
references, so this is NOT a benchmark — it answers product-sanity
questions only:

  - does the invariant hold on real spontaneous ASR output? (all 153)
  - what does it add? (marks, sentence lengths)
  - obvious over-segmentation: predicted sentences of <= 2 words
  - obvious under-segmentation: outputs > 25 words with no sentence ender

PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import json
import statistics
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULT = ROOT / "ml/evaluation/stt/results/2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23.json"

SENTENCE_ENDERS = ("।", "?", "!", ".")


def depunct(text: str) -> str:
    folded = unicodedata.normalize("NFC", text).casefold()
    cleaned = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in folded)
    return " ".join(cleaned.split())


def main() -> None:
    from punctuators.models import PunctCapSegModelONNX

    clips = json.loads(RESULT.read_text(encoding="utf-8"))["clips"]
    rows = [
        (c["clip_id"], c["hypothesis_text"])
        for c in clips
        if (c.get("hypothesis_text") or "").strip()
    ]
    model = PunctCapSegModelONNX.from_pretrained("pcs_47lang")

    outputs = model.infer([t for _, t in rows])
    results = []
    invariant_fails = 0
    over_seg_rows = 0
    under_seg_rows = 0
    sentence_word_counts: list[int] = []
    for (clip_id, before), out in zip(rows, outputs, strict=True):
        segments = out if isinstance(out, list) else [str(out)]
        joined = " ".join(segments)
        inv = depunct(joined) == depunct(before)
        if not inv:
            invariant_fails += 1
        seg_lens = [len(s.split()) for s in segments if s.strip()]
        sentence_word_counts.extend(seg_lens)
        tiny = sum(1 for n in seg_lens if n <= 2)
        if tiny:
            over_seg_rows += 1
        if len(before.split()) > 25 and not any(m in joined for m in SENTENCE_ENDERS):
            under_seg_rows += 1
        results.append(
            {
                "clip_id": clip_id,
                "invariant": "PASS" if inv else "FAIL",
                "input_words": len(before.split()),
                "sentences": len(seg_lens),
                "tiny_sentences_le2_words": tiny,
                "marks": {
                    "danda": joined.count("।"),
                    "comma": joined.count(","),
                    "question_mark": joined.count("?"),
                },
                "before": before,
                "after": joined,
            }
        )

    summary = {
        "experiment": "29a-hindi-punctuation-eval",
        "phase": "real-e3-sanity (NOT a benchmark: no human punctuation references)",
        "model": "1-800-BAD-CODE/punct_cap_seg_47_language"
        " @ 1b9d51fc7989ebc61e844d407d9dadd08ff4ba28",
        "source_transcripts": str(RESULT.relative_to(ROOT)),
        "rows": len(rows),
        "invariant_failures": invariant_fails,
        "rows_with_tiny_sentences_le2_words": over_seg_rows,
        "rows_over_25_words_with_no_sentence_ender": under_seg_rows,
        "sentence_length_words": {
            "mean": round(statistics.mean(sentence_word_counts), 2),
            "median": statistics.median(sentence_word_counts),
            "p95": sorted(sentence_word_counts)[int(0.95 * len(sentence_word_counts)) - 1],
        },
        "total_marks_added": {
            "danda": sum(r["marks"]["danda"] for r in results),
            "comma": sum(r["marks"]["comma"] for r in results),
            "question_mark": sum(r["marks"]["question_mark"] for r in results),
        },
        "results": results,
    }
    out_path = HERE / "e3-sanity.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"rows={len(rows)} invariant_fails={invariant_fails} "
        f"over-seg rows={over_seg_rows} under-seg rows={under_seg_rows} "
        f"mean sentence={summary['sentence_length_words']['mean']} words"
    )
    print(f"written: {out_path}")


if __name__ == "__main__":
    sys.exit(main())
