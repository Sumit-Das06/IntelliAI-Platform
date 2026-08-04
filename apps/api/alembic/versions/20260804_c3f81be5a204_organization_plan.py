"""organization plan: where admission limits come from

Revision ID: c3f81be5a204
Revises: 9d24f6b1ae37
Create Date: 2026-08-04 15:18:33.902114

Limits are never hardcoded per organization (ADR-0022): an org has a
plan, a plan carries limits. Text rather than a native enum — unlike
``usage_origin``, the plan catalog is code-declarative, so adding a tier
must be a configuration change rather than a migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f81be5a204"
down_revision: str | None = "9d24f6b1ae37"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
    )


def downgrade() -> None:
    op.drop_column("organizations", "plan")
