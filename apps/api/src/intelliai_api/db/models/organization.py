"""Organization: the tenant — the unit of ownership, quota, and billing."""

from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intelliai_api.db.base import Base, TimestampMixin, generate_public_id

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

    # Deliberately minimal: plan/quota/billing columns arrive with the
    # milestones that give them meaning (M4+), as additive migrations.

    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization")
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="organization")
