"""M33 — repeated-generation consistency probe (spec Phase 1).

Synthesizes the SAME text N times through an OpenAI-compatible /v1/audio/speech
endpoint (our gateway, or a candidate server speaking the same subset) and
reports: per-run wall time, audio duration, byte-level identity (sha256 set),
and duration variance. Byte-identical output = deterministic engine; varying
bytes with stable duration = stochastic sampling — a product fact for caching
and for regression testing.

Run from the repo root:
    uv run --package intelliai-evaluation python .../m33_consistency_probe.py \
      --url http://localhost:8000 --api-key-file <path> --model intelliai-tts \
      --voice reference-alto --runs 5 --out evidence/kokoro-consistency.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
import wave
from io import BytesIO
from pathlib import Path

import httpx

TEXT = "Thank you for calling IntelliAI customer care. How may I help you today?"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--api-key-file", default=None)
    parser.add_argument("--model", default="intelliai-tts")
    parser.add_argument("--voice", default=None)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    headers = {}
    if args.api_key_file:
        headers["Authorization"] = f"Bearer {Path(args.api_key_file).read_text().strip()}"

    runs: list[dict[str, object]] = []
    with httpx.Client(base_url=args.url, headers=headers, timeout=120.0) as client:
        body: dict[str, object] = {"model": args.model, "input": TEXT}
        if args.voice:
            body["voice"] = args.voice
        client.post("/v1/audio/speech", json=body)  # warm, excluded
        for index in range(args.runs):
            started = time.perf_counter()
            response = client.post("/v1/audio/speech", json=body)
            wall = time.perf_counter() - started
            response.raise_for_status()
            audio = response.content
            with wave.open(BytesIO(audio), "rb") as fh:
                seconds = fh.getnframes() / fh.getframerate()
            runs.append(
                {
                    "run": index + 1,
                    "wall_ms": round(wall * 1000.0, 1),
                    "audio_seconds": round(seconds, 3),
                    "bytes": len(audio),
                    "sha256": hashlib.sha256(audio).hexdigest()[:16],
                }
            )

    hashes = {str(run["sha256"]) for run in runs}
    durations = [float(run["audio_seconds"]) for run in runs]
    walls = [float(run["wall_ms"]) for run in runs]
    report = {
        "experiment": "33-english-tts-selection",
        "instrument": "m33_consistency_probe.py",
        "endpoint": args.url,
        "text": TEXT,
        "runs": runs,
        "distinct_audio_hashes": len(hashes),
        "byte_deterministic": len(hashes) == 1,
        "duration_stdev_s": round(statistics.pstdev(durations), 4) if durations else None,
        "wall_ms_stdev": round(statistics.pstdev(walls), 1) if walls else None,
    }
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"consistency @ {args.url}: {len(hashes)} distinct hashes over {len(runs)} runs, "
        f"duration stdev {report['duration_stdev_s']} s, wall stdev {report['wall_ms_stdev']} ms"
    )


if __name__ == "__main__":
    main()
