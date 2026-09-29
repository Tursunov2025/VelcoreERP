"""Package traceability, labels, scanner, and public tracking."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import ProductPassport, User
from services.mes_dispatch_terminal import get_job_dispatch
from services.label_printer import get_printers_config, save_printers_config
from services.package_traceability import (
    assign_package_location,
    build_passport,
    build_public_tracking,
    scan_dispatch_load,
    traceability_dashboard,
    build_product_label_png,
    build_product_label_pdf,
    build_product_labels_sheet_pdf,
    generate_product_passports_for_package,
    list_product_passports,
    product_passport_public_url,
    serialize_product_passport,
)
from services.permissions import user_has_permission
from services.audit import log_action
from services.product_passport_documents import (
    build_passport_docx,
    build_passport_pdf,
    build_passport_xlsx,
    build_passports_batch_xlsx,
)

router = APIRouter(tags=["traceability"])
public_router = APIRouter(tags=["traceability-public"])


class LocationAssignBody(BaseModel):
    warehouse_zone: str = ""
    rack: str = ""
    shelf: str = ""


class DispatchScanBody(BaseModel):
    label_code: str
    dispatch_id: int


class PrintersUpdateBody(BaseModel):
    printers: list[dict]


def _require_mes_view(db: Session, user: User) -> None:
    if user.role == "admin" or user_has_permission(db, user, "mes_view"):
        return
    raise HTTPException(status_code=403, detail="Permission required: mes_view")


def _require_traceability_view(db: Session, user: User) -> None:
    if user.role == "admin" or user_has_permission(db, user, "traceability_view"):
        return
    raise HTTPException(status_code=403, detail={"code": "traceability_view_required", "message": "Traceability permission required"})


@router.get("/traceability/dashboard")
def traceability_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_traceability_view(db, user)
    return traceability_dashboard(db)


@router.get("/traceability/products")
def product_passport_list(
    serial: str = Query(""),
    product: str = Query(""),
    project: str = Query(""),
    package: str = Query(""),
    trip: str = Query(""),
    status: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    with_issues: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_traceability_view(db, user)
    return {"items": list_product_passports(db, serial=serial, product=product, project=project, package=package, trip=trip, status=status, date_from=date_from, date_to=date_to, with_issues=with_issues)}


@router.get("/traceability/products/{serial}")
def product_passport_detail(
    serial: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_traceability_view(db, user)
    row = db.query(ProductPassport).filter(ProductPassport.serial_number == serial.strip()).first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "passport_not_found", "message": "Product passport not found"})
    return serialize_product_passport(db, row)


@router.post("/traceability/packages/{package_id}/passports")
def generate_product_passports(
    package_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin" and not user_has_permission(db, user, "traceability_generate_qr") and not user_has_permission(db, user, "mes_terminal_packaging"):
        raise HTTPException(status_code=403, detail={"code": "traceability_generate_required", "message": "QR generation permission required"})
    try:
        rows = generate_product_passports_for_package(db, package_id, username=user.username)
        db.commit()
    except ValueError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail={"code": "passport_generation_not_ready", "message": str(exc)}) from exc
    return {"items": [serialize_product_passport(db, row) for row in rows]}


class ProductPassportBatchBody(BaseModel):
    package_ids: list[int] = Field(default_factory=list, min_length=1, max_length=500)


@router.post("/traceability/passports/batch")
def generate_product_passports_batch(
    body: ProductPassportBatchBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin" and not user_has_permission(db, user, "traceability_generate_qr") and not user_has_permission(db, user, "mes_terminal_packaging"):
        raise HTTPException(status_code=403, detail={"code": "traceability_generate_required", "message": "QR generation permission required"})
    result = []
    try:
        for package_id in dict.fromkeys(body.package_ids):
            result.extend(generate_product_passports_for_package(db, package_id, username=user.username))
        db.commit()
    except ValueError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail={"code": "passport_generation_not_ready", "message": str(exc)}) from exc
    return {"items": [serialize_product_passport(db, row) for row in result]}


class ProductPassportLabelSheetBody(BaseModel):
    serial_numbers: list[str] = Field(default_factory=list, min_length=1, max_length=500)
    size: str = Field(default="60x60", pattern="^(60x60|100x50)$")


class ProductPassportExportBody(BaseModel):
    serial_numbers: list[str] = Field(default_factory=list, min_length=1, max_length=500)
    language: str = Field(default="uz", pattern="^(uz|ru)([-_][A-Za-z]+)?$")


@router.post("/traceability/passports/batch/labels.pdf")
def product_passport_label_sheet(
    body: ProductPassportLabelSheetBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin" and not user_has_permission(db, user, "traceability_print_labels"):
        raise HTTPException(status_code=403, detail={"code": "traceability_print_required", "message": "Label printing permission required"})
    try:
        pdf, ordered = build_product_labels_sheet_pdf(db, body.serial_numbers, size=body.size)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"code": "traceability_batch_invalid", "message": str(exc)}) from exc
    from services.audit import log_action
    log_action(db, user.username, "product_passport.batch_label_print", "product_passport", None, f"count={len(ordered)};size={body.size}")
    db.commit()
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=product-passports-{body.size}.pdf"},
    )


@router.get("/traceability/products/{serial}/label.png")
def product_passport_label(
    serial: str,
    size: str = Query("100x50", pattern="^(60x60|100x50|a4)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "admin" and not user_has_permission(db, user, "traceability_print_labels") and not user_has_permission(db, user, "traceability_view"):
        raise HTTPException(status_code=403, detail={"code": "traceability_print_required", "message": "Label printing permission required"})
    row = db.query(ProductPassport).filter(ProductPassport.serial_number == serial.strip()).first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "passport_not_found", "message": "Product passport not found"})
    data = serialize_product_passport(db, row)
    from services.audit import log_action
    log_action(db, user.username, "product_passport.label_print", "product_passport", row.id, row.serial_number)
    db.commit()
    return StreamingResponse(iter([build_product_label_png(row, data, size=size)]), media_type="image/png", headers={"Content-Disposition": f"inline; filename={row.serial_number}-{size}.png"})


@router.get("/traceability/products/{serial}/label.pdf")
def product_passport_label_pdf(
    serial: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a dependency-free A4-compatible PDF label for print workflows."""
    if user.role != "admin" and not user_has_permission(db, user, "traceability_print_labels") and not user_has_permission(db, user, "traceability_view"):
        raise HTTPException(status_code=403, detail={"code": "traceability_print_required", "message": "Label printing permission required"})
    row = db.query(ProductPassport).filter(ProductPassport.serial_number == serial.strip()).first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "passport_not_found", "message": "Product passport not found"})
    data = serialize_product_passport(db, row)
    from services.audit import log_action
    log_action(db, user.username, "product_passport.label_print", "product_passport", row.id, f"{row.serial_number}:pdf")
    db.commit()
    pdf = build_product_label_pdf(row, data)
    return StreamingResponse(iter([pdf]), media_type="application/pdf", headers={"Content-Disposition": f"inline; filename={row.serial_number}.pdf"})


