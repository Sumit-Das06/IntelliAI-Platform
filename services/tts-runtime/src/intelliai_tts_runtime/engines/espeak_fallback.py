"""Subprocess-isolated espeak-ng OOV fallback (M35, policy: M3 §8).

The GPL question, settled by shape: espeak-ng runs as a pinned BINARY
behind an exec boundary — the ffmpeg posture the M3 license review named
defensible and M32 measured for phoneme parity. The GPL chain never
enters this process: no phonemizer, no espeakng-loader, no ctypes — the
license firewall in `kokoro.py` keeps banning them, and the isolation
suite keeps proving it. What crosses the boundary is words out, IPA in.

Safety laws (Phase 21):
- **argv is constant** — user text NEVER becomes an argument; words go
  through stdin, one per line, so no input can grow the command.
- **timeout-bounded** — a hung binary kills the fallback, never the
  request: failure returns {} and the engine keeps the dictionary-only
  behavior for those words (fail-open, logged).
- **pinned** — absolute binary path from config; the reported version
  must start with the pinned prefix or the engine refuses to START
  (a wrong phonemizer is a wrong pronunciation model, caught at boot,
  not in production audio).
- **no downloads** — the binary and its data ship in the image (apt),
  hash-stable per image digest.

The espeak-IPA -> Kokoro-alphabet mapping below is adapted from misaki's
``EspeakFallback`` (hexgrad/misaki, Apache-2.0) so the fallback speaks
the same phoneme dialect as the native G2P — M32's parity probe measured
these exact transform classes.
"""

from __future__ import annotations

# ruff: noqa: RUF001 - this module is MADE of IPA glyphs;
# they are phoneme data, not lookalike typos.
import re
import subprocess
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

#: Tie character espeak-ng's CLI emits between multi-glyph phonemes
#: (U+0361 COMBINING DOUBLE INVERTED BREVE); misaki's tables use '^'.
_CLI_TIE = "͡"

#: Adapted from misaki EspeakFallback.E2M (Apache-2.0), longest-first.
_E2M = sorted(
    {
        "ʔˌn̩": "ʔn",
        "ʔn̩": "ʔn",
        "a^ɪ": "I",
        "a^ʊ": "W",
        "d^ʒ": "ʤ",
        "e^ɪ": "A",
        "e": "A",
        "t^ʃ": "ʧ",
        "ɔ^ɪ": "Y",
        "ə^l": "ᵊl",
        "ʲo": "jo",
        "ʲə": "jə",
        "ʲ": "",
        "ɚ": "əɹ",
        "r": "ɹ",
        "x": "k",
        "ç": "k",
        "ɐ": "ə",
        "ɬ": "l",
        "̃": "",
    }.items(),
    key=lambda kv: -len(kv[0]),
)

_SYLLABIC_N = re.compile(r"(\S)̩")
_LANGUAGE_SWITCH = re.compile(r"\([a-z-]+\)")
_MAX_WORD_CHARS = 100


def map_ipa_to_kokoro(ipa: str) -> str:
    """espeak CLI IPA -> the phoneme alphabet the Kokoro vocab expects
    (misaki's US-English dialect; espeak >= 1.51 rules)."""
    ps = _LANGUAGE_SWITCH.sub("", ipa).strip()
    ps = ps.replace(_CLI_TIE, "^")
    for old, new in _E2M:
        ps = ps.replace(old, new)
    ps = _SYLLABIC_N.sub(r"ᵊ\1", ps).replace(chr(809), "")
    ps = ps.replace("o^ʊ", "O")
    ps = ps.replace("ɜːɹ", "ɜɹ")
    ps = ps.replace("ɜː", "ɜɹ")
    ps = ps.replace("ɪə", "iə")
    ps = ps.replace("ː", "")
    ps = ps.replace("o", "ɔ")
    ps = ps.replace("ɾ", "T").replace("ʔ", "t")
    return ps.replace("^", "")


def validate_espeak_binary(binary: Path, *, version_prefix: str, timeout_seconds: float) -> str:
    """The startup gate both espeak components share: absolute pinned
    path, binary present, reported version under the pinned prefix.
    Returns the reported version; raises on any deviation — a wrong
    phonemizer is a wrong pronunciation model, caught at boot."""
    if not binary.is_absolute():
        msg = f"espeak binary path must be absolute, got {binary!r}"
        raise ValueError(msg)
    if not binary.exists():
        msg = f"espeak binary not found at {binary}"
        raise FileNotFoundError(msg)
    result = subprocess.run(  # noqa: S603 — fixed argv, no user input
        [str(binary), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_seconds,
        check=True,
    )
    # "eSpeak NG text-to-speech: 1.51  Data at: ..." -> "1.51"
    match = re.search(r":\s*([\d.]+)", result.stdout)
    reported = match.group(1) if match else result.stdout.strip()
    if not reported.startswith(version_prefix):
        msg = (
            f"espeak version {reported!r} does not match the pinned "
            f"prefix {version_prefix!r}; refusing an unverified phonemizer"
        )
        raise RuntimeError(msg)
    return reported


class EspeakSubprocessFallback:
    """Word -> phonemes through the pinned binary, batch per request."""

    def __init__(
        self,
        binary: Path,
        *,
        version_prefix: str,
        timeout_seconds: float,
        voice: str = "en-us",
    ) -> None:
        self._argv = (str(binary), "-q", "--ipa", "-v", voice)
        self._timeout = timeout_seconds
        self.version = validate_espeak_binary(
            binary, version_prefix=version_prefix, timeout_seconds=timeout_seconds
        )

    def phonemize_words(self, words: list[str]) -> dict[str, str]:
        """One subprocess call for every unknown word in a chunk.

        Words go in one per line on stdin; espeak answers one IPA line
        per input line. Any failure (timeout, crash, count mismatch)
        returns {} — the caller keeps dictionary-only behavior.
        """
        cleaned = [
            word
            for word in words
            if word and len(word) <= _MAX_WORD_CHARS and not set(word) & {"\n", "\r", "\x00"}
        ]
        if not cleaned:
            return {}
        try:
            # encoding pinned: IPA is UTF-8 regardless of the container's
            # locale — the C-locale default would mangle it.
            result = subprocess.run(  # noqa: S603 — constant argv; text via stdin only
                list(self._argv),
                input="\n".join(cleaned) + "\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("espeak_fallback_failed", reason=exc.__class__.__name__)
            return {}
        if result.returncode != 0:
            logger.warning("espeak_fallback_failed", reason=f"exit {result.returncode}")
            return {}
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if len(lines) != len(cleaned):
            logger.warning(
                "espeak_fallback_failed",
                reason=f"line mismatch: {len(cleaned)} words, {len(lines)} answers",
            )
            return {}
        return {
            word: mapped
            for word, line in zip(cleaned, lines, strict=True)
            if (mapped := map_ipa_to_kokoro(line))
        }
