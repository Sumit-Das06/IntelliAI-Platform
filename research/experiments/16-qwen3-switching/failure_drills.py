"""Milestone 16 Phase 5: failure/resilience drills against the multi-slot runtime.

Each drill records WHAT ACTUALLY HAPPENED — status, envelope type,
message safety (no internal names, no raw llama.cpp text), slot
isolation — into a JSON the report cites. Destructive by design: the
qwen3 child process is killed mid-session, so this runs LAST in a
serving session, and `--phase post-restart` runs against a fresh boot.
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
QWEN = "qwen3-asr-0.6b"
WHISPER = "whisper-small"
LEAK_MARKERS = ("llama", "gguf", "qwen", "ggml", "whisper", "ctranslate", "faster")


def request(client: httpx.Client, artifact: str, *, language: str | None = "hi") -> dict[str, Any]:
    params: dict[str, Any] = {"model": artifact}
    if language is not None:
        params["language"] = language
    started = time.perf_counter()
    try:
        response = client.post(
            "/v1/transcribe",
            files={"file": (HI_CLIP.name, HI_CLIP.read_bytes(), "audio/flac")},
            data={"params": json.dumps(params)},
        )
        body: dict[str, Any] = response.json()
        message = str(body.get("message", ""))
        return {
            "status": response.status_code,
            "error_type": body.get("type") if response.status_code != 200 else None,
            "message_leaks_internals": any(m in message.lower() for m in LEAK_MARKERS),
            "message": message[:160],
            "client_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    except httpx.HTTPError as exc:
        return {"status": 0, "transport_error": type(exc).__name__}


def llama_server_pids() -> list[int]:
    if sys.platform == "win32":
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
    completed = subprocess.run(
        ["pgrep", "-x", "llama-server"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return [int(line) for line in completed.stdout.split() if line.strip().isdigit()]


def kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603 — the drill IS the kill
            ["taskkill", "/F", "/PID", str(pid)],  # noqa: S607
            capture_output=True,
            timeout=15,
            check=False,
        )
        return
    subprocess.run(  # noqa: S603 — the drill IS the kill
        ["kill", "-9", str(pid)],  # noqa: S607
        capture_output=True,
        timeout=15,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8003")
    parser.add_argument("--phase", choices=["kill", "post-restart"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    drills: dict[str, Any] = {
        "phase": args.phase,
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
    }
    with httpx.Client(base_url=args.url, timeout=300.0) as client:
        if args.phase == "kill":
            drills["baseline_qwen_hi"] = request(client, QWEN)
            drills["baseline_whisper_hi"] = request(client, WHISPER)
            drills["garbage_audio"] = _garbage(client)
            drills["whisper_unsupported_language"] = request(client, WHISPER, language="xx")
            drills["qwen_unmapped_language_hint"] = request(client, QWEN, language="xx")

            pids = llama_server_pids()
            drills["llama_server_pids_before_kill"] = pids
            for pid in pids:
                kill_pid(pid)
            time.sleep(2)
            drills["qwen_after_child_killed"] = request(client, QWEN)
            drills["qwen_after_child_killed_repeat"] = request(client, QWEN)
            # Slot isolation: the incumbent must be untouched by the
            # challenger's death.
            drills["whisper_after_qwen_killed"] = request(client, WHISPER)
            info = client.get("/info")
            drills["info_after_kill"] = {
                "status": info.status_code,
                "still_lists_qwen_slot": QWEN in info.text,
            }
        else:
            drills["qwen_after_restart"] = request(client, QWEN)
            drills["whisper_after_restart"] = request(client, WHISPER)
            drills["llama_server_pids_after_restart"] = llama_server_pids()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if args.out.exists():
        existing = json.loads(args.out.read_text(encoding="utf-8"))
    existing[args.phase] = drills
    args.out.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(drills, indent=2)[:2000])
    print(f"written: {args.out}")
    return 0


def _garbage(client: httpx.Client) -> dict[str, Any]:
    try:
        response = client.post(
            "/v1/transcribe",
            files={"file": ("junk.wav", b"this is not audio at all", "audio/wav")},
            data={"params": json.dumps({"model": QWEN, "language": "hi"})},
        )
        body: dict[str, Any] = response.json()
        message = str(body.get("message", ""))
        return {
            "status": response.status_code,
            "error_type": body.get("type"),
            "message_leaks_internals": any(m in message.lower() for m in LEAK_MARKERS),
            "message": message[:160],
        }
    except httpx.HTTPError as exc:
        return {"status": 0, "transport_error": type(exc).__name__}


if __name__ == "__main__":
    raise SystemExit(main())
