"""M29B — all predictions in one pass (scratch venv instrument).

Systems:
  no-op          input unchanged (the production floor)
  rules          the M29A minimum rules baseline (imported from 29a)
  lead-old       the pinned model through the punctuators pipeline
                 (M29A configuration — the reconstruction that can emit <unk>)
  lead-wordcopy  the pinned model through the M29B word-copy decoder

Targets:
  v1   hi-punct-eval@v1 inputs (M29A harness, 265 rows)
  v2   hi-punct-eval@v2 inputs (148 rows: read-paragraph + spontaneous)
  qp   question probes (30 questions + 12 statement controls)
  ep   edge probes (22 corruption probes)

Writes harness/predictions-<target>-<system>.json. PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
M29A = HERE.parent / "29a-hindi-punctuation-eval"
sys.path.insert(0, str(M29A))
sys.path.insert(0, str(HERE))

from predict_baselines import rules_restore  # noqa: E402
from wordcopy_decoder import WordCopyPunctuator  # noqa: E402


def load_targets() -> dict[str, list[dict]]:
    v1 = json.loads((M29A / "harness/inputs.json").read_text(encoding="utf-8"))
    v2 = json.loads((HERE / "harness/v2-inputs.json").read_text(encoding="utf-8"))
    qp = json.loads((HERE / "question-probes.json").read_text(encoding="utf-8"))
    ep = json.loads((HERE / "edge-probes.json").read_text(encoding="utf-8"))
    return {
        "v1": [{"id": r["id"], "input_text": r["input_text"]} for r in v1["rows"]],
        "v2": [
            {"id": r["id"], "domain": r["domain"], "input_text": r["input_text"]}
            for r in v2["rows"]
        ],
        "qp": [{"id": p["id"], "kind": p["kind"], "input_text": p["text"]} for p in qp["probes"]],
        "ep": [{"id": p["id"], "kind": p["kind"], "input_text": p["text"]} for p in ep["probes"]],
    }


def main() -> None:
    targets = load_targets()

    from punctuators.models import PunctCapSegModelONNX

    old_model = PunctCapSegModelONNX.from_pretrained("pcs_47lang")
    wordcopy = WordCopyPunctuator()

    def old_restore(text: str) -> str:
        out = old_model.infer([text])[0]
        return " ".join(out) if isinstance(out, list) else str(out)

    systems = {
        "no-op": lambda t: t,
        "rules": rules_restore,
        "lead-old": old_restore,
        "lead-wordcopy": wordcopy.punctuate,
    }

    for target, rows in targets.items():
        for system, restore in systems.items():
            t0 = time.perf_counter()
            predictions = [
                {
                    **{k: v for k, v in row.items() if k != "input_text"},
                    "output_text": restore(row["input_text"]),
                }
                for row in rows
            ]
            elapsed = round(time.perf_counter() - t0, 2)
            out = HERE / "harness" / f"predictions-{target}-{system}.json"
            out.write_text(
                json.dumps(
                    {
                        "experiment": "29b-hindi-punctuation-eval",
                        "target": target,
                        "system": system,
                        "rows": len(predictions),
                        "wall_seconds": elapsed,
                        "predictions": predictions,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"{target}/{system}: {len(predictions)} rows in {elapsed}s")


if __name__ == "__main__":
    sys.exit(main())
