"""Capture Vercel pages using UI login."""

from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "https://azmus-crm.vercel.app"
OUT = Path(r"D:\AzmusERP\Data\migrations\cloud_sync\screenshots\fix_verify")
PAGES = ["", "orders", "mes", "llp", "settings"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("select", timeout=60_000)
        page.select_option("select", "admin")
        page.fill('input[type="password"]', "1234")
        page.click('button[type="submit"]')
        page.wait_for_function("() => !window.location.pathname.includes('login')", timeout=60_000)
        page.wait_for_timeout(3000)
        for path in PAGES:
            name = path or "dashboard"
            url = f"{BASE}/{path}" if path else f"{BASE}/"
            page.goto(url, wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(2500)
            body = page.inner_text("body")
            print(f"{name}: loading={'Yuklanmoqda' in body} url={page.url}")
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
