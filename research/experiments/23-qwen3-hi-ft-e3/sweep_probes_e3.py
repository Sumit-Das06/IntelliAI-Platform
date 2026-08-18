"""M23 Phase 12 (retention half): per-checkpoint English/short/silence probes.

The Hindi CER/WER half of the sweep runs through the M21 harness
(eval_checkpoint.py) unchanged; THIS instrument asks each checkpoint
the questions validation loss cannot answer — the E3 gates:

- English: the pinned JFK clip (WER + script flags) and two HELD-OUT
  FLEURS rows (ingested, never in the training slice)
- short speech: two HELD-OUT real sub-2 s utterances + 1 s / 2 s
  windows of a training-pool clip (the M22 battery's anchor)
- silence and quiet noise: must stay EMPTY (E2's win)

Held-out selections are deterministic: candidates minus the frozen
slice's ids, ascending sha256, first two.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from intelliai_evaluation.accuracy import score
from intelliai_evaluation.normalization import profile_for
from intelliai_training.audio_io import decode_to_float32
from intelliai_training.qwen_trainer import load_wrapper

RATE = 16_000
JFK_PATH = Path("ml/evaluation/data/jfk-flac.flac")
JFK_SHA = "63a4b1e4c1dc655ac70961ffbf518acd249df237e5a0152faae9a4a836949715"
JFK_REFERENCE = (
    "And so, my fellow Americans: ask not what your country can do for you; "
    "ask what you can do for your country."
)
ANCHOR_CLIP = Path("ml/datasets/data/indicvoices/hindi/train/indicvoices-hindi-train-0-000005.flac")


def held_out(
    candidates_path: Path, slice_jsonl: Path, *, window: tuple[float, float]
) -> list[dict[str, Any]]:
    """First two candidates (ascending sha256) inside the duration window
    that the frozen slice did NOT select."""
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    selected_ids = {
        json.loads(line)["id"]
        for line in slice_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    low, high = window
    pool = [
        c
        for c in payload["candidates"]
        if c["id"] not in selected_ids
        and low <= c["duration_seconds"] < high
        and c["text"].strip()
        and "<" not in c["text"]
    ]
    return sorted(pool, key=lambda c: c["sha256"].lower())[:2]


def probe_checkpoint(model_dir: Path, inputs: dict[str, Any]) -> dict[str, Any]:
    import torch

    wrapper = load_wrapper(model_dir, device_map="cuda:0")
    en_profile = profile_for("en")
    hi_profile = profile_for("hi")
    out: dict[str, Any] = {}
    for name, item in inputs.items():
        wave, reference, language = item
        result = wrapper.transcribe(wave)
        text = str(result[0].text) if result else ""
        entry: dict[str, Any] = {
            "empty": not text.strip(),
            "devanagari": any("ऀ" <= ch <= "ॿ" for ch in text),
            "latin": any("a" <= ch.lower() <= "z" for ch in text),
            "text_head": text[:70],
        }
        if reference:
            profile = en_profile if language == "en" else hi_profile
            entry["wer"] = round(score(reference, text, profile).wer, 4)
            entry["cer"] = round(score(reference, text, profile).cer, 4)
        out[name] = entry
    del wrapper
    torch.cuda.empty_cache()
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if hashlib.sha256(JFK_PATH.read_bytes()).hexdigest() != JFK_SHA:
        msg = "JFK clip does not match its pin"
        raise RuntimeError(msg)

    manifests = Path("ml/datasets/manifests")
    en_holdout = held_out(
        manifests / "candidates-fleurs-en_us-train.json",
        manifests / "qwen-en-retention-slice-v1.jsonl",
        window=(2.0, 30.0),
    )
    short_holdout = held_out(
        manifests / "candidates-indicvoices-hindi-train.json",
        manifests / "qwen-hi-short-slice-v1.jsonl",
        window=(0.5, 2.0),
    )

    rng = np.random.default_rng(20260818)
    speech = decode_to_float32(ANCHOR_CLIP)
    inputs: dict[str, Any] = {
        "jfk-english": (str(JFK_PATH), JFK_REFERENCE, "en"),
        "silence-10s": ((np.zeros(RATE * 10, dtype=np.float32), RATE), None, None),
        "noise-quiet(-50dBFS)-8s": (
            ((rng.standard_normal(RATE * 8) * 0.003).astype(np.float32), RATE),
            None,
            None,
        ),
        "window-1s-hindi": ((speech[RATE : RATE * 2], RATE), None, None),
        "window-2s-hindi": ((speech[RATE : RATE * 3], RATE), None, None),
    }
    for kind, rows in (("en-holdout", en_holdout), ("short-holdout", short_holdout)):
        for c in rows:
            inputs[f"{kind}:{c['id']}"] = (
                str(args.data_root / c["path"]),
                c["text"],
                c["language"],
            )

    checkpoints = sorted(
        args.checkpoints.glob("checkpoint-*/inferable"),
        key=lambda p: int(p.parent.name.split("-")[-1]),
    )
    payload: dict[str, Any] = {
        "experiment": "23-qwen3-hi-ft-e3",
        "phase": "sweep-probes (Phase 12 retention half)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "held_out_english": [c["id"] for c in en_holdout],
        "held_out_short": [c["id"] for c in short_holdout],
        "checkpoints": {},
    }
    for checkpoint in checkpoints:
        label = checkpoint.parent.name
        payload["checkpoints"][label] = probe_checkpoint(checkpoint, inputs)
        print(label, "done")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
