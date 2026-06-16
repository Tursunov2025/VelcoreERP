"""Verify Phase 12 GPS schema on production DB (read-only)."""
import sqlite3

DB = r"D:\AzmusERP\Data\database\azmus.db"
TABLES = ("vehicles", "drivers", "gps_locations", "trip_routes")

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
found = [
    r[0]
    for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('vehicles','drivers','gps_locations','trip_routes')"
    )
]
print("phase12 tables:", sorted(found))
for t in ("orders", "tasks", "documents", "mes_production_jobs", "users"):
    print(t, "=", conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
conn.close()
assert len(found) == len(TABLES), f"missing tables: {set(TABLES)-set(found)}"
print("OK")
