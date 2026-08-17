"""M22 Phase 13: the extended silence/noise battery — E2's acceptance gate.

Beyond the standard tripwire (digital silence, tone): quiet real-ish
noise at several levels, speech-to-silence and silence-to-speech
transitions, very short speech, and short noisy speech — the shapes a
real microphone hands a model. Compares the E1 and E2 candidates on
identical inputs; speech material comes from an approved public
training-pool clip (never the frozen eval).

Wanted: silence/noise -> EMPTY; speech (however framed) -> Devanagari.
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


def build_inputs(speech_path: Path) -> dict[str, Any]:
    rng = np.random.default_rng(20260818)
    speech = decode_to_float32(speech_path)
    speech = speech[: RATE * 8]  # up to 8 s of real Hindi speech

    def silence(seconds: float) -> Any:
        return np.zeros(int(seconds * RATE), dtype=np.float32)

    def noise(seconds: float, amplitude: float) -> Any:
        return (rng.standard_normal(int(seconds * RATE)) * amplitude).astype(np.float32)

    return {
        "digital-silence-10s": silence(10),
        "real-ish-noise-quiet(-50dBFS)-8s": noise(8, 0.003),
        "real-ish-noise-moderate(-40dBFS)-8s": noise(8, 0.01),
        "speech-then-silence-5s": np.concatenate([speech[: RATE * 5], silence(5)]),
        "silence-5s-then-speech": np.concatenate([silence(5), speech[: RATE * 5]]),
        "very-short-speech-1s": speech[RATE : RATE * 2],
        "short-speech-2.5s-in-noise": (
            speech[: int(RATE * 2.5)] + noise(2.5, 0.005)[: int(RATE * 2.5)]
        ),
    }


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
    parser.add_argument("--e1", type=Path, required=True)
    parser.add_argument("--e2", type=Path, required=True)
    parser.add_argument(
        "--speech",
        type=Path,
        default=Path(
            "ml/datasets/data/indicvoices/hindi/train/indicvoices-hindi-train-0-000005.flac"
        ),
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    inputs = build_inputs(args.speech)
    payload = {
        "experiment": "22-qwen3-hi-ft-e2",
        "phase": "silence-battery (Phase 13 acceptance gate)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "speech_source": str(args.speech),
        "e1_candidate": probe(args.e1, inputs),
        "e2_candidate": probe(args.e2, inputs),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:3500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
