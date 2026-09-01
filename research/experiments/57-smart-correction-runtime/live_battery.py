"""M57 live battery — the spec's Phase 19-23 cases + latency by length,
through the REAL authenticated gateway endpoint.

    python live_battery.py
"""

from __future__ import annotations

import json
import re
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
KEY = (SCRATCH / "m24-key.txt").read_text(encoding="utf-8").strip()
URL = "http://127.0.0.1:8000/v1/text/corrections"


def correct(text: str, language: str) -> tuple[str | None, float, int]:
    payload = json.dumps({"text": text, "language": language}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            body = json.loads(response.read())
        return str(body["corrected_text"]), round((time.perf_counter() - started) * 1000, 1), 200
    except urllib.error.HTTPError as exc:
        return None, round((time.perf_counter() - started) * 1000, 1), exc.code


EN_CASES = [
    ("i going office yesterday", "grammar"),
    ("he don't know where it is", "grammar"),
    ("i have went there yesterday", "tense"),
    ("i want to know what is status of my order", "articles"),
    ("i i want to to go home now", "repetition"),
    ("I am going to the office tomorrow.", "already_correct"),
    ("I went to the office.", "hallucination_bait"),
    ("i need to meat tomorrow", "ambiguous"),
]
HI_CASES = [
    ("mujhe kal office jana tha but main nahi ja saka", "roman_hindi"),
    ("मेरा बहन कल आएगा", "gender"),
    ("maine client ko email kar diya hai reply ka wait hai", "hinglish"),
    ("मैं कल सुबह दिल्ली जा रहा हूँ।", "already_correct"),
]
ENTITY_CASES = [
    ("please tell sumit from intelliai about the qwikcart deal", "en"),
    ("the amount is ₹12,500 due on 12 August 2026", "en"),
    ("call me at +91-9876543210 or mail test@example.com", "en"),
    ("we deploy version 2.5 on kubernetes at example.com", "en"),
]

EN_BASE = (
    "so basically we was working on the new dashboard since last week and the client have "
    "asked for two more changes which i think we can finished by friday the main issue is "
    "the login page it dont load properly on mobile and the team is looking into it now "
)
HI_BASE = (
    "to kal humne client ke saath meeting ki thi aur unko demo bahut pasand aaya lekin "
    "unhone bola ki report thodi late ho gayi hai isliye ab hume agle hafte tak sab kuch "
    "submit karna hai aur uske baad payment aayega "
)


def main() -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results: dict = {"english": [], "hindi": [], "entities": []}
    devanagari = re.compile(r"[ऀ-ॿ]")
    for text, category in EN_CASES:
        out, ms, status = correct(text, "en")
        results["english"].append(
            {
                "category": category,
                "in": text,
                "out": out,
                "ms": ms,
                "status": status,
                "latin_only": out is not None and not devanagari.search(out),
            }
        )
        print("EN", category, ms, "ms ->", (out or "")[:70])
    for text, category in HI_CASES:
        out, ms, status = correct(text, "hi")
        results["hindi"].append(
            {
                "category": category,
                "in": text,
                "out": out,
                "ms": ms,
                "status": status,
                "devanagari": out is not None and bool(devanagari.search(out)),
            }
        )
        print("HI", category, ms, "ms ->", (out or "")[:70])
    for text, language in ENTITY_CASES:
        out, ms, status = correct(text, language)
        results["entities"].append({"in": text, "out": out, "ms": ms, "status": status})
        print("ENT", ms, "ms ->", (out or "")[:80])

    # Latency by length through the FULL stack.
    lat: dict = {}
    for language, base in (("en", EN_BASE), ("hi", HI_BASE)):
        for count in (20, 50, 100, 250):
            words = (base * 20).split()[:count]
            times = []
            for _ in range(3):
                _, ms, status = correct(" ".join(words), language)
                if status == 200:
                    times.append(ms)
            lat[f"{language}_{count}w"] = {
                "p50_ms": round(statistics.median(times), 1) if times else None,
                "max_ms": max(times) if times else None,
            }
            print("LAT", language, count, lat[f"{language}_{count}w"])
    results["latency_by_length_full_stack"] = lat

    (EVIDENCE / "live-battery.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("live-battery.json written")


if __name__ == "__main__":
    main()
