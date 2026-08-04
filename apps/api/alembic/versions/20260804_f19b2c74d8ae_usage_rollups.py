"""usage rollups: a rebuildable cache of the ledger

Revision ID: f19b2c74d8ae
Revises: e5a71c9d3b64
Create Date: 2026-08-04 19:12:55.418620

Deliberately WITHOUT the append-only triggers that guard usage_events.
A rollup is a cache (design §8.5): it must be freely deletable and
rebuildable, and a rollup that cannot be dropped and regenerated is not
a cache. The asymmetry between the two tables is the design working.

CASCADE on the tenant, unlike the ledger's RESTRICT: losing a cache with
its organization is correct; losing revenue history with it is not.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f19b2c74d8ae"
down_revision: str | None = "e5a71c9d3b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_rollups",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "period_start < period_end", name=op.f("ck_usage_rollups_period_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_usage_rollups_organizations_organization_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_rollups")),
    )
    op.create_index(
        op.f("ix_usage_rollups_organization_id"),
        "usage_rollups",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_usage_rollups_organization_id"), table_name="usage_rollups")
    op.drop_table("usage_rollups")
