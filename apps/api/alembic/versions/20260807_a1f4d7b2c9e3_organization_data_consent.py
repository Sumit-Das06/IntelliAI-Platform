"""organization data consent: the opt-in gate for speech data collection

Revision ID: a1f4d7b2c9e3
Revises: f19b2c74d8ae
Create Date: 2026-08-07 09:10:00.000000

Consent is opt-in by law: the server default is FALSE, so every existing
and every future tenant starts non-consented and nothing downstream may
store a speech sample until an operator records an explicit grant. The
timestamp and the governing reference are stored so each collected sample
can snapshot the consent it was gathered under; revocation clears only
the flag, leaving the historical grant readable.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1f4d7b2c9e3"
down_revision: str | None = "f19b2c74d8ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("data_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "organizations",
        sa.Column("data_consented_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("consent_reference", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "consent_reference")
    op.drop_column("organizations", "data_consented_at")
    op.drop_column("organizations", "data_consent")
