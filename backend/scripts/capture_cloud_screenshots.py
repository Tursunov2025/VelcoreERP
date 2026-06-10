"""Capture Vercel UI screenshots after cloud sync (Orders, LLP, MES jobs)."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://azmus-crm.vercel.app"
USER = "admin"
PASS = "1234"
OUT = Path(r"D:\AzmusERP\Data\migrations\cloud_sync\screenshots")
PAGES = [
    ("orders", f"{BASE}/orders"),
    ("llp", f"{BASE}/llp"),
    ("mes_jobs", f"{BASE}/mes/jobs"),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("select", timeout=60_000)
        page.select_option("select", USER)
        page.fill('input[type="password"]', PASS)
        page.click('button[type="submit"]')
        page.wait_for_function(
            "() => !window.location.pathname.includes('login')",
            timeout=60_000,
        )
        page.wait_for_timeout(3000)
        for name, url in PAGES:
            page.goto(url, wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(2000)
            dest = OUT / f"{name}.png"
            page.screenshot(path=str(dest), full_page=True)
            print(f"saved {dest}")
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"screenshot failed: {exc}", file=sys.stderr)
        sys.exit(1)
