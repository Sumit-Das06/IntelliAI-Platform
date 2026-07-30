"""identity: organizations, users, memberships, api keys

Revision ID: 036346525a68
Revises: cd09df1257af
Create Date: 2026-07-30 16:29:52.938497
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "036346525a68"
down_revision: str | None = "cd09df1257af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("public_id", name=op.f("uq_organizations_public_id")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("public_id", name=op.f("uq_users_public_id")),
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_last4", sa.String(length=4), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_api_keys_users_created_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_api_keys_organizations_organization_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        sa.UniqueConstraint("key_hash", name=op.f("uq_api_keys_key_hash")),
        sa.UniqueConstraint("public_id", name=op.f("uq_api_keys_public_id")),
    )
    op.create_index(
        op.f("ix_api_keys_organization_id"), "api_keys", ["organization_id"], unique=False
    )
    op.create_table(
        "memberships",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.Enum("owner", "member", name="membership_role"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_memberships_organizations_organization_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_memberships_users_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint(
            "organization_id", "user_id", name=op.f("uq_memberships_organization_id_user_id")
        ),
        sa.UniqueConstraint("public_id", name=op.f("uq_memberships_public_id")),
    )
    op.create_index(
        op.f("ix_memberships_organization_id"), "memberships", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_memberships_user_id"), "memberships", ["user_id"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_index(op.f("ix_memberships_user_id"), table_name="memberships")
    op.drop_index(op.f("ix_memberships_organization_id"), table_name="memberships")
    op.drop_table("memberships")
    op.drop_index(op.f("ix_api_keys_organization_id"), table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("organizations")
    # Autogenerate misses this: the native enum is a standalone PG type and
    # survives the table drop; without this, re-upgrading fails.
    sa.Enum(name="membership_role").drop(op.get_bind())
