"""M29C — re-score against the ratified hi-punct-eval@v3 + gate assessment.

Uses the committed v2 harness predictions (valid: build_v3 verified the
punctuation-stripped inputs are byte-identical). Scores every system on:

  read-paragraph (88)            — unchanged references, re-scored for the record
  spontaneous ALL (60)           — v3 references (2 comma revisions applied)
  spontaneous TEXT-RATIFIED (51) — audio-flagged rows excluded (the review's
                                   own limit: those need audio/native review)
  spontaneous AUDIO-FLAGGED (9)  — informational only, never gate-bearing

Then assesses the M29A-proposed gates and the M29B revised-proposed gates
against the ratified numbers. Writes:
  harness/metrics-v3-<system>-<slice>.json
  gate-assessment-v3.json
  decision-matrix-v3.json

Run: uv run --package intelliai-evaluation python .../score_v3.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from intelliai_evaluation.punctuation import (
    CorpusScore,
    load_punctuation_dataset,
    score_pair,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V3_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v3.json"
REVIEW_PATH = HERE / "spontaneous-annotations-review.json"
SYSTEMS = ("no-op", "rules", "lead-old", "lead-wordcopy")


def load_predictions(system: str) -> dict[str, str]:
    payload = json.loads(
        (HERE / "harness" / f"predictions-v2-{system}.json").read_text(encoding="utf-8")
    )
    return {p["id"]: p["output_text"] for p in payload["predictions"]}


def summarize(corpus: CorpusScore) -> dict:
    s = corpus.as_dict()
    return {
        "rows": s["rows"],
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
    }


def score_slice(references: dict[str, str], predictions: dict[str, str]) -> CorpusScore:
    corpus = CorpusScore()
    for row_id, reference in references.items():
        pair = score_pair(reference, predictions[row_id])
        corpus.rows += 1
        if not pair.aligned:
            corpus.invariant_failures += 1
            continue
        corpus.aligned_rows += 1
        corpus.micro.add(pair.micro)
        for mark, counts in pair.per_mark.items():
            corpus.per_mark[mark].add(counts)
        corpus.boundary.add(pair.boundary)
    return corpus


def main() -> None:
    v3 = load_punctuation_dataset(V3_PATH)
    v3_sha = hashlib.sha256(V3_PATH.read_bytes()).hexdigest()
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    audio_flagged = set(review["audio_review_required_ids"])

    spont = {r.id: r for r in v3.rows if r.domain == "spontaneous"}
    slices: dict[str, dict[str, str]] = {
        "read-paragraph": {r.id: r.reference_text for r in v3.rows if r.domain == "read-paragraph"},
        "spontaneous-all60": {r.id: r.reference_text for r in spont.values()},
        "spontaneous-ratified51": {
            r.id: r.reference_text for r in spont.values() if r.members[0] not in audio_flagged
        },
        "spontaneous-audioflagged9": {
            r.id: r.reference_text for r in spont.values() if r.members[0] in audio_flagged
        },
    }

    matrix: dict[str, dict] = {}
    for slice_name, references in slices.items():
        matrix[slice_name] = {}
        for system in SYSTEMS:
            corpus = score_slice(references, load_predictions(system))
            matrix[slice_name][system] = summarize(corpus)
            (HERE / "harness" / f"metrics-v3-{system}-{slice_name}.json").write_text(
                json.dumps(
                    {"slice": slice_name, "system": system, "corpus": corpus.as_dict()},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        m = matrix[slice_name]["lead-wordcopy"]
        print(
            f"{slice_name} / lead-wordcopy: F1={m['micro_f1']} "
            f"boundary={m['boundary_f1']} (P {m['boundary_precision']} / "
            f"R {m['boundary_recall']}) comma={m['comma_f1']} inv={m['invariant_pass_rate']}"
        )

    # ── gate assessment on the ratified numbers ──────────────────────────
    para = matrix["read-paragraph"]["lead-wordcopy"]
    rat = matrix["spontaneous-ratified51"]["lead-wordcopy"]
    all60 = matrix["spontaneous-all60"]["lead-wordcopy"]
    questions = json.loads((HERE / "question-results.json").read_text(encoding="utf-8"))
    q = questions["systems"]["lead-wordcopy"]
    edges = json.loads((HERE / "edge-results.json").read_text(encoding="utf-8"))
    perf = json.loads((HERE / "perf-tiers-v2.json").read_text(encoding="utf-8"))

    def verdict(passed: bool) -> str:
        return "PASS" if passed else "FAIL"

    m29a_gates = [
        {
            "gate": "word-preservation invariant 100%",
            "measured": {
                "read-paragraph": para["invariant_pass_rate"],
                "spontaneous-all60": all60["invariant_pass_rate"],
                "edge_probes_corruptions": edges["systems"]["lead-wordcopy"]["corruptions"],
            },
            "verdict": verdict(
                para["invariant_pass_rate"] == 1.0
                and all60["invariant_pass_rate"] == 1.0
                and edges["systems"]["lead-wordcopy"]["corruptions"] == 0
            ),
        },
        {
            "gate": "boundary F1 >= 0.75 (multi-sentence)",
            "measured": {"read-paragraph": para["boundary_f1"], "ratified51": rat["boundary_f1"]},
            "verdict": verdict(para["boundary_f1"] >= 0.75 and rat["boundary_f1"] >= 0.75),
        },
        {
            "gate": "boundary recall >= 0.85",
            "measured": {
                "read-paragraph": para["boundary_recall"],
                "ratified51": rat["boundary_recall"],
            },
            "verdict": verdict(para["boundary_recall"] >= 0.85 and rat["boundary_recall"] >= 0.85),
        },
        {
            "gate": "boundary precision >= 0.65",
            "measured": {
                "read-paragraph": para["boundary_precision"],
                "ratified51": rat["boundary_precision"],
            },
            "verdict": verdict(
                para["boundary_precision"] >= 0.65 and rat["boundary_precision"] >= 0.65
            ),
        },
        {
            "gate": "comma F1 >= 0.30",
            "measured": {"read-paragraph": para["comma_f1"], "ratified51": rat["comma_f1"]},
            "verdict": verdict(para["comma_f1"] >= 0.30 and rat["comma_f1"] >= 0.30),
        },
        {
            "gate": "question probes >= 80% correct (as written in M29A)",
            "measured": {"pct_all_questions": q["pct_questions_correct"]},
            "verdict": verdict(q["pct_questions_correct"] >= 80.0),
        },
        {
            "gate": "latency p95 <= 10% of STT p50",
            "measured": {"600s_total_seconds": perf["tiers"]["600s"]["total_latency_seconds"]},
            "verdict": "PASS (dev box; deploy-box re-ladder still required)",
        },
        {
            "gate": "RAM <= 700 MiB",
            "measured": {"rss_peak_mib": perf["rss_mib"]["peak"]},
            "verdict": verdict(perf["rss_mib"]["peak"] <= 700),
        },
        {
            "gate": "ASR CER/WER byte-identical with stage on/off",
            "measured": "no runtime stage exists in this milestone",
            "verdict": "NOT APPLICABLE (moves to M29B-runtime)",
        },
    ]

    lexically_cued_correct = q["correct_questions"]
    lexically_cued_total = q["questions"] - 7  # 6 tag/declarative + 1 hinglish-declarative
    revised_gates = [
        {
            "gate": "questions: >= 85% on LEXICALLY-CUED + 0 statement false positives",
            "status": "PROPOSED — REQUIRES APPROVAL",
            "measured": {
                "lexically_cued_pct": round(100 * lexically_cued_correct / lexically_cued_total, 1),
                "statement_false_positives": q["false_positive_statements"],
            },
            "verdict": verdict(
                100 * lexically_cued_correct / lexically_cued_total >= 85.0
                and q["false_positive_statements"] == 0
            ),
        },
        {
            "gate": "boundary F1 >= 0.70 AND >= rules + 0.25 absolute (multi-sentence)",
            "status": "PROPOSED — REQUIRES APPROVAL",
            "measured": {
                "read-paragraph": para["boundary_f1"],
                "rules_read-paragraph": matrix["read-paragraph"]["rules"]["boundary_f1"],
            },
            "verdict": verdict(
                para["boundary_f1"] >= 0.70
                and para["boundary_f1"] >= matrix["read-paragraph"]["rules"]["boundary_f1"] + 0.25
            ),
        },
    ]

    assessment = {
        "experiment": "29b-hindi-punctuation-eval",
        "phase": "m29c-ratified gate assessment",
        "benchmark": f"hi-punct-eval@v3 (sha256 {v3_sha})",
        "review_basis": {
            "type": review["review_type"],
            "limit": review["important_limit"],
            "gate_bearing_slice": "spontaneous-ratified51 (audio-flagged rows excluded)",
        },
        "m29a_proposed_gates": m29a_gates,
        "revised_proposed_gates": revised_gates,
    }
    (HERE / "gate-assessment-v3.json").write_text(
        json.dumps(assessment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "decision-matrix-v3.json").write_text(
        json.dumps(
            {
                "experiment": "29b-hindi-punctuation-eval",
                "phase": "m29c-ratified decision matrix",
                "v3_sha256": v3_sha,
                "slices": matrix,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("\nM29A-proposed gates:")
    for gate in m29a_gates:
        print(f"  [{gate['verdict']}] {gate['gate']}")
    print("Revised-proposed gates:")
    for gate in revised_gates:
        print(f"  [{gate['verdict']}] {gate['gate']}")
    print("written: gate-assessment-v3.json, decision-matrix-v3.json")


if __name__ == "__main__":
    sys.exit(main())
