"""M19 Phase 14: long audio through the REAL product path, locally.

Every request goes through POST /v1/audio/transcriptions on a REAL
staging gateway (registry profile `staging`, hi→qwen3 route) backed by
the REAL multi-slot runtime with the M19 chunked engine — no research
endpoint, no fakes. The API key arrives via INTELLIAI_M19_KEY and never
enters this file or its output; response bodies are leak-scanned before
being summarized.

Drills:
  1. 300 s Hindi, contribution ON, verbose_json — one request, one
     usage event (+300 s), one sample, multi-window segments whose
     texts concatenate to `text`, correction lifecycle on the sample.
  2. 600 s Hindi, contribution OFF — one usage event (+600 s), NO
     sample, complete transcript.
  3. Kill llama-server DURING window 2 of a 600 s request, and again
     during window 4: at most one retry; recovery or clean whole-request
     failure; never a partial transcript; failed = amount 0, no sample.
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


def leak_scan(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in LEAK_MARKERS if marker in lowered]


class Drills:
    def __init__(self, base_url: str, runtime_url: str, key: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=500.0)
        self.runtime_url = runtime_url
        self.key = key
        self.record: dict[str, Any] = {}

    def transcribe(
        self,
        wav_path: Path,
        *,
        response_format: str | None = None,
        contribution: str | None = None,
    ) -> tuple[httpx.Response, float]:
        headers = {"Authorization": f"Bearer {self.key}", "X-IntelliAI-Client": "m19-drill/1.0"}
        if contribution is not None:
            headers["X-IntelliAI-Contribution"] = contribution
        data = {"model": "intelliai-stt", "language": "hi"}
        if response_format is not None:
            data["response_format"] = response_format
        started = time.perf_counter()
        response = self.client.post(
            "/v1/audio/transcriptions",
            headers=headers,
            files={"file": (wav_path.name, wav_path.read_bytes(), "audio/wav")},
            data=data,
        )
        return response, round(time.perf_counter() - started, 1)

    def usage_totals(self) -> dict[str, Any]:
        """The ledger's own summary: requests, speech_minutes, outcomes."""
        response = self.client.get(
            "/v1/usage/summary", headers={"Authorization": f"Bearer {self.key}"}
        )
        response.raise_for_status()
        totals: dict[str, Any] = response.json()["totals"]
        return totals

    @staticmethod
    def usage_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        return {
            "requests": after["requests"] - before["requests"],
            "speech_seconds": round((after["speech_minutes"] - before["speech_minutes"]) * 60, 1),
            "failed": after.get("outcomes", {}).get("failed", 0)
            - before.get("outcomes", {}).get("failed", 0),
        }

    def correction(self, sample_id: str, corrected: str) -> httpx.Response:
        return self.client.post(
            f"/v1/audio/transcriptions/{sample_id}/correction",
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
            content=json.dumps({"corrected_text": corrected}),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--runtime-url", default="http://127.0.0.1:8011")
    parser.add_argument(
        "--audio-dir", type=Path, required=True, help="dir with concat-300s.wav / concat-600s.wav"
    )
    parser.add_argument(
        "--kill-at",
        default="70,215",
        help="seconds into the 600 s request to kill the child (drill 3 runs once per value)",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ["INTELLIAI_M19_KEY"]

    d = Drills(args.base_url, args.runtime_url, key)
    d.record["drill"] = "19-long-audio-staging"
    d.record["run_at"] = datetime.datetime.now(tz=datetime.UTC).isoformat()

    wav300 = args.audio_dir / "concat-300s.wav"
    wav600 = args.audio_dir / "concat-600s.wav"

    # ── Drill 1: 300 s, contribution ON, verbose_json ────────────────────
    usage_before = d.usage_totals()
    response, elapsed = d.transcribe(wav300, response_format="verbose_json", contribution="on")
    body = response.json() if response.status_code == 200 else {}
    segments = body.get("segments", [])
    joined = " ".join(s.get("text", "") for s in segments)
    sample_id = response.headers.get("X-IntelliAI-Sample")
    d.record["hindi_300s_verbose"] = {
        "status": response.status_code,
        "elapsed_seconds": elapsed,
        "duration_reported": body.get("duration"),
        "language": body.get("language"),
        "text_chars": len(body.get("text", "")),
        "segments": len(segments),
        "segment_spans": [[s.get("start"), s.get("end")] for s in segments],
        "segments_join_equals_text": joined == body.get("text", ""),
        "sample_header_present": bool(sample_id),
        "usage_delta": d.usage_delta(usage_before, d.usage_totals()),
        "leaks": leak_scan(response.text),
    }

    # ── Correction lifecycle on the 300 s sample ─────────────────────────
    if sample_id:
        correction = d.correction(sample_id, body.get("text", "")[:2000] + " [सुधार]")
        d.record["correction_300s"] = {
            "status": correction.status_code,
            "leaks": leak_scan(correction.text),
        }

    # ── Drill 2: 600 s, contribution OFF, plain json ─────────────────────
    usage_before = d.usage_totals()
    response, elapsed = d.transcribe(wav600, contribution="off")
    body = response.json() if response.status_code == 200 else {}
    d.record["hindi_600s_no_contribution"] = {
        "status": response.status_code,
        "elapsed_seconds": elapsed,
        "text_chars": len(body.get("text", "")),
        "sample_header_present": bool(response.headers.get("X-IntelliAI-Sample")),
        "usage_delta": d.usage_delta(usage_before, d.usage_totals()),
        "leaks": leak_scan(response.text),
    }

    # ── Drill 3: kill the child mid-request (per kill-at offset) ─────────
    def run_request(outcome: dict[str, Any]) -> None:
        response, elapsed = d.transcribe(wav600, contribution="on")
        outcome["status"] = response.status_code
        outcome["elapsed_seconds"] = elapsed
        outcome["leaks"] = leak_scan(response.text)
        if response.status_code == 200:
            outcome["text_chars"] = len(response.json().get("text", ""))
        else:
            outcome["error_type"] = (
                response.json().get("error", {}).get("type", "") if response.text else ""
            )
            outcome["partial_text_present"] = '"text"' in response.text
        outcome["sample_header_present"] = bool(response.headers.get("X-IntelliAI-Sample"))

    for kill_at in (float(x) for x in args.kill_at.split(",")):
        usage_before = d.usage_totals()
        outcome: dict[str, Any] = {}
        worker = threading.Thread(target=run_request, args=(outcome,))
        worker.start()
        time.sleep(kill_at)
        pids = llama_server_pids()
        for pid in pids:
            kill_pid(pid)
        worker.join(timeout=520)
        d.record[f"kill_at_{int(kill_at)}s"] = {
            **outcome,
            "pids_killed": pids,
            "usage_delta": d.usage_delta(usage_before, d.usage_totals()),
        }
        # Wait for the supervisor to restore the slot before the next drill.
        deadline = time.monotonic() + 180
        recovered = False
        while time.monotonic() < deadline:
            ready = httpx.get(f"{args.runtime_url}/health/ready", timeout=5.0)
            if ready.status_code == 200 and ready.json().get("status") == "ready":
                recovered = True
                break
            time.sleep(2.0)
        d.record[f"kill_at_{int(kill_at)}s"]["runtime_recovered_after"] = recovered

    # ── A clean request after the drills proves the deployment healed ────
    response, elapsed = d.transcribe(wav300, contribution="off")
    d.record["hindi_300s_after_drills"] = {
        "status": response.status_code,
        "elapsed_seconds": elapsed,
        "text_chars": len(response.json().get("text", "")) if response.status_code == 200 else 0,
        "leaks": leak_scan(response.text),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(d.record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(d.record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
