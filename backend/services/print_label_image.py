"""Render package label as PNG for cloud print agent."""

from __future__ import annotations

import base64
import io
from typing import Any


def _qr_png_base64(data: str) -> str:
    try:
        import qrcode

        img = qrcode.make(data)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def _barcode_png_base64(data: str) -> str:
    try:
        from barcode import Code128
        from barcode.writer import ImageWriter

        buf = io.BytesIO()
        Code128(data, writer=ImageWriter()).write(buf, options={"write_text": False})
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


def build_label_png_bytes(
    *,
    company: str,
    label_code: str,
    product: str,
    weight_kg: float,
    quantity: int = 1,
) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    width, height = 576, 800
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font_lg = ImageFont.truetype("arial.ttf", 28)
        font_md = ImageFont.truetype("arial.ttf", 22)
        font_sm = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font_lg = ImageFont.load_default()
        font_md = font_lg
        font_sm = font_lg

    y = 20
    draw.text((20, y), company.upper()[:40], fill="black", font=font_lg)
    y += 50
    for label, value in (
        ("Package:", label_code),
        ("Product:", product or "—"),
        ("Weight:", f"{weight_kg:g} kg" if weight_kg else "—"),
        ("Qty:", str(quantity)),
    ):
        draw.text((20, y), label, fill="black", font=font_sm)
        draw.text((160, y), str(value)[:36], fill="black", font=font_md)
        y += 36

    qr_b64 = _qr_png_base64(label_code)
    if qr_b64:
        import base64

        qr_img = Image.open(io.BytesIO(base64.b64decode(qr_b64)))
        qr_img = qr_img.resize((200, 200))
        img.paste(qr_img, (20, y))
        y += 210

    bc_b64 = _barcode_png_base64(label_code)
    if bc_b64:
        import base64

        bc_img = Image.open(io.BytesIO(base64.b64decode(bc_b64)))
        bc_w = min(width - 40, bc_img.width)
        bc_h = int(bc_img.height * (bc_w / max(bc_img.width, 1)))
        bc_img = bc_img.resize((bc_w, max(bc_h, 40)))
        img.paste(bc_img, (20, y))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def label_meta_from_package(pkg, job, template) -> dict[str, Any]:
    return {
        "product_name": template.name if template else "",
        "product_code": template.code if template else "",
        "net_weight_kg": float(pkg.net_weight_kg or 0),
        "quantity": 1,
    }
