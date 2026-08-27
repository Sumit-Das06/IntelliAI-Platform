"""English punctuation stage (Milestone 50) — kredor INT8 ONNX.

The M30 laws, applied to English through the SAME word-copy core
(imported, never duplicated): the stage may only APPEND supported
marks to copied words; every stage problem yields the raw transcript;
gating follows the route-resolved language; identity is pinned
byte-for-byte and seeded, never downloaded.

v1 mark scope (M49/M50 contract): period (.), comma (,), question
mark (?). The pinned model's remaining labels ("-", ":") are DROPPED —
out of scope by decision, never silently emitted.

Model: kredor/punctuate-all @ 0fe37019de3f5e4fbd83289fd94e07fa588e47df,
converted to INT8 ONNX (weight-only dynamic quantization; provenance
travels INSIDE the artifact as provenance.json, hash-pinned below).

Tokenizer: the XLM-RoBERTa SentencePiece model (kredor is an
xlm-roberta-base fine-tune; tokenizer unchanged) with the fairseq id
law — ``hf_id = spm_id + 1``, spm-unk → 3, <s>=0, </s>=2 — PROVEN
equivalent to the HF tokenizer with 0 mismatches over every unique
word of the frozen en-punct-eval@v1 set (M50 Phase 2).
"""

from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

import structlog

