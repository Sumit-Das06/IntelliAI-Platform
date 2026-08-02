"""The platform's capability vocabulary — the single source of truth.

No module anywhere in the platform may use a string literal where a
capability is meant (ADR-0016). Members are append-only: never renamed,
never removed, never reused. A member lands in the same change as its
capability's schemas — not speculatively.
"""

from enum import StrEnum, unique


@unique
class Capability(StrEnum):
    """Primitive capabilities the platform serves (CAPABILITIES.md)."""

    TRANSCRIPTION = "transcription"
