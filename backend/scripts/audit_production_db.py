"""Read-only audit of production SQLite databases (no writes)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PATHS = [
    Path(r"D:\AzmusERP\Data\database\azmus.db"),
]

FORBIDDEN_PATHS = [
    Path(r"C:\Users\user\Desktop\AzmusCRM\backend\azmus_new.db"),
    Path(r"C:\Users\user\Desktop\AzmusCRM\backend\database.db"),
]

KEY_TABLES = [
    "users",
    "orders",
    "order_history",
    "order_images",
    "tasks",
    "llp_documents",
    "llp_document_versions",
    "materials",
    "material_categories",
    "mes_product_categories",
    "mes_product_templates",
    "mes_production_jobs",
    "mes_product_parts",
    "package_labels",
    "print_jobs",
    "system_settings",
]


def audit_db(path: Path) -> dict:
    if not path.is_file():
        return {"path": str(path), "exists": False}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [r[0] for r in cur.fetchall() if not r[0].startswith("sqlite_")]
    counts = {}
    for t in all_tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM [{t}]")
            counts[t] = cur.fetchone()[0]
        except sqlite3.Error as exc:
            counts[t] = f"error:{exc}"
    conn.close()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "table_count": len(all_tables),
        "counts": counts,
        "all_tables": all_tables,
    }


def main() -> None:
    upload_root = Path(r"D:\AzmusERP\Data\uploads")
    llp_root = upload_root / "llp"
    upload_files = list(upload_root.rglob("*")) if upload_root.is_dir() else []
    file_count = sum(1 for p in upload_files if p.is_file())
    llp_count = sum(1 for p in llp_root.rglob("*") if p.is_file()) if llp_root.is_dir() else 0

    print("UPLOAD_ROOT", upload_root, "exists=", upload_root.is_dir())
    print("upload_files_total", file_count)
    print("llp_files", llp_count)
    print()

    for path in FORBIDDEN_PATHS:
        r = audit_db(path)
        print("=" * 60)
        print("FORBIDDEN (must not be active):", r["path"])
        print("  exists:", r.get("exists", False))

    for path in PATHS:
        r = audit_db(path)
        print("=" * 60)
        print("DB:", r["path"])
        if not r.get("exists"):
            print("  MISSING")
            continue
        print("  size:", r["size_bytes"])
        print("  tables:", r["table_count"])
        for k in KEY_TABLES:
            if k in r["counts"]:
                print(f"  {k}: {r['counts'][k]}")
        llp_tables = {k: v for k, v in r["counts"].items() if "llp" in k.lower()}
        if llp_tables:
            print("  llp_related:", llp_tables)
        mes_sum = sum(
            v for k, v in r["counts"].items() if k.startswith("mes_") and isinstance(v, int)
        )
        print("  mes_row_sum:", mes_sum)


if __name__ == "__main__":
    main()
