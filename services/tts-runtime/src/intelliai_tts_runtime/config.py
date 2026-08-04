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
