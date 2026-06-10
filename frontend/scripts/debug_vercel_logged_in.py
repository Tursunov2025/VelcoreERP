"""Simulate logged-in user on Vercel — detect infinite loading."""

import httpx
from playwright.sync_api import sync_playwright

API = "https://azmus-crm.onrender.com"
URL = "https://azmus-crm.vercel.app/"

def main() -> None:
    c = httpx.Client(base_url=API, timeout=60)
    login = c.post("/auth/login", json={"username": "admin", "password": "1234"}).json()
    tokens = {
        "access_token": login["access_token"],
        "refresh_token": login["refresh_token"],
        "username": login["username"],
        "role": login["role"],
        "department": login.get("department", "Admin"),
    }
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: errors.append(f"[pageerror] {err}"))
        page.goto("https://azmus-crm.vercel.app/login", wait_until="domcontentloaded")
        page.evaluate(
            """(tokens) => localStorage.setItem('azmus_tokens', JSON.stringify(tokens))""",
            tokens,
        )
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(10000)
        text = page.inner_text("body")
        print("URL:", page.url)
        print("loading stuck:", "Yuklanmoqda" in text)
        print("dashboard hint:", "Dashboard" in text or "Zakazlar" in text or "Velcore" in text)
        print("body[:600]:", text[:600])
        print("errors:")
        for e in errors[:30]:
            print(e)
        page.screenshot(path=r"D:\AzmusERP\Data\migrations\cloud_sync\screenshots\dashboard_logged_in.png", full_page=True)
        browser.close()

if __name__ == "__main__":
    main()
