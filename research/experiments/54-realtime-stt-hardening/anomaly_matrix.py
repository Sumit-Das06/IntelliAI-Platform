"""M54 Phase 15/16 — the Hindi service-path anomaly, re-examined.

M52H found the CPU batch SERVICE path unstable on real30s (31.8 s,
multi-speaker) while every DIRECT call to the same llama child was
stable. This matrix answers ONLY the M54 questions:

    still reproducible? | CPU contention? | does GPU eliminate it?
    does realtime share the affected path?

Paths compared:
    cpu_service   — stt container /v1/transcribe (the affected path)
    cpu_service_contended — same, two calls in flight (contention probe)
    gpu_direct    — the realtime CUDA llama-server, same clip
    (realtime sessions come from the baseline battery evidence)

    python anomaly_matrix.py
"""

from __future__ import annotations

import base64
import concurrent.futures
import json
import statistics
import time
import urllib.request
import uuid
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
CLIPS = SCRATCH / "m52hclips"
CPU_RUNTIME = "http://127.0.0.1:8001/v1/transcribe"
GPU = "http://127.0.0.1:8797"


def parse_asr(raw: str) -> str:
    marker = "<asr_text>"
    return raw.partition(marker)[2].strip() if marker in raw else raw.strip()


def cpu_decode(path: Path) -> dict:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="params"\r\n\r\n'
        '{"language": "hi"}\r\n'
    ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += path.read_bytes() + b"\r\n" + f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        CPU_RUNTIME,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        envelope = json.loads(response.read())
    return {
        "words": len(str(envelope["output"]["text"]).split()),
        "latency_s": round(time.perf_counter() - started, 1),
        "inference_ms": round(envelope["timing"]["stages"]["inference"], 1),
    }


def gpu_decode(path: Path) -> dict:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                            "format": "wav",
                        },
                    },
                    {"type": "text", "text": "Transcribe the audio."},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
        "cache_prompt": False,
    }
    request = urllib.request.Request(  # noqa: S310 — loopback research server
        f"{GPU}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310
        body = json.loads(response.read())
    text = parse_asr(str(body["choices"][0]["message"]["content"]))
    return {"words": len(text.split()), "latency_s": round(time.perf_counter() - started, 1)}


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def spread(rows: list[dict]) -> dict:
    words = [row["words"] for row in rows]
    return {
        "runs": rows,
        "words_min": min(words),
        "words_max": max(words),
        "words_median": statistics.median(words),
        "stable": max(words) - min(words) <= max(2, round(0.05 * max(words))),
    }


def main() -> None:
    clips = {
        "real30s_multi": CLIPS / "real30s.wav",
        "real60s_multi": CLIPS / "real60s.wav",  # first 60 s of real2min (built below)
        "short_single": SCRATCH / "m52clips" / "16k_hindi_short.wav",
    }
    # Build the 60 s slice once.
    if not clips["real60s_multi"].exists():
        with wave.open(str(CLIPS / "real2min.wav"), "rb") as src:
            params = src.getparams()
            frames = src.readframes(60 * src.getframerate())
        with wave.open(str(clips["real60s_multi"]), "wb") as out:
            out.setparams(params)
            out.writeframes(frames)

    result: dict = {
        "date": "2026-08-31",
        "environment": "idle host, RTX 5070 laptop, "
        "stt container CPU, realtime stack up (idle during CPU runs)",
    }
    for name, path in clips.items():
        entry: dict = {"clip_seconds": round(wav_seconds(path), 1)}
        entry["cpu_service"] = spread([cpu_decode(path) for _ in range(5)])
        # Contention probe: two identical calls in flight at once.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            pair = list(pool.map(lambda _, p=path: cpu_decode(p), range(2)))
        entry["cpu_service_contended"] = spread(pair)
        entry["gpu_direct"] = spread([gpu_decode(path) for _ in range(3)])
        result[name] = entry
        print(name, json.dumps({k: v for k, v in entry.items() if k != "runs"})[:300])
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / "service-anomaly.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("anomaly matrix written")


if __name__ == "__main__":
    main()
