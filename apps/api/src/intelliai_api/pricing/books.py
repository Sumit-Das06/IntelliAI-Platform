"""The price book: what things cost, versioned and immutable.

ADR-0023, completed. Two properties carry the whole design:

**Versions are immutable and dated.** A price change publishes a new
version; a published one is never edited. That is what makes the
Commercial Interpretation Invariant enforceable — interpretation evolves
by *adding* a lens, never by rewriting the one that was applied before.

**A usage event is rated at the book in effect when it OCCURRED**, not
the book in effect when the rating runs. Publishing a price cut in
October must not retroactively re-price August, and an invoice
regenerated in 2029 must produce the 2026 number. This is the single
most important line in the module, and §5's historical-correctness test
exists to keep it true.

Prices are **internal and provisional** (founder decision F3): v0.5
publishes none. They exist so cost-to-serve and spend ceilings are
computable while customer evidence is gathered.

Nothing here can see an artifact, an engine, or a language. Price follows
the public capability's billing unit — the Commercial Identity Invariant
(§8.0) and the Protection Independence Invariant (§10.1a) meeting at the
money layer.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

CURRENCY = "USD"


@dataclass(frozen=True)
class PriceBook:
    """One immutable, dated set of unit prices."""

    version: str
    effective_from: date
    currency: str
    # unit -> price for ONE of that unit. Units are the ledger's
    # vocabulary (ADR-0021), not this module's: a unit with no price is
    # simply not billable yet, which is a pricing gap and never a
    # metering one.
    unit_prices: Mapping[str, Decimal]

    @property
    def effective_from_utc(self) -> datetime:
        return datetime(
            self.effective_from.year,
            self.effective_from.month,
            self.effective_from.day,
            tzinfo=UTC,
        )

    def price_of(self, unit: str) -> Decimal | None:
        return self.unit_prices.get(unit)


INTERNAL_V1 = PriceBook(
    version="internal-2026-08-v1",
    effective_from=date(2026, 8, 1),
    currency=CURRENCY,
    unit_prices={
        "audio_seconds": Decimal("0.0001"),  # $0.36 per audio hour
        "characters": Decimal("0.000015"),  # $15.00 per million characters
    },
)


@dataclass(frozen=True)
class PriceBookCatalog:
    """Every price book the platform has ever published, in order.

    Code-declarative in V1, mirroring Registry V1 (ADR-0017): a price
    change is a commercial decision that deserves a diff and a second
    look, and git supplies the audit trail without an admin surface to
    build and secure. It moves into the database the day a
    customer-specific negotiated price exists, which cannot be a deploy.
    """

    books: Sequence[PriceBook]

    def __post_init__(self) -> None:
        if not self.books:
            raise ValueError("a catalog with no price book can price nothing")
        dates = [book.effective_from for book in self.books]
        if dates != sorted(dates):
            raise ValueError("price books must be declared in effective-date order")
        versions = [book.version for book in self.books]
        if len(set(versions)) != len(versions):
            raise ValueError("price book versions are identities and must be unique")

    def book_for(self, moment: datetime) -> PriceBook:
        """The book in effect at ``moment`` — the latest one already
        effective. Rating asks this per EVENT, never per invoice run."""
        if moment.tzinfo is None:
            raise ValueError("price books are selected from timezone-aware instants only")
        applicable = [
            book for book in self.books if book.effective_from_utc <= moment.astimezone(UTC)
        ]
        if not applicable:
            # Usage older than any published price. Refusing beats
            # guessing: silently applying the earliest book would invent
            # a price nobody ever agreed to.
            raise ValueError(
                f"no price book was in effect at {moment.isoformat()}; "
                f"the earliest is {self.books[0].version}"
            )
        return applicable[-1]

    def version(self, version: str) -> PriceBook:
        """Look a book up by identity — how an invoice reproduces itself."""
        for book in self.books:
            if book.version == version:
                return book
        raise KeyError(f"unknown price book version: {version}")


CATALOG = PriceBookCatalog(books=(INTERNAL_V1,))
CURRENT = INTERNAL_V1
