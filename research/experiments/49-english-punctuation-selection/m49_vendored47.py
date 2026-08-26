# M49 - vendored punct-cap-seg-47 with the ENGLISH research label map
# (EXPERIMENTAL; shipped v1 Hindi scope untouched) run over
# en-punct-eval@v1, emitting the same predictions format.
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "services/stt-runtime/src")
sys.path.insert(0, "packages/runtime-contract/src")
sys.path.insert(0, "ml/evaluation/src")

from intelliai_evaluation.punctuation import (
    invariant_holds,
    strip_punctuation_for_input,
)
from intelliai_stt_runtime.engines import punctuation as punct

punct.SUPPORTED_MARKS = (".", ",", "?", "!")
punct.POST_LABEL_MAP = {
    "<NULL>": None,
    ".": ".",
    ",": ",",
    "?": "?",
    "？": "?",  # noqa: RUF001 - the model's actual label string
    "，": ",",  # noqa: RUF001
    "。": ".",
    "、": ",",
    "・": None,
    "।": ".",
    "؟": "?",
    "،": ",",
    ";": None,
    "።": ".",
    "፣": ",",
    "፧": "?",
}

DATASET = Path("ml/evaluation/punctuation/datasets/en-punct-eval-v1.json")
data = json.loads(DATASET.read_text(encoding="utf-8"))

restorer = punct.PunctuationRestorer(
    Path("models/punct-cap-seg-47/v1"), languages=["en"], timeout_ms=60000
)
preds, bad = [], 0
for row in data["rows"]:
    source_input = strip_punctuation_for_input(row["reference_text"])
    marks = restorer._predict_marks(source_input.split())
    out = punct.apply_marks(source_input, marks)
    ok = invariant_holds(source_input, out)
    if not ok:
        bad += 1
    preds.append({"id": row["id"], "input": source_input, "predicted_text": out, "invariant": ok})

payload = {
    "system": "vendored47-en-map",
    "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
    "invariant_failures": bad,
    "predictions": preds,
}
Path(sys.argv[1]).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
print("vendored47 done:", len(preds), "rows,", bad, "invariant failures")
