"""M56 Phase 16/19 — latency by input length against one server.

python latency_probe.py --url http://127.0.0.1:8899 --label gpu-4b --out <out.json>
"""

# ruff: noqa: T201 — research scripts report via stdout

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from run_correction import correct

EN_BASE = (
    "so basically we was working on the new dashboard since last week and the client have "
    "asked for two more changes which i think we can finished by friday if nothing else "
    "comes up the main issue is the login page it dont load properly on mobile and uh the "
    "team is looking into it right now "
)
HI_BASE = (
    "to kal humne client ke saath meeting ki thi aur unko demo bahut pasand aaya lekin "
    "unhone bola ki report thodi late ho gayi hai isliye ab hume agle hafte tak sab kuch "
    "submit karna hai aur uske baad payment aayega "
)


def words(base: str, count: int) -> str:
    tokens = (base * 20).split()
    return " ".join(tokens[:count])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reps", type=int, default=5)
    args = parser.parse_args()

    report: dict = {"label": args.label, "reps": args.reps}
    for language, base in (("en", EN_BASE), ("hi", HI_BASE)):
        for count in (20, 50, 100, 250):
            lats = []
            for _ in range(args.reps):
                _, ms = correct(args.url, words(base, count), language=language, timeout=600)
                lats.append(ms)
            report[f"{language}_{count}w"] = {
                "p50_ms": round(statistics.median(lats), 1),
                "max_ms": round(max(lats), 1),
            }
            print(args.label, language, count, report[f"{language}_{count}w"], flush=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
