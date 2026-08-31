"""Realtime STT alert checker (M55) — the M54 §17 thresholds, runnable.

    uv run python tools/ops/realtime_alerts.py --log <runtime-log> \
        [--ready-url http://127.0.0.1:8003/health/ready] [--window-lines 5000]

Prints one ``ALERT <code>: <detail>`` line per firing condition and
exits 1 when anything fired (0 when clean) — wire it into cron/CI or
any ops channel that can run a command. Normal user cancellation
produces NO log signature and therefore can never alert.

Thresholds (M54-calibrated, staging):
    stall            hot_decode max > 15 s in any session summary
    repetition       any realtime_repetition_trimmed
    decode_failures  >= 5 realtime_decode_failed lines in the window
    backend_down     realtime_backend_degraded / qwen3_external_backend_unreachable
    slow_punctuation punctuation_ms > 5 s in any session summary
    not_ready        readiness endpoint not answering status=ready
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

STALL_MS = 15_000.0
PUNCT_MS = 5_000.0
DECODE_FAILURE_LIMIT = 5


def check_log(lines: list[str]) -> list[str]:
    alerts: list[str] = []
    decode_failures = 0
    for line in lines:
        start = line.find("{")
        if start < 0:
            continue
        try:
            row = json.loads(line[start:])
        except json.JSONDecodeError:
            continue
        event = row.get("event", "")
        if event == "realtime_decode_failed":
            decode_failures += 1
        elif event == "realtime_repetition_trimmed":
            alerts.append(
                f"ALERT repetition: session {row.get('session')} trimmed "
                f"{row.get('removed_words')} words"
            )
        elif event in ("realtime_backend_degraded", "qwen3_external_backend_unreachable"):
            alerts.append(f"ALERT backend_down: {event}")
        elif event == "realtime_session_completed":
            metrics = row.get("metrics", {})
            decode_max = (metrics.get("hot_decode") or {}).get("max_ms", 0.0)
            if decode_max and decode_max > STALL_MS:
                alerts.append(
                    f"ALERT stall: session {row.get('session')} hot_decode max {decode_max} ms"
                )
            punct = metrics.get("punctuation_ms", 0.0)
            if punct and punct > PUNCT_MS:
                alerts.append(f"ALERT slow_punctuation: session {row.get('session')} {punct} ms")
    if decode_failures >= DECODE_FAILURE_LIMIT:
        alerts.append(f"ALERT decode_failures: {decode_failures} in window")
    return alerts


def check_ready(url: str) -> list[str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 — ops-configured URL
            payload = json.loads(response.read())
    except Exception as exc:
        return [f"ALERT not_ready: readiness unreachable ({type(exc).__name__})"]
    if payload.get("status") != "ready":
        return [f"ALERT not_ready: status={payload.get('status')}"]
    if payload.get("realtime") == "degraded":
        return ["ALERT backend_down: readiness reports realtime degraded"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--ready-url", default="")
    parser.add_argument("--window-lines", type=int, default=5000)
    args = parser.parse_args()
    alerts: list[str] = []
    if args.log is not None and args.log.exists():
        lines = args.log.read_text(encoding="utf-8", errors="replace").splitlines()
        alerts.extend(check_log(lines[-args.window_lines :]))
    if args.ready_url:
        alerts.extend(check_ready(args.ready_url))
    for alert in alerts:
        print(alert)  # noqa: T201 — the alert channel IS stdout
    if not alerts:
        print("OK: no realtime alerts")  # noqa: T201
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
