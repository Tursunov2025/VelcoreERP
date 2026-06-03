"""Send ZPL label jobs to network printers (Zebra, TSC, XPrinter, Godex)."""

from __future__ import annotations

import json
import socket
from typing import Any

from sqlalchemy.orm import Session

from models import PackageLabel
from services.settings_store import get_settings_group

SUPPORTED_BRANDS = ("Zebra", "TSC", "XPrinter", "Godex", "Generic")


def get_printers_config(db: Session) -> list[dict[str, Any]]:
    raw = get_settings_group(db, "label_printers").get("label_printers_json", "[]")
    try:
        data = json.loads(raw or "[]")
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def save_printers_config(db: Session, printers: list[dict]) -> list[dict]:
    from services.settings_store import update_settings

    payload = json.dumps(printers, ensure_ascii=False)
    update_settings(db, {"label_printers_json": payload})
    return printers


def pick_auto_printer(printers: list[dict]) -> dict | None:
    for p in printers:
        if p.get("auto_print_enabled"):
            return p
    return printers[0] if printers else None


def build_zpl_label(
    *,
    company: str,
    label_code: str,
    product: str,
    weight_kg: float,
    quantity: int = 1,
) -> str:
    weight_txt = f"{weight_kg:g} kg" if weight_kg else "—"
    return f"""^XA
^CF0,40
^FO40,30^FD{company}^FS
^CF0,28
^FO40,80^FDPackage:^FS
^FO200,80^FD{label_code}^FS
^FO40,120^FDProduct:^FS
^FO200,120^FD{product}^FS
^FO40,160^FDWeight:^FS
^FO200,160^FD{weight_txt}^FS
^FO40,200^FDQty:^FS
^FO200,200^FD{quantity}^FS
^FO40,250^BQN,2,6^FDQA,{label_code}^FS
^FO40,420^BCN,80,Y,N,N^FD{label_code}^FS
^XZ
"""


def send_zpl_to_printer(printer: dict, zpl: str, *, timeout: float = 8.0) -> None:
    host = (printer.get("ip_address") or "").strip()
    port = int(printer.get("port") or 9100)
    if not host:
        raise ValueError("Printer IP address is required")
    payload = zpl.encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(payload)


def print_package_label(
    db: Session,
    label: PackageLabel,
    *,
    package_meta: dict,
    printer: dict | None = None,
) -> str | None:
    printers = get_printers_config(db)
    target = printer or pick_auto_printer(printers)
    if not target:
        return None
    company = get_settings_group(db, "company").get("company_name", "AZMUS FURNITURE")
    zpl = build_zpl_label(
        company=company.upper() if company else "AZMUS FURNITURE",
        label_code=label.label_code,
        product=package_meta.get("product_name") or package_meta.get("product_code") or "—",
        weight_kg=float(package_meta.get("net_weight_kg") or 0),
        quantity=int(package_meta.get("quantity") or 1),
    )
    send_zpl_to_printer(target, zpl)
    return target.get("name") or target.get("printer_name") or "default"
