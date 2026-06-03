"""
Azmus Cloud Print Agent — polls Render ERP and prints labels to local USB/shared printers.

Supports XPrinter XP-350B and any Windows printer visible to win32print.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

API_URL = os.getenv("AZMUS_API_URL", "https://azmus-crm.onrender.com").rstrip("/")
API_KEY = os.getenv("PRINT_AGENT_API_KEY", "").strip()
PRINTER_NAME = os.getenv("PRINTER_NAME", "XPrinter XP-350B").strip()
WINDOWS_PRINTER = os.getenv("WINDOWS_PRINTER_NAME", PRINTER_NAME).strip()
POLL_SEC = float(os.getenv("POLL_INTERVAL_SECONDS", "5"))
VERSION = os.getenv("AGENT_VERSION", "1.0.0")
HOSTNAME = os.getenv("COMPUTERNAME", "windows-pc")


def headers() -> dict:
    return {"Authorization": f"Bearer {API_KEY}"}


def api_post(path: str, json_body: dict | None = None) -> dict:
    r = requests.post(f"{API_URL}{path}", headers=headers(), json=json_body or {}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"{path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def api_get(path: str) -> requests.Response:
    return requests.get(f"{API_URL}{path}", headers=headers(), timeout=60)


def send_heartbeat() -> None:
    try:
        api_post(
            "/printing/agent/heartbeat",
            {
                "printer_name": PRINTER_NAME,
                "hostname": HOSTNAME,
                "agent_version": VERSION,
            },
        )
    except Exception as exc:
        print(f"[heartbeat] {exc}")


def print_png_windows(png_path: str, printer_name: str) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows printing requires win32print (run on Windows)")
    import win32print
    import win32ui
    from PIL import Image

    img = Image.open(png_path)
    if img.mode != "RGB":
        img = img.convert("RGB")

    hprinter = win32print.OpenPrinter(printer_name)
    try:
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        hdc.StartDoc("Azmus Label")
        hdc.StartPage()
        printable = hdc.GetDeviceCaps(8), hdc.GetDeviceCaps(10)
        img.thumbnail((printable[0], printable[1]), Image.Resampling.LANCZOS)
        dib = img.tobytes("raw", "RGB")
        from PIL import ImageWin

        bmp = ImageWin.Dib(img)
        bmp.draw(hdc.GetHandleOutput(), (0, 0, img.width, img.height))
        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
    finally:
        win32print.ClosePrinter(hprinter)


def process_job(job: dict) -> None:
    job_id = job["id"]
    label_code = job.get("label_code", "")
    print(f"[print] job {job_id} {label_code}")
    api_post(f"/printing/jobs/{job_id}/start")
    try:
        resp = api_get(f"/printing/jobs/{job_id}/label.png")
        if resp.status_code != 200:
            raise RuntimeError(f"label download {resp.status_code}")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        try:
            print_png_windows(tmp_path, WINDOWS_PRINTER)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        api_post(f"/printing/jobs/{job_id}/complete")
        print(f"[ok] job {job_id} completed")
    except Exception as exc:
        api_post(f"/printing/jobs/{job_id}/failed", {"error_message": str(exc)})
        print(f"[fail] job {job_id}: {exc}")


def poll_once() -> None:
    send_heartbeat()
    r = api_get(f"/printing/jobs/pending?printer_name={requests.utils.quote(PRINTER_NAME)}")
    if r.status_code != 200:
        print(f"[poll] {r.status_code} {r.text[:200]}")
        return
    jobs = r.json().get("jobs") or []
    for job in jobs:
        process_job(job)


def main() -> None:
    if not API_KEY:
        print("Set PRINT_AGENT_API_KEY in .env (must match Render PRINT_AGENT_API_KEY)")
        sys.exit(1)
    print(f"Azmus Print Agent v{VERSION}")
    print(f"API: {API_URL}")
    print(f"ERP printer: {PRINTER_NAME}")
    print(f"Windows printer: {WINDOWS_PRINTER}")
    while True:
        try:
            poll_once()
        except Exception as exc:
            print(f"[error] {exc}")
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
