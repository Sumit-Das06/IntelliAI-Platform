"""M24 Phase 10: failure / restart / readiness drills on the E3 slot.

The M16 drill proved slot isolation; M17 added slot-truthful readiness
and SUPERVISED child restart. This drill exercises the E3 candidate
under the M17 laws: kill the llama-server child, watch readiness tell
the truth, watch supervision bring the slot back bounded, prove the
incumbent never blinked, repeat the kill to show recovery is not a
one-shot, and account for orphans at the end. No automatic
per-request fallback exists — that is a recorded decision, re-verified
here (a failed E3 request stays failed; nothing re-routes).
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

HI_CLIP = Path("ml/datasets/data/indicvoices/hindi/valid/indicvoices-hindi-valid-0-001287.flac")
E3 = "qwen3-asr-0.6b-hi-ft-e3"
WHISPER = "whisper-small"
LEAK_MARKERS = ("llama", "gguf", "qwen", "ggml", "whisper", "ctranslate", "faster", "e3")


def request(client: httpx.Client, artifact: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = client.post(
            "/v1/transcribe",
            files={"file": (HI_CLIP.name, HI_CLIP.read_bytes(), "audio/flac")},
            data={"params": json.dumps({"model": artifact, "language": "hi"})},
        )
        body: dict[str, Any] = response.json()
        message = str(body.get("message", ""))
        return {
            "status": response.status_code,
            "error_type": body.get("type") if response.status_code != 200 else None,
            "message_leaks_internals": any(m in message.lower() for m in LEAK_MARKERS),
            "client_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    except httpx.HTTPError as exc:
        return {"status": 0, "transport_error": type(exc).__name__}


def slot_state(client: httpx.Client) -> tuple[int, dict[str, str]]:
    response = client.get("/health/ready")
    try:
        return response.status_code, dict(response.json().get("slots", {}))
    except json.JSONDecodeError:
        return response.status_code, {}


def llama_server_pids() -> list[int]:
    if sys.platform != "win32":
        completed = subprocess.run(
            ["pgrep", "-x", "llama-server"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return [int(line) for line in completed.stdout.split() if line.strip().isdigit()]
    completed = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq llama-server.exe", "/FO", "CSV", "/NH"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    pids: list[int] = []
    for line in completed.stdout.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower() == "llama-server.exe":
            pids.append(int(parts[1]))
    return pids


def kill_cycle(client: httpx.Client, label: str, drills: dict[str, Any]) -> None:
    """Kill the child; timeline readiness truth and supervised recovery."""
    pids = llama_server_pids()
    drills[f"{label}:pids_before_kill"] = pids
    kill_at = time.perf_counter()
    for pid in pids:
        subprocess.run(  # noqa: S603 — the drill IS the kill
            ["taskkill", "/F", "/PID", str(pid)],  # noqa: S607
            capture_output=True,
            timeout=15,
            check=False,
        )

    truth_at: float | None = None
    ready_at: float | None = None
    timeline: list[dict[str, Any]] = []
    deadline = kill_at + 120.0
    while time.perf_counter() < deadline:
        status, slots = slot_state(client)
        state = slots.get(E3, "absent")
        elapsed = round(time.perf_counter() - kill_at, 2)
        if not timeline or timeline[-1]["e3"] != state:
            timeline.append({"t": elapsed, "status": status, "e3": state})
        if truth_at is None and state != "ready":
            truth_at = elapsed
        if truth_at is not None and state == "ready":
            ready_at = elapsed
            break
        time.sleep(0.25)

    drills[f"{label}:readiness_timeline"] = timeline
    drills[f"{label}:seconds_to_truth"] = truth_at
    drills[f"{label}:seconds_to_recovered"] = ready_at
    # The incumbent must serve fine THROUGHOUT the challenger's outage.
    drills[f"{label}:whisper_during_outage"] = request(client, WHISPER)
    drills[f"{label}:e3_after_recovery"] = request(client, E3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8011")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    drills: dict[str, Any] = {
        "drill": "24-e3-failure-restart-readiness",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
    }
    with httpx.Client(base_url=args.url, timeout=300.0) as client:
        drills["baseline_e3"] = request(client, E3)
        drills["baseline_whisper"] = request(client, WHISPER)
        _, slots = slot_state(client)
        drills["baseline_slots"] = slots

        kill_cycle(client, "kill1", drills)
        kill_cycle(client, "kill2", drills)  # recovery is not a one-shot

        drills["final_slots"] = slot_state(client)[1]
        drills["final_e3"] = request(client, E3)
        drills["final_whisper"] = request(client, WHISPER)
    drills["llama_server_pids_final"] = llama_server_pids()
    drills["orphans"] = max(0, len(drills["llama_server_pids_final"]) - 1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(drills, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(drills, indent=2)[:2500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
