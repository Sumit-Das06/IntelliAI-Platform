"""LocalAgreement-2 display policy, evaluated post-hoc on captured
partial sequences.

Raw partials churn (whisper re-hears the tail as context grows). The
standard mitigation is DISPLAY-level: show only the word-prefix on
which the last two decodes AGREE. This script measures what the user
would see under that policy:

    monotonic          — displayed text only ever grows
    lag_words          — words the display trails behind the raw partial
    coverage           — how much of the final text was already shown live

    python la2_analysis.py <partials.json> <out.json>
"""

from __future__ import annotations

import itertools
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "evidence"


def lcp_words(a: list[str], b: list[str]) -> list[str]:
    out = []
    for x, y in zip(a, b, strict=False):
        if x.casefold().strip(".,?!") != y.casefold().strip(".,?!"):
            break
        out.append(y)
    return out


def main() -> None:
    partials_name, out_name = sys.argv[1:3]
    partials: list[str] = json.loads((EVIDENCE / partials_name).read_text(encoding="utf-8"))
    displayed: list[list[str]] = []
    shrink_events = 0
    lags = []
    for previous, current in itertools.pairwise(partials):
        agreed = lcp_words(previous.split(), current.split())
        # display never shrinks: keep the longer of (old display, agreed)
        shown = agreed if not displayed or len(agreed) >= len(displayed[-1]) else displayed[-1]
        if displayed and len(shown) < len(displayed[-1]):
            shrink_events += 1
        displayed.append(shown)
        lags.append(len(current.split()) - len(shown))
    final_words = partials[-1].split()
    live_words = displayed[-1] if displayed else []
    payload = {
        "partials": len(partials),
        "policy": "LocalAgreement-2 word prefix, monotonic display",
        "monotonic": shrink_events == 0,
        "lag_words": {
            "mean": round(statistics.mean(lags), 1) if lags else 0,
            "max": max(lags) if lags else 0,
        },
        "live_coverage_of_final": round(len(live_words) / max(len(final_words), 1), 3),
        "displayed_growth": [len(d) for d in displayed],
    }
    (EVIDENCE / out_name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(out_name, {k: payload[k] for k in ("monotonic", "lag_words", "live_coverage_of_final")})


if __name__ == "__main__":
    main()
