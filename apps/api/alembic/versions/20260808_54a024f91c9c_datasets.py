"""datasets: reproducible training data - definitions, frozen versions, membership

Revision ID: 54a024f91c9c
Revises: c5e9a3d81f47
Create Date: 2026-08-08 17:12:44.002395

Three tables, one distinction: ``datasets`` is the logical definition
(criteria over the organization's speech samples), ``dataset_versions``
is the immutable snapshot a future fine-tuning run will consume, and
``dataset_version_samples`` is the frozen membership - one row per
(version, sample), pinning ``training_transcript`` (the sample's
current_transcript at freeze time) because that is the only
training-relevant fact that legitimately evolves after a freeze. Audio
is never copied: membership references the canonical sample row and its
object key.

Version rows and membership rows are written once inside the freeze
transaction and never updated or deleted - immutability is enforced by
the absence of any code path that would do so, and reproducibility by
the (dataset_id, version_number) uniqueness that makes every freeze a
new, citable number.

Every FK cascades: datasets die with their tenant (privacy-first, like
speech_samples), versions with their dataset, membership with either
side - if a sample is ever erased, versions honestly shrink rather than
dangle. Purely additive: no existing table changes meaning.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "54a024f91c9c"
down_revision: str | None = "c5e9a3d81f47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="dataset_status"),
            server_default="active",
            nullable=False,
        ),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            name=op.f("fk_datasets_organizations_organization_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_datasets")),
        sa.UniqueConstraint("public_id", name=op.f("uq_datasets_public_id")),
    )
    op.create_index(
        "ix_datasets_organization_id_created_at",
        "datasets",
        ["organization_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("dataset_id", sa.BigInteger(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("statistics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            name=op.f("fk_dataset_versions_datasets_dataset_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_versions")),
        sa.UniqueConstraint(
            "dataset_id",
            "version_number",
            name=op.f("uq_dataset_versions_dataset_id_version_number"),
        ),
        sa.UniqueConstraint("public_id", name=op.f("uq_dataset_versions_public_id")),
    )

    op.create_table(
        "dataset_version_samples",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("dataset_version_id", sa.BigInteger(), nullable=False),
        sa.Column("speech_sample_id", sa.BigInteger(), nullable=False),
        sa.Column("training_transcript", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["dataset_versions.id"],
            name=op.f("fk_dataset_version_samples_dataset_versions_dataset_version_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["speech_sample_id"],
            ["speech_samples.id"],
            name=op.f("fk_dataset_version_samples_speech_samples_speech_sample_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_version_samples")),
        sa.UniqueConstraint(
            "dataset_version_id",
            "speech_sample_id",
            name=op.f("uq_dataset_version_samples_dataset_version_id_speech_sample_id"),
        ),
    )
    op.create_index(
        "ix_dataset_version_samples_speech_sample_id",
        "dataset_version_samples",
        ["speech_sample_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dataset_version_samples_speech_sample_id", table_name="dataset_version_samples"
    )
    op.drop_table("dataset_version_samples")
    op.drop_table("dataset_versions")
    op.drop_index("ix_datasets_organization_id_created_at", table_name="datasets")
    op.drop_table("datasets")
    sa.Enum(name="dataset_status").drop(op.get_bind(), checkfirst=True)
