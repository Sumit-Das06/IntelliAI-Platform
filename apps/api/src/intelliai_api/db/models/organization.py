"""Organization: the tenant — the unit of ownership, quota, and billing."""

from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, Identity, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intelliai_api.db.base import Base, TimestampMixin, generate_public_id
from intelliai_api.db.models.usage_event import UsageOrigin
from intelliai_api.limits.plans import FREE

if TYPE_CHECKING:
    from intelliai_api.db.models.api_key import ApiKey
    from intelliai_api.db.models.membership import Membership


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "org")
    )
    name: Mapped[str] = mapped_column(String(120))

    # Why this tenant's traffic exists. Resolved at authentication and
    # stamped onto every usage event, so our own benchmark, evaluation,
    # and demo traffic is fully MEASURED and never RATED (F7, ADR-0021).
    # A commercial classification, deliberately not a permission: it says
    # nothing about what the tenant may do, only about how its
    # consumption is interpreted downstream.
    usage_origin: Mapped[UsageOrigin] = mapped_column(
        Enum(UsageOrigin, name="usage_origin", values_callable=lambda e: [m.value for m in e]),
        default=UsageOrigin.CUSTOMER,
        server_default=UsageOrigin.CUSTOMER.value,
    )

    # The commercial tier this tenant is on. Limits are never hardcoded
    # per organization: an org has a plan, a plan carries limits
    # (limits/plans.py), and overrides land here later as additive
    # columns. Text rather than an enum because the plan catalog is
    # code-declarative and adding a tier must not require a migration.
    plan: Mapped[str] = mapped_column(String(32), default=FREE, server_default=FREE)

    # A ceiling the CUSTOMER sets on their own spend for a period; None
    # means "whatever the plan allows". The effective ceiling is the
    # stricter of this and the plan's, because both parties need to be
    # able to protect themselves. NUMERIC, never float: sub-cent drift is
    # a real number at volume and an embarrassing one in an audit.
    spend_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    # Deliberately minimal: quota/billing columns arrive with the
    # milestones that give them meaning (M4+), as additive migrations.

    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="organization")
