"""M21 Phase 9: HF-side checkpoint evaluation on the FROZEN benchmark.

Selection instrument, not the final verdict: every checkpoint AND the
pinned base run through the SAME official wrapper + the evaluation
plane's own ruler on stt-hi-public-eval@v1, so checkpoint-to-checkpoint
and checkpoint-to-base deltas are apples to apples. The candidate that
survives selection gets converted and re-measured through the REAL
serving adapter (Phase 13) before any claim against the 0.1457 baseline
is made.
"""

from __future__ import annotations

import argparse
import datetime
import json
import time
from pathlib import Path
from typing import Any

from intelliai_evaluation.accuracy import score
from intelliai_evaluation.dataset import load_dataset
from intelliai_evaluation.normalization import profile_for
from intelliai_training.qwen_trainer import load_wrapper

#: Hallucination probes (15E discipline): markers that must NEVER appear
#: in a transcription of our eval clips (prompt-echo / template bleed).
PROBE_MARKERS = ("<asr_text>", "language ", "transcribe", "system", "assistant")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json"),
    )
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="0 = full benchmark")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    dataset = load_dataset(args.manifest)
    clips = [c for c in dataset.clips if c.synthetic is None]
    if args.limit:
        clips = clips[: args.limit]
    profile = profile_for("hi")

    wrapper = load_wrapper(args.model_dir, device_map="cuda:0")
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    total_audio = 0.0
    # Corpus scoring the evaluation plane's way: edit sums over reference
    # sums, never an average of per-clip ratios.
    cer_num = 0.0
    cer_den = 0.0
    wer_num = 0.0
    wer_den = 0.0
    started = time.perf_counter()
    for index in range(0, len(clips), args.batch):
        chunk = clips[index : index + args.batch]
        paths = [str(args.data_root / c.filename) for c in chunk]
        batch_started = time.perf_counter()
        results = wrapper.transcribe(paths)
        batch_elapsed = time.perf_counter() - batch_started
        for clip, result in zip(chunk, results, strict=True):
            hypothesis = str(getattr(result, "text", "") or "")
            scored = score(clip.reference_text, hypothesis, profile)
            ref_chars = len(profile.characters(clip.reference_text))
            ref_words = len(profile.words(clip.reference_text))
            cer_num += scored.cer * ref_chars
            cer_den += ref_chars
            wer_num += scored.wer * ref_words
            wer_den += ref_words
            lowered = hypothesis.lower()
            rows.append(
                {
                    "id": clip.id,
                    "cer": round(scored.cer, 4),
                    "wer": round(scored.wer, 4),
                    "empty": not hypothesis.strip(),
                    "probes": [m for m in PROBE_MARKERS if m in lowered],
                    "chars": len(hypothesis),
                }
            )
            latencies.append(batch_elapsed / len(chunk))
            total_audio += clip.duration_seconds
    wall = time.perf_counter() - started

    sorted_latencies = sorted(latencies)
    payload = {
        "experiment": "21-qwen3-hi-finetuning",
        "phase": "checkpoint-eval (HF-side selection instrument; NOT the adapter verdict)",
        "label": args.label,
        "model_dir": str(args.model_dir),
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "clips": len(rows),
        "cer": round(cer_num / cer_den, 5) if cer_den else None,
        "wer": round(wer_num / wer_den, 5) if wer_den else None,
        "empty_outputs": sum(1 for r in rows if r["empty"]),
        "probe_hits": sum(1 for r in rows if r["probes"]),
        "rtf": round(wall / total_audio, 4) if total_audio else None,
        "p50_seconds": round(sorted_latencies[len(sorted_latencies) // 2], 2),
        "p95_seconds": round(
            sorted_latencies[min(int(len(sorted_latencies) * 0.95), len(sorted_latencies) - 1)], 2
        ),
        "wall_seconds": round(wall, 1),
        "worst_clips": sorted(rows, key=lambda r: -r["cer"])[:5],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if args.out.exists():
        existing = json.loads(args.out.read_text(encoding="utf-8"))
    existing[args.label] = payload
    args.out.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        k: payload[k]
        for k in ("label", "clips", "cer", "wer", "empty_outputs", "probe_hits", "rtf")
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
