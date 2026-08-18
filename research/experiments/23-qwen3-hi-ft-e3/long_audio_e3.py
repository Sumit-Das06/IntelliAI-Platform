"""M23 Phase 18: long audio through the M19 chunked path, E3 artifact served.

300 s and 600 s concatenations (the M19 builder, frozen-eval natural
clips) posted to the real /v1/transcribe route of the runtime serving
the E3 GGUF. Wanted: COMPLETE transcripts (never partial), segments at
real offsets, join == text — the M19 laws — with the E3 weights.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "19-long-audio-strategy"))
from longaudio_probe import build_concat

RATE = 16_000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8123")
    parser.add_argument("--artifact", default="qwen3-asr-0.6b-hi-ft-e3")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json"),
    )
    parser.add_argument("--data-root", type=Path, default=Path("ml/datasets/data"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.work.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    with httpx.Client(timeout=httpx.Timeout(900.0, connect=10.0)) as client:
        for seconds in (300, 600):
            wav_path, _reference = build_concat(args.manifest, args.data_root, seconds, args.work)
            started = time.perf_counter()
            response = client.post(
                f"{args.url}/v1/transcribe",
                files={"file": (wav_path.name, wav_path.read_bytes(), "audio/wav")},
                data={"params": json.dumps({"model": args.artifact, "language": "hi"})},
            )
            wall = time.perf_counter() - started
            response.raise_for_status()
            output = response.json()["output"]
            text = str(output.get("text", ""))
            segments = output.get("segments") or []
            # The engine's own law (test_qwen3_asr): segments SPACE-join
            # back into exactly the merged text, at real offsets.
            join = " ".join(str(s.get("text", "")) for s in segments)
            results[f"{seconds}s"] = {
                "complete": bool(text.strip()),
                "chars": len(text),
                "segments": len(segments),
                "join_equals_text": join == text,
                "first_offset": segments[0].get("start_seconds") if segments else None,
                "last_end": segments[-1].get("end_seconds") if segments else None,
                "wall_seconds": round(wall, 1),
            }
            print(f"{seconds}s: {json.dumps(results[f'{seconds}s'])}")

    doc = {
        "experiment": "23-qwen3-hi-ft-e3",
        "phase": "long-audio (Phase 18; M19 chunked path, E3 served)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "artifact": args.artifact,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
