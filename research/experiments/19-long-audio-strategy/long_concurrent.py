"""M19 Phase 17: concurrent LONG requests — capacity characterization.

NOT a guarantee; a measurement of this machine's staging pair. Batches:
2 x 300 s, 5 x 300 s, 2 x 600 s, each through the REAL gateway. Per
batch: statuses, walls, admission refusals, and the llama-server RSS
trajectory (the §9 retention finding needs numbers under sustained
long-audio load). The runtime pool stays at the deployment default
(max_concurrency=2, queue=8): overloaded refusals are measurement, not
noise.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from longaudio_probe import RssSampler

LEAK_MARKERS = ("qwen", "llama", "gguf", "ggml", "whisper", "ctranslate", "faster")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ["INTELLIAI_M19_KEY"]

    record: dict[str, Any] = {
        "characterization": "19-long-audio-concurrency",
        "NOT_A_GUARANTEE": "capacity characterization of THIS machine's staging pair",
        "pool": "runtime deployment defaults (max_concurrency=2, max_queue=8)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "batches": [],
    }

    def one_request(wav_bytes: bytes, name: str) -> dict[str, Any]:
        started = time.perf_counter()
        with httpx.Client(base_url=args.base_url, timeout=500.0) as client:
            response = client.post(
                "/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "X-IntelliAI-Client": "m19-capacity/1.0",
                    "X-IntelliAI-Contribution": "off",
                },
                files={"file": (name, wav_bytes, "audio/wav")},
                data={"model": "intelliai-stt", "language": "hi"},
            )
        lowered = response.text.lower()
        return {
            "status": response.status_code,
            "wall_seconds": round(time.perf_counter() - started, 1),
            "text_chars": len(response.json().get("text", ""))
            if response.status_code == 200
            else 0,
            "error_type": ""
            if response.status_code == 200
            else response.json().get("error", {}).get("type", ""),
            "leaks": [m for m in LEAK_MARKERS if m in lowered],
        }

    for count, seconds in ((2, 300), (5, 300), (2, 600)):
        wav = (args.audio_dir / f"concat-{seconds}s.wav").read_bytes()
        sampler = RssSampler()
        batch_started = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
            results = list(
                pool.map(
                    lambda i, wav=wav, seconds=seconds: one_request(wav, f"cap-{seconds}s-{i}.wav"),
                    range(count),
                )
            )
        batch = {
            "shape": f"{count}x{seconds}s",
            "batch_wall_seconds": round(time.perf_counter() - batch_started, 1),
            "peak_llama_rss_mib": sampler.stop(),
            "results": results,
        }
        record["batches"].append(batch)
        print(json.dumps(batch, ensure_ascii=False), flush=True)
        time.sleep(10)  # let queues drain between shapes

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
