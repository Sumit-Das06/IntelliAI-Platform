"""Hindi punctuation restoration: predict marks, copy words, never rewrite.

Milestone 30, on the M28→M29C evidence chain. The stage runs AFTER the
final STT transcript exists (post chunk-merge for long audio) and obeys
one law with no exceptions:

    the model predicts WHERE marks go; the WORDS are copied from the
    input verbatim — the tokenizer never writes transcript text.

That word-copy contract is what M29B proved: the upstream reconstruction
destroyed rare Latin tokens (`M16 → <Unk>16`); copying input words makes
the word-preservation invariant hold BY CONSTRUCTION, and this module
still asserts it after every restoration (defense in depth, M29C
semantics: NFC → casefold → Cf deleted → category P → space → collapse).

Failure posture is FAIL-OPEN: any stage problem (load, inference,
malformed prediction, timeout, invariant) must yield the RAW transcript,
never an STT failure. The caller-facing seam for that is
``restore_safely``; everything it logs is an internal diagnostic and no
customer-visible surface changes on failure.

v1 mark scope (founder-approved): danda (।), comma (,), question mark (?).
The pinned model has NO exclamation label, and "." is out of the v1 Hindi
scope — predictions of unsupported labels are DROPPED, never remapped
into inventions.

Identity is pinned like every other artifact: the ONNX, sentencepiece,
and config files are seeded (deliberately non-downloadable URL), the
store hash-verifies them at startup, and the label table below is proven
against the pinned config.yaml hash at load. Mirrors the evaluation
plane's `punct_slots@v1` semantics; the planes stay import-separated by
law, so the small pure core is duplicated here with its own tests.
"""

from __future__ import annotations

import hashlib
import time
import unicodedata
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import structlog

from intelliai_runtime_contract import TranscriptionResult, TranscriptionSegment
from intelliai_runtime_core import ArtifactFile, ArtifactSpec

logger = structlog.get_logger(__name__)

#: Artifact identity (internal; never appears on a public surface).
PUNCTUATION_ARTIFACT: Final = "punct-cap-seg-47"

ONNX_FILENAME: Final = "punct_cap_seg_47lang.onnx"
SPM_FILENAME: Final = "spe_unigram_64k_lowercase_47lang.model"
CONFIG_FILENAME: Final = "config.yaml"

# Deliberately non-resolvable: the artifact distributes by SEEDING into
# the model volume (same law as the E3 GGUFs); the store hash-verifies.
_SEEDED_BASE: Final = "https://artifacts.intelliai.invalid/m30-hi-punctuation"

PUNCTUATION_FILES: Final = ArtifactSpec(
    artifact=PUNCTUATION_ARTIFACT,
    version=1,
    files=(
        ArtifactFile(
            filename=ONNX_FILENAME,
            url=f"{_SEEDED_BASE}/{ONNX_FILENAME}",
            sha256="640d91c06b7cc5b3e065c12a7097188378aad3bc11568ff1d72c4c0a2acb0df4",
        ),
        ArtifactFile(
            filename=SPM_FILENAME,
            url=f"{_SEEDED_BASE}/{SPM_FILENAME}",
            sha256="1bc15b6e5fd80dfac9999582ce3efcad2ac1f7cf4e0e9769b329f5de9ca5af47",
        ),
        ArtifactFile(
            filename=CONFIG_FILENAME,
            url=f"{_SEEDED_BASE}/{CONFIG_FILENAME}",
            sha256="30eb8e05fcea3865828ab73f41fbba21dd7faf127a61950a706af9156f5b84f2",
        ),
    ),
)

#: The pinned model's post-label table, in label-id order. Hardcoded and
#: PROVEN at load: the config.yaml carrying this exact table is part of
#: the hash-verified artifact, so table and weights cannot drift apart.
POST_LABELS: Final = (
    "<NULL>",
    ".",
    ",",
    "?",
    "？",  # noqa: RUF001 — the model's actual label string
    "，",  # noqa: RUF001 — the model's actual label string
    "。",
    "、",
    "・",
    "।",
    "؟",
    "،",
    ";",
    "።",
    "፣",
    "፧",
)

#: v1 product marks. Everything else a label may say is dropped.
SUPPORTED_MARKS: Final = ("।", ",", "?")

