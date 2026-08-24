"""Subprocess-isolated Hindi G2P (M39, policy: M3 §8 / M35 posture).

Hindi has no dictionary G2P in misaki — upstream Kokoro phonemizes
Hindi through espeak-ng. The GPL question stays settled by shape: the
same pinned espeak-ng BINARY behind the same exec boundary as the M35
English OOV fallback, now speaking ``-v hi`` at SENTENCE level (Hindi
G2P is whole-segment phonemization, not per-word rescue).

Safety laws (identical to M35):
- **argv is constant** — user text NEVER becomes an argument; segments
  go through stdin, one per line.
- **timeout-bounded** — a hung binary fails THIS request (G2P is the
  only pronunciation source for Hindi: no dictionary to fall back to),
  never the process.
- **pinned** — absolute path + version-prefix gate at construction
  (composition time), so a wrong binary refuses to START.
- **no downloads** — binary + data ship in the image (apt).

The IPA -> Kokoro transform below is adapted from misaki's
``EspeakG2P`` (hexgrad/misaki, Apache-2.0) — the exact table the Kokoro
Hindi voices were trained against. One CLI-vs-library difference is
handled explicitly: the library ties multi-glyph phonemes with ``^``;
the CLI emits U+0361 for affricates and NOTHING for diphthongs, so the
table is applied in both tied and untied forms (diphthongs only — a
bare vowel+glide pair inside a word is always one phoneme in espeak
output). Parity: 12/12 byte-identical against the upstream library on
the M39 fixture set (tests/fixtures/hi_g2p_parity.json).
"""

from __future__ import annotations

# ruff: noqa: RUF001 - this module is MADE of IPA glyphs;
# they are phoneme data, not lookalike typos.
import re
import subprocess
from pathlib import Path
from typing import Final

import structlog

from intelliai_tts_runtime.engines.espeak_fallback import validate_espeak_binary

logger = structlog.get_logger(__name__)

#: U+0361 COMBINING DOUBLE INVERTED BREVE — the CLI's tie for affricates.
_CLI_TIE = "͡"

#: misaki EspeakG2P.e2m verbatim (Apache-2.0), '^'-tied forms.
_HI_E2M_TIED: Final = sorted(
    {
        "a^ɪ": "I",
        "a^ʊ": "W",
        "d^z": "ʣ",
        "d^ʒ": "ʤ",
        "e^ɪ": "A",
        "o^ʊ": "O",
        "ə^ʊ": "Q",
        "s^s": "S",
        "t^s": "ʦ",
        "t^ʃ": "ʧ",
        "ɔ^ɪ": "Y",
    }.items()
)

#: The same diphthongs, untied — the CLI emits them without any tie.
#: Affricates are deliberately ABSENT here: adjacent stop+fricative
#: phonemes would be indistinguishable from a real affricate without
#: the tie, and the CLI does tie affricates (U+0361).
_HI_E2M_UNTIED: Final = sorted(
    {
        "aɪ": "I",
        "aʊ": "W",
        "eɪ": "A",
        "oʊ": "O",
        "əʊ": "Q",
        "ɔɪ": "Y",
    }.items(),
    key=lambda kv: -len(kv[0]),
)

#: espeak marks language switches (Latin tokens inside Devanagari) with
#: flags; upstream uses language_switch='remove-flags' — same effect.
_LANGUAGE_SWITCH = re.compile(r"\([a-z-]+\)")

#: Punctuation carried through to the phoneme string (prosody input for
#: the model) — the marks the upstream library preserves. Segments
#: between marks are phonemized; the marks are re-attached in order.
_SEGMENT_SPLIT: Final = re.compile(r"([;:,.!?…]+)")

_WHITESPACE: Final = re.compile(r"\s+")

_MAX_SEGMENT_CHARS: Final = 1000  # defensive; chunks are ≤300 chars upstream


def map_hindi_ipa_to_kokoro(ipa: str) -> str:
    """One espeak CLI IPA line -> the phoneme dialect Kokoro's Hindi
    voice packs were trained against (misaki EspeakG2P, hi)."""
    ps = _LANGUAGE_SWITCH.sub("", ipa).strip()
    ps = ps.replace(_CLI_TIE, "^")
    for old, new in _HI_E2M_TIED:
        ps = ps.replace(old, new)
    for old, new in _HI_E2M_UNTIED:
        ps = ps.replace(old, new)
    ps = ps.replace("^", "").replace("-", "")
    return _WHITESPACE.sub(" ", ps).strip()


class HindiG2PError(RuntimeError):
    """The subprocess could not phonemize this text. Hindi has no
    dictionary fallback, so the caller fails the REQUEST (internal
    error), never silently synthesizes wrong audio."""


class EspeakHindiG2P:
    """Devanagari text -> Kokoro Hindi phonemes through the pinned binary.

    One subprocess call per chunk: the chunk is split at preserved
    punctuation, every segment rides stdin (one per line), and the
    phonemized segments are reassembled with their marks — matching the
    upstream library's punctuation-preserving output format.
    """

    def __init__(
        self,
        binary: Path,
        *,
        version_prefix: str,
        timeout_seconds: float,
    ) -> None:
        self._argv = (str(binary), "-q", "--ipa", "-v", "hi")
        self._timeout = timeout_seconds
        self.version = validate_espeak_binary(
            binary, version_prefix=version_prefix, timeout_seconds=timeout_seconds
        )

    def phonemize(self, text: str) -> str:
        """Whole-chunk G2P, punctuation preserved. Raises HindiG2PError
        on any subprocess failure — never wrong audio, never a hang."""
        prepared = text.replace("।", ".").replace("॥", ".")
        pieces = [piece for piece in _SEGMENT_SPLIT.split(prepared) if piece.strip()]
        segments = [
            _WHITESPACE.sub(" ", piece).strip()
            for piece in pieces
            if not _SEGMENT_SPLIT.fullmatch(piece.strip())
        ]
        segments = [segment[:_MAX_SEGMENT_CHARS] for segment in segments]
        phonemized = self._phonemize_segments(segments)

        assembled: list[str] = []
        index = 0
        for piece in pieces:
            stripped = piece.strip()
            if _SEGMENT_SPLIT.fullmatch(stripped):
                if assembled:
                    assembled[-1] += stripped
                continue
            phonemes = phonemized[index]
            index += 1
            if phonemes:
                assembled.append(phonemes)
        return " ".join(assembled)

    def _phonemize_segments(self, segments: list[str]) -> list[str]:
        if not segments:
            return []
        try:
            # encoding pinned: IPA is UTF-8 regardless of container locale.
            result = subprocess.run(  # noqa: S603 — constant argv; text via stdin only
                list(self._argv),
                input="\n".join(segments) + "\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("hindi_g2p_failed", reason=exc.__class__.__name__)
            msg = "Hindi phonemization subprocess failed"
            raise HindiG2PError(msg) from exc
        if result.returncode != 0:
            logger.warning("hindi_g2p_failed", reason=f"exit {result.returncode}")
            msg = f"Hindi phonemization exited {result.returncode}"
            raise HindiG2PError(msg)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(lines) != len(segments):
            logger.warning(
                "hindi_g2p_failed",
                reason=f"line mismatch: {len(segments)} segments, {len(lines)} answers",
            )
            msg = "Hindi phonemization answered a different number of segments"
            raise HindiG2PError(msg)
        return [map_hindi_ipa_to_kokoro(line) for line in lines]