def _passport_or_404(db: Session, serial: str) -> tuple[ProductPassport, dict]:
    row = db.query(ProductPassport).filter(ProductPassport.serial_number == serial.strip()).first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "passport_not_found", "message": "Product passport not found"})
    return row, serialize_product_passport(db, row)


def _document_response(payload: bytes, media_type: str, filename: str) -> StreamingResponse:
    return StreamingResponse(iter([payload]), media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/traceability/products/{serial}/passport.pdf")
def product_passport_document_pdf(
    serial: str,
    language: str = Query("uz", pattern="^(uz|ru)([-_][A-Za-z]+)?$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_traceability_view(db, user)
    row, data = _passport_or_404(db, serial)
    payload = build_passport_pdf(db, data, lang=language)
    log_action(db, user.username, "product_passport.export_pdf", "product_passport", row.id, row.serial_number)
    db.commit()
    return _document_response(payload, "application/pdf", f"{row.serial_number}-passport.pdf")


@router.get("/traceability/products/{serial}/passport.docx")
def product_passport_document_docx(
    serial: str,
    language: str = Query("uz", pattern="^(uz|ru)([-_][A-Za-z]+)?$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_traceability_view(db, user)
    row, data = _passport_or_404(db, serial)
    payload = build_passport_docx(db, data, lang=language)
    log_action(db, user.username, "product_passport.export_docx", "product_passport", row.id, row.serial_number)
    db.commit()
    return _document_response(payload, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", f"{row.serial_number}-passport.docx")


@router.get("/traceability/products/{serial}/passport.xlsx")
def product_passport_document_xlsx(
    serial: str,
    language: str = Query("uz", pattern="^(uz|ru)([-_][A-Za-z]+)?$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_traceability_view(db, user)
    row, data = _passport_or_404(db, serial)
    payload = build_passport_xlsx(db, data, lang=language)
    log_action(db, user.username, "product_passport.export_xlsx", "product_passport", row.id, row.serial_number)
    db.commit()
    return _document_response(payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{row.serial_number}-passport.xlsx")


@router.post("/traceability/passports/batch/export.xlsx")
def product_passport_batch_xlsx(
    body: ProductPassportExportBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_traceability_view(db, user)
    ordered = list(dict.fromkeys(value.strip() for value in body.serial_numbers if value.strip()))
    rows = db.query(ProductPassport).filter(ProductPassport.serial_number.in_(ordered)).all()
    by_serial = {row.serial_number: row for row in rows}
    missing = [serial for serial in ordered if serial not in by_serial]
    if missing:
        raise HTTPException(status_code=422, detail={"code": "traceability_batch_invalid", "message": "One or more product passports were not found"})
    payload = build_passports_batch_xlsx(db, [serialize_product_passport(db, by_serial[serial]) for serial in ordered], lang=body.language)
    log_action(db, user.username, "product_passport.batch_export_xlsx", "product_passport", None, f"count={len(ordered)}")
    db.commit()
    return _document_response(payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "product-passports.xlsx")


@router.get("/packages/{label_code}")
def package_passport(
    label_code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_mes_view(db, user)
    data = build_passport(db, label_code)
    if not data:
        raise HTTPException(status_code=404, detail="Package not found")
    return data


@public_router.get("/track/package/{label_code}")
def public_package_track(label_code: str, db: Session = Depends(get_db)):
    data = build_public_tracking(db, label_code)
    if not data:
        raise HTTPException(status_code=404, detail="Package not found")
    return data


@public_router.get("/track/product/{token}")
def public_product_passport(token: str, db: Session = Depends(get_db)):
    row = db.query(ProductPassport).filter(ProductPassport.qr_token == token.strip()).first()
    if not row:
        raise HTTPException(status_code=404, detail={"code": "passport_not_found", "message": "Product passport not found"})
    return serialize_product_passport(db, row, include_internal=False)


@router.put("/packages/{label_code}/location")
def set_package_location(
    label_code: str,
    body: LocationAssignBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (
        user.role == "admin"
        or user_has_permission(db, user, "mes_terminal_warehouse")
        or user_has_permission(db, user, "mes_edit")
    ):
        raise HTTPException(status_code=403, detail="Warehouse permission required")
    try:
        loc = assign_package_location(
            db,
            label_code=label_code,
            warehouse_zone=body.warehouse_zone,
            rack=body.rack,
            shelf=body.shelf,
            username=user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "warehouse_zone": loc.warehouse_zone,
        "rack": loc.rack,
        "shelf": loc.shelf,
        "updated_at": loc.updated_at,
    }


@router.post("/mes/terminal/dispatch/scan-label")
def dispatch_scan_label(
    body: DispatchScanBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (
        user.role == "admin"
        or user_has_permission(db, user, "mes_terminal_dispatch")
    ):
        raise HTTPException(status_code=403, detail="Dispatch terminal permission required")
    try:
        result = scan_dispatch_load(
            db,
            label_code=body.label_code,
            dispatch_id=body.dispatch_id,
            username=user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


class DispatchScanJobBody(BaseModel):
    label_code: str


@router.post("/mes/terminal/dispatch/jobs/{job_id}/scan-label")
def dispatch_scan_label_for_job(
    job_id: int,
    body: DispatchScanJobBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not (
        user.role == "admin"
        or user_has_permission(db, user, "mes_terminal_dispatch")
    ):
        raise HTTPException(status_code=403, detail="Dispatch terminal permission required")
    dispatch = get_job_dispatch(db, job_id)
    if not dispatch:
        raise HTTPException(status_code=400, detail="Dispatch not started for this job")
    try:
        result = scan_dispatch_load(
            db,
            label_code=body.label_code,
            dispatch_id=dispatch.id,
            username=user.username,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/admin/settings/label-printers")
def get_label_printers(
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    return {"printers": get_printers_config(db)}


@router.put("/admin/settings/label-printers")
def put_label_printers(
    body: PrintersUpdateBody,
    db: Session = Depends(get_db),
    _user: User = Depends(require_admin),
):
    printers = save_printers_config(db, body.printers)
    db.commit()
    return {"printers": printers}