#: label → v1 mark (None = drop). Foreign-script variants normalize to
#: the local equivalent; "." and "!"-less labels stay out of v1 scope.
POST_LABEL_MAP: Final[dict[str, str | None]] = {
    "<NULL>": None,
    ".": None,  # out of v1 scope (Hindi sentences end with danda)
    ",": ",",
    "?": "?",
    "？": "?",  # noqa: RUF001 — the model's actual label string
    "，": ",",  # noqa: RUF001
    "。": None,
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

_MAX_LENGTH: Final = 128  # model context incl. BOS/EOS (pinned config)
_WINDOW_OVERLAP_WORDS: Final = 8


class PunctuationStageError(RuntimeError):
    """Any stage-internal refusal. Always caught by restore_safely."""


# ── The pure word-copy core (mirrors punct_slots@v1) ─────────────────────


def depunct(text: str) -> str:
    """The invariant transform: NFC, casefold, Cf deleted, P→space, collapse."""
    folded = unicodedata.normalize("NFC", text).casefold()
    kept: list[str] = []
    for ch in folded:
        category = unicodedata.category(ch)
        if category == "Cf":
            continue
        kept.append(" " if category.startswith("P") else ch)
    return " ".join("".join(kept).split())


def invariant_holds(input_text: str, output_text: str) -> bool:
    """Punctuation may be added; words may never change."""
    return depunct(input_text) == depunct(output_text)


def apply_marks(
    text: str,
    marks_per_slot: Sequence[Sequence[str]],
    allowed: Sequence[str] = SUPPORTED_MARKS,
) -> str:
    """Original whitespace tokens verbatim + supported marks appended.

    ``marks_per_slot`` has ``len(tokens) + 1`` entries (slot 0 = before the
    first token). Word changes are impossible by construction: tokens are
    copies, and every supported mark is category P, so it depuncts away.
    ``allowed`` defaults to the Hindi v1 scope; the English stage (M50)
    passes its own scope — the copy law itself never varies.
    """
    tokens = text.split()
    if len(marks_per_slot) != len(tokens) + 1:
        msg = f"need {len(tokens) + 1} slots for {len(tokens)} tokens"
        raise PunctuationStageError(msg)
    for slot in marks_per_slot:
        for mark in slot:
            if mark not in allowed:
                msg = f"unsupported mark {mark!r}"
                raise PunctuationStageError(msg)
    if not tokens:
        return "".join(marks_per_slot[0])
    decorated = [
        token + "".join(marks) for token, marks in zip(tokens, marks_per_slot[1:], strict=True)
    ]
    prefix = "".join(marks_per_slot[0])
    if prefix:
        decorated[0] = prefix + decorated[0]
    return " ".join(decorated)


def redistribute_segments(
    segments: tuple[TranscriptionSegment, ...], punctuated_text: str
) -> tuple[TranscriptionSegment, ...]:
    """Push punctuated words back into the segments, timings untouched.

    The engines guarantee ``" ".join(segment texts) == text`` by
    construction; the word-copy stage preserves the word COUNT exactly, so
    re-slicing the punctuated words by each segment's original word count
    keeps that law intact — text changes, timing and segmentation never do.
    """
    punctuated_words = punctuated_text.split()
    expected = sum(len(segment.text.split()) for segment in segments)
    if expected != len(punctuated_words):
        msg = "segment word count no longer matches the transcript"
        raise PunctuationStageError(msg)
    rebuilt: list[TranscriptionSegment] = []
    cursor = 0
    for segment in segments:
        count = len(segment.text.split())
        rebuilt.append(
            TranscriptionSegment(
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                text=" ".join(punctuated_words[cursor : cursor + count]),
            )
        )
        cursor += count
    return tuple(rebuilt)


# ── The model wrapper ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class StageOutcome:
    """What the stage did: the (possibly rewritten) result + timing."""

    result: TranscriptionResult
    applied: bool
    elapsed_ms: float


class PunctuationRestorer:
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
        # config re-check below additionally proves the HARDCODED label
        # table corresponds to these exact weights.
        config_path = local_dir / CONFIG_FILENAME
        actual = hashlib.sha256(config_path.read_bytes()).hexdigest()
        expected = next(
            file.sha256 for file in PUNCTUATION_FILES.files if file.filename == CONFIG_FILENAME
        )
        if actual != expected:
            msg = "punctuation config drifted from the pinned label table"
            raise PunctuationStageError(msg)

        import onnxruntime
        import sentencepiece

        self._sp = sentencepiece.SentencePieceProcessor(str(local_dir / SPM_FILENAME))
        self._session = onnxruntime.InferenceSession(
            str(local_dir / ONNX_FILENAME), providers=["CPUExecutionProvider"]
        )
        self._languages = frozenset(tag.strip().casefold() for tag in languages if tag.strip())
        self._timeout_seconds = timeout_ms / 1000.0
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="punctuation"
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

    # -- prediction ------------------------------------------------------

    def _pieces_per_word(self, words: list[str]) -> list[list[int]]:
        pieces: list[list[int]] = []
        for word in words:
            ids = list(self._sp.EncodeAsIds(word.casefold()))
            pieces.append(ids if ids else [self._sp.unk_id()])
        return pieces

    def _predict_marks(self, words: list[str]) -> list[list[str]]:
        """Marks per slot (len(words)+1; slot 0 stays empty — post-marks only)."""
        pieces = self._pieces_per_word(words)
        budget = _MAX_LENGTH - 2  # BOS/EOS
        marks: list[list[str]] = [[] for _ in range(len(words) + 1)]
        start = 0
        while start < len(words):
            window_start = max(0, start - (_WINDOW_OVERLAP_WORDS if start else 0))
            ids: list[int] = []
            last_piece_index: dict[int, int] = {}
            end = window_start
            while end < len(words) and len(ids) + len(pieces[end]) <= budget:
                ids.extend(pieces[end])
                last_piece_index[end] = len(ids) - 1
                end += 1
            if end == start:  # a single word larger than the whole window
                ids = pieces[start][:budget]
                last_piece_index = {start: len(ids) - 1}
                end = start + 1
            input_ids = [[self._sp.bos_id(), *ids, self._sp.eos_id()]]
            outputs = self._session.run(None, {"input_ids": input_ids})
            post = outputs[1][0]  # argmaxed post-label ids; +1 skips BOS
            for word_index in range(start, end):
                label_id = int(post[last_piece_index[word_index] + 1])
                try:
                    label = POST_LABELS[label_id]
                except IndexError as exc:  # malformed prediction
                    msg = "prediction outside the pinned label table"
                    raise PunctuationStageError(msg) from exc
                mark = POST_LABEL_MAP[label]
                if mark is not None:
                    marks[word_index + 1] = [mark]
            start = end
        return marks

    # -- the stage -------------------------------------------------------

    def restore(self, result: TranscriptionResult) -> TranscriptionResult:
        """Rewrite text+segments with marks; words and timings untouched."""
        raw = result.text
        if not raw.strip():
            return result  # silence stays silent — nothing to punctuate
        words = raw.split()
        future = self._executor.submit(self._predict_marks, words)
        try:
            marks = future.result(timeout=self._timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            msg = "punctuation stage timed out"
            raise PunctuationStageError(msg) from exc
        punctuated = apply_marks(raw, marks)
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
    ) -> StageOutcome:
        """FAIL-OPEN seam: every stage problem yields the raw result.

        STT success must never become a punctuation failure — the caller
        gets the original result back and the request stays a 200.
        """
        started = time.perf_counter()
        if not self.applies_to(requested_language):
            return StageOutcome(result=result, applied=False, elapsed_ms=0.0)
        try:
            restored = self.restore(result)
        except Exception as exc:
            logger.warning(
                "punctuation_stage_failed",
                reason=type(exc).__name__,
                transcript_chars=len(result.text),
            )
            return StageOutcome(
                result=result,
                applied=False,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )
        return StageOutcome(
            result=restored,
            applied=restored.raw_text is not None,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )


def load_punctuation(
    local_dir: Path, *, languages: Sequence[str], timeout_ms: float
) -> PunctuationRestorer:
    """Loader called at startup AFTER the store hash-verified local_dir."""
    return PunctuationRestorer(local_dir, languages=languages, timeout_ms=timeout_ms)
