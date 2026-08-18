"""M25 Phase 13: failure / restart / readiness — INSIDE the Docker stack.

The M24 drill proved the M17 supervision on the native runtime; this
one proves the same laws hold in the production-shaped container: the
llama-server child dies INSIDE the stt container (killed via /proc —
the slim image ships no procps), readiness tells the truth, the
supervisor restarts the child bounded, whisper never blinks, a second
kill behaves identically, and the container ends with exactly one
llama-server process.
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

HI_CLIP = Path("ml/datasets/data/indicvoices/hindi/valid/indicvoices-hindi-valid-0-001287.flac")
E3 = "qwen3-asr-0.6b-hi-ft-e3"
WHISPER = "whisper-small"
LEAK_MARKERS = ("llama", "gguf", "qwen", "ggml", "whisper", "ctranslate", "faster", "e3")
COMPOSE = ["docker", "compose", "-f", "docker-compose.yml", "-f", "infra/compose/local-prod.yml"]

#: Pure-sh /proc scan: list llama-server PIDs inside the container.
LIST_SH = (
    'for p in /proc/[0-9]*; do grep -q "^llama-server" "$p/comm" 2>/dev/null '
    '&& echo "${p#/proc/}"; done'
)
KILL_SH = (
    'for p in /proc/[0-9]*; do grep -q "^llama-server" "$p/comm" 2>/dev/null '
    '&& kill -9 "${p#/proc/}"; done; true'
)


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


def slot_state(client: httpx.Client) -> dict[str, str]:
    response = client.get("/health/ready")
    try:
        return dict(response.json().get("slots", {}))
    except json.JSONDecodeError:
        return {}


def in_container_pids() -> list[str]:
    completed = subprocess.run(  # noqa: S603 — fixed compose exec command
        [*COMPOSE, "exec", "-T", "stt-runtime", "sh", "-c", LIST_SH],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip().isdigit()]


def kill_cycle(client: httpx.Client, label: str, drills: dict[str, Any]) -> None:
    drills[f"{label}:pids_before_kill"] = in_container_pids()
    kill_at = time.perf_counter()
    subprocess.run(  # noqa: S603 — the drill IS the kill
        [*COMPOSE, "exec", "-T", "stt-runtime", "sh", "-c", KILL_SH],
        capture_output=True,
        timeout=30,
        check=False,
    )
    truth_at: float | None = None
    ready_at: float | None = None
    timeline: list[dict[str, Any]] = []
    deadline = kill_at + 180.0
    while time.perf_counter() < deadline:
        state = slot_state(client).get(E3, "absent")
        elapsed = round(time.perf_counter() - kill_at, 2)
        if not timeline or timeline[-1]["e3"] != state:
            timeline.append({"t": elapsed, "e3": state})
        if truth_at is None and state != "ready":
            truth_at = elapsed
        if truth_at is not None and state == "ready":
            ready_at = elapsed
            break
        time.sleep(0.25)
    drills[f"{label}:readiness_timeline"] = timeline
    drills[f"{label}:seconds_to_truth"] = truth_at
    drills[f"{label}:seconds_to_recovered"] = ready_at
    drills[f"{label}:whisper_during_outage"] = request(client, WHISPER)
    drills[f"{label}:e3_after_recovery"] = request(client, E3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    drills: dict[str, Any] = {
        "drill": "25-e3-failure-restart-in-container",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
    }
    with httpx.Client(base_url=args.url, timeout=300.0) as client:
        drills["baseline_e3"] = request(client, E3)
        drills["baseline_whisper"] = request(client, WHISPER)
        drills["baseline_slots"] = slot_state(client)
        kill_cycle(client, "kill1", drills)
        kill_cycle(client, "kill2", drills)
        drills["final_slots"] = slot_state(client)
        drills["final_e3"] = request(client, E3)
        drills["final_whisper"] = request(client, WHISPER)
    drills["llama_pids_final"] = in_container_pids()
    drills["orphans"] = max(0, len(drills["llama_pids_final"]) - 1)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(drills, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(drills, indent=2)[:2200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
