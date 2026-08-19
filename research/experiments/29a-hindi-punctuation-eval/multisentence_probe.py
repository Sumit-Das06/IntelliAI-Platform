"""M29A — multi-sentence probe: where the product actually lives.

The frozen benchmark's rows are mostly SINGLE sentences (FLEURS reads one
sentence per clip), which flatters a rules baseline that appends exactly one
final ender. Real dictation is a WALL of sentences — the product question is
mid-text boundary detection. This probe measures that, deterministically:

  build: concatenate consecutive benchmark rows in groups of 3 (dedup
         order, no randomness) -> paragraph references with 3 sentences
         each; write probe inputs (punctuation-stripped)
  score: score rules + lead predictions against the paragraph references
         with the same punct_slots@v1 module

A probe, NOT the frozen benchmark: derived text (concatenation) never
spoken as a paragraph. It isolates one property — boundaries INSIDE text.

Run from the repo root (build and score need the repo env; predictions come
from predict_multisentence.py in the scratch venv):
  uv run --package intelliai-evaluation python .../multisentence_probe.py --build
  <venv python> .../predict_multisentence.py
  uv run --package intelliai-evaluation python .../multisentence_probe.py --score
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
    strip_punctuation_for_input,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DATASET_PATH = ROOT / "ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json"
GROUP = 3


def build() -> None:
    dataset = load_punctuation_dataset(DATASET_PATH)
    rows = list(dataset.rows)
    paragraphs = []
    for start in range(0, len(rows) - len(rows) % GROUP, GROUP):
        group = rows[start : start + GROUP]
        reference = " ".join(row.reference_text for row in group)
        paragraphs.append(
            {
                "id": f"para-{start // GROUP:03d}",
                "member_ids": [row.id for row in group],
                "reference_text": reference,
                "input_text": strip_punctuation_for_input(reference),
            }
        )
    payload = {
        "experiment": "29a-hindi-punctuation-eval",
        "phase": "multisentence-probe (derived from hi-punct-eval@v1; NOT the frozen benchmark)",
        "group_size": GROUP,
        "dataset_sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
        "paragraphs": paragraphs,
    }
    out = HERE / "harness/multisentence-inputs.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"built {len(paragraphs)} paragraphs of {GROUP} sentences -> {out.name}")


def score() -> None:
    inputs = json.loads((HERE / "harness/multisentence-inputs.json").read_text(encoding="utf-8"))
    references = {p["id"]: p["reference_text"] for p in inputs["paragraphs"]}
    results: dict[str, object] = {}
    for system in ("rules", "lead-onnx"):
        payload = json.loads(
            (HERE / "harness" / f"multisentence-predictions-{system}.json").read_text(
                encoding="utf-8"
            )
        )
        corpus = CorpusScore()
        for prediction in payload["predictions"]:
            reference = references[prediction["id"]]
            pair = score_pair(reference, prediction["output_text"])
            corpus.rows += 1
            if not pair.aligned:
                corpus.invariant_failures += 1
                continue
            corpus.aligned_rows += 1
            corpus.micro.add(pair.micro)
            for mark, counts in pair.per_mark.items():
                corpus.per_mark[mark].add(counts)
            corpus.boundary.add(pair.boundary)
        results[system] = corpus.as_dict()
        summary = corpus.as_dict()
        boundary = summary["sentence_boundary"]
        print(
            f"{system}: boundary P={boundary['precision']} R={boundary['recall']} "
            f"F1={boundary['f1']} | micro F1={summary['micro']['f1']} "
            f"| invariant={summary['invariant_pass_rate']}"
        )
    out = HERE / "multisentence-results.json"
    out.write_text(
        json.dumps(
            {
                "experiment": "29a-hindi-punctuation-eval",
                "phase": inputs["phase"],
                "group_size": inputs["group_size"],
                "paragraphs": len(references),
                "systems": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"written: {out.name}")


if __name__ == "__main__":
    if "--build" in sys.argv:
        build()
    elif "--score" in sys.argv:
        score()
    else:
        sys.exit("pass --build or --score")
