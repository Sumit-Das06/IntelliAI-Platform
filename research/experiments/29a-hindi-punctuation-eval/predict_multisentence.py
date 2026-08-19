"""M29A — multi-sentence probe predictions: rules + lead model (venv).

Reads harness/multisentence-inputs.json, writes one predictions file per
system. The rules logic is imported from predict_baselines.py (same
instrument directory). PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from predict_baselines import rules_restore  # noqa: E402


def main() -> None:
    inputs = json.loads((HERE / "harness/multisentence-inputs.json").read_text(encoding="utf-8"))
    paragraphs = inputs["paragraphs"]

    rules_predictions = [
        {"id": p["id"], "output_text": rules_restore(p["input_text"])} for p in paragraphs
    ]
    (HERE / "harness/multisentence-predictions-rules.json").write_text(
        json.dumps(
            {"system": "rules", "predictions": rules_predictions}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )

    from punctuators.models import PunctCapSegModelONNX

    model = PunctCapSegModelONNX.from_pretrained("pcs_47lang")
    outputs = model.infer([p["input_text"] for p in paragraphs])
    lead_predictions = []
    for paragraph, out in zip(paragraphs, outputs, strict=True):
        joined = " ".join(out) if isinstance(out, list) else str(out)
        lead_predictions.append({"id": paragraph["id"], "output_text": joined})
    (HERE / "harness/multisentence-predictions-lead-onnx.json").write_text(
        json.dumps(
            {"system": "lead-onnx", "predictions": lead_predictions}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"rules + lead-onnx predictions written for {len(paragraphs)} paragraphs")


if __name__ == "__main__":
    sys.exit(main())
