"""Runtime settings — typed, frozen, fail-fast (the platform Settings pattern).

Concurrency knobs are the runtime's own business (ADR-0016: the runtime owns
its concurrency; the gateway owns routing and end-to-end deadlines). The
text limit is a runtime-owned protection, not contract vocabulary — the
contract requires non-empty text; how MUCH text one request may carry is
deployment policy.
"""

from typing import Literal

from pydantic import Field
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
    # Which engine the default slot binds. "reference" needs no weights
    # (CI, tests); the Kokoro engine arrives as the next Literal member
    # with its own optional extra and artifact spec (M3 step 4).
    default_engine: Literal["reference"] = "reference"
