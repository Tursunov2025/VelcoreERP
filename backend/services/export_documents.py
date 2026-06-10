from __future__ import annotations

import html
import json
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from sqlalchemy.orm import Session

from models import (
    Document,
    DocumentFolder,
    ExportShipment,
    ExportShipmentDocument,
    ExportShipmentItem,
)
from routers.uploads_router import UPLOAD_DIR

EXPORT_UPLOAD_DIR = UPLOAD_DIR / "export_shipments"
EXPORT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DOCUMENT_TYPES = {
    "invoice": "Invoice",
    "packing_list": "Packing List",
    "specification": "Export Specification",
    "contract_attachment": "Contract Attachment",
    "invoice_xlsx": "Invoice.xlsx",
    "packing_list_xlsx": "PackingList.xlsx",
}


def _money(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency}".replace(",", " ")


def _dt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d") if value else ""


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_simple_pdf(title: str, lines: list[str]) -> bytes:
    """Small valid PDF writer for text export docs without adding dependencies."""
    y = 800
    text_ops = ["BT", "/F1 16 Tf", f"50 {y} Td", f"({_pdf_escape(title)}) Tj"]
    y -= 28
    text_ops.extend(["/F1 10 Tf", f"0 -28 Td", "(Company logo: AZMUS ERP) Tj"])
    for line in lines:
        y -= 15
        safe = _pdf_escape(line[:110])
        text_ops.extend(["0 -15 Td", f"({safe}) Tj"])
        if y < 80:
            break
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{idx} 0 obj\n".encode())
        out.write(obj)
        out.write(b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return out.getvalue()


def build_xlsx(sheet_name: str, rows: list[list[object]]) -> bytes:
    def cell_ref(col: int, row: int) -> str:
        name = ""
        col += 1
        while col:
            col, rem = divmod(col - 1, 26)
            name = chr(65 + rem) + name
        return f"{name}{row}"

    sheet_rows = []
    for r_idx, row in enumerate(rows, start=1):
        cells = []
        for c_idx, value in enumerate(row):
            ref = cell_ref(c_idx, r_idx)
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                escaped = html.escape("" if value is None else str(value))
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>')
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(sheet_rows)}</sheetData></worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{html.escape(sheet_name[:31])}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return out.getvalue()


def shipment_lines(shipment: ExportShipment) -> list[str]:
    lines = [
        f"Shipment Number: {shipment.shipment_number}",
        f"Customer: {shipment.customer}",
        f"Country: {shipment.country}",
        f"Contract Number: {shipment.contract_number}",
        f"Currency: {shipment.currency}",
        f"Shipment Date: {_dt(shipment.shipment_date)}",
        "",
        "Products:",
    ]
    for item in shipment.items:
        lines.append(
            f"- {item.product_name}: qty {item.quantity:g} {item.unit}, "
            f"weight {item.weight_kg:g} kg, amount {_money(item.total_amount, shipment.currency)}"
        )
    lines.extend(
        [
            "",
            f"Total Quantity: {shipment.total_quantity:g}",
            f"Total Weight: {shipment.total_weight:g} kg",
            f"Total Amount: {_money(shipment.total_amount, shipment.currency)}",
        ]
    )
    return lines


def invoice_rows(shipment: ExportShipment) -> list[list[object]]:
    rows: list[list[object]] = [
        ["Invoice", shipment.shipment_number],
        ["Customer", shipment.customer],
        ["Country", shipment.country],
        ["Contract", shipment.contract_number],
        ["Currency", shipment.currency],
        ["Shipment Date", _dt(shipment.shipment_date)],
        [],
        ["Product", "Description", "Quantity", "Unit", "Weight kg", "Unit Price", "Total"],
    ]
    for item in shipment.items:
        rows.append(
            [
                item.product_name,
                item.description,
                item.quantity,
                item.unit,
                item.weight_kg,
                item.unit_price,
                item.total_amount,
            ]
        )
    rows.append([])
    rows.append(["Totals", "", shipment.total_quantity, "", shipment.total_weight, "", shipment.total_amount])
    return rows


def packing_rows(shipment: ExportShipment) -> list[list[object]]:
    rows: list[list[object]] = [
        ["Packing List", shipment.shipment_number],
        ["Customer", shipment.customer],
        ["Country", shipment.country],
        ["Shipment Date", _dt(shipment.shipment_date)],
        [],
        ["No", "Product", "Quantity", "Unit", "Weight kg"],
    ]
    for idx, item in enumerate(shipment.items, start=1):
        rows.append([idx, item.product_name, item.quantity, item.unit, item.weight_kg])
    rows.append([])
    rows.append(["Totals", "", shipment.total_quantity, "", shipment.total_weight])
    return rows


def ensure_export_llp_folder(db: Session, username: str) -> DocumentFolder:
    folder = db.query(DocumentFolder).filter(DocumentFolder.name == "Export Shipments").first()
    if folder:
        return folder
    folder = DocumentFolder(name="Export Shipments", parent_id=None, created_by=username)
    db.add(folder)
    db.flush()
    return folder


def _write_file(shipment: ExportShipment, filename: str, content: bytes) -> dict:
    folder = EXPORT_UPLOAD_DIR / shipment.shipment_number
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    path.write_bytes(content)
    rel = f"/uploads/export_shipments/{shipment.shipment_number}/{filename}"
    return {"path": path, "url": rel, "filename": filename, "size": len(content)}


