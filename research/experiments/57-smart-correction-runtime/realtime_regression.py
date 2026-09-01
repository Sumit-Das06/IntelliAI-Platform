"""M57 Phase 39 — realtime STT while Smart Correction hammers its own
llama-server: realtime must not materially regress.

    python realtime_regression.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
sys.path.insert(0, str(HERE.parents[1] / "experiments" / "55-production-gpu-readiness"))
import rt55_client as client  # noqa: E402 — the M55 battery harness

SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()
WS = "ws://127.0.0.1:8000/v1/audio/realtime"
CORRECTION_URL = "http://127.0.0.1:8000/v1/text/corrections"
HI_TEXT = (
    "to kal humne client ke saath meeting ki thi aur unko demo bahut pasand aaya lekin "
    "unhone bola ki report thodi late ho gayi hai isliye ab hume agle hafte tak sab kuch "
    "submit karna hai aur uske baad payment aayega "
) * 8


def correction_hammer(stop: threading.Event, counter: list[int]) -> None:
    words = HI_TEXT.split()[:250]
    while not stop.is_set():
        payload = json.dumps({"text": " ".join(words), "language": "hi"}).encode("utf-8")
        request = urllib.request.Request(
            CORRECTION_URL,
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
                response.read()
            counter[0] += 1
        except Exception:
            break


async def main() -> None:
    result: dict = {}
    # Idle reference (same day, same stack).
    for name, wav, language in (
        ("en_idle", SCRATCH / "m52clips" / "boss30.wav", "en"),
        ("hi_idle", SCRATCH / "m52hclips" / "real30s.wav", "hi"),
    ):
        row = await client.run(WS, str(wav), language, "realtime", f"m57-{name}.json")
        result[name] = {
            k: row[k]
            for k in (
                "first_partial_at_s",
                "partial_gap_p50_s",
                "partial_gap_p95_s",
                "finalization_ms",
            )
        }
        print(name, result[name], flush=True)
    # Under continuous correction load.
    stop = threading.Event()
    done: list[int] = [0]
    thread = threading.Thread(target=correction_hammer, args=(stop, done), daemon=True)
    thread.start()
    try:
        for name, wav, language in (
            ("en_under_correction", SCRATCH / "m52clips" / "boss30.wav", "en"),
            ("hi_under_correction", SCRATCH / "m52hclips" / "real30s.wav", "hi"),
        ):
            row = await client.run(WS, str(wav), language, "realtime", f"m57-{name}.json")
            result[name] = {
                k: row[k]
                for k in (
                    "first_partial_at_s",
                    "partial_gap_p50_s",
                    "partial_gap_p95_s",
                    "finalization_ms",
                )
            }
            print(name, result[name], flush=True)
    finally:
        stop.set()
        thread.join(timeout=130)
    result["correction_jobs_completed_during_sessions"] = done[0]
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "realtime-regression.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("realtime-regression.json written")


if __name__ == "__main__":
    asyncio.run(main())
