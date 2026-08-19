"""M29A — lead-model predictor (research instrument, scratch venv only).

Runs the pinned punctuation-restoration candidate on the harness inputs and
writes predictions for the repo-side scorer. The model executes ONLY inside
the M28/M29A scratch venv (punctuators + onnxruntime); nothing is added to
any product environment.

Model identity (verified against the Hugging Face API and the local cache
snapshot before every run):
    repo      1-800-BAD-CODE/punct_cap_seg_47_language
    revision  1b9d51fc7989ebc61e844d407d9dadd08ff4ba28
    license   Apache-2.0
    files     punct_cap_seg_47lang.onnx + spe_unigram_64k_lowercase_47lang.model
              (full sha256 values live ONLY in the EXPECTED_* constants below
              and are asserted against the cache before every run)

NOTE (corrects the M28 doc): the `punctuators` alias "pcs_47lang" resolves to
THIS repo, not to 1-800-BAD-CODE/xlm-roberta_punctuation_fullstop_truecase as
the M28 document stated. The M28 tiny benchmark therefore already ran this
model; the identity above is the one all M29A evidence pins.

Run with PYTHONIOENCODING=utf-8 inside the scratch venv.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

EXPECTED_REVISION = "1b9d51fc7989ebc61e844d407d9dadd08ff4ba28"
EXPECTED_ONNX_SHA256 = "640d91c06b7cc5b3e065c12a7097188378aad3bc11568ff1d72c4c0a2acb0df4"
EXPECTED_SPM_SHA256 = "1bc15b6e5fd80dfac9999582ce3efcad2ac1f7cf4e0e9769b329f5de9ca5af47"
CACHE = Path(
    "C:/Users/VIKASHAN TECHNOLOGIE/.cache/huggingface/hub/"
    "models--1-800-BAD-CODE--punct_cap_seg_47_language"
)


def verify_identity() -> dict:
    snapshots = sorted((CACHE / "snapshots").iterdir())
    if [s.name for s in snapshots] != [EXPECTED_REVISION]:
        msg = f"cache snapshot mismatch: {[s.name for s in snapshots]}"
        raise SystemExit(msg)
    snap = snapshots[0]
    checks = {}
    for name, expected in (
        ("punct_cap_seg_47lang.onnx", EXPECTED_ONNX_SHA256),
        ("spe_unigram_64k_lowercase_47lang.model", EXPECTED_SPM_SHA256),
    ):
        actual = hashlib.sha256((snap / name).read_bytes()).hexdigest()
        if actual != expected:
            msg = f"sha256 mismatch for {name}: {actual}"
            raise SystemExit(msg)
        checks[name] = actual
    return {
        "repo": "1-800-BAD-CODE/punct_cap_seg_47_language",
        "revision": EXPECTED_REVISION,
        "license": "Apache-2.0",
        "verified_sha256": checks,
    }


def main() -> None:
    identity = verify_identity()
    print("identity verified:", identity["revision"])

    inputs_path = HERE / "harness" / "inputs.json"
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    rows = inputs["rows"]

    t0 = time.perf_counter()
    from punctuators.models import PunctCapSegModelONNX

    model = PunctCapSegModelONNX.from_pretrained("pcs_47lang")
    load_seconds = round(time.perf_counter() - t0, 2)
    print(f"model loaded in {load_seconds}s")

    texts = [r["input_text"] for r in rows]
    t0 = time.perf_counter()
    outputs = model.infer(texts)
    infer_seconds = round(time.perf_counter() - t0, 2)

    predictions = []
    for row, out in zip(rows, outputs, strict=True):
        joined = " ".join(out) if isinstance(out, list) else str(out)
        predictions.append({"id": row["id"], "output_text": joined})

    out_path = HERE / "harness" / "predictions-lead-onnx.json"
    out_path.write_text(
        json.dumps(
            {
                "experiment": "29a-hindi-punctuation-eval",
                "system": "lead-onnx",
                "model_identity": identity,
                "dataset": inputs["dataset"],
                "dataset_sha256": inputs["dataset_sha256"],
                "model_load_seconds": load_seconds,
                "batch_inference_seconds": infer_seconds,
                "rows": len(predictions),
                "predictions": predictions,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"lead-onnx: {len(predictions)} predictions in {infer_seconds}s -> {out_path.name}")


if __name__ == "__main__":
    sys.exit(main())
