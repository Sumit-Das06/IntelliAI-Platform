"""M23 Phases 15-16: the retention battery — E3's short-speech and silence gates.

Extends the M22 silence battery with the graded short-speech ladder the
milestone demands (0.5 / 1.0 / 1.5 / 2.0 / 2.5 s windows of real Hindi
speech) alongside the silence/noise/transition inputs E2 already
passed. Compares the E2 and E3 candidates on identical inputs; speech
material comes from an approved public training-pool clip (never the
frozen eval).

Wanted: silence/noise -> EMPTY; speech at EVERY duration -> Devanagari
(E2's recorded failure: 1 s speech -> empty).
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np

from intelliai_training.audio_io import decode_to_float32
from intelliai_training.qwen_trainer import load_wrapper

RATE = 16_000


def build_inputs(speech_path: Path, real_shorts: list[Path]) -> dict[str, Any]:
    rng = np.random.default_rng(20260818)
    speech = decode_to_float32(speech_path)
    speech = speech[: RATE * 8]  # up to 8 s of real Hindi speech

    def silence(seconds: float) -> Any:
        return np.zeros(int(seconds * RATE), dtype=np.float32)

    def noise(seconds: float, amplitude: float) -> Any:
        return (rng.standard_normal(int(seconds * RATE)) * amplitude).astype(np.float32)

    inputs: dict[str, Any] = {
        # ── the silence/noise gate (Phase 16): E2's win, must not regress ──
        "digital-silence-10s": silence(10),
        "real-ish-noise-quiet(-50dBFS)-8s": noise(8, 0.003),
        "real-ish-noise-moderate(-40dBFS)-8s": noise(8, 0.01),
        "speech-then-silence-5s": np.concatenate([speech[: RATE * 5], silence(5)]),
        "silence-5s-then-speech": np.concatenate([silence(5), speech[: RATE * 5]]),
        "short-speech-2.5s-in-noise": (
            speech[: int(RATE * 2.5)] + noise(2.5, 0.005)[: int(RATE * 2.5)]
        ),
    }
    # ── the short-speech ladder (Phase 15): E3's own gate ──────────────
    # Windows anchored at 1 s into the clip (same anchor the M22 battery
    # used for its 1 s probe, so E2/E3 numbers compare directly).
    for seconds in (0.5, 1.0, 1.5, 2.0, 2.5):
        end = RATE + int(seconds * RATE)
        inputs[f"speech-ladder-{seconds}s"] = speech[RATE:end]
    # Real whole short utterances (Phase 15 prefers real speech): held-out
    # approved-pool clips that did NOT enter the training slice.
    for path in real_shorts:
        inputs[f"real-short:{path.name}"] = decode_to_float32(path)
    return inputs


def probe(model_dir: Path, inputs: dict[str, Any]) -> dict[str, Any]:
    import torch

    wrapper = load_wrapper(model_dir, device_map="cuda:0")
    out: dict[str, Any] = {}
    for name, wave in inputs.items():
        result = wrapper.transcribe((wave, RATE))
        text = str(result[0].text) if result else ""
        out[name] = {
            "empty": not text.strip(),
            "devanagari": any("ऀ" <= ch <= "ॿ" for ch in text),
            "repetition": _repeats(text),
            "text_head": text[:70],
        }
    del wrapper
    torch.cuda.empty_cache()
    return out


def _repeats(text: str) -> bool:
    words = text.split()
    if len(words) < 4:
        return False
    return any(words[i] == words[i + 1] == words[i + 2] for i in range(len(words) - 2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e2", type=Path, required=True)
    parser.add_argument("--e3", type=Path, required=True)
    parser.add_argument(
        "--speech",
        type=Path,
        default=Path(
            "ml/datasets/data/indicvoices/hindi/train/indicvoices-hindi-train-0-000005.flac"
        ),
    )
    parser.add_argument(
        "--real-short",
        type=Path,
        nargs="*",
        default=[],
        help="whole real short utterances held OUT of the training slice",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    inputs = build_inputs(args.speech, list(args.real_short))
    payload = {
        "experiment": "23-qwen3-hi-ft-e3",
        "phase": "retention-battery (Phases 15-16 gates)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "speech_source": str(args.speech),
        "e2_candidate": probe(args.e2, inputs),
        "e3_candidate": probe(args.e3, inputs),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:3500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
