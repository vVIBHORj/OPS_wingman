"""
Unit tests and regression coverage for Alembic database migrations.

Verifies:
- Linear migration graph with a single head and no missing revisions
- Successful migration of a fresh database from base to 0005_audit_events
- Idempotent execution of 1605711be9a0 without duplicate column errors
- order_items.updated_at column exists exactly once
"""

from pathlib import Path
import sqlalchemy as sa
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

REPO_ROOT = Path(__file__).parent.parent.parent.resolve()


def test_migration_graph_structure():
    """Verifies that the Alembic migration history is linear with a single head."""
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)

    # 1. Exactly one head revision
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 head, got: {heads}"
    assert heads[0] == "0005_audit_events"

    # 2. Linear revision walk from head to base
    expected_chain = [
        "0005_audit_events",
        "0004_idempotency_records",
        "1605711be9a0",
        "0003_rag_and_approvals",
        "0002_domain_events",
        "0001_initial_schema",
    ]

    current = heads[0]
    visited = []
    while current:
        assert isinstance(current, str)
        visited.append(current)
        rev = script.get_revision(current)
        assert rev is not None, f"Revision {current} not found in script directory"
        current = rev.down_revision

    assert visited == expected_chain, f"Revision chain mismatch: {visited} != {expected_chain}"


def test_fresh_database_migration_to_head(tmp_path, monkeypatch):
    """Verifies that a fresh database successfully migrates from base to head without duplicate column errors."""
    db_file = tmp_path / "fresh_test.db"
    sqlite_url = f"sqlite:///{db_file.as_posix()}"

    monkeypatch.setenv("DATABASE_SYNC_URL", sqlite_url)

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", sqlite_url)

    # Run upgrade to head
    command.upgrade(cfg, "head")

    # Inspect migrated database
    engine = sa.create_engine(sqlite_url)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current_rev = ctx.get_current_revision()
        assert current_rev == "0005_audit_events", f"Expected head 0005_audit_events, got {current_rev}"

        insp = sa.inspect(conn)
        assert insp.has_table("order_items")

        columns = [c["name"] for c in insp.get_columns("order_items")]
        updated_at_count = columns.count("updated_at")
        assert updated_at_count == 1, f"Expected updated_at to exist exactly once, found {updated_at_count} times"

        # Verify other required tables from the full migration chain exist
        assert insp.has_table("orders")
        assert insp.has_table("domain_events")
        assert insp.has_table("knowledge_documents")
        assert insp.has_table("knowledge_chunks")
        assert insp.has_table("approval_records")
        assert insp.has_table("idempotency_records")
        assert insp.has_table("audit_events")


def test_idempotent_migration_execution(tmp_path, monkeypatch):
    """Verifies that running upgrade head repeatedly is fully idempotent."""
    db_file = tmp_path / "idempotent_test.db"
    sqlite_url = f"sqlite:///{db_file.as_posix()}"

    monkeypatch.setenv("DATABASE_SYNC_URL", sqlite_url)

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", sqlite_url)

    # Initial upgrade
    command.upgrade(cfg, "head")

    # Second upgrade (should be no-op and succeed)
    command.upgrade(cfg, "head")

    engine = sa.create_engine(sqlite_url)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() == "0005_audit_events"
