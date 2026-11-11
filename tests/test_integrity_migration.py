
"""Static safeguards for the additive index-only migration (no database writes)."""

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations/004_sales_integrity_indexes.sql"
)


def test_index_migration_is_additive_and_idempotent():
    """Verify the SQL contains the expected indexes and no destructive operations."""

    sql = MIGRATION.read_text()

    # Exclude SQL comments before checking statements.
    sql_statements = "\n".join(
        line
        for line in sql.splitlines()
        if not line.lstrip().startswith("--")
    ).lower()

    # All three indexes must be safe to recreate.
    assert sql_statements.count("create index if not exists") == 3

    # Prevent destructive database operations.
    assert "drop table" not in sql_statements
    assert "truncate " not in sql_statements
    assert "delete from" not in sql_statements
    assert "update " not in sql_statements
    assert "alter table" not in sql_statements

    # Verify indexes target the expected upload fields.
    assert "raw_data->>'sha256'" in sql_statements
    assert "raw_data->>'data_hash'" in sql_statements
    assert "business_id" in sql_statements

