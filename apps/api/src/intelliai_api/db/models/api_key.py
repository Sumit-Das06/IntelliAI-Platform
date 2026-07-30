"""ApiKey: the credential store — hashes and metadata, never secrets.

The plaintext key exists in exactly two places, ever: the creation response
and the customer's clipboard. This table stores ``HMAC-SHA256(pepper, key)``
plus enough metadata for display (prefix, last4), support, and audit
(ADR-0012).
Revocation is soft (``revoked_at``): the key stops working instantly, the
audit trail survives forever.

Keys belong to ORGANIZATIONS, never users (ADR-0010): when a person leaves
a company, you revoke their membership — production infrastructure keeps
running.
"""

from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intelliai_api.db.base import Base, TimestampMixin, generate_public_id

if TYPE_CHECKING:
    from intelliai_api.db.models.organization import Organization


class ApiKey(TimestampMixin, Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=partial(generate_public_id, "key")
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String(120))  # human label: "prod-server"
    key_prefix: Mapped[str] = mapped_column(String(16))  # "ik_live_a1b2c3d4" — display/support
    key_last4: Mapped[str] = mapped_column(String(4))  # "…x4Kq" — display
    # HMAC-SHA256(pepper, key) hex. Unique: it IS the lookup path —
    # deterministic hash → one indexed equality query at auth time.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)

    # Audit trail: who made it (survives the user leaving: SET NULL not CASCADE).
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    last_used_at: Mapped[datetime | None]  # throttled writes — approximate by design
    expires_at: Mapped[datetime | None]  # optional; enforced at auth time
    revoked_at: Mapped[datetime | None]  # soft revocation

    organization: Mapped["Organization"] = relationship(back_populates="api_keys")
