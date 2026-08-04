"""Usage rollups: a cache of the ledger, and never a second truth.

The Rollup Invariant (design §8.5) in table form. Everything about this
model is the deliberate opposite of ``usage_events``, and the contrast is
the design working rather than an inconsistency:

| | ``usage_events`` | ``usage_rollups`` |
|---|---|---|
| authority | the truth | a cache of it |
| mutation | refused by trigger | freely updated and deleted |
| on disagreement | wins | is rebuilt |
| contains money | never | never |

**No money here either.** A rollup stores measured usage; money is
computed from it at read time under a stated price book version, so a
price change never requires touching stored aggregates — and a rollup
can never quietly become the record of what someone was charged.

Rebuilt by deletion and recomputation from the ledger. A cache that
cannot be dropped and regenerated is not a cache, so the absence of an
append-only trigger on this table is a feature, asserted by test.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Identity, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intelliai_api.db.base import Base


class UsageRollup(Base):
    """One organization's consumption of one unit over one period."""

    __tablename__ = "usage_rollups"
    __table_args__ = (
        # The identity of a rollup row IS its coordinates: rebuilding
        # must be able to replace exactly what it recomputed.
        CheckConstraint("period_start < period_end", name="period_ordered"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # CASCADE, unlike the ledger's RESTRICT: losing a cache with its
    # tenant is correct; losing revenue history with its tenant is not.

    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    unit: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))

    # When this row was last recomputed from the ledger. Not a fact about
    # usage — a fact about the cache, and the first thing to look at when
    # a total looks wrong.
    computed_at: Mapped[datetime] = mapped_column(server_default=func.now())
