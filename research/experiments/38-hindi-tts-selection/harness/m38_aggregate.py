"""M38 — aggregate a roundtrip_judge output into category tables + clean slice.

The clean slice extends the M32 definition (numbers/currency/dates excluded)
to every verbalization-prone category this probe set adds: a TTS that
correctly expands "₹12,500" or "25%" into spoken words is PUNISHED by
edit distance against the written form, so those categories conflate
verbalization with error and are reported separately, never hidden.

    python m38_aggregate.py --roundtrip <roundtrip.json> --out <summary.json>
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

VERBALIZATION_PRONE = {
    "numbers",
    "currency",
    "dates",
    "percent",
    "phone",
    "time",
    "numerals_devanagari",
    "abbreviations",
}


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--roundtrip", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = json.loads(Path(args.roundtrip).read_text(encoding="utf-8"))
    rows = report["rows"]

    by_category: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"wer": [], "cer": []})
    clean = {"wer": [], "cer": []}
    full = {"wer": [], "cer": []}
    for row in rows:
        wer = row.get("wer_hi")
        cer = row.get("cer_hi")
        if wer is None or cer is None:
            continue
        category = row.get("category") or "uncategorized"
        by_category[category]["wer"].append(float(wer))
        by_category[category]["cer"].append(float(cer))
        full["wer"].append(float(wer))
        full["cer"].append(float(cer))
        # long_ladder is excluded from the clean slice too: on the upstream
        # research path those rows measure the ~510-phoneme silent-truncation
        # defect (reported separately), not per-sentence intelligibility.
        if category not in VERBALIZATION_PRONE and category != "long_ladder":
            clean["wer"].append(float(wer))
            clean["cer"].append(float(cer))

    categories = {
        name: {
            "rows": len(values["wer"]),
            "wer_mean": mean(values["wer"]),
            "cer_mean": mean(values["cer"]),
        }
        for name, values in sorted(by_category.items())
    }
    summary = {
        "experiment": "38-hindi-tts-selection",
        "instrument": "m38_aggregate.py",
        "engine_label": report.get("engine_label"),
        "source": Path(args.roundtrip).name,
        "clean_slice_definition": (
            "hi/mixed rows whose category is NOT verbalization-prone; excluded: "
            + ", ".join(sorted(VERBALIZATION_PRONE))
        ),
        "full": {
            "rows": len(full["wer"]),
            "wer_mean": mean(full["wer"]),
            "cer_mean": mean(full["cer"]),
        },
        "clean_slice": {
            "rows": len(clean["wer"]),
            "wer_mean": mean(clean["wer"]),
            "cer_mean": mean(clean["cer"]),
        },
        "by_category": categories,
    }
    Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    headline = {
        "engine": summary["engine_label"],
        "full": summary["full"],
        "clean": summary["clean_slice"],
    }
    print(json.dumps(headline))
    for name, stats in categories.items():
        print(f"  {name:<26} rows={stats['rows']} wer={stats['wer_mean']} cer={stats['cer_mean']}")


if __name__ == "__main__":
    main()
