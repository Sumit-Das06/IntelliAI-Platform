"""M24 Phase 5: the extended product safety battery — E3 vs the incumbent.

The promotion question is not CER; it is behavior on the inputs a real
microphone produces. Identical inputs through the SAME multi-slot
runtime process, per artifact: digital silence, low-level noise,
speech<->silence transitions, the graded 0.5-2.5 s Hindi ladder, real
held-out short utterances, normal Hindi, English, and the malformed /
empty / tiny inputs. Base-qwen behavior is cited from the committed
M22/M23 batteries (it is not hosted here and is supporting context
only, per the milestone).

Wanted per arm: silence/noise -> EMPTY; speech -> text in the right
script; malformed -> clean 400; no repetition; no leaks.
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
LEAK_MARKERS = ("qwen", "llama", "gguf", "ggml", "ctranslate", "faster", "e3")


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


def build_inputs(data_root: Path) -> dict[str, tuple[bytes, str]]:
    """name -> (payload bytes, language hint)."""
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

    inputs: dict[str, tuple[bytes, str]] = {
        "digital-silence-10s": (wav_bytes(silence(10)), "hi"),
        "noise-quiet(-50dBFS)-8s": (wav_bytes(noise(8, 0.003)), "hi"),
        "speech-then-silence-5s": (
            wav_bytes(np.concatenate([speech[: RATE * 5], silence(5)])),
            "hi",
        ),
        "silence-5s-then-speech": (
            wav_bytes(np.concatenate([silence(5), speech[: RATE * 5]])),
            "hi",
        ),
        "normal-hindi-8s": (wav_bytes(speech), "hi"),
        "english-jfk": (JFK_PATH.read_bytes(), "en"),
        "malformed-audio": (b"this is not audio at all", "hi"),
        "empty-audio": (b"", "hi"),
        "tiny-malformed": (b"RIFFxxxx", "hi"),
    }
    for seconds in (0.5, 1.0, 1.5, 2.0, 2.5):
        end = RATE + int(seconds * RATE)
        inputs[f"speech-ladder-{seconds}s"] = (wav_bytes(speech[RATE:end]), "hi")

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
        inputs[f"real-short:{c['id']}"] = ((data_root / c["path"]).read_bytes(), "hi")
    return inputs


def probe(client: httpx.Client, artifact: str, inputs: dict[str, tuple[bytes, str]]) -> dict:
    out: dict[str, Any] = {}
    for name, (payload, language) in inputs.items():
        try:
            response = client.post(
                "/v1/transcribe",
                files={"file": (f"{name}.wav", payload, "audio/wav")},
                data={"params": json.dumps({"model": artifact, "language": language})},
            )
        except httpx.HTTPError as exc:
            out[name] = {"transport_error": type(exc).__name__}
            continue
        if response.status_code != 200:
            body = response.json()
            message = str(body.get("message", ""))
            out[name] = {
                "status": response.status_code,
                "error_type": body.get("type"),
                "leaks": [m for m in LEAK_MARKERS if m in message.lower()],
            }
            continue
        text = str(response.json()["output"].get("text", ""))
        words = text.split()
        out[name] = {
            "status": 200,
            "empty": not text.strip(),
            "devanagari": any("ऀ" <= ch <= "ॿ" for ch in text),
            "latin": any("a" <= ch.lower() <= "z" for ch in text),
            "repetition": len(words) >= 4
            and any(words[i] == words[i + 1] == words[i + 2] for i in range(len(words) - 2)),
            "text_head": text[:60],
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    inputs = build_inputs(args.data_root)
    with httpx.Client(base_url=args.url, timeout=300.0) as client:
        payload = {
            "experiment": "24-e3-promotion",
            "phase": "safety-battery (Phase 5; base-qwen cited from M22/M23 evidence)",
            "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            "e3": probe(client, "qwen3-asr-0.6b-hi-ft-e3", inputs),
            "whisper_small": probe(client, "whisper-small", inputs),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in inputs:
        e3 = payload["e3"][name]
        wh = payload["whisper_small"][name]

        def verdict(row: dict[str, Any]) -> str:
            if row.get("status") != 200:
                return f"{row.get('status')}/{row.get('error_type')}"
            if row.get("empty"):
                return "EMPTY"
            return "deva" if row.get("devanagari") else ("latin" if row.get("latin") else "other")

        print(f"{name}: e3={verdict(e3)} whisper={verdict(wh)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
