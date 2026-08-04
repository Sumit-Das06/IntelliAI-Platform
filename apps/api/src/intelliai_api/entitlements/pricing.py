"""The minimum of ADR-0023 needed to enforce a money ceiling.

A spend limit is a limit on *money*, and money does not exist until
usage is rated — so enforcing one requires the rating function to exist.
This module brings forward exactly that much of the pricing design and
no more. Step 5 completes it: rollups, invoice-shaped rating, retroactive
correction, and the reproducibility evidence.

Everything ADR-0023 commits to is already true here, because these are
the properties that are expensive to retrofit:

- **rating is a pure function** of ``(measured totals, price book
  version)`` — same inputs, same money, forever;
- **the price book is versioned and immutable**; a change publishes a new
  version, and anything derived records which version produced it;
- **prices are declared in code**, reviewed like any other decision;
- **money is ``Decimal``**, never float, and carries a currency;
- **price follows the public capability's billing unit**, never an
  engine — nothing here can see an artifact, and by the Protection
  Independence Invariant nothing here may.

**These numbers are INTERNAL and provisional (founder decision F3).**
v0.5 publishes no prices; they exist to make cost-to-serve and spend
ceilings computable while customer evidence is gathered.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

CURRENCY = "USD"


@dataclass(frozen=True)
class PriceBook:
    """One immutable, dated set of unit prices."""

    version: str
    effective_from: date
    currency: str
    # unit -> price for ONE of that unit. Units are the ledger's
    # vocabulary (ADR-0021), not this module's: a unit that has no price
    # is simply not billable yet, which is a pricing gap and never a
    # metering one.
    unit_prices: Mapping[str, Decimal]


INTERNAL_V1 = PriceBook(
    version="internal-2026-08-v1",
    effective_from=date(2026, 8, 1),
    currency=CURRENCY,
    unit_prices={
        # $0.36 per audio hour.
        "audio_seconds": Decimal("0.0001"),
        # $15.00 per million characters.
        "characters": Decimal("0.000015"),
    },
)

CURRENT = INTERNAL_V1


def rate(totals: Mapping[str, Decimal], book: PriceBook = CURRENT) -> Decimal:
    """Money owed for measured totals, under one price book version.

    Pure: no clock, no database, no I/O. That is what makes a spend
    ceiling explicable ("you spent this because you used that, at these
    prices") and what will make invoices reproducible in Step 5.

    Unpriced units contribute nothing rather than raising. A capability
    can therefore ship, be metered, and be studied before anyone decides
    what it costs — measurement never waits on a pricing decision.
    """
    priced = (
        amount * book.unit_prices[unit]
        for unit, amount in totals.items()
        if unit in book.unit_prices
    )
    return sum(priced, Decimal(0))
