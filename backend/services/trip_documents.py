"""Immutable corporate documents for the canonical MesTrip cargo snapshot."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from sqlalchemy.orm import Session

from config.paths import UPLOAD_PATH
from models import MesShipmentItem, MesTrip, MesTripDocumentSnapshot
from services.corporate_documents import BORDER, NAVY, PALE, WHITE, corporate_branding, language


DOCUMENT_TYPES = {"packing_list", "loading_list", "trip_manifest", "delivery_note"}


def _items(db: Session, trip_id: int) -> list[MesShipmentItem]:
    return (
        db.query(MesShipmentItem)
        .filter(MesShipmentItem.trip_id == trip_id, MesShipmentItem.assignment_status == "active")
        .order_by(MesShipmentItem.project_id, MesShipmentItem.id)
        .all()
    )


def _cargo_payload(trip: MesTrip, items: list[MesShipmentItem]) -> list[dict]:
    rows = []
    for item in items:
        project = item.project_line.project if item.project_line else None
        package = item.package
        rows.append({
            "item_id": item.id,
            "project_id": item.project_id,
            "project": project.project_code if project else f"#{item.project_id}",
            "order": project.project_name if project else "",
            "package": package.package_number if package else f"#{item.package_id}",
            "product": item.template.code if item.template else f"#{item.template_id}",
            "quantity": float(item.assigned_quantity),
            "loaded": float(item.loaded_quantity),
            "delivered": float(item.delivered_quantity),
            "accepted": float(item.accepted_quantity),
            "destination": " · ".join(filter(None, [getattr(project, "destination_city", ""), getattr(project, "site_name", "")])),
            "weight_kg": float(item.gross_weight_kg) if item.gross_weight_kg is not None else None,
            "volume_m3": (float(item.length_mm) * float(item.width_mm) * float(item.height_mm) / 1_000_000_000)
            if all(value is not None for value in (item.length_mm, item.width_mm, item.height_mm)) else None,
        })
    return rows


def _pdf(db: Session, trip: MesTrip, document_type: str, rows: list[dict], lang: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    lang = language(lang)
    labels = {
        "uz": {"packing_list": "Qadoqlash ro‘yxati", "loading_list": "Yuklash ro‘yxati", "trip_manifest": "Reys manifesti", "delivery_note": "Yetkazib berish dalolatnomasi",
               "project": "Loyiha / buyurtma", "package": "Qadoq", "product": "Mahsulot", "qty": "Miqdor", "destination": "Manzil", "weight": "Og‘irlik, kg", "volume": "Hajm, m³", "missing": "Ma’lumot yo‘q"},
        "ru": {"packing_list": "Упаковочный лист", "loading_list": "Погрузочный лист", "trip_manifest": "Манифест рейса", "delivery_note": "Накладная доставки",
               "project": "Проект / заказ", "package": "Упаковка", "product": "Продукция", "qty": "Кол-во", "destination": "Назначение", "weight": "Вес, кг", "volume": "Объём, м³", "missing": "Нет данных"},
    }[lang]
    brand = corporate_branding(db)
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=landscape(A4), leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=13*mm, bottomMargin=13*mm, title=f"{labels[document_type]} {trip.trip_number}")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TripTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=16,
                           leading=19, textColor=colors.HexColor(f"#{WHITE}"))
    body = ParagraphStyle("TripBody", parent=styles["BodyText"], fontSize=8, leading=10)
    header = Table([[Paragraph(brand["name"].upper(), title), Paragraph(f"{labels[document_type]}<br/>{trip.trip_number}", title)]], colWidths=[135*mm, 135*mm])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(f"#{NAVY}")), ("PADDING", (0, 0), (-1, -1), 9)]))
    data = [[labels["project"], labels["package"], labels["product"], labels["qty"], labels["destination"], labels["weight"], labels["volume"]]]
    for row in rows:
        qty = row["loaded"] if document_type in {"loading_list", "trip_manifest"} else row["delivered"] if document_type == "delivery_note" else row["quantity"]
        data.append([f'{row["project"]}\n{row["order"]}', row["package"], row["product"], qty,
                     row["destination"] or labels["missing"], row["weight_kg"] if row["weight_kg"] is not None else labels["missing"],
                     round(row["volume_m3"], 3) if row["volume_m3"] is not None else labels["missing"]])
    table = Table([[Paragraph(str(value), body) for value in row] for row in data], colWidths=[48*mm, 36*mm, 38*mm, 20*mm, 65*mm, 32*mm, 31*mm], repeatRows=1)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .4, colors.HexColor(f"#{BORDER}")),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{PALE}")),
                               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("PADDING", (0, 0), (-1, -1), 5)]))
    doc.build([header, Spacer(1, 6*mm), table])
    return out.getvalue()


def generate_trip_document(db: Session, trip_id: int, document_type: str, actor: str, lang: str = "uz") -> MesTripDocumentSnapshot:
    if document_type not in DOCUMENT_TYPES:
        raise ValueError("unsupported_document_type")
    trip = db.get(MesTrip, trip_id)
    if not trip:
        raise ValueError("trip_not_found")
    rows = _cargo_payload(trip, _items(db, trip.id))
    cargo_hash = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = db.query(MesTripDocumentSnapshot).filter_by(trip_id=trip.id, document_type=document_type,
                                                            scope_project_id=0, cargo_hash=cargo_hash).first()
    if existing:
        return existing
    version = (db.query(MesTripDocumentSnapshot).filter_by(trip_id=trip.id, document_type=document_type).count() + 1)
    content = _pdf(db, trip, document_type, rows, lang)
    relative = Path("trip-documents") / str(trip.id) / f"{document_type}-v{version}-{cargo_hash[:12]}.pdf"
    target = (UPLOAD_PATH / relative).resolve()
    root = UPLOAD_PATH.resolve()
    if root not in target.parents:
        raise ValueError("unsafe_document_path")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    row = MesTripDocumentSnapshot(trip_id=trip.id, document_type=document_type, scope_project_id=0,
                                  cargo_hash=cargo_hash, version=version, original_filename=f"{trip.trip_number}-{document_type}-v{version}.pdf",
                                  mime_type="application/pdf", file_size=len(content), checksum=hashlib.sha256(content).hexdigest(),
                                  storage_relative_path=relative.as_posix(), generated_by=actor)
    db.add(row); db.flush()
    return row


def document_path(row: MesTripDocumentSnapshot) -> Path:
    target = (UPLOAD_PATH / row.storage_relative_path).resolve()
    if UPLOAD_PATH.resolve() not in target.parents or not target.is_file():
        raise ValueError("document_not_found")
    return target
