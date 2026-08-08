"""dataset preparations: the training-data verdict, one per frozen version

Revision ID: bfe7e9613396
Revises: 54a024f91c9c
Create Date: 2026-08-08 19:20:20.835930

One additive table. A preparation resolves a Dataset Version's frozen
membership into a validated JSONL manifest and records the verdict:
counts, per-language totals, machine-readable errors, and — when READY —
the artifact's identity (version-addressed object key, sha256 content
checksum, size). UNIQUE(dataset_version_id): the artifact a future
fine-tuning run cites is singular, and READY rows are terminal — a
citation can never silently change meaning. FAILED rows are retried in
place.

Status is TEXT, not a native enum: today's synchronous implementation
persists only ready/failed, and the reserved pending/preparing
vocabulary (a future background executor) must arrive without a
migration — the organizations.plan reasoning. organization_id is
denormalized on purpose so isolation never depends on a join
(ADR-0010). Every FK cascades: verdicts about erased data must not
outlive it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bfe7e9613396"
down_revision: str | None = "54a024f91c9c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_preparations",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("dataset_id", sa.BigInteger(), nullable=False),
        sa.Column("dataset_version_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False),
        sa.Column("invalid_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifact_key", sa.String(length=512), nullable=True),
        sa.Column("manifest_checksum", sa.String(length=80), nullable=True),
        sa.Column("manifest_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["dataset_id"],
            ["datasets.id"],
            name=op.f("fk_dataset_preparations_datasets_dataset_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["dataset_versions.id"],
            name=op.f("fk_dataset_preparations_dataset_versions_dataset_version_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_dataset_preparations_organizations_organization_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_preparations")),
        sa.UniqueConstraint(
            "dataset_version_id", name=op.f("uq_dataset_preparations_dataset_version_id")
        ),
        sa.UniqueConstraint("public_id", name=op.f("uq_dataset_preparations_public_id")),
    )


def downgrade() -> None:
    op.drop_table("dataset_preparations")
