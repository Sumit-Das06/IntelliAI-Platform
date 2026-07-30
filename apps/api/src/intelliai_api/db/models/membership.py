"""Membership: the many-to-many bridge between users and organizations.

Carries relationship-owned data (the role). One user may belong to many
organizations; one organization has many members; a given pair exists at
most once (unique constraint — the database is the final referee even if
application code slips).
"""

from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Identity, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intelliai_api.db.base import Base, TimestampMixin, generate_public_id

if TYPE_CHECKING:
    from intelliai_api.db.models.organization import Organization
    from intelliai_api.db.models.user import User


class MembershipRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"
    # Future roles (admin, billing, viewer…) are additive enum values.


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "mem")
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[MembershipRole] = mapped_column(
        Enum(
            MembershipRole,
            name="membership_role",
            values_callable=lambda e: [m.value for m in e],
        )
    )

    organization: Mapped["Organization"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")
