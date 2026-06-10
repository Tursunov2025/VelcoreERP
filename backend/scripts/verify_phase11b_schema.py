"""Verify Phase 11B additive schema on the production database (read-only)."""
import sqlite3

DB = r"D:\AzmusERP\Data\database\azmus.db"

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
tables = [
    r[0]
    for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('currencies','exchange_rates','transports','transport_events','customer_payments')"
    )
]
print("new tables:", sorted(tables))
print("currencies:", conn.execute("SELECT code, is_base FROM currencies ORDER BY sort_order").fetchall())
cols = [r[1] for r in conn.execute("PRAGMA table_info(orders)")]
print("orders.currency column:", "currency" in cols)
for t in ("orders", "tasks", "documents", "mes_production_jobs", "users"):
    print(t, "=", conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
conn.close()