from intelliai_runtime_contract import TranscriptionResult
from intelliai_runtime_core import ArtifactFile, ArtifactSpec
from intelliai_stt_runtime.engines.punctuation import (
    PunctuationStageError,
    apply_marks,
    invariant_holds,
    redistribute_segments,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger(__name__)

PUNCTUATION_EN_ARTIFACT: Final = "punct-en-kredor"

ONNX_EN_FILENAME: Final = "model.int8.onnx"
SPM_EN_FILENAME: Final = "sentencepiece.bpe.model"
PROVENANCE_FILENAME: Final = "provenance.json"

# Deliberately non-resolvable: the artifact distributes by SEEDING into
# the model volume (the M30 law); the store hash-verifies at startup.
_SEEDED_BASE: Final = "https://artifacts.intelliai.invalid/m50-en-punctuation"

PUNCTUATION_EN_FILES: Final = ArtifactSpec(
    artifact=PUNCTUATION_EN_ARTIFACT,
    version=1,
    files=(
        ArtifactFile(
            filename=ONNX_EN_FILENAME,
            url=f"{_SEEDED_BASE}/{ONNX_EN_FILENAME}",
            sha256="b0d8d68ca907012e832282920c43ce8342c7920022ec9e9c125498de9478a925",
        ),
        ArtifactFile(
            filename=SPM_EN_FILENAME,
            url=f"{_SEEDED_BASE}/{SPM_EN_FILENAME}",
            sha256="cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
        ),
        ArtifactFile(
            filename=PROVENANCE_FILENAME,
            url=f"{_SEEDED_BASE}/{PROVENANCE_FILENAME}",
            sha256="bb74cc2440f342a69e3cbec427f7627769fd39abad6f7f1b3a1fbc72402374c3",
        ),
    ),
)

#: The pinned model's label table in label-id order (kredor config.json,
#: recorded inside the hash-verified provenance.json so table and
#: weights cannot drift apart — the M30 pattern).
EN_POST_LABELS: Final = ("0", ".", ",", "?", "-", ":")

#: v1 product marks for English.
EN_SUPPORTED_MARKS: Final = (".", ",", "?")

#: label → v1 mark (None = drop). "-" and ":" are out of scope.
EN_LABEL_MAP: Final[dict[str, str | None]] = {
    "0": None,
    ".": ".",
    ",": ",",
    "?": "?",
    "-": None,
    ":": None,
}

# The M49-validated windowing (never changed casually: the harness that
# produced the selection evidence used exactly these).
_WINDOW_WORDS: Final = 180
_OVERLAP_WORDS: Final = 20
_MAX_PIECES: Final = 510  # model context 512 incl. <s>/</s>

# XLM-R fairseq specials (hf ids).
_BOS_ID: Final = 0
_EOS_ID: Final = 2
_UNK_ID: Final = 3
_FAIRSEQ_OFFSET: Final = 1

#: Marks whose presence at the END of any token means the ENGINE already
#: punctuated this transcript. Whisper emits full punctuation on clean
#: read speech (M51 browser E2E finding: the stage then doubled marks —
#: "Sumit.."), while spontaneous speech arrives bare — exactly the gap
#: this stage exists for. Token-FINAL only, so intra-word marks
#: ("2.5", "example.com", "test@example.com") never count as engine
#: punctuation.
_ENGINE_MARKS: Final = frozenset(".,?!;:")


def engine_already_punctuated(words: Sequence[str]) -> bool:
    """True when the raw transcript already carries sentence punctuation."""
    return any(word and word[-1] in _ENGINE_MARKS for word in words)


@dataclass(frozen=True)
class EnStageOutcome:
    """What the stage did: the (possibly rewritten) result + timing."""

    result: TranscriptionResult
    applied: bool
    elapsed_ms: float


class EnPunctuationRestorer:
    """One shared instance per process; requests never load models."""

    def __init__(
        self,
        local_dir: Path,
        *,
        languages: Sequence[str],
        timeout_ms: float,
        max_workers: int = 2,
    ) -> None:
        # The store already hash-verified every file this startup; the
        # provenance re-check below additionally proves the HARDCODED
        # label table corresponds to these exact weights.
        provenance_path = local_dir / PROVENANCE_FILENAME
        actual = hashlib.sha256(provenance_path.read_bytes()).hexdigest()
        expected = next(
            file.sha256
            for file in PUNCTUATION_EN_FILES.files
            if file.filename == PROVENANCE_FILENAME
        )
        if actual != expected:
            msg = "english punctuation provenance drifted from the pinned identity"
            raise PunctuationStageError(msg)

        import onnxruntime
        import sentencepiece

        self._sp = sentencepiece.SentencePieceProcessor(str(local_dir / SPM_EN_FILENAME))
        self._session = onnxruntime.InferenceSession(
            str(local_dir / ONNX_EN_FILENAME), providers=["CPUExecutionProvider"]
        )
        self._languages = frozenset(tag.strip().casefold() for tag in languages if tag.strip())
        self._timeout_seconds = timeout_ms / 1000.0
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="punctuation-en"
        )

    def close(self) -> None:
        executor: ThreadPoolExecutor | None = getattr(self, "_executor", None)
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def applies_to(self, requested_language: str | None) -> bool:
        """Gate on the ROUTE the gateway resolved (the requested language),
        never on a client's 'auto': no language, no stage."""
        if requested_language is None:
            return False
        return requested_language.strip().casefold() in self._languages

    # -- tokenization ------------------------------------------------------

    def _word_ids(self, word: str) -> list[int]:
        """SentencePiece pieces mapped by the PROVEN fairseq law."""
        ids: list[int] = []
        for piece in self._sp.EncodeAsPieces(word):
            piece_id = self._sp.PieceToId(piece)
            ids.append(_UNK_ID if piece_id == self._sp.unk_id() else piece_id + _FAIRSEQ_OFFSET)
        return ids or [_UNK_ID]

    # -- prediction --------------------------------------------------------

    def _predict_marks(self, words: list[str]) -> list[list[str]]:
        """Marks per slot (len(words)+1); post-marks only, M49 windowing."""
        import numpy as np

        marks: list[list[str]] = [[] for _ in range(len(words) + 1)]
        start = 0
        while start < len(words):
            base = max(0, start - (_OVERLAP_WORDS if start else 0))
            ids: list[int] = []
            last_piece_index: dict[int, int] = {}
            index = base
            while index < len(words) and index < start + _WINDOW_WORDS:
                piece_ids = self._word_ids(words[index])
                if len(ids) + len(piece_ids) > _MAX_PIECES:
                    break
                ids.extend(piece_ids)
                last_piece_index[index] = len(ids)  # +1 below accounts for <s>
                index += 1
            if index == start:  # a single word larger than the whole window
                ids = self._word_ids(words[start])[:_MAX_PIECES]
                last_piece_index = {start: len(ids)}
                index = start + 1
            input_ids = np.array([[_BOS_ID, *ids, _EOS_ID]], dtype=np.int64)
            attention = np.ones_like(input_ids)
            logits = self._session.run(None, {"input_ids": input_ids, "attention_mask": attention})[
                0
            ][0]
            predicted = logits.argmax(-1)
            for word_index, piece_pos in last_piece_index.items():
                if word_index < start and start > 0:
                    continue  # overlap region: the earlier window already decided
                try:
                    label = EN_POST_LABELS[int(predicted[piece_pos])]
                except IndexError as exc:  # malformed prediction
                    msg = "prediction outside the pinned label table"
                    raise PunctuationStageError(msg) from exc
                mark = EN_LABEL_MAP[label]
                if mark is not None:
                    marks[word_index + 1] = [mark]
            start = index
        return marks

    # -- the stage ----------------------------------------------------------

    def restore(self, result: TranscriptionResult) -> TranscriptionResult:
        """Rewrite text+segments with marks; words and timings untouched."""
        raw = result.text
        if not raw.strip():
            return result  # silence stays silent — nothing to punctuate
        words = raw.split()
        if engine_already_punctuated(words):
            # The engine's own punctuation stands; restoring on top of it
            # would double marks. No stage effect, raw_text stays None.
            return result
        future = self._executor.submit(self._predict_marks, words)
        try:
            marks = future.result(timeout=self._timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            msg = "english punctuation stage timed out"
            raise PunctuationStageError(msg) from exc
        punctuated = apply_marks(raw, marks, allowed=EN_SUPPORTED_MARKS)
        if not invariant_holds(raw, punctuated):  # structurally impossible
            msg = "word-preservation invariant violated"
            raise PunctuationStageError(msg)
        if punctuated == raw:
            return result  # no marks predicted; no stage effect to record
        return TranscriptionResult(
            text=punctuated,
            language=result.language,
            duration_seconds=result.duration_seconds,
            segments=redistribute_segments(result.segments, punctuated),
            raw_text=raw,
        )

    def restore_safely(
        self, result: TranscriptionResult, requested_language: str | None
    ) -> EnStageOutcome:
        """FAIL-OPEN seam: every stage problem yields the raw result."""
        started = time.perf_counter()
        if not self.applies_to(requested_language):
            return EnStageOutcome(result=result, applied=False, elapsed_ms=0.0)
        try:
            restored = self.restore(result)
        except Exception as exc:
            logger.warning(
                "punctuation_en_stage_failed",
                reason=type(exc).__name__,
                transcript_chars=len(result.text),
            )
            return EnStageOutcome(
                result=result,
                applied=False,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )
        return EnStageOutcome(
            result=restored,
            applied=restored.raw_text is not None,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )


def load_punctuation_en(
    local_dir: Path, *, languages: Sequence[str], timeout_ms: float
) -> EnPunctuationRestorer:
    """Loader called at startup AFTER the store hash-verified local_dir."""
    return EnPunctuationRestorer(local_dir, languages=languages, timeout_ms=timeout_ms)
