"""M52 GPU datapoint — the CURRENT English engine (whisper-small CT2)
on the laptop RTX 5070, WSL CUDA via the torch-bundled NVIDIA libs.

Measures the decode-time-vs-window curve that dominates streaming UX
(the fixed encoder pass + tokens), greedy and beam-5, plus one
growing-window streaming sim on boss30 for FPT/cadence on GPU.

    python gpu_whisper.py <boss30_wav> <out.json>
"""

from __future__ import annotations

import itertools
import json
import statistics
import sys
import time
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
MODEL_DIR = ROOT / "models" / "whisper-small" / "v1"


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


def main() -> None:
    wav_path, out_name = sys.argv[1:3]
    audio = load_wav(Path(wav_path))
    total_s = len(audio) / 16_000.0

    from faster_whisper import WhisperModel

    model = WhisperModel(str(MODEL_DIR), device="cuda", compute_type="float16")

    def decode(window: np.ndarray, beam: int) -> tuple[str, float]:
        started = time.perf_counter()
        segments, _ = model.transcribe(
            window,
            task="transcribe",
            language="en",
            beam_size=beam,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        text = "".join(segment.text for segment in segments).strip()
        return text, time.perf_counter() - started

    decode(audio[:16_000], 5)  # warm-up (CUDA kernels + model)
    decode(audio, 5)

    curve = {}
    for window_s in (0.5, 1, 2, 5, 10, 25, 30):
        samples = audio[: int(window_s * 16_000)]
        row = {}
        for beam in (1, 5):
            times = []
            for _ in range(5):
                _, elapsed = decode(samples, beam)
                times.append(elapsed * 1000.0)
            row[f"beam{beam}_ms_median"] = round(statistics.median(times), 1)
        curve[f"{window_s}s"] = row

    # Growing-window streaming sim, 500 ms chunks, greedy partials.
    chunk_s = 0.5
    clock = chunk_s
    events = []
    while True:
        available = min(total_s, (int(max(clock, chunk_s) / chunk_s)) * chunk_s)
        text, elapsed = decode(audio[: int(available * 16_000)], 1)
        clock = max(clock, available) + elapsed
        events.append(
            {
                "audio_s": round(available, 2),
                "latency_ms": round((clock - available) * 1000.0, 1),
                "decode_ms": round(elapsed * 1000.0, 1),
                "has_text": bool(text),
            }
        )
        if available >= total_s:
            break
    fpt = next((e for e in events if e["has_text"]), None)
    gaps = [b["audio_s"] - a["audio_s"] for a, b in itertools.pairwise(events)]

    payload = {
        "device": "cuda (RTX 5070 Laptop, WSL2), compute_type=float16",
        "model": "whisper-small (current production artifact)",
        "decode_curve_ms": curve,
        "stream_sim_500ms_greedy": {
            "updates": len(events),
            "fpt_ms": round(fpt["latency_ms"] + fpt["audio_s"] * 0, 1) if fpt else None,
            "fpt_done_at_s": round(fpt["audio_s"] + fpt["latency_ms"] / 1000.0, 2) if fpt else None,
            "update_latency_p50_ms": round(
                statistics.median(e["latency_ms"] for e in events[:-1]), 1
            )
            if len(events) > 1
            else None,
            "cadence_p50_s": round(statistics.median(gaps), 2) if gaps else None,
            "finalization_ms": events[-1]["latency_ms"],
        },
    }
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / out_name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["stream_sim_500ms_greedy"]))
    print("0.5s window:", curve["0.5s"], " 25s window:", curve["25s"])


if __name__ == "__main__":
    main()
