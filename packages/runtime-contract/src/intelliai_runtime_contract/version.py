"""Contract version — owned by the contract, never by individual runtimes.

Within a version, every change is additive-with-defaults. Removing or
re-typing a field, changing an enum value, or changing envelope shape
increments this number — a rare, platform-wide event (ADR-0016).
"""

from typing import Final

CONTRACT_VERSION: Final[int] = 1
