"""Runtime settings — typed, frozen, fail-fast (the platform Settings pattern).

Concurrency knobs are the runtime's own business (ADR-0016: the runtime owns
its concurrency; the gateway owns routing and end-to-end deadlines). The
text limit is a runtime-owned protection, not contract vocabulary — the
contract requires non-empty text; how MUCH text one request may carry is
deployment policy. Slot configuration is settings-driven: one deployment
declares the artifacts it hosts, and ``slots.build_slot_specs`` turns that
declaration into slots.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTELLIAI_TTS_", frozen=True, extra="ignore")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    console_logs: bool = False  # pretty console rendering (dev); JSON otherwise

    # Inference slots actually executing at once (thread pool size)...
    max_concurrency: int = Field(default=2, ge=1)
    # ...plus how many admitted requests may wait for a slot. Beyond
    # concurrency + queue, the runtime answers `overloaded` immediately —
    # a fast honest no beats a slow timeout (the gateway owns retries).
    max_queue: int = Field(default=8, ge=0)

    # ── Text pipeline limits ────────────────────────────────────────────
    # Upper bound on request text; beyond it the runtime answers
    # `invalid_input` before any engine runs.
    max_text_chars: int = Field(default=2000, gt=0)

    # ── Text normalization (M35, pipeline seam) ─────────────────────────
    # v1 deterministic rules: currency, percent, slash-dates, phone digit
    # groups. Speech-only — billing and provenance always use the
    # original request text. The switch exists for rollback, not doubt.
    normalize_text: bool = True

    # ── OOV pronunciation fallback (M35, policy: M3 §8 exec boundary) ───
    # "espeak" runs the pinned espeak-ng BINARY as a subprocess for words
    # the dictionary G2P cannot phonemize (measured: halves trap-set WER).
    # The GPL python chain stays banned in-process regardless — this is
    # the ffmpeg posture, an executable behind argv, never a library.
    # Default OFF: a deployment declares the binary it ships (the M30
    # punctuation pattern — capabilities arrive explicitly, never by
    # surprise).
    oov_fallback: Literal["off", "espeak"] = "off"

    # ── Streaming (M36) ─────────────────────────────────────────────────
    # First-chunk text budget for `stream=true` requests: whole sentences
    # up to this many chars synthesize FIRST so audio starts early; the
    # rest rides the regular merge budget. Chosen by the M36 chunk-size
    # experiment, not by guess.
    stream_first_chunk_chars: int = Field(default=90, gt=0)
    # Bounded producer->consumer buffer (chunks) for one streaming
    # request: a slow client blocks synthesis instead of growing memory.
    stream_buffer_chunks: int = Field(default=4, ge=1)

    # ── Hindi voices (M39, local/staging deployments) ───────────────────
    # "espeak" serves the two M38-approved Hindi voices (hindi-female /
    # hindi-male) with sentence-level Hindi G2P through the SAME pinned
    # espeak-ng binary at the SAME exec boundary as the EN OOV fallback.
    # Default OFF: the voices and their phonemizer arrive together,
    # explicitly, per deployment — never by surprise (the M30 pattern).
    # Production ships no TTS and never declares this.
    hindi_g2p: Literal["off", "espeak"] = "off"
    espeak_binary: Path = Path("/usr/bin/espeak-ng")
    #: The engine refuses to start if the binary reports a different
    #: version family — a wrong phonemizer is a wrong pronunciation
    #: model, caught at boot rather than in production audio.
    espeak_version_pin: str = "1.5"
    espeak_timeout_seconds: float = Field(default=2.0, gt=0)

    # ── Model serving ───────────────────────────────────────────────────
    # Which artifacts this deployment hosts, in declaration order: a
    # comma-separated list of engine names, each optionally followed by
    # `:artifact` to host a weightless engine under another identity
    # (how the reference engine simulates future artifacts). The FIRST
    # entry takes the `default` slot — the role that answers a request
    # pinning no artifact. "reference" needs no weights (CI, tests);
    # "kokoro" requires the `kokoro` extra and downloads the hash-pinned
    # artifact (weights + voice packs) on first startup.
    #   "kokoro"                      -> one deployment, one artifact
    #   "kokoro,reference:future-hi"  -> two artifacts, one process
    slots: str = "reference"
    model_dir: Path = Path("models")  # ArtifactStore root (gitignored)

    # Replaced by `slots` in M5 step 2. Kept as a tripwire, not as a
    # feature: a stale INTELLIAI_TTS_DEFAULT_ENGINE would otherwise be
    # ignored silently and a deployment meant to serve kokoro would come
    # up serving the reference engine — healthy, and wrong. The twice-
    # learned lesson: absent configuration must fail loudly, never pass.
    default_engine: Literal["reference", "kokoro"] | None = None

    @model_validator(mode="after")
    def _refuse_the_replaced_setting(self) -> "Settings":
        if self.default_engine is not None:
            msg = (
                "INTELLIAI_TTS_DEFAULT_ENGINE was replaced by INTELLIAI_TTS_SLOTS "
                f"(use INTELLIAI_TTS_SLOTS={self.default_engine!r}); a deployment now "
                "declares every artifact it hosts, not one engine"
            )
            raise ValueError(msg)
        return self
