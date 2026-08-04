"""organization spend limit: the customer's own money ceiling

Revision ID: e5a71c9d3b64
Revises: c3f81be5a204
Create Date: 2026-08-04 17:44:09.331207

NUMERIC, never float: sub-cent drift per request becomes a real number at
volume and an embarrassing one in an audit (ADR-0023). Nullable means
"whatever the plan allows" — the effective ceiling is the stricter of the
plan's cap and this, because both parties need to be able to protect
themselves.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a71c9d3b64"
down_revision: str | None = "c3f81be5a204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("spend_limit", sa.Numeric(precision=12, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "spend_limit")
