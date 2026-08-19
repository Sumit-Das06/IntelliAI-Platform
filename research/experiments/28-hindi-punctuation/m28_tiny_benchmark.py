"""M28 — tiny CPU benchmark of one candidate punctuation restorer (read-only).

Runs 1-800-BAD-CODE/xlm-roberta_punctuation_fullstop_truecase (Apache-2.0,
ONNX, via the `punctuators` package, model alias pcs_47lang) on REAL E3
outputs from the frozen-eval result file. Nothing in the product is touched;
this is a research instrument in a scratch venv.

Measures, per transcript-length tier (5s/30s/120s/300s/600s char-equivalents
at the frozen eval's measured 12.18 chars/sec):
  - wall latency
  - word-preservation invariant (the M28 contract check):
        depunct(output) == depunct(input)   after casefold + whitespace collapse
  - punctuation marks added (danda/comma/question mark/full stop)
  - before/after examples for the research doc

Long tiers are REAL E3 hypotheses concatenated to the target length (labelled
as such — no synthetic text is invented).

Evidence: tiny-benchmark.json. Run inside the m28 scratch venv with
PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import json
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "tiny-benchmark.json"
RESULT = ROOT / "ml/evaluation/stt/results/2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23.json"

CHARS_PER_SECOND = 12.18  # MEASURED on stt-hi-public-eval@v1 references (M28 baseline)
TIERS = {"5s": 5, "30s": 30, "120s": 120, "300s": 300, "600s": 600}


def depunct(text: str) -> str:
    """The invariant transform: punctuation→space, casefold, collapse."""
    folded = unicodedata.normalize("NFC", text).casefold()
    cleaned = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in folded)
    return " ".join(cleaned.split())


def mark_counts(text: str) -> dict:
    return {
        "danda": text.count("।"),
        "comma": text.count(","),
        "question_mark": text.count("?"),
        "exclamation": text.count("!"),
        "full_stop": text.count("."),
    }


# ── Assemble real inputs ─────────────────────────────────────────────────
clips = json.loads(RESULT.read_text(encoding="utf-8"))["clips"]
hyps = [c["hypothesis_text"] for c in clips if (c.get("hypothesis_text") or "").strip()]
hyps.sort(key=len, reverse=True)

pool: list[str] = []
i = 0
while sum(len(h) + 1 for h in pool) < 8000 and i < len(hyps):
    pool.append(hyps[i])
    i += 1

inputs: dict[str, str] = {}
for tier, seconds in TIERS.items():
    target = int(seconds * CHARS_PER_SECOND)
    acc: list[str] = []
    for h in pool:
        if sum(len(a) + 1 for a in acc) >= target:
            break
        acc.append(h)
    inputs[tier] = " ".join(acc)[: target + 200]
# One English control (E3's own JFK probe head from the M23 sweep, punct stripped
# so the restorer has work to do):
jfk = (
    "and so my fellow americans ask not what your country can do for you "
    "ask what you can do for your country"
)
inputs["english_control"] = jfk

# ── Load the model ───────────────────────────────────────────────────────
from punctuators.models import PunctCapSegModelONNX  # noqa: E402

t0 = time.perf_counter()
model = PunctCapSegModelONNX.from_pretrained("pcs_47lang")
load_seconds = time.perf_counter() - t0

# Warmup (JIT/session init noise out of the tier timings)
model.infer([inputs["5s"]])

# ── Run tiers ────────────────────────────────────────────────────────────
results: dict[str, dict] = {}
for tier, text in inputs.items():
    t0 = time.perf_counter()
    out = model.infer([text])
    latency = time.perf_counter() - t0
    raw = out[0]
    joined = " ".join(raw) if isinstance(raw, list) else str(raw)
    preserved = depunct(joined) == depunct(text)
    results[tier] = {
        "input_chars": len(text),
        "approx_speech_seconds": round(len(text) / CHARS_PER_SECOND, 1),
        "latency_seconds": round(latency, 3),
        "word_preservation_invariant": "PASS" if preserved else "FAIL",
        "marks_added": mark_counts(joined),
        "sentences_segmented": len(raw) if isinstance(raw, list) else None,
        "output_head": joined[:220],
    }
    print(
        f"{tier}: chars={len(text)} latency={latency:.2f}s "
        f"invariant={'PASS' if preserved else 'FAIL'} marks={mark_counts(joined)}"
    )

# ── Small before/after gallery (short real clips) ────────────────────────
gallery = []
for h in [h for h in hyps if 40 <= len(h) <= 120][:4]:
    out = model.infer([h])[0]
    joined = " ".join(out) if isinstance(out, list) else str(out)
    gallery.append(
        {
            "before": h,
            "after": joined,
            "invariant": "PASS" if depunct(joined) == depunct(h) else "FAIL",
        }
    )

evidence = {
    "experiment": "28-hindi-punctuation",
    "phase": "tiny-benchmark (single candidate, research instrument only)",
    "model": "1-800-BAD-CODE/xlm-roberta_punctuation_fullstop_truecase (pcs_47lang)",
    "license": "Apache-2.0",
    "runtime": "onnxruntime CPU via punctuators package, scratch venv",
    "model_load_seconds": round(load_seconds, 2),
    "chars_per_second_basis": CHARS_PER_SECOND,
    "inputs_note": (
        "All Hindi inputs are REAL E3 hypothesis_text from the M23 frozen-eval "
        "result; long tiers are concatenations of real outputs to the tier's "
        "char-equivalent length. The English control is E3's JFK probe text "
        "with punctuation removed."
    ),
    "tiers": results,
    "gallery": gallery,
}
OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\nmodel load: {load_seconds:.1f}s\nwritten: {OUT}")
