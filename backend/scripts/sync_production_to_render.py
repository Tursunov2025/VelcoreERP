"""
Export local production data (D:\\AzmusERP\\Data) and import into Render.

Does NOT modify the local production database except creating an export ZIP.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

# Production paths before app import
os.environ["DATA_ROOT"] = r"D:\AzmusERP\Data"
os.environ["DB_PATH"] = r"D:\AzmusERP\Data\database\azmus.db"
os.environ["UPLOAD_PATH"] = r"D:\AzmusERP\Data\uploads"
os.environ["MIGRATION_BACKUP_PATH"] = r"D:\AzmusERP\Data\migrations"
os.environ.setdefault("SKIP_DEMO_SEED", "true")

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

RENDER_API = os.getenv("RENDER_API_URL", "https://azmus-crm.onrender.com").rstrip("/")
ADMIN_USER = os.getenv("SYNC_ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("SYNC_ADMIN_PASS", "1234")

OUT_DIR = Path(r"D:\AzmusERP\Data\migrations\cloud_sync")
EXPECTED = {
    "orders": 3,
    "tasks": 4,
    "documents": 5,
    "mes_templates": 7,  # API: non-deleted templates (DB has 9 incl. 2 soft-deleted)
    "mes_templates_db": 9,
    "mes_jobs": 10,
    "users": 9,
}


def build_package() -> tuple[Path, dict]:
    from services.migration import build_export_bundle, export_filename

    options = {
        "include_database": True,
        "include_llp_files": True,
        "include_branding_files": True,
        "include_mes_files": True,
        "include_tasks": True,
        "include_permissions": True,
        "include_notification_settings": True,
        "include_telegram_settings": True,
    }
    zip_path, manifest = build_export_bundle(options, label="local-production-to-render")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / export_filename()
    shutil.copy2(zip_path, dest)
    try:
        Path(zip_path).unlink(missing_ok=True)
    except OSError:
        pass
    manifest["zip_path"] = str(dest)
    manifest["zip_size_bytes"] = dest.stat().st_size
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return dest, manifest


def import_to_render(zip_path: Path) -> dict:
    import httpx

    with httpx.Client(base_url=RENDER_API, timeout=300.0) as client:
        login = client.post(
            "/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with zip_path.open("rb") as f:
            files = {"file": (zip_path.name, f, "application/zip")}
            data = {"admin_password": ADMIN_PASS, "confirm": "true"}
            resp = client.post(
                "/admin/migration/import",
                headers=headers,
                files=files,
                data=data,
            )
        log = {
            "status_code": resp.status_code,
            "body": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text[:2000],
        }
        if resp.status_code >= 400:
            raise RuntimeError(f"Import failed: {log}")
        return log


def count_templates_in_zip(zip_path: Path) -> int:
    with zipfile.ZipFile(zip_path) as zf:
        db_name = next((n for n in zf.namelist() if n.endswith("database.db")), None)
        if not db_name:
            return 0
        with zf.open(db_name) as src:
            tmp = Path(tempfile.mkdtemp()) / "database.db"
            tmp.write_bytes(src.read())
        try:
            conn = sqlite3.connect(tmp)
            try:
                return conn.execute("SELECT COUNT(*) FROM mes_product_templates").fetchone()[0]
            finally:
                conn.close()
        finally:
            tmp.unlink(missing_ok=True)


def verify_render_counts() -> dict:
    import httpx

    with httpx.Client(base_url=RENDER_API, timeout=60.0) as client:
        login = client.post(
            "/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        orders = client.get("/orders", headers=headers).json()
        tasks_active = client.get("/tasks", headers=headers).json()
        tasks_archived = client.get("/tasks", params={"archived": "true"}, headers=headers).json()
        tasks = (
            (tasks_active if isinstance(tasks_active, list) else [])
            + (tasks_archived if isinstance(tasks_archived, list) else [])
        )
        llp = client.get("/llp/documents", headers=headers)
        llp.raise_for_status()
        llp_docs = llp.json()
        if not isinstance(llp_docs, list):
            llp_docs = llp_docs.get("documents", []) if isinstance(llp_docs, dict) else []

        mes_templates = client.get(
            "/mes/templates",
            params={"include_inactive": "true"},
            headers=headers,
        )
        mes_templates.raise_for_status()
        tpl_body = mes_templates.json()
        tpl_list = tpl_body.get("templates", tpl_body) if isinstance(tpl_body, dict) else tpl_body

        mes_jobs = client.get("/mes/jobs", headers=headers)
        mes_jobs.raise_for_status()
        job_body = mes_jobs.json()
        job_list = job_body if isinstance(job_body, list) else job_body.get("jobs", [])

        users = client.get("/users", headers=headers)
        user_list = users.json() if users.status_code == 200 else []

        counts = {
            "orders": len(orders) if isinstance(orders, list) else 0,
            "tasks": len(tasks) if isinstance(tasks, list) else 0,
            "tasks_active": len(tasks_active) if isinstance(tasks_active, list) else 0,
            "tasks_archived": len(tasks_archived) if isinstance(tasks_archived, list) else 0,
            "llp_documents": len(llp_docs) if isinstance(llp_docs, list) else 0,
            "mes_templates": len(tpl_list) if isinstance(tpl_list, list) else 0,
            "mes_jobs": len(job_list) if isinstance(job_list, list) else 0,
            "users": len(user_list) if isinstance(user_list, list) else 0,
        }
        return counts


def main() -> None:
    verify_only = "--verify-only" in sys.argv
    zip_path = None
    manifest: dict = {}
    if verify_only:
        existing = sorted(OUT_DIR.glob("velcore_migration_v*.zip"), key=lambda p: p.stat().st_mtime)
        if not existing:
            print("No migration ZIP in", OUT_DIR)
            sys.exit(1)
        zip_path = existing[-1]
        manifest_path = OUT_DIR / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        print("=== Verify-only (no export/import) ===")
        print(f"Package: {zip_path}")
    else:
        print("=== Step 1: Export local production ===")
        zip_path, manifest = build_package()
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Package: {zip_path}")
    print(f"Size: {zip_path.stat().st_size} bytes ({size_mb:.2f} MB)")
    print("Manifest counts:", json.dumps(manifest.get("counts", {}), indent=2))

    import_log: dict = {}
    if not verify_only:
        print("\n=== Step 2: Import to Render ===")
        print(f"API: {RENDER_API}")
        import_log = import_to_render(zip_path)
        print(json.dumps(import_log, indent=2))
        log_path = OUT_DIR / "import_log.json"
        log_path.write_text(json.dumps(import_log, indent=2), encoding="utf-8")
    else:
        hist_log = OUT_DIR / "import_log.json"
        if hist_log.is_file():
            import_log = json.loads(hist_log.read_text(encoding="utf-8"))
            print("\n=== Step 2: Import log (cached) ===")
            print(json.dumps(import_log, indent=2))

    print("\n=== Step 3: Verify Render API counts ===")
    counts = verify_render_counts()
    print(json.dumps(counts, indent=2))
    ok = True
    mapping = {
        "orders": "orders",
        "tasks": "tasks",
        "documents": "llp_documents",
        "mes_templates": "mes_templates",
        "mes_jobs": "mes_jobs",
        "users": "users",
    }
    for exp_key, api_key in mapping.items():
        exp = EXPECTED[exp_key]
        got = counts.get(api_key, 0)
        match = got == exp
        print(f"  {exp_key}: expected {exp}, got {got} {'OK' if match else 'FAIL'}")
        if not match:
            ok = False
    db_tpl = EXPECTED.get("mes_templates_db")
    pkg_tpl = count_templates_in_zip(zip_path)
    if db_tpl is not None and pkg_tpl == db_tpl:
        print(f"  mes_templates_db (zip database): expected {db_tpl}, got {pkg_tpl} OK")
    elif db_tpl is not None:
        print(f"  mes_templates_db (zip database): expected {db_tpl}, got {pkg_tpl} FAIL")
        ok = False
    if not ok:
        sys.exit(1)
    print("\nAll counts match. Vercel (https://azmus-crm.vercel.app) uses Render API — refresh to see data.")


if __name__ == "__main__":
    main()
