"""Schema convention tests — the naming law of db/base.py, enforced.

These run against metadata only (no database): they pin the promises that
every table follows the conventions fixed before the first table existed.
"""

from sqlalchemy import UniqueConstraint

from intelliai_api.db import models  # noqa: F401 — registers all mappers
from intelliai_api.db.base import Base, generate_public_id

EXPECTED_TABLES = {"organizations", "users", "memberships", "api_keys"}


def test_all_identity_tables_are_registered() -> None:
    assert set(Base.metadata.tables) >= EXPECTED_TABLES


def test_every_table_has_conventional_core_columns() -> None:
    for name in EXPECTED_TABLES:
        table = Base.metadata.tables[name]
        for column in ("id", "public_id", "created_at", "updated_at"):
            assert column in table.c, f"{name} is missing {column}"
        assert table.c.created_at.server_default is not None, (
            f"{name}.created_at must be database-generated"
        )


def test_constraint_names_follow_the_naming_convention() -> None:
    for name in EXPECTED_TABLES:
        table = Base.metadata.tables[name]
        assert table.primary_key.name == f"pk_{name}"
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                assert constraint.name is not None
                assert str(constraint.name).startswith(f"uq_{name}_"), (
                    f"unconventional unique name on {name}: {constraint.name}"
                )


def test_membership_pairs_are_unique_at_database_level() -> None:
    table = Base.metadata.tables["memberships"]
    unique_column_sets = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("organization_id", "user_id") in unique_column_sets


def test_public_ids_are_prefixed_and_random() -> None:
    first, second = generate_public_id("org"), generate_public_id("org")
    assert first.startswith("org_") and second.startswith("org_")
    assert first != second
    assert len(first) == len("org_") + 24
