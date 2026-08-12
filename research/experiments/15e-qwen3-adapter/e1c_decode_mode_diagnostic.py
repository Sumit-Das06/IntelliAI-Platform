"""E1c diagnostic: does timestamp-mode decoding explain the E1/E1b failure?

NOT ledger evidence, and NOT a benchmark: arm B deliberately changes the
decode policy (`without_timestamps=True`), so its numbers may never be
compared against the official baseline or entered in the results ledger.
The ONLY legal comparison is arm A vs arm B — same artifact, same clips,
same ruler, one changed variable.

Hypothesis under test (E1b close-out §11): training labels were built in
the `<|notimestamps|>` regime while the product decode runs WITH
timestamps, so the adapter damaged exactly the token mode the server
uses. If that is the mechanism, decoding the SAME failed artifact with
`without_timestamps=True` should collapse the insertion loops, probe
hallucinations, and fallback stalls; if it changes little, the
hypothesis is weakened.

Method: the E1b CT2 artifact (checkpoint-600, model.bin pin 806cfdb9…)
loaded directly through faster-whisper (int8, same library build the
runtime uses), run over the first N natural clips of the FROZEN
`stt-hi-public-eval@v1` plus its probes, once per arm:
  arm A: without_timestamps=False (the product decode policy)
  arm B: without_timestamps=True  (the diagnostic variable)
Scoring uses the evaluation plane's own rulers (`score`,
`hallucinated_words`, `unicode_generic@v2` via `profile_for`) — one
aligner, one normalization registry, no second framework.

Reproduce:
    uv run --package intelliai-evaluation python \
        research/experiments/15e-qwen3-adapter/e1c_decode_mode_diagnostic.py \
        --model-dir models/whisper-small-hi-lora-e1b/v1 \
        --manifest ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json \
        --data-root ml/datasets/data --clips 30 \
        --out research/experiments/15e-qwen3-adapter/e1c-results.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import platform
import time
from pathlib import Path
from typing import Any

from intelliai_evaluation.accuracy import RulerFailureError, hallucinated_words, score
from intelliai_evaluation.dataset import load_dataset
from intelliai_evaluation.fetch import generate_synthetic, sha256_file
from intelliai_evaluation.normalization import profile_for


def transcribe(model: Any, audio_path: Path, *, without_timestamps: bool) -> tuple[str, float]:
    started = time.perf_counter()
    segments, _info = model.transcribe(
        str(audio_path),
        language="hi",
        task="transcribe",
        vad_filter=False,
        without_timestamps=without_timestamps,
    )
    text = " ".join(s.text.strip() for s in segments if s.text.strip())
    return text, time.perf_counter() - started


def run_arm(
    model: Any,
    clips: list[Any],
    probes: list[Any],
    data_root: Path,
    profile: Any,
    *,
    without_timestamps: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_audio = 0.0
    total_wall = 0.0
    for clip in clips:
        text, wall = transcribe(
            model, data_root / clip.filename, without_timestamps=without_timestamps
        )
        row: dict[str, Any] = {
            "clip_id": clip.id,
            "duration_seconds": clip.duration_seconds,
            "wall_seconds": round(wall, 3),
            "rtf": round(wall / clip.duration_seconds, 3),
            "hypothesis": text,
        }
        try:
            scores = score(clip.reference_text, text, profile)
            row["cer_unicode"] = round(scores.cer, 4)
            row["wer_unicode"] = round(scores.wer, 4)
            row["insertions"] = scores.words.insertions
            row["reference_words"] = scores.words.reference_words
        except RulerFailureError as exc:
            row["ruler_failure"] = str(exc)
        total_audio += clip.duration_seconds
        total_wall += wall
        rows.append(row)

    probe_rows: list[dict[str, Any]] = []
    for clip in probes:
        audio = data_root / clip.filename
        if not audio.exists() and clip.synthetic is not None:
            generate_synthetic(clip.synthetic, audio)
        text, wall = transcribe(model, audio, without_timestamps=without_timestamps)
        probe_rows.append(
            {
                "clip_id": clip.id,
                "hallucinated_words": hallucinated_words(
                    declared_reference="", hypothesis=text, profile=profile
                ),
                "wall_seconds": round(wall, 3),
                "hypothesis": text[:200],
            }
        )

    scored = [r for r in rows if "cer_unicode" in r]
    ref_chars = {
        r["clip_id"]: len(profile.characters(c.reference_text))
        for r, c in zip(rows, clips, strict=True)
        if "cer_unicode" in r
    }
    weighted_cer = (
        sum(r["cer_unicode"] * ref_chars[r["clip_id"]] for r in scored) / sum(ref_chars.values())
        if scored
        else None
    )
    insertion_total = sum(r.get("insertions", 0) for r in scored)
    reference_total = sum(r.get("reference_words", 0) for r in scored)
    return {
        "without_timestamps": without_timestamps,
        "aggregates": {
            "clips_scored": len(scored),
            "cer_unicode_char_weighted": round(weighted_cer, 4) if weighted_cer else None,
            "insertion_rate": round(insertion_total / reference_total, 4)
            if reference_total
            else None,
            "rtf": round(total_wall / total_audio, 3) if total_audio else None,
            "hallucinated_probe_words": sum(p["hallucinated_words"] for p in probe_rows),
        },
        "probes": probe_rows,
        "clips": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--clips", type=int, default=30)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    dataset = load_dataset(args.manifest)
    profile = profile_for("hi")
    natural = [c for c in dataset.clips if c.synthetic is None][: args.clips]
    probes = [c for c in dataset.clips if c.synthetic is not None]
    model = WhisperModel(str(args.model_dir), device="cpu", compute_type="int8")

    arms = {
        "arm_a_product_decode": run_arm(
            model, natural, probes, args.data_root, profile, without_timestamps=False
        ),
        "arm_b_no_timestamps": run_arm(
            model, natural, probes, args.data_root, profile, without_timestamps=True
        ),
    }
    payload = {
        "diagnostic": "e1c-decode-mode-mismatch",
        "NOT_LEDGER_EVIDENCE": (
            "arm B changes decode policy; compare arms against each other ONLY, "
            "never against the official baseline"
        ),
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "artifact": {
            "dir": str(args.model_dir),
            "model_bin_sha256": sha256_file(args.model_dir / "model.bin"),
        },
        "manifest": {
            "name": dataset.name,
            "version": dataset.version,
            "sha256": sha256_file(args.manifest),
        },
        "environment": {
            "cpu": platform.processor(),
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "compute": "int8",
            "decoder": "faster-whisper (direct library, same build as the runtime)",
        },
        **arms,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, arm in arms.items():
        print(name, json.dumps(arm["aggregates"], ensure_ascii=False))
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
