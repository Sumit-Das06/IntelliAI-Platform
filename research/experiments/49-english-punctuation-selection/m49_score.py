"""M49 - score every predictor on en-punct-eval@v1 with the FROZEN
punct_slots@v1 ruler (mirrors the M29A scorer; ruler untouched).

Usage:
  uv run --package intelliai-evaluation python m49_score.py \
      <predictions-dir> <out-json>
"""

import hashlib
import json
import sys
from pathlib import Path

from intelliai_evaluation.punctuation import (
    PUNCTUATION_RULER,
    load_punctuation_dataset,
    score_pair,
)

ROOT = Path(__file__).resolve()
DATASET_PATH = Path("ml/evaluation/punctuation/datasets/en-punct-eval-v1.json")


def class_of(row_id: str) -> str:
    if row_id.startswith("lj-para"):
        return "paragraph"
    if row_id.startswith("lj-"):
        return "single"
    if row_id.startswith("boss-"):
        return "spontaneous"
    return "probe"


def main() -> None:
    pred_dir = Path(sys.argv[1])
    dataset = load_punctuation_dataset(DATASET_PATH)
    dataset_sha = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    references = {row.id: row.reference_text for row in dataset.rows}

    matrix: dict = {"ruler": PUNCTUATION_RULER, "dataset_sha256": dataset_sha, "systems": {}}
    for pfile in sorted(pred_dir.glob("predictions-*.json")):
        payload = json.loads(pfile.read_text(encoding="utf-8"))
        if payload["dataset_sha256"] != dataset_sha:
            raise SystemExit(f"{pfile.name}: stale dataset")
        name = payload["system"]
        agg: dict = {}
        per_class: dict = {}
        invariant_fail = 0
        for pred in payload["predictions"]:
            ref = references[pred["id"]]
            score = score_pair(ref, pred["predicted_text"])
            if not pred.get("invariant", True) or not score.aligned:
                invariant_fail += 1
                continue
            buckets = [agg.setdefault("all", {}), per_class.setdefault(class_of(pred["id"]), {})]
            for bucket in buckets:
                for mark, counts in score.per_mark.items():
                    b = bucket.setdefault(mark, {"tp": 0, "fp": 0, "fn": 0})
                    d = counts.as_dict()
                    b["tp"] += d["true_positives"]
                    b["fp"] += d["false_positives"]
                    b["fn"] += d["false_negatives"]
                bb = bucket.setdefault("boundary", {"tp": 0, "fp": 0, "fn": 0})
                d = score.boundary.as_dict()
                bb["tp"] += d["true_positives"]
                bb["fp"] += d["false_positives"]
                bb["fn"] += d["false_negatives"]

        def f1(c):
            p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
            r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
            return {
                "precision": round(p, 4),
                "recall": round(r, 4),
                "f1": round(2 * p * r / (p + r), 4) if p + r else 0.0,
            }

        def render(bucket):
            out = {}
            micro = {"tp": 0, "fp": 0, "fn": 0}
            for mark, c in bucket.items():
                out[mark] = f1(c)
                if mark != "boundary":
                    for k in micro:
                        micro[k] += c[k]
            out["micro"] = f1(micro)
            return out

        matrix["systems"][name] = {
            "invariant_failures": invariant_fail,
            "overall": render(agg.get("all", {})),
            "per_class": {k: render(v) for k, v in per_class.items()},
        }
        ov = matrix["systems"][name]["overall"]
        print(
            name,
            "micro",
            ov["micro"]["f1"],
            "boundary",
            ov.get("boundary", {}).get("f1"),
            "comma",
            ov.get(",", {}).get("f1"),
            "invariant_fail",
            invariant_fail,
        )

    Path(sys.argv[2]).write_text(json.dumps(matrix, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SCORE-DONE")


if __name__ == "__main__":
    main()
