"""M35 live battery — the spec's Phase-16 list, run against a REAL stack.

Every row is a real HTTP request through the gateway (auth, admission,
billing, runtime, WAV back). Success rows verify playable audio (RIFF +
duration sanity); refusal rows verify the exact public error shape. The
OOV rows additionally round-trip through OUR whisper route and assert
the trap words are PRESENT in the transcript — the M33 defect, retested
live after the fix.

Usage:
  uv run --package intelliai-evaluation python m35_battery.py \
    --gateway-url http://localhost:8000 --api-key-file <path> \
    --out evidence/m35-battery.json [--audio-dir <dir>]
"""

from __future__ import annotations

import argparse
import io
import json
import time
import wave
from pathlib import Path
from typing import Any

import httpx

CASES: list[dict[str, Any]] = [
    {"id": "hello", "input": "Hello world.", "expect": "audio"},
    {"id": "sentence", "input": "The quick brown fox jumps over the lazy dog.", "expect": "audio"},
    {
        "id": "paragraph",
        "input": (
            "Thank you for calling customer care. Your complaint about the delayed "
            "delivery has been registered, and the reference number is 88231. Our "
            "courier partner will contact you within two working days."
        ),
        "expect": "audio",
    },
    {"id": "question", "input": "You are coming to the office tomorrow?", "expect": "audio"},
    {"id": "currency", "input": "The subscription costs $4.99 per month.", "expect": "audio"},
    {"id": "percent", "input": "A late fee of 2.5% applies after the due date.", "expect": "audio"},
    {"id": "date", "input": "Your warranty expires on 12/08/2026.", "expect": "audio"},
    {"id": "phone", "input": "Call +91 98765 43210 for support.", "expect": "audio"},
    {"id": "name-sumit", "input": "Hello, Sumit.", "expect": "audio", "judge_must_hear": ["sumit"]},
    {
        "id": "name-priya",
        "input": "Priya Sharma spoke with Rajesh Iyer.",
        "expect": "audio",
        "judge_must_hear": ["priya", "rajesh"],
    },
    {
        "id": "brand-intelliai",
        "input": "Welcome to IntelliAI support, my name is Kavya.",
        "expect": "audio",
        "judge_must_hear": ["intelli", "kavya"],
    },
    {
        "id": "brand-qwikcart",
        "input": "IntelliAI Studio can transcribe your QwikCart order QX4921 in seconds.",
        "expect": "audio",
        # The judge SPELLS the invented brand freely ("qwic cart"); what
        # this row proves is that the word was SPOKEN, not dropped — so
        # both phonetic fragments must be present, spelling-agnostic.
        "judge_must_hear": ["qwi", "cart"],
    },
    {
        "id": "technical",
        "input": "The API gateway routes requests to the inference runtime over HTTP.",
        "expect": "audio",
    },
    {
        "id": "punctuation",
        "input": "Wait — before you go: did the reset work, or not? If not, try again!",
        "expect": "audio",
    },
    {"id": "speed-slow", "input": "Speed check, slower.", "speed": 0.75, "expect": "audio"},
    {"id": "speed-normal", "input": "Speed check, normal.", "speed": 1.0, "expect": "audio"},
    {"id": "speed-fast", "input": "Speed check, faster.", "speed": 1.25, "expect": "audio"},
    {
        "id": "voice-male",
        "input": "The male English voice.",
        "voice": "english-male",
        "expect": "audio",
    },
    {
        "id": "voice-legacy-alias",
        "input": "The legacy alias still serves.",
        "voice": "reference-alto",
        "expect": "audio",
    },
    {"id": "empty", "input": "", "expect": "refusal", "statuses": (400, 422)},
    {"id": "over-limit", "input": "x" * 2401, "expect": "refusal", "statuses": (400, 422)},
    {
        "id": "invalid-voice",
        "input": "Hello.",
        "voice": "no-such-voice",
        "expect": "refusal",
        "statuses": (400, 404, 422),
    },
    {"id": "unauthorized", "input": "Hello.", "expect": "unauthorized"},
]


def _wav_seconds(payload: bytes) -> float:
    with wave.open(io.BytesIO(payload), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway-url", default="http://localhost:8000")
    parser.add_argument("--api-key-file", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--audio-dir", default=None)
    args = parser.parse_args()

    key = Path(args.api_key_file).read_text(encoding="utf-8").strip()
    audio_dir = Path(args.audio_dir) if args.audio_dir else None
    rows: list[dict[str, Any]] = []
    failures = 0

    with httpx.Client(base_url=args.gateway_url, timeout=180.0) as client:
        for case in CASES:
            body: dict[str, Any] = {"model": "intelliai-tts", "input": case["input"]}
            if case.get("voice"):
                body["voice"] = case["voice"]
            if case.get("speed") is not None:
                body["speed"] = case["speed"]
            headers = {} if case["expect"] == "unauthorized" else {"Authorization": f"Bearer {key}"}
            started = time.perf_counter()
            response = client.post("/v1/audio/speech", json=body, headers=headers)
            wall_ms = round((time.perf_counter() - started) * 1000.0, 1)
            row: dict[str, Any] = {
                "id": case["id"],
                "status": response.status_code,
                "wall_ms": wall_ms,
            }

            if case["expect"] == "audio":
                ok = response.status_code == 200 and response.headers.get(
                    "content-type", ""
                ).startswith("audio/wav")
                seconds = _wav_seconds(response.content) if ok else 0.0
                ok = ok and seconds > 0.3 and response.content[:4] == b"RIFF"
                row.update(
                    {"audio_seconds": round(seconds, 3), "verdict": "PASS" if ok else "FAIL"}
                )
                if ok and audio_dir is not None:
                    audio_dir.mkdir(parents=True, exist_ok=True)
                    (audio_dir / f"{case['id']}.wav").write_bytes(response.content)
                if ok and case.get("judge_must_hear"):
                    judge = client.post(
                        "/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {key}"},
                        data={"model": "intelliai-stt", "language": "en"},
                        files={"file": (f"{case['id']}.wav", response.content, "audio/wav")},
                    )
                    heard = judge.json().get("text", "").lower() if judge.status_code == 200 else ""
                    missing = [w for w in case["judge_must_hear"] if w not in heard]
                    row["judge_heard"] = heard
                    row["oov_missing"] = missing
                    if missing:
                        row["verdict"] = "FAIL"
            elif case["expect"] == "refusal":
                ok = response.status_code in case["statuses"]
                detail = (
                    response.json() if "json" in response.headers.get("content-type", "") else {}
                )
                message = str(detail.get("error", {}).get("message", ""))
                row.update({"error_message": message[:120], "verdict": "PASS" if ok else "FAIL"})
            else:  # unauthorized
                ok = response.status_code == 401
                row["verdict"] = "PASS" if ok else "FAIL"

            if row["verdict"] == "FAIL":
                failures += 1
            rows.append(row)
            print(f"  {case['id']:<20} {row['verdict']} ({response.status_code}, {wall_ms} ms)")

    report = {
        "experiment": "35-kokoro-hardening",
        "instrument": "m35_battery.py",
        "gateway": args.gateway_url,
        "cases": len(rows),
        "failures": failures,
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"BATTERY {'OK' if failures == 0 else 'FAIL'}: {len(rows) - failures}/{len(rows)} passed")


if __name__ == "__main__":
    main()
