"""The usage ledger: what customers consumed, recorded once, forever.

The platform's second permanent ledger. The first (evaluation evidence,
M2.5) records what models did; this one records what customers consumed.
Both are append-only, for the same reason: a record that can be edited is
a record whose numbers are opinions (ADR-0021).

Four properties are structural, not conventional:

- **Append-only.** Database triggers refuse UPDATE, DELETE, and TRUNCATE
  on both tables. Corrections are *compensating events* that reference
  the original (``reverses_usage_event_id``) and carry negated
  quantities, so ``SUM(amount)`` is the netting operation.
- **Money-free.** Quantities are measurements as the runtime reported
  them — never rounded, never priced. Rounding, minimums, tiers, and
  discounts are pricing decisions applied later (ADR-0023).
- **Capability-agnostic.** Quantities are ``(unit, amount)`` rows,
  mirroring the runtime contract's ``Usage`` tuple. Adding OCR (pages),
  vision (images), or chat (tokens) adds zero columns.
- **Traceable.** Every customer-facing event carries the ``request_id``
  already returned to the caller in ``X-Request-ID``, enforced by a check
  constraint — every billed unit is explicable to the party paying for
  it.

**Vocabulary ownership.** The ledger *enforces* the vocabularies it owns
(``origin``, ``outcome``: native database enums, so a typo is impossible
and appending a member is a reviewed migration) and merely *records* the
vocabularies others own (``capability``, ``public_model_id``, ``unit``:
plain text, because the registry and the runtime contract are their
source of truth and shipping a capability must not require a migration
here).

**Commercial Identity Invariant.** ``public_model_id`` is the public
capability the customer bought (``intelliai-stt``, ``intelliai-tts``).
Which artifact, engine, fine-tune, adapter, or quantization served it
lives in ``lineage`` — internal forever, never projected, never an input
to rating.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from functools import partial
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intelliai_api.db.base import Base, generate_public_id


class UsageOrigin(StrEnum):
    """Why this work was performed — the platform's commercial taxonomy.

    Append-only: members are added, never renamed and never removed. A
    renamed member rewrites history, and history is the asset.

    Measurement always occurs for every origin; **rating** decides which
    are billable (today: ``customer`` only). Suppressing measurement to
    avoid a charge is forbidden — a suppressed measurement is
    unrecoverable, an unbilled one is a filter.
    """

    CUSTOMER = "customer"
    INTERNAL_QA = "internal_qa"
    BENCHMARK = "benchmark"
    EVALUATION = "evaluation"
    RESEARCH = "research"
    FINE_TUNING = "fine_tuning"
    DEMO = "demo"


class UsageOutcome(StrEnum):
    """What happened to the work, once it was performed.

    ``DISCONNECTED`` exists because **successful generation, not socket
    completion, defines billability** (founder decision F1): the platform
    produced the output and the customer's connection went away. It is
    billable, and it must stay distinguishable from a clean delivery for
    support and anomaly analysis.
    """

    SUCCEEDED = "succeeded"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class UsageEvent(Base):
    """One unit of work the platform performed, as measured by the platform.

    No ORM relationship to ``Organization`` or ``ApiKey`` on purpose: the
    ledger is a fact table read by scoped aggregate queries, not an
    object graph to navigate. The one relationship that exists —
    ``quantities`` — is composition, not navigation.

    ``TimestampMixin`` is deliberately not used: an ``updated_at`` column
    on an append-only table is a lie. The two timestamps here mean
    different things — ``occurred_at`` is when the work completed (and
    therefore which billing period owns it), ``recorded_at`` is when we
    wrote it down.
    """

    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("request_id"),
        # An event may be reversed at most once. Two reversals of one
        # event would net to a credit the customer never earned.
        UniqueConstraint("reverses_usage_event_id"),
        # The at-most-once BILLING guarantee (ADR-0024) enforced where it
        # actually matters — on the ledger, not in application logic.
        # Partial: only keyed requests occupy the index.
        Index(
            "uq_usage_events_organization_id_idempotency_key",
            "organization_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        # The two query shapes the ledger actually serves: per-tenant
        # period aggregation, and platform-wide daily reconciliation.
        Index("ix_usage_events_organization_id_occurred_at", "organization_id", "occurred_at"),
        Index("ix_usage_events_occurred_at", "occurred_at"),
        # Traceability law: a customer-facing event without a request id
        # is a charge nobody can explain. Compensating events are exempt —
        # they answer to no HTTP request.
        CheckConstraint(
            "request_id IS NOT NULL OR reverses_usage_event_id IS NOT NULL",
            name="request_id_required",
        ),
        # A reversal states why; a normal event has nothing to explain.
        CheckConstraint(
            "(reverses_usage_event_id IS NULL) = (reversal_reason IS NULL)",
            name="reversal_reason_paired",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "use")
    )

    # RESTRICT, not CASCADE: the ledger outlives the tenant row. Deleting
    # an organization must fail loudly rather than silently destroy
    # revenue history.
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    # Nullable: the key may be deleted one day, the usage never is.
    api_key_id: Mapped[int | None] = mapped_column(ForeignKey("api_keys.id", ondelete="SET NULL"))

    # The customer's receipt number — the same value returned in
    # X-Request-ID, so a disputed charge resolves to one request.
    request_id: Mapped[str | None] = mapped_column(String(128))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))

    # Registry and contract vocabulary: recorded as text, never
    # foreign-keyed. The catalog is code-declarative (ADR-0017) so there
    # is no table to reference, and a retired public model must not
    # invalidate the history it produced.
    capability: Mapped[str] = mapped_column(String(64))
    public_model_id: Mapped[str] = mapped_column(String(64))

    origin: Mapped[UsageOrigin] = mapped_column(
        Enum(UsageOrigin, name="usage_origin", values_callable=lambda e: [m.value for m in e])
    )
    outcome: Mapped[UsageOutcome] = mapped_column(
        Enum(UsageOutcome, name="usage_outcome", values_callable=lambda e: [m.value for m in e])
    )
    # "The platform delivered value and measured the quantity" — a fact,
    # and a NECESSARY condition for a charge, never a sufficient one.
    # Whether money is owed is rating's decision (origin, price book).
    billable: Mapped[bool]

    occurred_at: Mapped[datetime]  # completion time; owns the billing period
    recorded_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Internal lineage: artifact id, foundation model, quantization,
    # adapter/merge identity, dataset and fine-tune version, runtime
    # version. JSONB because — unlike quantities — this is read for
    # analysis, never aggregated in revenue SQL, and its shape differs
    # per capability. Normalized where billing runs; JSONB where analysis
    # runs. Stored, never projected.
    lineage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    reverses_usage_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("usage_events.id", ondelete="RESTRICT")
    )
    reversal_reason: Mapped[str | None] = mapped_column(String(255))

    quantities: Mapped[list["UsageQuantity"]] = relationship(
        back_populates="event", lazy="selectin"
    )


class UsageQuantity(Base):
    """One measured quantity of one event — the capability-agnostic seam.

    ``unit`` is free text at this layer on purpose. The runtime contract's
    ``UsageUnit`` enum governs what a *runtime may report*; the ledger's
    job is to record faithfully whatever it was told. That is what makes
    "adding a capability adds zero columns" true rather than aspirational.

    Amounts are ``NUMERIC``, never float: sub-cent drift per request
    becomes a real number at volume and an embarrassing one in an audit.
    Compensating events carry negated amounts, so netting a period is
    ``SUM(amount) GROUP BY unit`` — boring, indexable revenue SQL.
    """

    __tablename__ = "usage_quantities"
    __table_args__ = (
        # One row per unit per event: the shape every aggregation assumes.
        UniqueConstraint("usage_event_id", "unit"),
        # A zero quantity is a measurement that says nothing; recording it
        # only creates rows that dilute every average.
        CheckConstraint("amount <> 0", name="amount_nonzero"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    usage_event_id: Mapped[int] = mapped_column(
        ForeignKey("usage_events.id", ondelete="RESTRICT"), index=True
    )
    unit: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))

    event: Mapped["UsageEvent"] = relationship(back_populates="quantities")
