# ruff: noqa: S310 — research script: long Devanagari rows; operator-local URLs
"""M58 Phase 7 — the REALISTIC interference case: exactly ONE correction
(the actual user gesture — ✨ Improve on an earlier transcript) fired
mid-way through a live realtime session, EN and HI. M57 proved the
continuous-hammer worst case; this measures what a real user causes.

    python realtime_single_correction.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
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
HI_100 = (
    "to kal humne client ke saath meeting ki thi aur unko demo bahut pasand aaya lekin "
    "unhone bola ki report thodi late ho gayi hai isliye ab hume agle hafte tak sab kuch "
    "submit karna hai aur uske baad payment aayega phir maine bola ki theek hai hum "
    "poori koshish karenge lekin testing ke liye thoda aur time chahiye kyunki naya "
    "feature abhi stable nahi hai aur mobile par bhi check karna baki hai"
)

KEYS = ("first_partial_at_s", "partial_gap_p50_s", "partial_gap_p95_s", "finalization_ms")


def one_correction(delay_s: float, slot: dict) -> None:
    time.sleep(delay_s)
    payload = json.dumps({"text": HI_100, "language": "hi"}).encode("utf-8")
    request = urllib.request.Request(
        CORRECTION_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response.read()
        slot["status"] = 200
    except urllib.error.HTTPError as exc:
        slot["status"] = exc.code
    except Exception as exc:
        slot["status"] = f"error: {exc}"
    slot["ms"] = round((time.perf_counter() - started) * 1000, 1)


async def measure(name: str, wav: Path, language: str, with_correction: bool) -> dict:
    slot: dict = {}
    thread = None
    if with_correction:
        # Fire once, ~10 s into the ~30 s session — mid-decode interference.
        thread = threading.Thread(target=one_correction, args=(10.0, slot), daemon=True)
        thread.start()
    row = await client.run(WS, str(wav), language, "realtime", f"m58-{name}.json")
    if thread is not None:
        thread.join(timeout=125)
    summary = {k: row[k] for k in KEYS}
    if with_correction:
        summary["correction"] = slot
    print(name, summary, flush=True)
    return summary


async def main() -> None:
    result: dict = {}
    cases = (
        ("en_idle", SCRATCH / "m52clips" / "boss30.wav", "en", False),
        ("hi_idle", SCRATCH / "m52hclips" / "real30s.wav", "hi", False),
        ("en_one_correction", SCRATCH / "m52clips" / "boss30.wav", "en", True),
        ("hi_one_correction", SCRATCH / "m52hclips" / "real30s.wav", "hi", True),
    )
    for name, wav, language, with_correction in cases:
        result[name] = await measure(name, wav, language, with_correction)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "realtime-single-correction.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("realtime-single-correction.json written")


if __name__ == "__main__":
    asyncio.run(main())
