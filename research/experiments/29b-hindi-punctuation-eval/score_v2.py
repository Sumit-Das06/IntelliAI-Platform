"""M29B — score every system on every target; build the decision matrix.

Reads the frozen v1 + v2 benchmarks and the harness predictions, scores
with the evaluation plane's punct_slots@v1 module, and writes:

  harness/metrics-<target>-<system>[-<domain>].json
  question-results.json      (final-mark correctness + detection P/R/F1)
  edge-results.json          (corruption scan: invariant + unk markers)
  spontaneous-examples.json  (best/worst lead-wordcopy rows, never hidden)
  decision-matrix-v2.json    (systems x domains)

Run: uv run --package intelliai-evaluation python .../score_v2.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from intelliai_evaluation.punctuation import (
    CorpusScore,
    invariant_holds,
    load_punctuation_dataset,
    score_pair,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V1_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json"
V2_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v2.json"
SYSTEMS = ("no-op", "rules", "lead-old", "lead-wordcopy")


def load_predictions(target: str, system: str) -> list[dict]:
    payload = json.loads(
        (HERE / "harness" / f"predictions-{target}-{system}.json").read_text(encoding="utf-8")
    )
    return payload["predictions"]


def score_rows(
    references: dict[str, str], predictions: list[dict]
) -> tuple[CorpusScore, list[dict]]:
    corpus = CorpusScore()
    per_row: list[dict] = []
    for prediction in predictions:
        row_id = prediction["id"]
        if row_id not in references:
            continue
        reference = references[row_id]
        predicted = prediction["output_text"]
        pair = score_pair(reference, predicted)
        corpus.rows += 1
        if not pair.aligned:
            corpus.invariant_failures += 1
            per_row.append(
                {
                    "id": row_id,
                    "invariant": "FAIL",
                    "f1": None,
                    "reference": reference,
                    "output": predicted,
                }
            )
            continue
        corpus.aligned_rows += 1
        corpus.micro.add(pair.micro)
        for mark, counts in pair.per_mark.items():
            corpus.per_mark[mark].add(counts)
        corpus.boundary.add(pair.boundary)
        per_row.append(
            {
                "id": row_id,
                "invariant": "PASS",
                "f1": round(pair.micro.f1, 4),
                "boundary_f1": round(pair.boundary.f1, 4),
                "reference": reference,
                "output": predicted,
            }
        )
    return corpus, per_row


def summarize(corpus: CorpusScore) -> dict:
    s = corpus.as_dict()
    return {
        "micro_f1": s["micro"]["f1"],
        "micro_precision": s["micro"]["precision"],
        "micro_recall": s["micro"]["recall"],
        "danda_f1": s["per_mark"]["।"]["f1"],
        "comma_f1": s["per_mark"][","]["f1"],
        "question_f1": s["per_mark"]["?"]["f1"],
        "boundary_f1": s["sentence_boundary"]["f1"],
        "boundary_precision": s["sentence_boundary"]["precision"],
        "boundary_recall": s["sentence_boundary"]["recall"],
        "invariant_pass_rate": s["invariant_pass_rate"],
        "invariant_failures": s["invariant_failures"],
        "rows": s["rows"],
    }


def main() -> None:
    v1 = load_punctuation_dataset(V1_PATH)
    v2 = load_punctuation_dataset(V2_PATH)
    matrix: dict[str, dict] = {}

    # ── v1 (single-sentence read) + v2 domains ──────────────────────────
    slices = {
        "fleurs-single (v1)": ({r.id: r.reference_text for r in v1.rows}, "v1"),
        "read-paragraph (v2)": (
            {r.id: r.reference_text for r in v2.rows if r.domain == "read-paragraph"},
            "v2",
        ),
        "spontaneous (v2)": (
            {r.id: r.reference_text for r in v2.rows if r.domain == "spontaneous"},
            "v2",
        ),
    }
    spontaneous_rows_by_system: dict[str, list[dict]] = {}
    for slice_name, (references, target) in slices.items():
        matrix[slice_name] = {}
        for system in SYSTEMS:
            corpus, per_row = score_rows(references, load_predictions(target, system))
            matrix[slice_name][system] = summarize(corpus)
            safe = slice_name.split(" ")[0]
            (HERE / "harness" / f"metrics-{target}-{system}-{safe}.json").write_text(
                json.dumps(
                    {
                        "slice": slice_name,
                        "system": system,
                        "corpus": corpus.as_dict(),
                        "per_row": per_row,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            if slice_name.startswith("spontaneous"):
                spontaneous_rows_by_system[system] = per_row
            m = matrix[slice_name][system]
            print(
                f"{slice_name} / {system}: F1={m['micro_f1']} "
                f"boundary={m['boundary_f1']} "
                f"(P {m['boundary_precision']} / R {m['boundary_recall']}) "
                f"comma={m['comma_f1']} q={m['question_f1']} inv={m['invariant_pass_rate']}"
            )

    # ── question probes ──────────────────────────────────────────────────
    probes = json.loads((HERE / "question-probes.json").read_text(encoding="utf-8"))["probes"]
    kinds = {p["id"]: p["kind"] for p in probes}
    question_results: dict[str, dict] = {}
    for system in ("rules", "lead-old", "lead-wordcopy"):
        tp = fp = fn = tn = 0
        wrong: list[dict] = []
        for prediction in load_predictions("qp", system):
            kind = kinds[prediction["id"]]
            out = prediction["output_text"].strip()
            ends_q = out.endswith("?")
            if kind == "question" and ends_q:
                tp += 1
            elif kind == "question":
                fn += 1
                wrong.append({"id": prediction["id"], "expected": "?", "output": out})
            elif ends_q:
                fp += 1
                wrong.append({"id": prediction["id"], "expected": "।", "output": out})
            else:
                tn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        question_results[system] = {
            "questions": 30,
            "statement_controls": 12,
            "correct_questions": tp,
            "missed_questions": fn,
            "false_positive_statements": fp,
            "correct_statements": tn,
            "detection_precision": round(precision, 4),
            "detection_recall": round(recall, 4),
            "detection_f1": round(f1, 4),
            "pct_questions_correct": round(100 * tp / 30, 1),
            "wrong": wrong,
        }
        r = question_results[system]
        print(
            f"questions / {system}: {r['correct_questions']}/30 correct "
            f"({r['pct_questions_correct']}%), FP on statements: {fp}/12, F1={r['detection_f1']}"
        )
    (HERE / "question-results.json").write_text(
        json.dumps(
            {
                "experiment": "29b-hindi-punctuation-eval",
                "proposed_gate": ">=80% questions correct (PROPOSED, not yet approved)",
                "systems": question_results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # ── edge probes ──────────────────────────────────────────────────────
    edge_inputs = {
        p["id"]: p["text"]
        for p in json.loads((HERE / "edge-probes.json").read_text(encoding="utf-8"))["probes"]
    }
    edge_results: dict[str, dict] = {}
    for system in ("lead-old", "lead-wordcopy"):
        corruptions: list[dict] = []
        for prediction in load_predictions("ep", system):
            text = edge_inputs[prediction["id"]]
            out = prediction["output_text"]
            ok = invariant_holds(text, out) and "unk" not in out.casefold().replace("unke", "")
            if not ok:
                corruptions.append({"id": prediction["id"], "input": text, "output": out})
        edge_results[system] = {
            "probes": len(edge_inputs),
            "corruptions": len(corruptions),
            "verdict": "PASS" if not corruptions else "FAIL",
            "corrupted": corruptions,
        }
        print(
            f"edges / {system}: {len(corruptions)}/{len(edge_inputs)} corrupted "
            f"-> {edge_results[system]['verdict']}"
        )
    (HERE / "edge-results.json").write_text(
        json.dumps(
            {
                "experiment": "29b-hindi-punctuation-eval",
                "rule": "any lexical corruption = FAIL",
                "systems": edge_results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    # ── spontaneous examples (lead-wordcopy, best + worst) ───────────────
    rows = [r for r in spontaneous_rows_by_system["lead-wordcopy"] if r["invariant"] == "PASS"]
    good = sorted(rows, key=lambda r: (-r["f1"], r["id"]))[:8]
    bad = sorted(rows, key=lambda r: (r["f1"], r["id"]))[:8]
    (HERE / "spontaneous-examples.json").write_text(
        json.dumps(
            {
                "selection": "best and WORST lead-wordcopy rows on the spontaneous domain",
                "good": good,
                "bad": bad,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (HERE / "decision-matrix-v2.json").write_text(
        json.dumps(
            {
                "experiment": "29b-hindi-punctuation-eval",
                "v1_sha256": hashlib.sha256(V1_PATH.read_bytes()).hexdigest(),
                "v2_sha256": hashlib.sha256(V2_PATH.read_bytes()).hexdigest(),
                "slices": matrix,
                "questions": {
                    s: {k: v for k, v in r.items() if k != "wrong"}
                    for s, r in question_results.items()
                },
                "edges": {
                    s: {k: v for k, v in r.items() if k != "corrupted"}
                    for s, r in edge_results.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("written: decision-matrix-v2.json + per-slice metrics + examples")


if __name__ == "__main__":
    sys.exit(main())
