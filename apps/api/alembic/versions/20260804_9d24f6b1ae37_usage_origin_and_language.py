"""organization usage origin; ledger language as a first-class fact

Revision ID: 9d24f6b1ae37
Revises: 7c1a4b90e2d5
Create Date: 2026-08-04 13:02:44.517210

Two additive columns, both required by laws ratified at Step 1 close:

- ``organizations.usage_origin`` — why a tenant's traffic exists,
  resolved at authentication and stamped onto every event so our own
  benchmark, evaluation, and demo traffic is fully MEASURED and never
  RATED (F7). A commercial classification, never a permission.
- ``usage_events.language`` — an observed property of the request and
  therefore a ledger fact (Ledger Fact Invariant), given a column rather
  than a lineage key because the Core Speech Language Policy needs it
  grouped and counted. It never affects billing semantics.

The ``usage_origin`` enum type already exists (created with the ledger),
so the column reuses it: ``create_type=False`` keeps the migration from
attempting a duplicate CREATE TYPE.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9d24f6b1ae37"
down_revision: str | None = "7c1a4b90e2d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USAGE_ORIGIN = postgresql.ENUM(
    "customer",
    "internal_qa",
    "benchmark",
    "evaluation",
    "research",
    "fine_tuning",
    "demo",
    name="usage_origin",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "usage_origin",
            USAGE_ORIGIN,
            nullable=False,
            server_default="customer",
        ),
    )
    op.add_column("usage_events", sa.Column("language", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("usage_events", "language")
    op.drop_column("organizations", "usage_origin")
