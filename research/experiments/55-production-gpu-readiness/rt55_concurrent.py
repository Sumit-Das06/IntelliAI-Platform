"""M55 concurrency (M54 harness) — concurrency fairness: N simultaneous gateway sessions.

    python rt54_concurrent.py <c> <out.json> [long]

Mixed EN+HI short sessions (boss30 / real30s alternating). With `long`,
one EN 10-minute "loud" session runs alongside the short ones — the
starvation probe: the short sessions' FPT/finalization under a long
neighbor is the fairness measurement.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import rt55_client as client

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"
SCRATCH = Path(
    r"C:\Users\VIKASH~1\AppData\Local\Temp\claude"
    r"\d--Sumit-Projects-IntelliAI-Platform"
    r"\67762b73-e6aa-43b8-a730-264d0d432d4f\scratchpad"
)
URL = "ws://127.0.0.1:8000/v1/audio/realtime"
EN_SHORT = SCRATCH / "m52clips" / "boss30.wav"
HI_SHORT = SCRATCH / "m52hclips" / "real30s.wav"
EN_LONG = SCRATCH / "m51long" / "10min.wav"


async def main() -> None:
    c = int(sys.argv[1])
    out_name = sys.argv[2]
    with_long = len(sys.argv) > 3 and sys.argv[3] == "long"
    jobs = []
    for i in range(c):
        wav, language = (EN_SHORT, "en") if i % 2 == 0 else (HI_SHORT, "hi")
        jobs.append(client.run(URL, str(wav), language, "realtime", f"{out_name}.s{i}.json"))
    if with_long:
        jobs.append(client.run(URL, str(EN_LONG), "en", "realtime", f"{out_name}.loud.json"))
    rows = await asyncio.gather(*jobs, return_exceptions=True)
    summary = []
    for row in rows:
        if isinstance(row, BaseException):
            summary.append({"error": type(row).__name__})
        else:
            summary.append(
                {
                    k: row.get(k)
                    for k in (
                        "wav",
                        "language",
                        "first_partial_at_s",
                        "partial_gap_p50_s",
                        "partial_gap_p95_s",
                        "finalization_ms",
                        "degraded",
                    )
                }
            )
    result = {"c": c, "with_long_neighbor": with_long, "sessions": summary}
    (EVIDENCE / f"{out_name}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
