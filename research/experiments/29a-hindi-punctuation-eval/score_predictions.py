"""M29A — score every predictor on hi-punct-eval@v1 (repo-env instrument).

Reads the frozen benchmark + each predictions file, scores with the
evaluation plane's punctuation module (punct_slots@v1), and writes:

  harness/metrics-<system>.json    corpus metrics + per-row scores
  examples.json                    10 good + 10 bad lead-model examples
                                   (good: best rows with >=2 reference
                                   marks; bad: WORST rows — never
                                   cherry-picked away)
  decision-matrix.json             the systems side by side

Run from the repo root:
  uv run --package intelliai-evaluation python \
      research/experiments/29a-hindi-punctuation-eval/score_predictions.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from intelliai_evaluation.punctuation import (
    PUNCTUATION_RULER,
    CorpusScore,
    load_punctuation_dataset,
    score_pair,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATASET_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json"
SYSTEMS = ("no-op", "rules", "lead-onnx")


def main() -> None:
    dataset = load_punctuation_dataset(DATASET_PATH)
    dataset_sha = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    references = {row.id: row.reference_text for row in dataset.rows}
    ref_mark_counts = {
        row.id: sum(1 for ch in row.reference_text if ch in "।,?!.") for row in dataset.rows
    }

    matrix: dict[str, dict] = {}
    lead_rows: list[dict] = []

    for system in SYSTEMS:
        payload = json.loads(
            (HERE / "harness" / f"predictions-{system}.json").read_text(encoding="utf-8")
        )
        if payload["dataset_sha256"] != dataset_sha:
            msg = f"{system}: predictions were made against a different dataset"
            raise SystemExit(msg)

        corpus = CorpusScore()
        per_row: list[dict] = []
        for prediction in payload["predictions"]:
            row_id = prediction["id"]
            reference = references[row_id]
            predicted = prediction["output_text"]
            pair = score_pair(reference, predicted)
            corpus.rows += 1
            if not pair.aligned:
                corpus.invariant_failures += 1
                row_record = {
                    "id": row_id,
                    "invariant": "FAIL",
                    "f1": None,
                    "reference": reference,
                    "output": predicted,
                }
            else:
                corpus.aligned_rows += 1
                corpus.micro.add(pair.micro)
                for mark, counts in pair.per_mark.items():
                    corpus.per_mark[mark].add(counts)
                corpus.boundary.add(pair.boundary)
                row_record = {
                    "id": row_id,
                    "invariant": "PASS",
                    "f1": round(pair.micro.f1, 4),
                    "reference_marks": ref_mark_counts[row_id],
                    "reference": reference,
                    "output": predicted,
                }
            per_row.append(row_record)

        metrics = {
            "experiment": "29a-hindi-punctuation-eval",
            "system": system,
            "dataset": f"{dataset.name}@v{dataset.version}",
            "dataset_sha256": dataset_sha,
            "ruler": PUNCTUATION_RULER,
            "corpus": corpus.as_dict(),
            "per_row": per_row,
        }
        (HERE / "harness" / f"metrics-{system}.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        summary = corpus.as_dict()
        matrix[system] = {
            "micro_f1": summary["micro"]["f1"],
            "micro_precision": summary["micro"]["precision"],
            "micro_recall": summary["micro"]["recall"],
            "danda_f1": summary["per_mark"]["।"]["f1"],
            "comma_f1": summary["per_mark"][","]["f1"],
            "question_f1": summary["per_mark"]["?"]["f1"],
            "exclamation_f1": summary["per_mark"]["!"]["f1"],
            "full_stop_f1": summary["per_mark"]["."]["f1"],
            "boundary_f1": summary["sentence_boundary"]["f1"],
            "invariant_pass_rate": summary["invariant_pass_rate"],
            "invariant_failures": summary["invariant_failures"],
        }
        print(
            f"{system}: micro F1={matrix[system]['micro_f1']} "
            f"danda={matrix[system]['danda_f1']} comma={matrix[system]['comma_f1']} "
            f"boundary={matrix[system]['boundary_f1']} "
            f"invariant={matrix[system]['invariant_pass_rate']}"
        )
        if system == "lead-onnx":
            lead_rows = per_row

    scored = [r for r in lead_rows if r["invariant"] == "PASS"]
    failed = [r for r in lead_rows if r["invariant"] == "FAIL"]
    good = sorted(
        (r for r in scored if r["reference_marks"] >= 2),
        key=lambda r: (-r["f1"], r["id"]),
    )[:10]
    bad = failed + sorted(
        (r for r in scored if r["reference_marks"] >= 1),
        key=lambda r: (r["f1"], r["id"]),
    )
    bad = bad[:10]
    (HERE / "examples.json").write_text(
        json.dumps(
            {
                "experiment": "29a-hindi-punctuation-eval",
                "system": "lead-onnx",
                "selection": (
                    "good: highest row micro-F1 among rows with >=2 reference "
                    "marks; bad: every invariant failure first, then the "
                    "lowest row micro-F1 - the worst rows are shown, not "
                    "hidden"
                ),
                "good": good,
                "bad": bad,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (HERE / "decision-matrix.json").write_text(
        json.dumps(
            {
                "experiment": "29a-hindi-punctuation-eval",
                "dataset": f"{dataset.name}@v{dataset.version}",
                "dataset_sha256": dataset_sha,
                "rows": len(dataset.rows),
                "systems": matrix,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("written: metrics-*.json, examples.json, decision-matrix.json")


if __name__ == "__main__":
    sys.exit(main())
