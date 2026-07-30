"""User: a human, as a record — NOT an authentication principal in M1.

Deliberately absent: any password/credential column. Human authentication
is a future milestone's decision (M6 console); an empty column now would
prejudge it. Emails are normalized to lowercase at the service layer before
storage — the unique constraint applies to the normalized value.
"""

from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intelliai_api.db.base import Base, TimestampMixin, generate_public_id

if TYPE_CHECKING:
    from intelliai_api.db.models.membership import Membership


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "user")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")
