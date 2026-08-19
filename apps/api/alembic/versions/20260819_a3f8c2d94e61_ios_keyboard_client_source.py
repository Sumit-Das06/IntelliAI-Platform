"""ios-keyboard joins the client_source enum (Milestone 27).

The iOS keyboard client identifies as ``X-IntelliAI-Client:
ios-keyboard/<version>``. The enum records which capture surface
produced a speech sample — an acoustic/product fact, never a
user-tracking dimension — and iOS microphone capture is a distinct
surface from Android's.

Additive only: no rows change, no defaults change, unknown client
headers keep falling back to ``api`` at the parsing layer.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3f8c2d94e61"
down_revision: str | None = "bfe7e9613396"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL 12+ allows ADD VALUE inside a transaction; IF NOT EXISTS
    # keeps re-runs harmless on a database that already has it.
    op.execute("ALTER TYPE client_source ADD VALUE IF NOT EXISTS 'ios-keyboard'")


def downgrade() -> None:
    # PostgreSQL cannot remove an enum value in place; a true downgrade
    # would require rebuilding the type and every dependent column. The
    # value is additive and harmless to leave — document, don't destroy.
    pass
