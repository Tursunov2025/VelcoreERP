"""Read-only local database preflight used by scripts/start-local.ps1."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

EXPECTED_TABLES = {"users", "orders", "tasks", "mes_production_jobs"}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: check_local_database.py <database-path>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1]).resolve()
    if not path.is_file():
        print(f"Database not found: {path}", file=sys.stderr)
        return 1
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        connection.close()
    missing = sorted(EXPECTED_TABLES - tables)
    if missing:
        print(f"Database is missing required tables: {', '.join(missing)}", file=sys.stderr)
        return 1
    print(f"Database preflight OK: {path} ({len(tables)} tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
