"""M23 Phases 15-16, adapter-side: the retention battery on the SERVED artifact.

The sweep probed every checkpoint HF-side; this battery asks the same
questions of the PRODUCT PATH — the quantized GGUF served by the pinned
b10344 runtime behind the real /v1/transcribe route — because the gate
that matters is the one users hit. Inputs: the graded short-speech
ladder (0.5-2.5 s of real Hindi), silence, noise at two levels,
speech<->silence transitions, real held-out short utterances, and the
pinned JFK English clip.

Wanted: silence/noise -> EMPTY; speech at every duration -> text in the
RIGHT language; no repeated-token hallucination.
"""

from __future__ import annotations

import argparse
import datetime
import io
import json
import wave
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import soundfile

RATE = 16_000
ANCHOR_CLIP = Path("ml/datasets/data/indicvoices/hindi/train/indicvoices-hindi-train-0-000005.flac")
JFK_PATH = Path("ml/evaluation/data/jfk-flac.flac")


def wav_bytes(wave_f32: np.ndarray) -> bytes:
    pcm = np.clip(wave_f32, -1.0, 1.0)
    ints = (pcm * 32767.0).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(ints.tobytes())
    return buffer.getvalue()


def build_inputs(data_root: Path) -> dict[str, bytes]:
    rng = np.random.default_rng(20260818)
    speech, sr = soundfile.read(ANCHOR_CLIP, dtype="float32")
    if sr != RATE:
        msg = f"anchor clip rate {sr} != {RATE}"
        raise RuntimeError(msg)
    speech = speech[: RATE * 8]

    def silence(seconds: float) -> np.ndarray:
        return np.zeros(int(seconds * RATE), dtype=np.float32)

    def noise(seconds: float, amplitude: float) -> np.ndarray:
        return (rng.standard_normal(int(seconds * RATE)) * amplitude).astype(np.float32)

    inputs: dict[str, bytes] = {
        "digital-silence-10s": wav_bytes(silence(10)),
        "noise-quiet(-50dBFS)-8s": wav_bytes(noise(8, 0.003)),
        "noise-moderate(-40dBFS)-8s": wav_bytes(noise(8, 0.01)),
        "speech-then-silence-5s": wav_bytes(np.concatenate([speech[: RATE * 5], silence(5)])),
        "silence-5s-then-speech": wav_bytes(np.concatenate([silence(5), speech[: RATE * 5]])),
        "short-speech-2.5s-in-noise": wav_bytes(
            speech[: int(RATE * 2.5)] + noise(2.5, 0.005)[: int(RATE * 2.5)]
        ),
    }
    for seconds in (0.5, 1.0, 1.5, 2.0, 2.5):
        end = RATE + int(seconds * RATE)
        inputs[f"speech-ladder-{seconds}s"] = wav_bytes(speech[RATE:end])

    # Real held-out shorts: same deterministic picks as the HF-side sweep.
    manifests = Path("ml/datasets/manifests")
    selected = {
        json.loads(line)["id"]
        for line in (manifests / "qwen-hi-short-slice-v1.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }
    payload = json.loads(
        (manifests / "candidates-indicvoices-hindi-train.json").read_text(encoding="utf-8")
    )
    pool = [
        c
        for c in payload["candidates"]
        if c["id"] not in selected
        and 0.5 <= c["duration_seconds"] < 2.0
        and c["text"].strip()
        and "<" not in c["text"]
    ]
    for c in sorted(pool, key=lambda x: x["sha256"].lower())[:2]:
        inputs[f"real-short:{c['id']}"] = (data_root / c["path"]).read_bytes()

    inputs["jfk-english"] = JFK_PATH.read_bytes()
    return inputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8123")
    parser.add_argument("--artifact", default="qwen3-asr-0.6b-hi-ft-e3")
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    inputs = build_inputs(args.data_root)
    results: dict[str, Any] = {}
    with httpx.Client(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        for name, payload in inputs.items():
            language = "en" if "english" in name else "hi"
            response = client.post(
                f"{args.url}/v1/transcribe",
                files={"file": ("probe.wav", payload, "audio/wav")},
                data={"params": json.dumps({"model": args.artifact, "language": language})},
            )
            response.raise_for_status()
            output = response.json()["output"]
            text = str(output.get("text", ""))
            words = text.split()
            results[name] = {
                "empty": not text.strip(),
                "devanagari": any("ऀ" <= ch <= "ॿ" for ch in text),
                "latin": any("a" <= ch.lower() <= "z" for ch in text),
                "repetition": len(words) >= 4
                and any(words[i] == words[i + 1] == words[i + 2] for i in range(len(words) - 2)),
                "text_head": text[:70],
            }

    doc = {
        "experiment": "23-qwen3-hi-ft-e3",
        "phase": "adapter-battery (Phases 15-16 through the served artifact)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "artifact": args.artifact,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, entry in results.items():
        verdict = "EMPTY" if entry["empty"] else ("deva" if entry["devanagari"] else "latin")
        print(f"{name}: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
