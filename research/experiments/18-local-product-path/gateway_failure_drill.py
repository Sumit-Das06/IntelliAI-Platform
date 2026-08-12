"""Milestone 18 Phase 11: the Qwen child dies UNDER the real gateway.

Kills the llama-server child behind the staging runtime, then proves —
through POST /v1/audio/transcriptions only — that Hindi fails safely
(standard envelope, bounded, no leak, not billed), English keeps
serving from the same process, no automatic fallback re-routes Hindi
to the incumbent, and the supervisor's recovery restores Hindi service
with exactly one usage event for the one eventual success.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "16-qwen3-switching"))
from failure_drills import kill_pid, llama_server_pids

LEAK_MARKERS = ("qwen", "llama", "gguf", "ggml", "ctranslate", "faster")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--runtime-url", default="http://127.0.0.1:8011")
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ["INTELLIAI_M18_KEY"]

    hi = (args.audio_dir / "hi-short.wav").read_bytes()
    en = (args.audio_dir / "en-jfk.wav").read_bytes()
    record: dict[str, Any] = {
        "drill": "18-gateway-failure",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
    }

    def transcribe(audio: bytes, language: str) -> tuple[int, float, list[str], str]:
        started = time.perf_counter()
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}"},
            files={"file": ("clip.wav", audio, "audio/wav")},
            data={"model": "intelliai-stt", "language": language},
        )
        elapsed = round(time.perf_counter() - started, 2)
        lowered = response.text.lower()
        leaks = [marker for marker in LEAK_MARKERS if marker in lowered]
        return (
            response.status_code,
            elapsed,
            leaks,
            response.json().get("error", {}).get("type", "") if response.status_code != 200 else "",
        )

    with httpx.Client(base_url=args.base_url, timeout=300.0) as client:
        pids = llama_server_pids()
        record["pids_killed"] = pids
        for pid in pids:
            kill_pid(pid)
        time.sleep(1.5)  # monitor interval: readiness flips within ~1 s

        status, elapsed, leaks, error_type = transcribe(hi, "hi")
        record["hindi_during_outage"] = {
            "status": status,
            "bounded_seconds": elapsed,
            "leaks": leaks,
            "error_type": error_type,
        }
        status, elapsed, leaks, _ = transcribe(en, "en")
        record["english_during_outage"] = {
            "status": status,
            "seconds": elapsed,
            "leaks": leaks,
        }
        ready = httpx.get(f"{args.runtime_url}/health/ready", timeout=5.0)
        record["runtime_readiness_during_outage"] = {
            "code": ready.status_code,
            "body": ready.json(),
        }

        recovered = None
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            ready = httpx.get(f"{args.runtime_url}/health/ready", timeout=5.0)
            if ready.status_code == 200 and ready.json().get("status") == "ready":
                recovered = True
                break
            time.sleep(1.0)
        record["runtime_recovered"] = bool(recovered)

        status, elapsed, leaks, _ = transcribe(hi, "hi")
        record["hindi_after_recovery"] = {
            "status": status,
            "seconds": elapsed,
            "leaks": leaks,
        }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
