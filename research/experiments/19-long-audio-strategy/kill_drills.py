"""M19 Phase 14 (rerun): kill the child MID-WINDOW, with honest timing.

The first drill pass timed its kills against the CONTENDED sandbox
walls; the fresh staging process decodes a 600 s request in ~180 s
(~20-25 s per window), so "kill at 215 s" landed after completion and
proved nothing. This rerun kills at ~35 s (early window) and ~100 s
(middle window) — verified against the engine fix that keeps
mid-response disconnects inside the retry contract.

Expected, per the M19 law: at most one retry; a complete transcript if
the supervisor's restart beats the 12 s retry delay, otherwise a clean
WHOLE-request failure (no partial text, amount 0, no sample). Either
outcome passes; which one occurred is recorded.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "16-qwen3-switching"))
from failure_drills import kill_pid, llama_server_pids

LEAK_MARKERS = (
    "qwen",
    "llama",
    "gguf",
    "ggml",
    "whisper",
    "ctranslate",
    "faster",
    "chunk",
    "window",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--runtime-url", default="http://127.0.0.1:8011")
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--kill-at", default="35,100")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ["INTELLIAI_M19_KEY"]

    record: dict[str, Any] = {
        "drill": "19-kill-mid-window-rerun",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
    }
    client = httpx.Client(base_url=args.base_url, timeout=500.0)

    def usage_totals() -> dict[str, Any]:
        response = client.get("/v1/usage/summary", headers={"Authorization": f"Bearer {key}"})
        response.raise_for_status()
        totals: dict[str, Any] = response.json()["totals"]
        return totals

    def run_request(outcome: dict[str, Any]) -> None:
        started = time.perf_counter()
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {key}", "X-IntelliAI-Client": "m19-drill/1.0"},
            files={"file": (args.wav.name, args.wav.read_bytes(), "audio/wav")},
            data={"model": "intelliai-stt", "language": "hi"},
        )
        outcome["status"] = response.status_code
        outcome["elapsed_seconds"] = round(time.perf_counter() - started, 1)
        lowered = response.text.lower()
        outcome["leaks"] = [m for m in LEAK_MARKERS if m in lowered]
        if response.status_code == 200:
            outcome["text_chars"] = len(response.json().get("text", ""))
        else:
            body = response.json() if response.text else {}
            outcome["error_type"] = body.get("error", {}).get("type", "")
            outcome["error_message"] = body.get("error", {}).get("message", "")[:120]
            outcome["partial_text_present"] = '"text"' in response.text
        outcome["sample_header_present"] = bool(response.headers.get("X-IntelliAI-Sample"))

    for kill_at in (float(x) for x in args.kill_at.split(",")):
        before = usage_totals()
        outcome: dict[str, Any] = {}
        worker = threading.Thread(target=run_request, args=(outcome,))
        worker.start()
        time.sleep(kill_at)
        pids = llama_server_pids()
        for pid in pids:
            kill_pid(pid)
        worker.join(timeout=520)
        after = usage_totals()
        record[f"kill_at_{int(kill_at)}s"] = {
            **outcome,
            "pids_killed": pids,
            "seconds_from_kill_to_response": round(outcome.get("elapsed_seconds", 0) - kill_at, 1),
            "usage_delta": {
                "requests": after["requests"] - before["requests"],
                "speech_seconds": round(
                    (after["speech_minutes"] - before["speech_minutes"]) * 60, 1
                ),
                "failed": after.get("outcomes", {}).get("failed", 0)
                - before.get("outcomes", {}).get("failed", 0),
            },
        }
        print(
            json.dumps(
                {f"kill_at_{int(kill_at)}s": record[f"kill_at_{int(kill_at)}s"]}, ensure_ascii=False
            ),
            flush=True,
        )

        deadline = time.monotonic() + 180
        recovered = False
        while time.monotonic() < deadline:
            ready = httpx.get(f"{args.runtime_url}/health/ready", timeout=5.0)
            if ready.status_code == 200 and ready.json().get("status") == "ready":
                recovered = True
                break
            time.sleep(2.0)
        record[f"kill_at_{int(kill_at)}s"]["runtime_recovered_after"] = recovered

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
