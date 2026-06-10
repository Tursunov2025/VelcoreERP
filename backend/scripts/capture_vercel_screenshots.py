"""Capture Vercel screenshots after Render import."""

from pathlib import Path

from playwright.sync_api import sync_playwright

VERCEL = "https://azmus-crm.vercel.app"
OUT = Path(r"D:\AzmusERP\Data\migrations\cloud_sync\screenshots\diagnose")


def capture(path_suffix: str, url: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / path_suffix
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{VERCEL}/login", wait_until="networkidle", timeout=120_000)
        page.wait_for_selector("select", timeout=60_000)
        page.select_option("select", "admin")
        page.fill('input[type="password"]', "1234")
        page.click('button[type="submit"]')
        page.wait_for_function("() => !window.location.pathname.includes('login')", timeout=60_000)
        page.wait_for_timeout(2000)
        page.goto(url, wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(dest), full_page=True)
        browser.close()
    print(f"saved {dest}")
    return dest


if __name__ == "__main__":
    capture("vercel_orders_with_data.png", f"{VERCEL}/orders")
    capture("vercel_mes_jobs_with_data.png", f"{VERCEL}/mes/jobs")
