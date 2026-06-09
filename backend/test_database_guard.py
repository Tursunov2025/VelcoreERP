"""Database guard — production path protection."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

os.environ["DATABASE_GUARD"] = "false"

from config.database_guard import (  # noqa: E402
    CANONICAL_WINDOWS_DB,
    DatabaseGuardError,
    collect_database_stats,
    is_forbidden_database_path,
    is_guard_enabled,
    validate_production_database_at_startup,
)


def test_forbidden_paths() -> None:
    assert is_forbidden_database_path(BACKEND / "azmus_new.db")
    assert is_forbidden_database_path(BACKEND / "database.db")
    assert not is_forbidden_database_path(CANONICAL_WINDOWS_DB)


def test_guard_blocks_missing_db(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    monkeypatch.setenv("DATABASE_GUARD", "true")
    monkeypatch.setenv("SKIP_DEMO_SEED", "true")
    monkeypatch.setenv("DB_PATH", str(missing))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{missing.as_posix()}")

    from importlib import reload
    import config.paths as paths
    import config.database_guard as guard

    reload(paths)
    reload(guard)

    try:
        guard.validate_production_database_at_startup()
        raise AssertionError("expected DatabaseGuardError")
    except guard.DatabaseGuardError as exc:
        assert "not found" in str(exc).lower()


def test_guard_allows_existing_db(monkeypatch, tmp_path: Path) -> None:
    db = tmp_path / "prod.db"
    import sqlite3

    conn = sqlite3.connect(db)
    for i in range(6):
        conn.execute(f"CREATE TABLE t{i} (id INTEGER)")
    for _ in range(3):
        conn.execute("INSERT INTO t0 DEFAULT VALUES")
    conn.execute("CREATE TABLE orders (id INTEGER)")
    conn.execute("CREATE TABLE tasks (id INTEGER)")
    conn.execute("CREATE TABLE documents (id INTEGER)")
    conn.execute("CREATE TABLE mes_production_jobs (id INTEGER)")
    conn.execute("CREATE TABLE users (id INTEGER)")
    for _ in range(3):
        conn.execute("INSERT INTO orders DEFAULT VALUES")
    for _ in range(4):
        conn.execute("INSERT INTO tasks DEFAULT VALUES")
    for _ in range(5):
        conn.execute("INSERT INTO documents DEFAULT VALUES")
    for _ in range(10):
        conn.execute("INSERT INTO mes_production_jobs DEFAULT VALUES")
    for _ in range(9):
        conn.execute("INSERT INTO users DEFAULT VALUES")
    conn.commit()
    conn.close()

    monkeypatch.setenv("DATABASE_GUARD", "true")
    monkeypatch.setenv("DB_PATH", str(db))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db.as_posix()}")
    monkeypatch.setenv("BASELINE_ORDERS", "3")

    from importlib import reload
    import config.paths as paths
    import config.database_guard as guard

    reload(paths)
    reload(guard)
    stats = guard.validate_production_database_at_startup()
    assert stats["orders_count"] == 3


if __name__ == "__main__":
    test_forbidden_paths()
    print("test_database_guard: OK")
