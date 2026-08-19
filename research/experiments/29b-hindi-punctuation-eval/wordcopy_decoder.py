"""M29B — research-only WORD-COPY decoder for the pinned punctuation model.

The M29A finding: the `punctuators` pipeline reconstructs output text from
sentencepiece ids, and uppercase/rare Latin tokens come back as `<unk>` —
word destruction (10/265 benchmark rows, the email probe). The classifier
HEADS were never the problem; the text reconstruction was.

This decoder never asks the tokenizer to write text:

    input words ──(casefolded pieces)──▶ ONNX model ──▶ post-mark label
                                                          per word
    output = apply_marks(input text, predicted marks)   ← words VERBATIM

Design, verified against the installed `punctuators` source and the model's
config.yaml (research/experiments/29b evidence):
  - the ONNX graph takes {"input_ids": [batch, seq]} with BOS/EOS and
    returns ARGMAXED label ids for 4 heads (pre, post, cap, seg)
  - post_labels (config.yaml) include । . , ? plus fullwidth/Arabic/CJK
    variants; there is NO "!" label — the model cannot predict exclamation
  - the sentencepiece model is lowercase-trained; the upstream pipeline
    encodes RAW text, so uppercase becomes <unk> pieces. We casefold before
    encoding (matching training) — predictions improve AND the original
    casing survives because output words are copies of the input.
  - per-word alignment: each word is encoded separately (sentencepiece
    never merges across whitespace); the word's mark is the post-head
    prediction at its LAST piece.
  - windows: max_length 128 incl. BOS/EOS; long texts run in word-aligned
    windows with an 8-word overlap, keeping predictions from the window
    core (first window keeps its head; later windows drop the overlap).

Foreign-script mark variants (fullwidth/CJK/Arabic forms) are normalized
to the local equivalent per POST_LABEL_MAP; unsupported labels (semicolon,
Ethiopic marks, middle dot) are dropped. The final write is
`intelliai_evaluation.punctuation.apply_marks`, so the word-preservation
invariant holds BY CONSTRUCTION and is still asserted after every call.

Research instrument only — runs in the scratch venv; never imported by
product code. PYTHONIOENCODING=utf-8.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import onnxruntime as ort
import yaml
from sentencepiece import SentencePieceProcessor

from intelliai_evaluation.punctuation import (
    SUPPORTED_MARKS,
    apply_marks,
    invariant_holds,
)

EXPECTED_REVISION = "1b9d51fc7989ebc61e844d407d9dadd08ff4ba28"
EXPECTED_ONNX_SHA256 = "640d91c06b7cc5b3e065c12a7097188378aad3bc11568ff1d72c4c0a2acb0df4"
EXPECTED_SPM_SHA256 = "1bc15b6e5fd80dfac9999582ce3efcad2ac1f7cf4e0e9769b329f5de9ca5af47"
CACHE = Path(
    "C:/Users/VIKASHAN TECHNOLOGIE/.cache/huggingface/hub/"
    "models--1-800-BAD-CODE--punct_cap_seg_47_language"
)

#: config.yaml post-label -> our supported mark (None = drop).
POST_LABEL_MAP: dict[str, str | None] = {
    "<NULL>": None,
    ".": ".",
    ",": ",",
    "?": "?",
    "？": "?",  # noqa: RUF001 — the model's actual label string
    "，": ",",  # noqa: RUF001
    "。": ".",
    "、": ",",
    "・": None,
    "।": "।",
    "؟": "?",
    "،": ",",
    ";": None,
    "።": None,
    "፣": None,
    "፧": None,
}

WINDOW_OVERLAP_WORDS = 8


class WordCopyPunctuator:
    """Predict marks with the pinned ONNX model; write with apply_marks."""

    def __init__(self) -> None:
        snap = CACHE / "snapshots" / EXPECTED_REVISION
        if not snap.is_dir():
            msg = f"pinned snapshot missing: {snap}"
            raise SystemExit(msg)
        onnx_path = snap / "punct_cap_seg_47lang.onnx"
        spm_path = snap / "spe_unigram_64k_lowercase_47lang.model"
        for path, expected in ((onnx_path, EXPECTED_ONNX_SHA256), (spm_path, EXPECTED_SPM_SHA256)):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                msg = f"sha256 mismatch for {path.name}: {actual}"
                raise SystemExit(msg)
        config = yaml.safe_load((snap / "config.yaml").read_text(encoding="utf-8"))
        self.post_labels: list[str] = list(config["post_labels"])
        self.max_length: int = int(config["max_length"])
        unknown = set(self.post_labels) - set(POST_LABEL_MAP)
        if unknown:
            msg = f"config carries unmapped post labels: {sorted(unknown)}"
            raise SystemExit(msg)
        self.sp = SentencePieceProcessor(str(spm_path))
        self.session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    def _pieces_per_word(self, words: list[str]) -> list[list[int]]:
        pieces = []
        for word in words:
            ids = self.sp.EncodeAsIds(word.casefold())
            pieces.append(ids if ids else [self.sp.unk_id()])
        return pieces

    def predict_marks(self, text: str) -> list[list[str]]:
        """Marks per slot (len(words)+1; slot 0 always empty — post-marks only)."""
        words = text.split()
        if not words:
            return [[]]
        pieces = self._pieces_per_word(words)
        budget = self.max_length - 2  # BOS/EOS
        marks: list[list[str]] = [[] for _ in range(len(words) + 1)]

        start = 0  # first word whose prediction this window must produce
        while start < len(words):
            window_start = max(0, start - (WINDOW_OVERLAP_WORDS if start else 0))
            ids: list[int] = []
            last_piece_index: dict[int, int] = {}
            end = window_start
            while end < len(words) and len(ids) + len(pieces[end]) <= budget:
                ids.extend(pieces[end])
                last_piece_index[end] = len(ids) - 1
                end += 1
            if end == start:  # single word longer than the budget
                ids = pieces[start][:budget]
                last_piece_index = {start: len(ids) - 1}
                end = start + 1
            input_ids = [[self.sp.bos_id(), *ids, self.sp.eos_id()]]
            outputs = self.session.run(None, {"input_ids": input_ids})
            post = outputs[1][0]  # [seq] argmaxed label ids; strip BOS offset below
            for word_index in range(start, end):
                label_id = int(post[last_piece_index[word_index] + 1])  # +1 for BOS
                mark = POST_LABEL_MAP[self.post_labels[label_id]]
                if mark is not None and mark in SUPPORTED_MARKS:
                    marks[word_index + 1] = [mark]
            start = end
        return marks

    def punctuate(self, text: str) -> str:
        result = apply_marks(text, self.predict_marks(text))
        if not invariant_holds(text, result):  # structurally impossible; assert anyway
            msg = f"invariant violated for input: {text[:80]!r}"
            raise AssertionError(msg)
        return result


if __name__ == "__main__":
    decoder = WordCopyPunctuator()
    for probe in (
        "रोलैंडो मेंडोज़ा ने अपनी M16 राइफल से पर्यटकों के ऊपर फायर किया",
        "इसे केमिकल का pH कहा जाता है आप जूस से एक संकेतक बना सकते हैं",
        "वाहन 1200 GMT पर दुर्घटनास्थल से दूर ले जाया गया",
        "मुझे अपना बायोडाटा support@example.com पर भेज दीजिए",
        "क्या आप कल ऑफिस आओगे",
    ):
        print(decoder.punctuate(probe))
