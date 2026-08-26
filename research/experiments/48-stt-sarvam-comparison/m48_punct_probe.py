# M48 Phase 15 — EXPERIMENTAL research probe: the SAME pinned
# punct-cap-seg-47 model + word-copy wrapper, with an ENGLISH label map
# (v1 product scope is Hindi: danda/comma/question only, "." dropped).
# The patch lives ONLY in this research process; production code and
# the shipped v1 semantics are untouched. Output is labeled
# EXPERIMENTAL — it is NOT a shipped capability.
import sys
from pathlib import Path

sys.path.insert(0, "services/stt-runtime/src")
sys.path.insert(0, "packages/runtime-contract/src")

from intelliai_stt_runtime.engines import punctuation as punct

# English research scope: periods kept, danda mapped to period.
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

raw = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
restorer = punct.PunctuationRestorer(
    Path("models/punct-cap-seg-47/v1"),
    languages=["en"],
    timeout_ms=30000,
)
marks = restorer._predict_marks(raw.split())
punctuated = punct.apply_marks(raw, marks)
if not punct.invariant_holds(raw, punctuated):
    raise SystemExit("word-preservation invariant broke")
Path(sys.argv[2]).write_text(punctuated, encoding="utf-8")
print(punctuated[:400])
print("...PUNCT-PROBE-DONE, invariant held, words unchanged")
