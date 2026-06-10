"""Debug Vercel app load — console errors and loading state."""

from playwright.sync_api import sync_playwright

URL = "https://azmus-crm.vercel.app/login"

def main() -> None:
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: errors.append(f"[pageerror] {err}"))
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(8000)
        text = page.inner_text("body")
        print("=== body snippet ===")
        print(text[:800])
        print("=== still loading? ===", "Yuklanmoqda" in text)
        print("=== console ===")
        for line in errors[:40]:
            print(line)
        page.screenshot(path=r"D:\AzmusERP\Data\migrations\cloud_sync\screenshots\login_debug.png", full_page=True)
        browser.close()

if __name__ == "__main__":
    main()
