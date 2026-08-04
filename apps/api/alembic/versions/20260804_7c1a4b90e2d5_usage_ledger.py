"""usage ledger: append-only usage events and quantities

Revision ID: 7c1a4b90e2d5
Revises: 036346525a68
Create Date: 2026-08-04 11:40:12.104883

Append-only is enforced by the schema, not by the application: a trigger
function raises on UPDATE, DELETE, and TRUNCATE for both ledger tables.
TRUNCATE needs its own statement-level trigger — row-level triggers do
not fire for it, which is exactly the hole an accidental "clean the test
data" script would fall through.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7c1a4b90e2d5"
down_revision: str | None = "036346525a68"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("api_key_id", sa.BigInteger(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("public_model_id", sa.String(length=64), nullable=False),
        sa.Column(
            "origin",
            sa.Enum(
                "customer",
                "internal_qa",
                "benchmark",
                "evaluation",
                "research",
                "fine_tuning",
                "demo",
                name="usage_origin",
            ),
            nullable=False,
        ),
        sa.Column(
            "outcome",
            sa.Enum("succeeded", "disconnected", "failed", name="usage_outcome"),
            nullable=False,
        ),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("lineage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reverses_usage_event_id", sa.BigInteger(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "request_id IS NOT NULL OR reverses_usage_event_id IS NOT NULL",
            name=op.f("ck_usage_events_request_id_required"),
        ),
        sa.CheckConstraint(
            "(reverses_usage_event_id IS NULL) = (reversal_reason IS NULL)",
            name=op.f("ck_usage_events_reversal_reason_paired"),
        ),
        sa.ForeignKeyConstraint(
            ["api_key_id"],
            ["api_keys.id"],
            name=op.f("fk_usage_events_api_keys_api_key_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_usage_events_organizations_organization_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_usage_event_id"],
            ["usage_events.id"],
            name=op.f("fk_usage_events_usage_events_reverses_usage_event_id"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_events")),
        sa.UniqueConstraint("public_id", name=op.f("uq_usage_events_public_id")),
        sa.UniqueConstraint("request_id", name=op.f("uq_usage_events_request_id")),
        sa.UniqueConstraint(
            "reverses_usage_event_id",
            name=op.f("uq_usage_events_reverses_usage_event_id"),
        ),
    )
    op.create_index(
        op.f("ix_usage_events_organization_id"), "usage_events", ["organization_id"], unique=False
    )
    op.create_index(
        "ix_usage_events_organization_id_occurred_at",
        "usage_events",
        ["organization_id", "occurred_at"],
        unique=False,
    )
    op.create_index("ix_usage_events_occurred_at", "usage_events", ["occurred_at"], unique=False)
    op.create_index(
        "uq_usage_events_organization_id_idempotency_key",
        "usage_events",
        ["organization_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "usage_quantities",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("usage_event_id", sa.BigInteger(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.CheckConstraint("amount <> 0", name=op.f("ck_usage_quantities_amount_nonzero")),
        sa.ForeignKeyConstraint(
            ["usage_event_id"],
            ["usage_events.id"],
            name=op.f("fk_usage_quantities_usage_events_usage_event_id"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_quantities")),
        sa.UniqueConstraint(
            "usage_event_id", "unit", name=op.f("uq_usage_quantities_usage_event_id_unit")
        ),
    )
    op.create_index(
        op.f("ix_usage_quantities_usage_event_id"),
        "usage_quantities",
        ["usage_event_id"],
        unique=False,
    )

    # ── Append-only, enforced by the database (ADR-0021) ────────────────
    op.execute(
        """
        CREATE FUNCTION intelliai_forbid_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'append-only ledger: % is not permitted on % (ADR-0021); '
                'corrections are compensating events'
                , TG_OP, TG_TABLE_NAME
                USING ERRCODE = 'restrict_violation';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER usage_events_no_mutation
        BEFORE UPDATE OR DELETE ON usage_events
        FOR EACH ROW EXECUTE FUNCTION intelliai_forbid_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER usage_events_no_truncate
        BEFORE TRUNCATE ON usage_events
        FOR EACH STATEMENT EXECUTE FUNCTION intelliai_forbid_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER usage_quantities_no_mutation
        BEFORE UPDATE OR DELETE ON usage_quantities
        FOR EACH ROW EXECUTE FUNCTION intelliai_forbid_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER usage_quantities_no_truncate
        BEFORE TRUNCATE ON usage_quantities
        FOR EACH STATEMENT EXECUTE FUNCTION intelliai_forbid_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS usage_quantities_no_truncate ON usage_quantities;")
    op.execute("DROP TRIGGER IF EXISTS usage_quantities_no_mutation ON usage_quantities;")
    op.execute("DROP TRIGGER IF EXISTS usage_events_no_truncate ON usage_events;")
    op.execute("DROP TRIGGER IF EXISTS usage_events_no_mutation ON usage_events;")
    op.execute("DROP FUNCTION IF EXISTS intelliai_forbid_mutation();")

    op.drop_index(op.f("ix_usage_quantities_usage_event_id"), table_name="usage_quantities")
    op.drop_table("usage_quantities")
    op.drop_index("uq_usage_events_organization_id_idempotency_key", table_name="usage_events")
    op.drop_index("ix_usage_events_occurred_at", table_name="usage_events")
    op.drop_index("ix_usage_events_organization_id_occurred_at", table_name="usage_events")
    op.drop_index(op.f("ix_usage_events_organization_id"), table_name="usage_events")
    op.drop_table("usage_events")
    # Native enums are standalone PG types and survive the table drop;
    # without this, re-upgrading fails (same lesson as membership_role).
    sa.Enum(name="usage_outcome").drop(op.get_bind())
    sa.Enum(name="usage_origin").drop(op.get_bind())