def _attach_document(
    db: Session,
    shipment: ExportShipment,
    username: str,
    document_type: str,
    title: str,
    file_info: dict,
    content_type: str,
) -> ExportShipmentDocument:
    folder = ensure_export_llp_folder(db, username)
    doc = Document(
        folder_id=folder.id,
        title=title,
        description=f"Export shipment {shipment.shipment_number}: {DOCUMENT_TYPES[document_type]}",
        url=file_info["url"],
        filename=file_info["filename"],
        original_filename=file_info["filename"],
        content_type=content_type,
        file_size=file_info["size"],
        is_important=False,
        uploaded_by=username,
    )
    db.add(doc)
    db.flush()
    record = ExportShipmentDocument(
        shipment_id=shipment.id,
        document_type=document_type,
        title=title,
        url=file_info["url"],
        filename=file_info["filename"],
        content_type=content_type,
        file_size=file_info["size"],
        llp_document_id=doc.id,
        generated_by=username,
    )
    db.add(record)
    db.flush()
    return record


def generate_documents(db: Session, shipment: ExportShipment, username: str) -> list[ExportShipmentDocument]:
    old_records = (
        db.query(ExportShipmentDocument)
        .filter(ExportShipmentDocument.shipment_id == shipment.id)
        .all()
    )
    old_llp_ids = [record.llp_document_id for record in old_records if record.llp_document_id]
    db.query(ExportShipmentDocument).filter(ExportShipmentDocument.shipment_id == shipment.id).delete()
    db.flush()
    if old_llp_ids:
        db.query(Document).filter(Document.id.in_(old_llp_ids)).delete(synchronize_session=False)
    # Also clean orphaned generated LLP rows from older non-idempotent runs for this shipment.
    db.query(Document).filter(
        Document.description.like(f"Export shipment {shipment.shipment_number}:%")
    ).delete(synchronize_session=False)
    db.flush()
    lines = shipment_lines(shipment)
    generated: list[ExportShipmentDocument] = []

    pdf_specs = [
        ("invoice", "Invoice"),
        ("packing_list", "Packing List"),
        ("specification", "Export Specification"),
        ("contract_attachment", "Contract Attachment"),
    ]
    for doc_type, title in pdf_specs:
        filename = f"{title.replace(' ', '')}_{shipment.shipment_number}.pdf"
        file_info = _write_file(
            shipment,
            filename,
            build_simple_pdf(f"{title} / {shipment.shipment_number}", lines),
        )
        generated.append(
            _attach_document(
                db,
                shipment,
                username,
                doc_type,
                f"{title} {shipment.shipment_number}",
                file_info,
                "application/pdf",
            )
        )

    excel_specs = [
        ("invoice_xlsx", "Invoice.xlsx", "Invoice", invoice_rows(shipment)),
        ("packing_list_xlsx", "PackingList.xlsx", "Packing List", packing_rows(shipment)),
    ]
    for doc_type, filename, title, rows in excel_specs:
        file_info = _write_file(shipment, f"{shipment.shipment_number}_{filename}", build_xlsx(title, rows))
        generated.append(
            _attach_document(
                db,
                shipment,
                username,
                doc_type,
                f"{title} Excel {shipment.shipment_number}",
                file_info,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        )
    return generated


def recompute_totals(shipment: ExportShipment) -> None:
    shipment.total_quantity = sum(float(i.quantity or 0) for i in shipment.items)
    shipment.total_weight = sum(float(i.weight_kg or 0) for i in shipment.items)
    shipment.total_amount = sum(float(i.total_amount or 0) for i in shipment.items)


def serialize_shipment(shipment: ExportShipment) -> dict:
    return {
        "id": shipment.id,
        "shipment_number": shipment.shipment_number,
        "order_id": shipment.order_id,
        "customer": shipment.customer,
        "country": shipment.country,
        "contract_number": shipment.contract_number,
        "currency": shipment.currency,
        "shipment_date": shipment.shipment_date,
        "status": shipment.status,
        "total_quantity": shipment.total_quantity,
        "total_weight": shipment.total_weight,
        "total_amount": shipment.total_amount,
        "notes": shipment.notes or "",
        "created_by": shipment.created_by,
        "created_at": shipment.created_at,
        "updated_at": shipment.updated_at,
        "items": [
            {
                "id": item.id,
                "order_id": item.order_id,
                "product_name": item.product_name,
                "description": item.description or "",
                "quantity": item.quantity,
                "unit": item.unit,
                "weight_kg": item.weight_kg,
                "unit_price": item.unit_price,
                "total_amount": item.total_amount,
                "sort_order": item.sort_order,
            }
            for item in sorted(shipment.items or [], key=lambda i: i.sort_order or i.id)
        ],
        "documents": [
            {
                "id": doc.id,
                "document_type": doc.document_type,
                "title": doc.title,
                "url": doc.url,
                "filename": doc.filename,
                "content_type": doc.content_type,
                "file_size": doc.file_size,
                "llp_document_id": doc.llp_document_id,
                "generated_at": doc.generated_at,
            }
            for doc in sorted(shipment.documents or [], key=lambda d: d.id)
        ],
    }


def audit_payload(shipment: ExportShipment) -> str:
    return json.dumps(
        {
            "shipment_number": shipment.shipment_number,
            "customer": shipment.customer,
            "status": shipment.status,
            "items": len(shipment.items or []),
            "documents": len(shipment.documents or []),
        },
        ensure_ascii=False,
    )

