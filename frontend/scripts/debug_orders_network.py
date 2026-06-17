"""Capture login + GET /orders network from local dev and Vercel."""
from playwright.sync_api import sync_playwright

CASES = [
    ("local_dev", "http://127.0.0.1:5173"),
    ("vercel", "https://azmus-crm.vercel.app"),
]


def run_case(name, base):
    logs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on(
            "console",
            lambda msg: logs.append(f"console:{msg.type}:{msg.text}"),
        )

        def on_request(req):
            if "/auth/login" in req.url or "/orders" in req.url or "onrender" in req.url:
                logs.append(f"req:{req.method} {req.url}")

        def on_response(res):
            url = res.url
            if "/auth/login" in url or "/orders" in url or "onrender" in url:
                logs.append(f"res:{res.status} {url}")

        page.on("request", on_request)
        page.on("response", on_response)

        page.goto(f"{base}/login", timeout=30000)
        page.wait_for_selector("select", timeout=20000)
        page.select_option("select", "admin")
        page.fill("input[type=password]", "1234")
        page.click("button[type=submit]")
        page.wait_for_timeout(3000)
        page.goto(f"{base}/orders", timeout=30000)
        page.wait_for_timeout(4000)
        cards = page.locator("[class*='rounded']").count()
        text = page.inner_text("body")[:500]
        browser.close()
    print(f"\n=== {name} ({base}) ===")
    for line in logs:
        print(line)
    print("body snippet:", text.replace("\n", " ")[:200])


if __name__ == "__main__":
    for name, base in CASES:
        try:
            run_case(name, base)
        except Exception as e:
            print(f"\n=== {name} FAILED ===", e)
