"""Declarative base and platform-wide schema conventions.

These conventions are fixed BEFORE the first table exists, so no table is
ever renamed to comply:

- **Tables:** plural snake_case — ``organizations``, ``api_keys``, ``usage_events``.
- **Primary key:** ``id`` (internal, never exposed in the API).
- **Public identity:** ``public_id``, prefixed text (``org_…``, ``key_…``,
  ``job_…``) — the only identifier clients ever see.
- **Foreign keys:** ``<singular>_id`` — ``organization_id``, ``user_id``.
- **Timestamps:** ``created_at`` / ``updated_at``, timezone-aware,
  database-generated (see ``TimestampMixin``).
- **Constraint/index names:** deterministic patterns below. Without them,
  PostgreSQL invents names, every environment drifts, and migrations become
  irreversible — the convention is what makes ``op.drop_constraint`` work
  identically everywhere.
"""

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: DateTime(timezone=True)}


class TimestampMixin:
    """``created_at``/``updated_at`` for every table.

    Database-generated (``server_default``/``onupdate``) so the values are
    trustworthy no matter which code path — or which future service — writes
    the row.
    """

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
