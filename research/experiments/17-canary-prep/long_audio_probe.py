"""Milestone 17 Phase 6: long-audio behavior of the qwen3-asr engine.

NOT ledger evidence. Probes 60/120/300/600-second inputs (concatenated
frozen-eval clips — public audio, speech-dense) through the runtime's
real product path and records what actually happens at ctx=4096:
latency, RSS growth, output completeness, degeneration, and where the
usable ceiling is. The frozen benchmark is untouched; no reference
scoring happens here because concatenation invalidates the references —
completeness is judged structurally (output density vs the short-clip
norm, tail repetition, truncation signature).
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx


def rss_mib_of(process_name: str) -> float | None:
    if sys.platform == "win32":
        return None  # windows sampling lives in the PS sidecars
    completed = subprocess.run(  # noqa: S603 — fixed argv, probe tooling
        ["pgrep", "-x", process_name],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    total_kib = 0
    for pid in completed.stdout.split():
        status = Path(f"/proc/{pid}/status")
        if status.exists():
            match = re.search(r"VmRSS:\s+(\d+) kB", status.read_text())
            if match:
                total_kib += int(match.group(1))
    return round(total_kib / 1024, 1) if total_kib else None


def tail_repetition_ratio(text: str, window: int = 40) -> float:
    """How much of the transcript's tail is one repeated shingle.

    The degenerate-decode signature measured in E1/E1b was unbounded
    repetition; a healthy transcript scores near 0.
    """
    if len(text) < window * 3:
        return 0.0
    tail = text[-window * 10 :]
    shingle = tail[-window:]
    occurrences = tail.count(shingle)
    return round((occurrences - 1) * window / max(len(tail), 1), 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8004")
    parser.add_argument("--clips-dir", type=Path, required=True, help="dir of NNNs.wav probes")
    parser.add_argument("--durations", default="60,120,300,600")
    parser.add_argument("--short-clip", type=Path, required=True, help="short reference clip")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.url, timeout=1800.0) as client:
        # Short-clip norm: output density (chars per audio second) that a
        # healthy decode produces on this corpus.
        short = args.short_clip.read_bytes()
        response = client.post(
            "/v1/transcribe",
            files={"file": (args.short_clip.name, short, "audio/wav")},
            data={"params": json.dumps({"language": "hi"})},
        )
        response.raise_for_status()
        body = response.json()
        norm_chars_per_second = len(body["output"]["text"]) / body["output"]["duration_seconds"]

        for seconds in (int(s) for s in args.durations.split(",")):
            wav = args.clips_dir / f"{seconds}s.wav"
            started = time.perf_counter()
            try:
                response = client.post(
                    "/v1/transcribe",
                    files={"file": (wav.name, wav.read_bytes(), "audio/wav")},
                    data={"params": json.dumps({"language": "hi"})},
                )
                wall = time.perf_counter() - started
                ok = response.status_code == 200
                body = response.json()
                text = body["output"]["text"] if ok else ""
                duration = body["output"]["duration_seconds"] if ok else float(seconds)
                density = len(text) / duration if duration else 0.0
                rows.append(
                    {
                        "input_seconds": seconds,
                        "status": response.status_code,
                        "error_type": None if ok else body.get("type"),
                        "wall_seconds": round(wall, 1),
                        "rtf": round(wall / seconds, 3),
                        "output_chars": len(text),
                        "chars_per_second": round(density, 2),
                        "completeness_vs_norm": round(density / norm_chars_per_second, 3),
                        "tail_repetition_ratio": tail_repetition_ratio(text),
                        "segments": len(body["output"].get("segments", [])) if ok else 0,
                        "llama_server_rss_mib": rss_mib_of("llama-server"),
                        "text_tail": text[-160:],
                    }
                )
            except httpx.HTTPError as exc:
                rows.append(
                    {
                        "input_seconds": seconds,
                        "status": 0,
                        "transport_error": type(exc).__name__,
                        "wall_seconds": round(time.perf_counter() - started, 1),
                    }
                )

    payload = {
        "probe": "17-long-audio-ctx4096",
        "NOT_LEDGER_EVIDENCE": (
            "structural completeness probe on concatenated public audio; "
            "references invalid by construction, no accuracy claim"
        ),
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "norm_chars_per_second": round(norm_chars_per_second, 2),
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False, indent=2)[:3000])
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
