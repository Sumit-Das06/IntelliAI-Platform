"""Rating: turning immutable facts into money, reproducibly.

The Commercial Interpretation Invariant in executable form. Everything
here is a **pure function of (ledger events, catalog, agreement)** — no
clock, no database, no I/O — which is what makes an invoice regenerable
years later from inputs that cannot have changed.

Three properties, each load-bearing:

**Per-event book selection.** Each event is priced by the book in effect
at its ``occurred_at``. A period spanning a price change therefore
produces lines under two versions, and every line names the version that
produced it. Rating the whole period at "the current book" would be one
line of code shorter and would silently re-price history.

**Discounts are interpretation, never evidence.** An agreement is
applied here, at read time, and is recorded on the result. Nothing about
a discount is ever written into a usage row — a promotion that touched
the ledger would make last quarter unreproducible.

**Rounding happens once, at the line** (ADR-0023). Quantities and unit
prices stay exact; each line is rounded to the currency's minor unit and
the total is the sum of rounded lines, so nothing is ever rounded twice.
A line worth less than half a cent rounds to zero, which is the honest
answer: we do not charge fractions of a cent.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from intelliai_api.db.models import UsageEvent, UsageOrigin
from intelliai_api.pricing.books import CATALOG, PriceBookCatalog

CENTS = Decimal("0.01")

# The Rating Reproducibility Invariant (design §8.6). Money is a function
# of THREE immutable inputs — events, price book version, and this — and
# the third is the one systems forget until they need it.
#
# Version 1 is the only implementation, and that is exactly why the field
# is reserved now: introduced alongside version 2 it would be useless,
# because every invoice already produced would have no version recorded
# and no way to acquire one.
#
# A new version is required for any change to how money is derived from
# the SAME facts and prices — rounding, tiering, minimum billable units,
# proration, discount composition order. Adding a unit or changing a
# price is not an algorithm change; the price book already versions those.
RATING_ALGORITHM_VERSION = 1
SUPPORTED_RATING_ALGORITHMS = frozenset({1})

# Founder decision F7: only customer traffic is rated. Benchmark,
# evaluation, research, and demo usage is metered exactly like a
# customer's and excluded HERE — measurement is unconditional,
# billability is a filter applied at interpretation time.
RATEABLE_ORIGINS = frozenset({UsageOrigin.CUSTOMER})


@dataclass(frozen=True)
class Agreement:
    """The commercial lens applied to a period's facts.

    Discounts, promotions, and (later) committed-use terms live here:
    things that may change, be renegotiated, or expire, and that must
    never leave a trace in the ledger.
    """

    id: str
    discount_percent: Decimal = Decimal(0)  # 0..100
    reason: str = ""

    def __post_init__(self) -> None:
        if not Decimal(0) <= self.discount_percent <= Decimal(100):
            raise ValueError("a discount is a percentage between 0 and 100")


NO_AGREEMENT = Agreement(id="standard")


def _require_supported(algorithm_version: int) -> None:
    """Refuse an arithmetic we cannot perform, rather than substituting one.

    The failure this prevents is the quiet one: a caller asking for
    version 1 in 2029, silently receiving version 3, and reporting a
    number the customer never paid.
    """
    if algorithm_version not in SUPPORTED_RATING_ALGORITHMS:
        raise ValueError(
            f"rating algorithm version {algorithm_version} is not implemented; "
            f"supported: {sorted(SUPPORTED_RATING_ALGORITHMS)}"
        )


@dataclass(frozen=True)
class RatedLine:
    """One (unit, price book version) pair — the shape of an invoice line."""

    unit: str
    quantity: Decimal
    unit_price: Decimal
    price_book_version: str
    amount: Decimal  # rounded to the currency's minor unit


@dataclass(frozen=True)
class RatedPeriod:
    """What a period costs, and everything needed to prove it.

    Deliberately NOT persisted in M4 — invoice generation and delivery
    are explicit non-goals (§17). This is the rating *capability* an
    invoice will later be a document of, and it exists now so that the
    ledger can be proven sufficient to produce one.
    """

    organization_public_id: str
    period_label: str
    currency: str
    lines: tuple[RatedLine, ...]
    subtotal: Decimal
    discount_amount: Decimal
    total: Decimal
    agreement_id: str
    price_book_versions: tuple[str, ...]
    # The third leg of the reproducible triple. An invoice that records
    # events and prices but not the arithmetic can be re-derived to a
    # different number by a future release.
    rating_algorithm_version: int
    rated_events: int
    unrated_events: int  # recorded, but not this agreement's to bill


def rate_totals(
    totals: Mapping[str, Decimal],
    *,
    at: datetime,
    catalog: PriceBookCatalog = CATALOG,
) -> Decimal:
    """Money for measured totals under the book in effect at ``at``.

    The cheap path, used by spend limits: one book, no line breakdown.
    Unpriced units contribute nothing rather than raising, so a
    capability can ship, be metered, and be studied before anyone decides
    what it costs — measurement never waits on a pricing decision.
    """
    book = catalog.book_for(at)
    priced = (
        amount * price
        for unit, amount in totals.items()
        if (price := book.price_of(unit)) is not None
    )
    return sum(priced, Decimal(0))


def rate_events(
    events: Iterable[UsageEvent],
    *,
    organization_public_id: str,
    period_label: str,
    catalog: PriceBookCatalog = CATALOG,
    agreement: Agreement = NO_AGREEMENT,
    algorithm_version: int = RATING_ALGORITHM_VERSION,
) -> RatedPeriod:
    """Rate a period's ledger events into invoice-shaped lines.

    Pure and total: the same events, catalog, agreement, and algorithm
    version produce the same money forever. Reversals participate
    naturally — they carry negated quantities (ADR-0021), so a corrected
    period rates to the corrected number without anything being edited.

    ``algorithm_version`` is how a 2029 caller regenerates a 2026
    invoice: it asks for the arithmetic that produced it, and gets an
    error rather than today's if that version is gone.
    """
    _require_supported(algorithm_version)
    # (unit, book version) -> quantity. Grouping by book version is what
    # keeps a period that spans a price change honest.
    grouped: dict[tuple[str, str], Decimal] = {}
    prices: dict[tuple[str, str], Decimal] = {}
    rated = unrated = 0

    for event in events:
        if event.origin not in RATEABLE_ORIGINS or not event.billable:
            unrated += 1
            continue
        rated += 1
        book = catalog.book_for(event.occurred_at)
        for quantity in event.quantities:
            price = book.price_of(quantity.unit)
            if price is None:
                continue
            key = (quantity.unit, book.version)
            grouped[key] = grouped.get(key, Decimal(0)) + quantity.amount
            prices[key] = price

    lines = tuple(
        RatedLine(
            unit=unit,
            quantity=quantity,
            unit_price=prices[(unit, version)],
            price_book_version=version,
            amount=(quantity * prices[(unit, version)]).quantize(CENTS, rounding=ROUND_HALF_UP),
        )
        for (unit, version), quantity in sorted(grouped.items())
    )

    subtotal = sum((line.amount for line in lines), Decimal(0))
    discount_amount = (subtotal * agreement.discount_percent / Decimal(100)).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )
    versions = tuple(sorted({line.price_book_version for line in lines}))
    currency = catalog.version(versions[0]).currency if versions else catalog.books[-1].currency

    return RatedPeriod(
        organization_public_id=organization_public_id,
        period_label=period_label,
        currency=currency,
        lines=lines,
        subtotal=subtotal,
        discount_amount=discount_amount,
        total=subtotal - discount_amount,
        agreement_id=agreement.id,
        price_book_versions=versions,
        rating_algorithm_version=algorithm_version,
        rated_events=rated,
        unrated_events=unrated,
    )


def rate_rollup(
    rows: Sequence[tuple[str, Decimal]],
    *,
    organization_public_id: str,
    period_label: str,
    at: datetime,
    catalog: PriceBookCatalog = CATALOG,
    agreement: Agreement = NO_AGREEMENT,
    algorithm_version: int = RATING_ALGORITHM_VERSION,
) -> RatedPeriod:
    """Rate pre-aggregated totals — the fast path, from the rollup cache.

    Valid only where one book covers the whole period, because a rollup
    has already thrown away the per-event timestamps that book selection
    needs. That is the price of the cache, and it is why the ledger stays
    authoritative: when a period spans a price change, rating falls back
    to ``rate_events`` rather than guessing (Rollup Invariant, §8.5).
    """
    _require_supported(algorithm_version)
    book = catalog.book_for(at)
    lines = tuple(
        RatedLine(
            unit=unit,
            quantity=amount,
            unit_price=price,
            price_book_version=book.version,
            amount=(amount * price).quantize(CENTS, rounding=ROUND_HALF_UP),
        )
        for unit, amount in sorted(rows)
        if (price := book.price_of(unit)) is not None
    )
    subtotal = sum((line.amount for line in lines), Decimal(0))
    discount_amount = (subtotal * agreement.discount_percent / Decimal(100)).quantize(
        CENTS, rounding=ROUND_HALF_UP
    )
    return RatedPeriod(
        organization_public_id=organization_public_id,
        period_label=period_label,
        currency=book.currency,
        lines=lines,
        subtotal=subtotal,
        discount_amount=discount_amount,
        total=subtotal - discount_amount,
        agreement_id=agreement.id,
        price_book_versions=(book.version,) if lines else (),
        rating_algorithm_version=algorithm_version,
        rated_events=0,  # a rollup does not remember how many events it came from
        unrated_events=0,
    )
