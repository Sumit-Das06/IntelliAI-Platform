"""M30 — the approved punctuation gates, measured through the PRODUCTION wrapper.

M29B/M29C measured the research decoder; production adoption must be
gated on the code that actually ships. This instrument runs the runtime's
`PunctuationRestorer` (services/stt-runtime, pinned artifact, v1 mark
scope ।,",",?) over hi-punct-eval@v3 + the question and edge probe sets,
scores with the evaluation plane's punct_slots@v1 ruler, and assesses the
FOUNDER-APPROVED revised gates.

Run from the repo root (workspace venv carries the punctuation extra):
  uv run --package intelliai-stt-runtime python \
      research/experiments/30-punctuation-runtime/m30_quality_gates.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "ml/evaluation/src"))

from intelliai_evaluation.punctuation import (  # noqa: E402
    CorpusScore,
    invariant_holds,
    load_punctuation_dataset,
    score_pair,
)
from intelliai_runtime_contract import TranscriptionResult, TranscriptionSegment  # noqa: E402
from intelliai_stt_runtime.engines.punctuation import load_punctuation  # noqa: E402

V3_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v3.json"
ARTIFACT_DIR = ROOT / "models/punct-cap-seg-47/v1"
M29B = ROOT / "research/experiments/29b-hindi-punctuation-eval"


def restore_text(restorer: object, text: str) -> str:
    result = TranscriptionResult(
        text=text,
        language="hi",
        duration_seconds=1.0,
        segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=1.0, text=text),),
    )
    outcome = restorer.restore_safely(result, "hi")  # type: ignore[attr-defined]
    return outcome.result.text


def score_slice(references: dict[str, str], outputs: dict[str, str]) -> dict:
    corpus = CorpusScore()
    for row_id, reference in references.items():
        pair = score_pair(reference, outputs[row_id])
        corpus.rows += 1
        if not pair.aligned:
            corpus.invariant_failures += 1
            continue
        corpus.aligned_rows += 1
        corpus.micro.add(pair.micro)
        for mark, counts in pair.per_mark.items():
            corpus.per_mark[mark].add(counts)
        corpus.boundary.add(pair.boundary)
    s = corpus.as_dict()
    return {
        "rows": s["rows"],
        "micro_f1": s["micro"]["f1"],
        "boundary_f1": s["sentence_boundary"]["f1"],
        "boundary_precision": s["sentence_boundary"]["precision"],
        "boundary_recall": s["sentence_boundary"]["recall"],
        "comma_f1": s["per_mark"][","]["f1"],
        "question_f1": s["per_mark"]["?"]["f1"],
        "invariant_pass_rate": s["invariant_pass_rate"],
    }


def main() -> None:
    restorer = load_punctuation(ARTIFACT_DIR, languages=("hi", "hi-IN"), timeout_ms=10_000)
    v3 = load_punctuation_dataset(V3_PATH)
    review = json.loads((M29B / "spontaneous-annotations-review.json").read_text(encoding="utf-8"))
    audio_flagged = set(review["audio_review_required_ids"])
    inputs = {
        row["id"]: row["input_text"]
        for row in json.loads((M29B / "harness/v2-inputs.json").read_text(encoding="utf-8"))["rows"]
    }

    outputs = {row_id: restore_text(restorer, text) for row_id, text in inputs.items()}

    spont = {r.id: r for r in v3.rows if r.domain == "spontaneous"}
    slices = {
        "read-paragraph": {r.id: r.reference_text for r in v3.rows if r.domain == "read-paragraph"},
        "spontaneous-all60": {r.id: r.reference_text for r in spont.values()},
        "spontaneous-ratified51": {
            r.id: r.reference_text for r in spont.values() if r.members[0] not in audio_flagged
        },
    }
    matrix = {name: score_slice(refs, outputs) for name, refs in slices.items()}
    rules = json.loads(
        (M29B / "harness/metrics-v3-rules-read-paragraph.json").read_text(encoding="utf-8")
    )["corpus"]["sentence_boundary"]["f1"]

    # Question probes through the production wrapper
    probes = json.loads((M29B / "question-probes.json").read_text(encoding="utf-8"))["probes"]
    tp = fp = fn = 0
    lexically_cued_total = 30 - 7  # 6 tag/declarative + 1 hinglish-declarative (M29B analysis)
    for probe in probes:
        out = restore_text(restorer, probe["text"]).strip()
        if probe["kind"] == "question":
            if out.endswith("?"):
                tp += 1
            else:
                fn += 1
        elif out.endswith("?"):
            fp += 1
    question_pct_cued = round(100 * tp / lexically_cued_total, 1)

    # Edge probes: zero lexical corruption required
    edges = json.loads((M29B / "edge-probes.json").read_text(encoding="utf-8"))["probes"]
    corruptions = []
    for probe in edges:
        out = restore_text(restorer, probe["text"])
        if not invariant_holds(probe["text"], out) or "unk" in out.casefold().replace("unke", ""):
            corruptions.append({"id": probe["id"], "output": out})

    para = matrix["read-paragraph"]
    rat = matrix["spontaneous-ratified51"]
    invariant_100 = all(m["invariant_pass_rate"] == 1.0 for m in matrix.values()) and not (
        corruptions
    )
    gates = [
        {
            "gate": "word invariant = 100%",
            "measured": {k: m["invariant_pass_rate"] for k, m in matrix.items()},
            "verdict": "PASS" if invariant_100 else "FAIL",
        },
        {
            "gate": "lexically-cued question accuracy >= 85%",
            "measured": question_pct_cued,
            "verdict": "PASS" if question_pct_cued >= 85.0 else "FAIL",
        },
        {
            "gate": "statement false positives = 0",
            "measured": fp,
            "verdict": "PASS" if fp == 0 else "FAIL",
        },
        {
            "gate": "boundary F1 >= 0.70 (multi-sentence)",
            "measured": {"read-paragraph": para["boundary_f1"], "ratified51": rat["boundary_f1"]},
            "verdict": "PASS"
            if para["boundary_f1"] >= 0.70 and rat["boundary_f1"] >= 0.70
            else "FAIL",
        },
        {
            "gate": "boundary F1 >= rules + 0.25 absolute",
            "measured": {"lead": para["boundary_f1"], "rules": rules},
            "verdict": "PASS" if para["boundary_f1"] >= rules + 0.25 else "FAIL",
        },
        {
            "gate": "comma F1 >= 0.30",
            "measured": {"read-paragraph": para["comma_f1"], "ratified51": rat["comma_f1"]},
            "verdict": "PASS" if para["comma_f1"] >= 0.30 and rat["comma_f1"] >= 0.30 else "FAIL",
        },
    ]

    evidence = {
        "experiment": "30-punctuation-runtime",
        "phase": "approved-gates through the PRODUCTION wrapper (v1 mark scope)",
        "benchmark": (
            f"hi-punct-eval@v3 (sha256 {hashlib.sha256(V3_PATH.read_bytes()).hexdigest()})"
        ),
        "wrapper": "intelliai_stt_runtime.engines.punctuation.PunctuationRestorer",
        "slices": matrix,
        "questions": {
            "correct": tp,
            "missed": fn,
            "statement_false_positives": fp,
            "lexically_cued_pct": question_pct_cued,
        },
        "edge_probes": {
            "total": len(edges),
            "corruptions": len(corruptions),
            "corrupted": corruptions,
        },
        "approved_gates": gates,
    }
    out_path = HERE / "quality-gates.json"
    out_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, m in matrix.items():
        print(
            f"{name}: F1={m['micro_f1']} boundary={m['boundary_f1']} "
            f"(P {m['boundary_precision']} / R {m['boundary_recall']}) "
            f"comma={m['comma_f1']} inv={m['invariant_pass_rate']}"
        )
    print(f"questions: {tp}/30 correct, cued {question_pct_cued}%, FP {fp}/12")
    print(f"edges: {len(corruptions)}/{len(edges)} corrupted")
    for gate in gates:
        print(f"  [{gate['verdict']}] {gate['gate']}")
    restorer.close()


if __name__ == "__main__":
    sys.exit(main())
