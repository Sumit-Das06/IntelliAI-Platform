"""Canonical time source for the platform.

Every "what time is it?" in application code goes through ``utc_now()`` —
never ``datetime.now()``/``datetime.utcnow()`` directly. One source means:
tests can freeze or offset time in exactly one place; audit timestamps are
uniformly timezone-aware UTC; and a future time abstraction (simulated
clocks, drift injection) is a one-file change.

Row timestamps (``created_at``/``updated_at``) remain DATABASE-generated
(``func.now()`` in ``TimestampMixin``) on purpose: the DB is the arbiter of
record time regardless of which process wrote the row. ``utc_now()`` is for
*application* decisions: expiry checks, revocation stamps, throttling.
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)
