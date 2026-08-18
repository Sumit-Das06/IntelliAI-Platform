"""M23 Phase 7: the data-comparison report — what changed in E3, and ONLY E3.

Reads the three frozen corpora (E1's v1, E2's v2, E3's v3) plus v3's
part sidecars and answers the composition questions side by side:
hours, rows, per-language rows/hours, short-speech rows, negatives,
markup, sources, duration percentiles — and proves mechanically that
v3 ⊃ v2 row-for-row (the E2 corpus enters E3 verbatim, byte-equal per
row), so the ONLY deltas are the two named slices.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * q), len(ordered) - 1)]


def describe(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    durs = [float(r["duration_seconds"]) for r in rows]
    by_lang: dict[str, list[float]] = {}
    for r in rows:
        by_lang.setdefault(r["language"], []).append(float(r["duration_seconds"]))
    prefixes: dict[str, int] = {}
    for r in rows:
        prefix = r["id"].split("-", 1)[0]
        prefixes[prefix] = prefixes.get(prefix, 0) + 1
    return {
        "corpus": name,
        "rows": len(rows),
        "hours": round(sum(durs) / 3600, 3),
        "per_language": {
            lang: {
                "rows": len(ds),
                "hours": round(sum(ds) / 3600, 3),
                "row_share": round(len(ds) / len(rows), 4),
            }
            for lang, ds in sorted(by_lang.items())
        },
        "short_rows_below_2s": sum(1 for d in durs if d < 2.0),
        "markup_rows": sum(1 for r in rows if "<" in r["text"] and r["language"] != "zxx"),
        "id_prefixes": prefixes,
        "duration_seconds": {
            "min": min(durs),
            "median": round(percentile(durs, 0.5), 3),
            "p95": round(percentile(durs, 0.95), 3),
            "max": max(durs),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    manifests = Path("ml/datasets/manifests")
    parser.add_argument("--v1", type=Path, default=manifests / "hi-public-train-v1.jsonl")
    parser.add_argument("--v2", type=Path, default=manifests / "qwen-hi-public-train-v2.jsonl")
    parser.add_argument("--v3", type=Path, default=manifests / "qwen-hi-public-train-v3.jsonl")
    parser.add_argument(
        "--v3-provenance",
        type=Path,
        default=manifests / "qwen-hi-public-train-v3.provenance.json",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    v1_rows, v2_rows, v3_rows = load_rows(args.v1), load_rows(args.v2), load_rows(args.v3)

    # The containment proof: every v2 row appears in v3 BYTE-IDENTICALLY
    # (same 5 fields, same values), so E3 = E2's corpus + the two slices.
    def row_key(r: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(r, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    v3_keys = {row_key(r) for r in v3_rows}
    missing = [r["id"] for r in v2_rows if row_key(r) not in v3_keys]
    v2_ids = {r["id"] for r in v2_rows}
    added = [r for r in v3_rows if r["id"] not in v2_ids]
    added_langs: dict[str, int] = {}
    for r in added:
        added_langs[r["language"]] = added_langs.get(r["language"], 0) + 1

    sidecar = json.loads(args.v3_provenance.read_text(encoding="utf-8"))
    payload = {
        "experiment": "23-qwen3-hi-ft-e3",
        "phase": "data-comparison (Phase 7)",
        "run_at": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        "corpora": [
            describe("E1: hi-public-train@v1", v1_rows),
            describe("E2: qwen-hi-public-train@v2", v2_rows),
            describe("E3: qwen-hi-public-train@v3", v3_rows),
        ],
        "containment": {
            "v2_rows_missing_from_v3": missing,
            "v2_subset_of_v3": not missing,
            "rows_added_beyond_v2": len(added),
            "added_by_language": added_langs,
        },
        "v3_parts": sidecar.get("merged_from", []),
        "v3_curation": sidecar.get("curation", ""),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["containment"], ensure_ascii=False, indent=2))
    for corpus in payload["corpora"]:
        langs = ", ".join(f"{k}:{v['rows']}" for k, v in corpus["per_language"].items())
        print(
            f"{corpus['corpus']}: {corpus['rows']} rows / {corpus['hours']}h; "
            f"langs={{{langs}}}; <2s rows={corpus['short_rows_below_2s']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
