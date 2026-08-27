"""M51 latency + long-audio evidence against the STAGING stt-runtime
container (127.0.0.1:8001, flag ON).

The runtime envelope carries raw_text and per-stage timings, so every
run yields the invariant check and the exact punctuation overhead.
Long clips are built by concatenating the boss clip with ffmpeg into
the scratchpad (audio never enters git).

    python m51_latency_long.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVIDENCE = HERE / "evidence"
sys.path.insert(0, str(ROOT / "services/stt-runtime/src"))
sys.path.insert(0, str(ROOT / "packages/runtime-contract/src"))

from intelliai_stt_runtime.engines.punctuation import depunct  # noqa: E402

SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
BOSS = Path(r"C:\Users\VIKASHAN TECHNOLOGIE\Downloads\WhatsApp Ptt 2026-08-26 at 7.58.05 PM.ogg")
LONG_DIR = SCRATCH / "m51long"
RUNTIME = "http://127.0.0.1:8001/v1/transcribe"


def transcribe(audio: Path) -> tuple[dict, float]:
    boundary = uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="params"\r\n\r\n'
        '{"language": "en"}\r\n'
    ).encode()
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{audio.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
    ).encode()
    body += audio.read_bytes() + b"\r\n" + f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        RUNTIME,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=900) as response:  # noqa: S310
        envelope = json.loads(response.read())
    return envelope, time.perf_counter() - started


def ffmpeg(*args: str) -> None:
    # Fixed argv built entirely in this file; PATH ffmpeg is the repo law.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)  # noqa: S603, S607


def build_long_clips() -> dict[str, Path]:
    LONG_DIR.mkdir(exist_ok=True)
    clips = {"30s": LONG_DIR / "30s.wav"}
    ffmpeg("-i", str(BOSS), "-t", "30", "-ar", "16000", "-ac", "1", str(clips["30s"]))
    concat_list = LONG_DIR / "list.txt"
    escaped = str(BOSS).replace("'", "'\\''")
    concat_list.write_text(f"file '{escaped}'\n" * 6, encoding="utf-8")
    for name, seconds in (("2min", "120"), ("5min", "300"), ("10min", "595")):
        clips[name] = LONG_DIR / f"{name}.wav"
        ffmpeg(
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-t",
            seconds,
            "-ar",
            "16000",
            "-ac",
            "1",
            str(clips[name]),
        )
    return clips


def summarize(envelope: dict, wall: float) -> dict:
    output = envelope["output"]
    stages = envelope["timing"]["stages"]
    raw = output.get("raw_text")
    text = output["text"]
    return {
        "duration_seconds": round(output["duration_seconds"], 1),
        "inference_ms": round(stages.get("inference", 0.0), 1),
        "punctuation_en_ms": round(stages.get("punctuation_en", 0.0), 1),
        "stage_applied": raw is not None,
        "words_out": len(text.split()),
        "invariant_holds": (depunct(raw) == depunct(text)) if raw is not None else None,
        "wall_seconds": round(wall, 2),
    }


def main() -> None:
    EVIDENCE.mkdir(exist_ok=True)

    # ── latency: boss x5 through the staging runtime ─────────────────────
    runs = []
    for _ in range(5):
        envelope, wall = transcribe(BOSS)
        runs.append(summarize(envelope, wall))
    punct = sorted(run["punctuation_en_ms"] for run in runs)
    inference = sorted(run["inference_ms"] for run in runs)
    latency = {
        "clip": "boss 102 s",
        "runs": runs,
        "punctuation_en_ms": {
            "p50": statistics.median(punct),
            "max": punct[-1],
        },
        "inference_ms_p50": statistics.median(inference),
        "overhead_percent_of_inference_p50": round(
            100.0 * statistics.median(punct) / statistics.median(inference), 2
        ),
    }
    (EVIDENCE / "latency-staging.json").write_text(
        json.dumps(latency, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        "latency:",
        latency["punctuation_en_ms"],
        f"{latency['overhead_percent_of_inference_p50']}% of inference",
    )

    # ── long audio ladder ────────────────────────────────────────────────
    ladder = {}
    for name, clip in build_long_clips().items():
        envelope, wall = transcribe(clip)
        ladder[name] = summarize(envelope, wall)
        print(name, ladder[name])
    (EVIDENCE / "long-audio-staging.json").write_text(
        json.dumps(ladder, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
