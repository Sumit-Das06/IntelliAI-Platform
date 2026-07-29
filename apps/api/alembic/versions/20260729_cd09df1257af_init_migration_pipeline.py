"""init migration pipeline

Revision ID: cd09df1257af
Revises: (base)
Create Date: 2026-07-29 18:27:15.064754
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cd09df1257af"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
