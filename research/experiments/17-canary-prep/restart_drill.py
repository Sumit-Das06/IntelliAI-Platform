"""Milestone 17 Phases 2+3, live: readiness truth + supervised recovery.

Against a REAL runtime hosting the qwen3 slot: kill the llama-server
child, then watch /health/ready tell the truth (not_ready for a default
slot / degraded for a specialist), watch the supervisor bring the child
back within its bounded backoff, and prove serving works again — with
timings for every transition and orphan accounting at the end.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "16-qwen3-switching"))
from failure_drills import kill_pid, llama_server_pids

HI_CLIP = Path("ml/datasets/data/indicvoices/hindi/valid/indicvoices-hindi-valid-0-001287.flac")


def ready_body(client: httpx.Client) -> tuple[int, dict[str, Any]]:
    response = client.get("/health/ready")
    return response.status_code, response.json()


def transcribe_status(client: httpx.Client) -> int:
    response = client.post(
        "/v1/transcribe",
        files={"file": (HI_CLIP.name, HI_CLIP.read_bytes(), "audio/flac")},
        data={"params": json.dumps({"language": "hi"})},
    )
    return response.status_code


def wait_for(client: httpx.Client, predicate: Any, timeout: float) -> float | None:
    """Seconds until /health/ready satisfies predicate, or None."""
    started = time.perf_counter()
    while time.perf_counter() - started < timeout:
        code, body = ready_body(client)
        if predicate(code, body):
            return round(time.perf_counter() - started, 2)
        time.sleep(0.25)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8004")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    record: dict[str, Any] = {
        "drill": "17-supervised-restart-live",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "platform": sys.platform,
    }
    with httpx.Client(base_url=args.url, timeout=600.0) as client:
        code, body = ready_body(client)
        record["baseline_ready"] = {"code": code, "body": body}
        record["baseline_transcribe_status"] = transcribe_status(client)

        pids = llama_server_pids()
        record["pids_before_kill"] = pids
        for pid in pids:
            kill_pid(pid)
        killed_at = time.perf_counter()

        # 1) Readiness must flip to the truth within the monitor interval.
        record["seconds_until_unready"] = wait_for(
            client, lambda c, b: c == 503 or b.get("status") != "ready", timeout=15.0
        )
        code, body = ready_body(client)
        record["ready_during_outage"] = {"code": code, "body": body}

        # 2) A request during the outage must refuse truthfully (503-class
        # envelope), never hang.
        started = time.perf_counter()
        status = transcribe_status(client)
        record["transcribe_during_outage"] = {
            "status": status,
            "bounded_seconds": round(time.perf_counter() - started, 2),
        }

        # 3) The supervisor's bounded backoff must bring the slot back.
        record["seconds_until_ready_again"] = wait_for(
            client, lambda c, b: c == 200 and b.get("status") == "ready", timeout=120.0
        )
        record["total_outage_seconds"] = round(time.perf_counter() - killed_at, 2)
        record["transcribe_after_recovery_status"] = transcribe_status(client)
        record["pids_after_recovery"] = llama_server_pids()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
