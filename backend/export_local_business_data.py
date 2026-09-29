"""Read-only SQLite snapshot export; preserves inactive, deleted and test records."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

try:
    from .business_transfer import FORMAT, TABLE_KEYS, REFERENCE_KEYS, LOGICAL_FKS, primary_key
except ImportError:
    from business_transfer import FORMAT, TABLE_KEYS, REFERENCE_KEYS, LOGICAL_FKS, primary_key


def checksum(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def export_snapshot(path):
    path = Path(path).resolve(strict=True)
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("Source integrity check failed")
        tables, schema, references, problems = {}, {}, {}, []
        all_tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        inventory = {t: db.execute('SELECT count(*) FROM "' + t.replace('"', '""') + '"').fetchone()[0] for t in all_tables}
        for name in TABLE_KEYS:
            if name not in all_tables:
                raise ValueError(f"Required source table missing: {name}")
            schema[name] = {
                "columns": [dict(r) for r in db.execute(f'PRAGMA table_info("{name}")')],
                "foreign_keys": [dict(r) for r in db.execute(f'PRAGMA foreign_key_list("{name}")')],
                "unique_keys": [[x["name"] for x in db.execute('PRAGMA index_info("' + idx["name"].replace('"', '""') + '")')] for idx in db.execute(f'PRAGMA index_list("{name}")').fetchall() if idx["unique"]],
            }
            tables[name] = [dict(r) for r in db.execute(f'SELECT * FROM "{name}" ORDER BY "{primary_key(name)}"')]
        visited = set()

        def collect(table, source_id):
            if (table, source_id) in visited:
                return
            visited.add((table, source_id))
            if table in tables:
                row = next((r for r in tables[table] if r[primary_key(table)] == source_id), None)
            elif table in REFERENCE_KEYS and table in all_tables:
                raw = db.execute(f'SELECT * FROM "{table}" WHERE id=?', (source_id,)).fetchone()
                row = {k: raw[k] for k in ("id", *REFERENCE_KEYS[table])} if raw else None
                if row:
                    references.setdefault(table, []).append(row)
            else:
                row = None
            if row is None:
                problems.append({"table": table, "source_id": source_id, "code": "missing_source_dependency"})
                return
            for col, parent in LOGICAL_FKS.get(table, {}).items():
                if row.get(col) is not None:
                    collect(parent, row[col])

        for name, rows in tables.items():
            for row in rows:
                collect(name, row[primary_key(name)])
        payload = {"format": FORMAT, "exported_at": datetime.now(timezone.utc).isoformat(),
                   "integrity": integrity, "tables": tables, "schema": schema,
                   "references": references, "dependency_errors": problems,
                   "source_table_counts": inventory, "exclusions": []}
        payload["sha256"] = checksum(payload)
        return payload
    finally:
        db.rollback()
        db.close()


def write_new_json(path, payload):
    # Never overwrite an existing source, database, report or export.
    with Path(path).open("x", encoding="utf-8") as out:
        json.dump(payload, out, ensure_ascii=False, indent=2, default=str)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = export_snapshot(args.database)
    write_new_json(args.output, payload)
    print(json.dumps({"export": str(args.output), "integrity": payload["integrity"],
                      "counts": {t: len(r) for t, r in payload["tables"].items()},
                      "dependency_errors": payload["dependency_errors"], "sha256": payload["sha256"]}, indent=2))
    return 0 if not payload["dependency_errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
