"""M28 — Hindi punctuation restoration research: the measured baseline.

Read-only instrument. It measures punctuation presence in:
  A. the E3 training corpus (qwen-hi-public-train@v3), per language, per mark
  B. the frozen eval references (stt-hi-public-eval@v1) + chars/sec density
  C. E3's actual outputs on the frozen eval (hypothesis_text, M23 run + replicate)
  D. the incumbent whisper-small's outputs on the same eval (M24 fresh run)
  E. the base (pre-fine-tune) Qwen3-ASR outputs where available
  F. E3's English probe outputs (M23 sweep) and the founder's real sessions (M25)

Nothing is modified. Evidence is written to punctuation-baseline.json.
Run with PYTHONIOENCODING=utf-8 (Devanagari on a cp1252 console).
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "punctuation-baseline.json"

# The marks the milestone asks about, by name, plus a catch-all.
NAMED_MARKS = {
    "danda": "।",  # ।
    "double_danda": "॥",  # ॥
    "comma": ",",
    "question_mark": "?",
    "exclamation": "!",
    "colon": ":",
    "semicolon": ";",
    "full_stop": ".",
    "quote_double": '"',
    "quote_single": "'",
    "hyphen": "-",
}


def is_punct(ch: str) -> bool:
    """Unicode punctuation, the same lens the normalization profile uses."""
    return unicodedata.category(ch).startswith("P")


def text_stats(texts: list[str]) -> dict:
    """Per-mark presence (rows containing >=1) and total mark counts."""
    rows = len(texts)
    presence = dict.fromkeys(NAMED_MARKS, 0)
    counts = dict.fromkeys(NAMED_MARKS, 0)
    any_punct_rows = 0
    total_punct_chars = 0
    total_chars = 0
    for t in texts:
        total_chars += len(t)
        row_punct = sum(1 for ch in t if is_punct(ch))
        total_punct_chars += row_punct
        if row_punct:
            any_punct_rows += 1
        for name, mark in NAMED_MARKS.items():
            n = t.count(mark)
            counts[name] += n
            if n:
                presence[name] += 1
    return {
        "rows": rows,
        "rows_with_any_punctuation": any_punct_rows,
        "pct_rows_with_any_punctuation": round(100 * any_punct_rows / rows, 2) if rows else None,
        "total_punctuation_chars": total_punct_chars,
        "total_chars": total_chars,
        "per_mark_rows_containing": presence,
        "per_mark_total_count": counts,
    }


def examples(texts: list[str], n: int = 3) -> list[str]:
    picked = []
    for t in texts:
        if t.strip():
            picked.append(t if len(t) <= 160 else t[:160] + "…")
        if len(picked) == n:
            break
    return picked


evidence: dict = {
    "experiment": "28-hindi-punctuation",
    "phase": "baseline-measurement",
    "instrument": "m28_punctuation_baseline.py (read-only)",
}

# ── A. Training corpus v3 ────────────────────────────────────────────────
train_path = ROOT / "ml/datasets/manifests/qwen-hi-public-train-v3.jsonl"
by_lang: dict[str, list[str]] = {}
with train_path.open(encoding="utf-8") as fh:
    for line in fh:
        row = json.loads(line)
        by_lang.setdefault(row["language"], []).append(row["text"])
evidence["training_corpus_v3"] = {
    "manifest": str(train_path.relative_to(ROOT)),
    "languages": {
        lang: {**text_stats(texts), "examples": examples(texts)}
        for lang, texts in sorted(by_lang.items())
    },
}

# ── B. Frozen eval references ────────────────────────────────────────────
eval_path = ROOT / "ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json"
eval_ds = json.loads(eval_path.read_text(encoding="utf-8"))
refs = [c.get("reference", c.get("reference_text", "")) for c in eval_ds["clips"]]
durations = [float(c.get("duration_seconds") or 0) for c in eval_ds["clips"]]
ref_stats = text_stats([r for r in refs if r])
speech_secs = sum(durations)
ref_chars = sum(len(r) for r in refs)
evidence["frozen_eval_references"] = {
    "dataset": f"{eval_ds['name']}@v{eval_ds['version']}",
    "clips": len(eval_ds["clips"]),
    "stats": ref_stats,
    "total_speech_seconds": round(speech_secs, 1),
    "total_reference_chars": ref_chars,
    "chars_per_speech_second": round(ref_chars / speech_secs, 2) if speech_secs else None,
    "examples": examples([r for r in refs if r]),
}

# ── C/D/E. Model outputs on the frozen eval ──────────────────────────────
_R = "ml/evaluation/stt/results"
RESULTS = {
    "e3_m23": f"{_R}/2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23.json",
    "e3_m23_replicate": (f"{_R}/2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23-replicate.json"),
    "whisper_small_incumbent_m24": (
        f"{_R}/2026-08-18-intelliai-stt-hi-whisper-small-int8-m24-incumbent.json"
    ),
    "qwen_base_m17_linux": f"{_R}/2026-08-12-research-qwen3-asr-0.6b-hi-17-linux.json",
    "e2_m22": f"{_R}/2026-08-18-research-qwen3-asr-0.6b-hi-ft-e2-hi-m22.json",
    "e1_m21": f"{_R}/2026-08-17-research-qwen3-asr-0.6b-hi-ft-e1-hi-m21.json",
}
outputs: dict = {}
for label, rel in RESULTS.items():
    p = ROOT / rel
    if not p.exists():
        outputs[label] = {"note": "result file not found"}
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    clips = d.get("clips")
    if not isinstance(clips, list) or not clips or "hypothesis_text" not in clips[0]:
        outputs[label] = {"note": "no per-clip hypothesis_text in this result file"}
        continue
    hyps = [c.get("hypothesis_text") or "" for c in clips]
    outputs[label] = {
        "result_file": rel,
        "stats": text_stats(hyps),
        "examples_with_punct": examples([h for h in hyps if any(is_punct(ch) for ch in h)]),
        "examples": examples(hyps),
    }
evidence["model_outputs_frozen_eval"] = outputs

# ── F1. E3 English probes (M23 sweep) ────────────────────────────────────
sweep = json.loads(
    (ROOT / "research/experiments/23-qwen3-hi-ft-e3/sweep-probes.json").read_text(encoding="utf-8")
)
english_texts: list[str] = []
for ck in (sweep.get("checkpoints") or {}).values():
    for probe, result in ck.items():
        if ("english" in probe or probe.startswith("en-holdout")) and isinstance(result, dict):
            head = result.get("text_head") or ""
            if head:
                english_texts.append(head)
evidence["e3_english_probe_outputs"] = {
    "source": "research/experiments/23-qwen3-hi-ft-e3/sweep-probes.json",
    "note": (
        "text_head fields are truncated probe outputs — punctuation presence is still observable"
    ),
    "stats": text_stats(english_texts),
    "examples": examples(english_texts),
}

# ── F2. Real founder sessions (M25) ──────────────────────────────────────
evidence["real_client_sessions_m25"] = {
    "source": "research/experiments/25-local-prod-e3/real-client-verification.json",
    "note": (
        "Evidence stores request metadata only (no transcript text, by design). "
        "The punctuation observation for real sessions comes from the founder's "
        "Speech Samples console screenshot (2026-08-19) and matches the frozen-eval "
        "measurement: Hindi outputs carry no punctuation."
    ),
}

OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# Console summary
def _marks_line(s: dict) -> str:
    m = s["per_mark_total_count"]
    return (
        f"danda={m['danda']} comma={m['comma']} "
        f"qmark={m['question_mark']} fullstop={m['full_stop']}"
    )


tc = evidence["training_corpus_v3"]["languages"]
print("=== A. Training corpus v3 ===")
for lang, s in tc.items():
    print(
        f"  {lang}: rows={s['rows']} any-punct={s['rows_with_any_punctuation']} "
        f"({s['pct_rows_with_any_punctuation']}%)  {_marks_line(s)}"
    )
er = evidence["frozen_eval_references"]
print(
    f"=== B. Frozen eval refs === clips={er['clips']} "
    f"any-punct-rows={er['stats']['rows_with_any_punctuation']} "
    f"chars/sec={er['chars_per_speech_second']}"
)
print("=== C/D/E. Model outputs on frozen eval ===")
for label, o in outputs.items():
    if "stats" in o:
        s = o["stats"]
        print(
            f"  {label}: rows={s['rows']} any-punct-rows={s['rows_with_any_punctuation']} "
            f"({s['pct_rows_with_any_punctuation']}%) "
            f"total-punct-chars={s['total_punctuation_chars']}  {_marks_line(s)}"
        )
    else:
        print(f"  {label}: {o['note']}")
s = evidence["e3_english_probe_outputs"]["stats"]
print(
    f"=== F1. E3 English probes === rows={s['rows']} "
    f"any-punct={s['rows_with_any_punctuation']} "
    f"({s['pct_rows_with_any_punctuation']}%) {_marks_line(s)}"
)
print(f"\nwritten: {OUT}")
