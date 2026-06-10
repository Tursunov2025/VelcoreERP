"""Diagnose where ERP data disappears (DB vs API vs cloud)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

PROD_DB = Path(r"D:\AzmusERP\Data\database\azmus.db")
OUT = Path(r"D:\AzmusERP\Data\migrations\cloud_sync\screenshots\diagnose")
LOCAL = "http://127.0.0.1:8000"
RENDER = "https://azmus-crm.onrender.com"
VERCEL = "https://azmus-crm.vercel.app"


def sqlite_counts() -> dict:
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    try:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("orders", "tasks", "documents", "mes_production_jobs", "users")
        }
    finally:
        conn.close()


def api_probe(base: str) -> dict:
    out: dict = {"base": base, "health": {}, "endpoints": {}}
    c = httpx.Client(base_url=base, timeout=60)
    try:
        out["health"] = c.get("/").json()
    except Exception as exc:
        out["health_error"] = str(exc)
        return out
    try:
        token = c.post("/auth/login", json={"username": "admin", "password": "1234"}).json()[
            "access_token"
        ]
        h = {"Authorization": f"Bearer {token}"}
        for path in ("/orders", "/tasks", "/llp/documents", "/mes/jobs", "/users"):
            r = c.get(path, headers=h)
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
            if isinstance(body, list):
                count = len(body)
            elif isinstance(body, dict):
                count = len(body.get("documents", body.get("jobs", body)))
            else:
                count = None
            out["endpoints"][path] = {"status": r.status_code, "count": count, "sample": body}
    except Exception as exc:
        out["api_error"] = str(exc)
    return out


def screenshot_ui(base_url: str, name: str, api_label: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{base_url}/login", wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("select", timeout=60_000)
        page.select_option("select", "admin")
        page.fill('input[type="password"]', "1234")
        page.click('button[type="submit"]')
        page.wait_for_function("() => !window.location.pathname.includes('login')", timeout=60_000)
        page.wait_for_timeout(2000)
        page.goto(f"{base_url}/orders", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(2000)
        dest = OUT / f"{name}_orders.png"
        page.screenshot(path=str(dest), full_page=True)
        print(f"screenshot {dest} (API={api_label})")
        browser.close()


def main() -> None:
    report = {
        "production_db_file": str(PROD_DB),
        "sqlite_counts": sqlite_counts(),
        "frontend": {
            "development_VITE_API_URL": "http://127.0.0.1:8000",
            "production_VITE_API_URL": RENDER,
            "vercel_ui": VERCEL,
        },
        "local_api": api_probe(LOCAL),
        "render_api": api_probe(RENDER),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str)[:6000])
    try:
        screenshot_ui(VERCEL, "vercel", RENDER)
    except Exception as exc:
        print("vercel screenshot failed:", exc)
    try:
        screenshot_ui("http://localhost:5173", "local_dev", LOCAL)
    except Exception as exc:
        print("local dev screenshot skipped:", exc)


if __name__ == "__main__":
    main()
