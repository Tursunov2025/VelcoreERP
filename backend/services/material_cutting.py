"""Physical profile issue/cutting layered on the canonical material ledger."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from models import (Material, MaterialBomLine, MaterialCutOperation, MaterialIssue, MaterialIssuePiece,
                    MaterialReservation, MaterialScrap, MaterialStockLengthLot, MaterialStockMovement,
                    MaterialStockPiece, MesJobBomLine, MesJobRouteStep, MesProductionJob, ProductionProject,
                    ProductionProjectLine)
from services.audit import log_value_change

EPS = 1e-6


def fail(code: str, message: str, status: int = 400):
    error = ValueError(message); error.code = code; error.status_code = status
    raise error


def piece_payload(p: MaterialStockPiece) -> dict:
    return {"id": p.id, "material_id": p.material_id, "source_length_lot_id": p.source_length_lot_id,
            "source_receipt_id": p.source_receipt_id, "parent_piece_id": p.parent_piece_id,
            "source_cut_id": p.source_cut_id, "original_length_m": p.original_length_m,
            "current_length_m": p.current_length_m, "status": p.status,
            "warehouse_name": p.warehouse_name, "location_code": p.location_code,
            "lot_number": p.lot_number, "reserved_issue_id": p.reserved_issue_id,
            "version": p.version, "created_at": p.created_at}


def list_pieces(db: Session, material_id: int | None = None, status: str | None = None):
    q = db.query(MaterialStockPiece)
    if material_id: q = q.filter(MaterialStockPiece.material_id == material_id)
    if status: q = q.filter(MaterialStockPiece.status == status)
    return [piece_payload(p) for p in q.order_by(MaterialStockPiece.current_length_m, MaterialStockPiece.id).all()]


def materialize_lot(db: Session, lot_id: int, username: str, operation_key: str) -> dict:
    """Explicit/lazy representation: never explodes historical lots at startup."""
    lot = db.query(MaterialStockLengthLot).filter_by(id=lot_id).first()
    if not lot: fail("material_length_lot_not_found", "Physical length lot not found", 404)
    existing = db.query(MaterialStockPiece).filter_by(source_length_lot_id=lot.id).count()
    target = int(lot.pieces_on_hand or 0)
    if existing > target: fail("material_piece_materialization_conflict", "Piece records exceed aggregate lot", 409)
    for _ in range(target - existing):
        db.add(MaterialStockPiece(material_id=lot.material_id, source_length_lot_id=lot.id,
            source_receipt_id=lot.receipt_document_id or lot.receipt_id, original_length_m=lot.length_m,
            current_length_m=lot.length_m, status="AVAILABLE", warehouse_name=lot.warehouse_name or "",
            location_code=lot.location_code or "", lot_number=lot.lot_number or "", created_by=username))
    db.flush()
    return {"created": target - existing, "pieces": list_pieces(db, lot.material_id)}


def create_issue_document(db: Session, username: str, data: dict) -> dict:
    key = str(data.get("operation_key") or "").strip() or f"issue-{uuid4().hex}"
    prior = db.query(MaterialIssue).filter_by(operation_key=key).first()
    if prior: return issue_payload(db, prior, True)
    material = db.query(Material).filter_by(id=int(data["material_id"])).first()
    if not material: fail("material_not_found", "Material not found", 404)
    qty = float(data.get("quantity") or 0)
    if qty <= 0: fail("material_quantity_positive", "Quantity must be positive")
    issue = MaterialIssue(material_id=material.id, quantity=qty, reason=str(data.get("reason") or ""),
        reference=str(data.get("reference") or ""), notes=str(data.get("notes") or ""), created_by=username,
        document_number=str(data.get("document_number") or "").strip() or None, operation_key=key,
        status="DRAFT", project_id=data.get("project_id"), project_line_id=data.get("project_line_id"),
        job_id=data.get("job_id"), release_snapshot_id=data.get("release_snapshot_id"),
        material_reservation_id=data.get("material_reservation_id"),
        source_material_bom_line_id=data.get("source_material_bom_line_id"),
        source_job_bom_line_id=data.get("source_job_bom_line_id"),
        planned_required_quantity=data.get("planned_required_quantity") or qty,
        operation_stage=str(data.get("operation_stage") or "LAZER"),
        warehouse_name=str(data.get("warehouse_name") or ""), responsible_employee=str(data.get("responsible_employee") or username))
    db.add(issue); db.flush()
    if not issue.document_number: issue.document_number = f"MI-{issue.id:06d}"
    log_value_change(db, username, "create", "material_issue", issue.id, "status", None, "DRAFT")
    return issue_payload(db, issue)


def issue_payload(db: Session, issue: MaterialIssue, idempotent=False):
    links = db.query(MaterialIssuePiece).filter_by(issue_id=issue.id).all()
    pieces = [db.query(MaterialStockPiece).filter_by(id=x.piece_id).first() for x in links]
    cuts = db.query(MaterialCutOperation).filter_by(issue_id=issue.id).order_by(MaterialCutOperation.id).all()
    return {"id": issue.id, "document_number": issue.document_number, "operation_key": issue.operation_key,
        "material_id": issue.material_id, "quantity": issue.quantity, "status": issue.status,
        "project_id": issue.project_id, "project_line_id": issue.project_line_id, "job_id": issue.job_id,
        "release_snapshot_id": issue.release_snapshot_id, "material_reservation_id": issue.material_reservation_id,
        "source_material_bom_line_id": issue.source_material_bom_line_id,
        "source_job_bom_line_id": issue.source_job_bom_line_id,
        "planned_required_quantity": issue.planned_required_quantity,
        "operation_stage": issue.operation_stage, "warehouse_name": issue.warehouse_name,
        "responsible_employee": issue.responsible_employee, "reason": issue.reason, "notes": issue.notes,
        "version": issue.version, "created_by": issue.created_by, "created_at": issue.created_at,
        "issued_at": issue.issued_at, "completed_at": issue.completed_at, "idempotent": idempotent,
        "pieces": [piece_payload(p) for p in pieces if p],
        "cuts": [{"id": c.id, "source_piece_id": c.source_piece_id, "offcut_piece_id": c.offcut_piece_id,
            "length_before_m": c.length_before_m, "actual_cut_length_m": c.actual_cut_length_m,
            "kerf_m": c.kerf_m, "remainder_m": c.remainder_m, "scrap_length_m": c.scrap_length_m,
            "operator": c.operator, "created_at": c.created_at} for c in cuts]}


def reserve_piece(db: Session, issue_id: int, piece_id: int, expected_version: int, username: str):
    issue = db.query(MaterialIssue).filter_by(id=issue_id).first()
    if not issue: fail("material_issue_not_found", "Issue not found", 404)
    if issue.status not in {"DRAFT", "RESERVED", "ISSUED"}: fail("material_issue_state_conflict", "Issue cannot reserve in current state", 409)
    piece = db.query(MaterialStockPiece).filter_by(id=piece_id).first()
    if not piece or piece.material_id != issue.material_id: fail("material_piece_not_found", "Physical piece not found", 404)
    changed = db.execute(update(MaterialStockPiece).where(MaterialStockPiece.id == piece_id,
        MaterialStockPiece.status.in_(["AVAILABLE", "OFFCUT"]), MaterialStockPiece.version == expected_version)
        .values(status="RESERVED", reserved_issue_id=issue.id, version=expected_version + 1, updated_at=datetime.utcnow()))
    if changed.rowcount != 1:
        existing = db.query(MaterialIssuePiece).filter_by(issue_id=issue.id, piece_id=piece_id).first()
        if existing: return issue_payload(db, issue, True)
        fail("material_piece_reservation_conflict", "Physical piece is no longer available", 409)
    db.add(MaterialIssuePiece(issue_id=issue.id, piece_id=piece_id, reserved_length_m=piece.current_length_m))
    if piece.source_length_lot_id and piece.parent_piece_id is None:
        lot = db.query(MaterialStockLengthLot).filter_by(id=piece.source_length_lot_id).first()
        if lot: lot.pieces_reserved += 1; lot.version += 1
    if issue.status != "ISSUED": issue.status = "RESERVED"
    issue.version += 1
    log_value_change(db, username, "reserve", "material_issue", issue.id, "piece_id", None, piece_id)
    db.flush(); return issue_payload(db, issue)


def release_reservation(db: Session, issue_id: int, username: str):
    issue = db.query(MaterialIssue).filter_by(id=issue_id).first()
    if not issue: fail("material_issue_not_found", "Issue not found", 404)
    if issue.status == "DRAFT": return issue_payload(db, issue, True)
    if issue.status != "RESERVED": fail("material_cut_cannot_restore", "A cut bar cannot be restored as a full bar", 409)
    for link in db.query(MaterialIssuePiece).filter_by(issue_id=issue.id).all():
        p = db.query(MaterialStockPiece).filter_by(id=link.piece_id).first()
        if p and p.status == "RESERVED" and p.reserved_issue_id == issue.id:
            p.status = "OFFCUT" if p.parent_piece_id else "AVAILABLE"; p.reserved_issue_id = None; p.version += 1
            if p.source_length_lot_id and p.parent_piece_id is None:
                lot = db.query(MaterialStockLengthLot).filter_by(id=p.source_length_lot_id).first()
                if lot: lot.pieces_reserved = max(0, lot.pieces_reserved - 1); lot.version += 1
        db.delete(link)
    issue.status = "DRAFT"; issue.version += 1
    log_value_change(db, username, "release", "material_issue", issue.id, "status", "RESERVED", "DRAFT")
    db.flush(); return issue_payload(db, issue)


def issue_reserved(db: Session, issue_id: int, username: str):
    issue = db.query(MaterialIssue).filter_by(id=issue_id).first()
    if not issue: fail("material_issue_not_found", "Issue not found", 404)
    if issue.status == "COMPLETED": return issue_payload(db, issue, True)
    if issue.status not in {"RESERVED", "ISSUED"}: fail("material_issue_state_conflict", "Reserve a physical piece first", 409)
    links = db.query(MaterialIssuePiece).filter_by(issue_id=issue.id).all()
    reserveds = [link for link in links if (db.query(MaterialStockPiece).filter_by(id=link.piece_id).first() or type("P",(),{"status":""})()).status == "RESERVED"]
    if issue.status == "ISSUED" and not reserveds: return issue_payload(db, issue, True)
    links = reserveds
    total = 0.0
    for link in links:
        p = db.query(MaterialStockPiece).filter_by(id=link.piece_id).first()
        if not p or p.status != "RESERVED" or p.reserved_issue_id != issue.id: fail("material_piece_reservation_conflict", "Reserved piece changed", 409)
        total += p.current_length_m; p.status = "ISSUED"; p.version += 1
        if p.source_length_lot_id and p.parent_piece_id is None:
            lot = db.query(MaterialStockLengthLot).filter_by(id=p.source_length_lot_id).first()
            if lot: lot.pieces_reserved = max(0, lot.pieces_reserved - 1); lot.pieces_on_hand = max(0, lot.pieces_on_hand - 1); lot.total_meters = round(lot.length_m * lot.pieces_on_hand, 6); lot.version += 1
    mat = db.query(Material).filter_by(id=issue.material_id).first()
    if not mat or mat.quantity + EPS < total: fail("material_stock_insufficient", "Insufficient stock", 409)
    mat.quantity = round(mat.quantity - total, 6)
    db.add(MaterialStockMovement(material_id=mat.id, movement_type="physical_issue", quantity=total,
        balance_after=mat.quantity, reference_type="issue", reference_id=issue.id, notes=issue.notes, created_by=username))
    issue.status = "ISSUED"; issue.issued_at = datetime.utcnow(); issue.version += 1
    db.flush(); return issue_payload(db, issue)


def record_cut(db: Session, issue_id: int, piece_id: int, actual: float, kerf_m: float | None,
               operation_key: str, username: str, planned: float | None = None):
    prior = db.query(MaterialCutOperation).filter_by(operation_key=operation_key).first()
    if prior:
        issue = db.query(MaterialIssue).filter_by(id=prior.issue_id).first(); return issue_payload(db, issue, True)
    issue = db.query(MaterialIssue).filter_by(id=issue_id).first()
    piece = db.query(MaterialStockPiece).filter_by(id=piece_id).first()
    if not issue or not piece: fail("material_issue_not_found", "Issue or physical piece not found", 404)
    if issue.status not in {"ISSUED", "COMPLETED"} or piece.reserved_issue_id != issue.id or piece.status not in {"ISSUED", "PARTIALLY_USED"}:
        fail("material_cut_state_conflict", "Piece is not issued for this document", 409)
    cut = round(float(actual), 6); kerf = round(float(kerf_m if kerf_m is not None else ((db.query(Material).get(issue.material_id).default_kerf_mm or 3) / 1000)), 6)
    before = round(piece.current_length_m, 6); remainder = round(before - cut - kerf, 6)
    if cut <= 0 or kerf < 0 or remainder < -EPS: fail("material_cut_exceeds_piece", "Cut and kerf exceed physical piece", 409)
    remainder = max(0.0, remainder); mat = db.query(Material).filter_by(id=issue.material_id).first()
    threshold = float(mat.min_reusable_offcut_m if mat.min_reusable_offcut_m is not None else 0.3)
    op = MaterialCutOperation(operation_key=operation_key, issue_id=issue.id, source_piece_id=piece.id,
        material_id=mat.id, project_id=issue.project_id, project_line_id=issue.project_line_id,
        release_snapshot_id=issue.release_snapshot_id, job_id=issue.job_id,
        source_material_bom_line_id=issue.source_material_bom_line_id,
        source_job_bom_line_id=issue.source_job_bom_line_id,
        length_before_m=before, planned_cut_length_m=float(planned or actual),
        actual_cut_length_m=cut, kerf_m=kerf, remainder_m=remainder, scrap_length_m=0, operator=username)
    db.add(op); db.flush(); offcut = None
    piece.current_length_m = 0; piece.status = "CONSUMED"; piece.version += 1
    if remainder + EPS >= threshold:
        offcut = MaterialStockPiece(material_id=mat.id, source_length_lot_id=piece.source_length_lot_id,
            source_receipt_id=piece.source_receipt_id, parent_piece_id=piece.id, source_cut_id=op.id,
            original_length_m=remainder, current_length_m=remainder, status="OFFCUT", warehouse_name=piece.warehouse_name,
            location_code=piece.location_code, lot_number=piece.lot_number, created_by=username)
        db.add(offcut); db.flush(); op.offcut_piece_id = offcut.id
    elif remainder > EPS:
        op.scrap_length_m = remainder
        weight = remainder * mat.theoretical_weight_kg_per_m if mat.theoretical_weight_kg_per_m else None
        db.add(MaterialScrap(material_id=mat.id, source_piece_id=piece.id, cut_operation_id=op.id,
            scrap_length_m=remainder, theoretical_weight_kg=weight, reason="below_reusable_threshold", operator=username))
    if offcut:
        mat.quantity = round(mat.quantity + remainder, 6)
        db.add(MaterialStockMovement(material_id=mat.id, movement_type="offcut_return",
            quantity=remainder, balance_after=mat.quantity, reference_type="cut", reference_id=op.id,
            notes="Reusable offcut", created_by=username))
    elif remainder > EPS:
        # Scrap is traceable evidence, never available stock.  The full issued
        # bar was already removed from Material.quantity.
        db.add(MaterialStockMovement(material_id=mat.id, movement_type="scrap",
            quantity=remainder, balance_after=mat.quantity, reference_type="cut", reference_id=op.id,
            notes="Non-reusable scrap", created_by=username))
    total_cut = sum(float(row.actual_cut_length_m or 0) for row in db.query(MaterialCutOperation).filter_by(issue_id=issue.id).all())
    if total_cut + EPS >= float(issue.planned_required_quantity or issue.quantity):
        issue.status = "COMPLETED"; issue.completed_at = datetime.utcnow(); issue.version += 1
    else:
        issue.status = "ISSUED"; issue.version += 1
    db.flush(); return issue_payload(db, issue)


def recommend(db: Session, material_id: int, cuts: list[float], kerf_m: float = .003):
    requested = [float(x) for x in cuts if float(x) > 0]
    total = sum(requested) + kerf_m * len(requested)
    candidates = db.query(MaterialStockPiece).filter(MaterialStockPiece.material_id == material_id,
        MaterialStockPiece.status.in_(["AVAILABLE", "OFFCUT"]), MaterialStockPiece.current_length_m + EPS >= total).all()
    candidates.sort(key=lambda p: (0 if p.status == "OFFCUT" else 1, p.current_length_m - total, p.id))
    if not candidates: return {"piece": None, "cuts": requested, "required_m": round(total, 6)}
    p = candidates[0]; remainder = round(p.current_length_m - total, 6)
    return {"piece": piece_payload(p), "cuts": requested, "kerf_total_m": round(kerf_m * len(requested), 6),
            "remainder_m": remainder, "utilization_pct": round(sum(requested) / p.current_length_m * 100, 2)}


def cutting_context(db: Session) -> dict:
    projects = db.query(ProductionProject).filter(ProductionProject.status.in_(["released", "in_progress"])).order_by(ProductionProject.project_code).all()
    return {"projects": [{"id": p.id, "project_code": p.project_code, "project_name": p.project_name,
        "lines": [{"id": line.id, "product_id": line.product_id,
            "product_code": line.product.code if line.product else "", "product_name": line.product.name if line.product else "",
            "quantity": float(line.quantity), "jobs": [{"id": job.id, "job_number": job.job_number,
                "status": job.status, "release_snapshot_id": job.project_release_snapshot_id}
                for job in db.query(MesProductionJob).filter_by(project_line_id=line.id).order_by(MesProductionJob.id).all()]}
            for line in p.lines]} for p in projects]}


def job_material_requirements(db: Session, job_id: int) -> dict:
    job = db.query(MesProductionJob).filter_by(id=job_id).first()
    if not job or not job.project_id: fail("material_job_not_found", "Released project job not found", 404)
    stages=[str(x.stage_name or "").strip().lower() for x in db.query(MesJobRouteStep).filter_by(job_id=job.id).all()]
    if not any(name in {"lazer", "laser", "лазер", "project-lazer"} or "lazer" in name for name in stages):
        fail("material_job_not_cutting_eligible", "Job has no authoritative cutting stage", 409)
    rows=[]
    for jl in db.query(MesJobBomLine).filter_by(job_id=job.id).order_by(MesJobBomLine.id).all():
        for ml in db.query(MaterialBomLine).filter_by(part_id=jl.part_id, is_active=True).order_by(MaterialBomLine.id).all():
            required=round(float(jl.allocated_quantity or 0)*float(ml.quantity_per_part or 0),6)
            reservation=db.query(MaterialReservation).filter_by(job_id=job.id,material_id=ml.material_id).first()
            issues=db.query(MaterialIssue).filter_by(job_id=job.id,source_job_bom_line_id=jl.id,
                source_material_bom_line_id=ml.id).all()
            issue_ids=[x.id for x in issues]
            cut_total=sum(float(x.actual_cut_length_m or 0) for x in db.query(MaterialCutOperation).filter(MaterialCutOperation.issue_id.in_(issue_ids)).all()) if issue_ids else 0
            issued_total=sum(float(link.reserved_length_m or 0) for link in db.query(MaterialIssuePiece).filter(MaterialIssuePiece.issue_id.in_(issue_ids)).join(MaterialStockPiece,MaterialStockPiece.id==MaterialIssuePiece.piece_id).filter(MaterialStockPiece.status.in_(["ISSUED","CONSUMED","PARTIALLY_USED"])).all()) if issue_ids else 0
            mat=db.query(Material).filter_by(id=ml.material_id).first()
            if not mat or str(mat.material_type or "").upper() != "PROFILE": continue
            rows.append({"key":f"{jl.id}:{ml.id}","project_id":job.project_id,"project_line_id":job.project_line_id,
                "release_snapshot_id":job.project_release_snapshot_id,"job_id":job.id,"job_number":job.job_number,
                "source_job_bom_line_id":jl.id,"source_material_bom_line_id":ml.id,"detail_id":jl.part_id,
                "detail_code":jl.part_number,"detail_name":jl.part_name,"material_id":ml.material_id,
                "material_code":mat.code if mat else "","material_name":mat.name if mat else "",
                "required_quantity":required,"reserved_quantity":float(reservation.reserved_quantity or 0) if reservation else 0,
                "issued_quantity":round(issued_total,6),"cut_quantity":round(cut_total,6),
                "remaining_quantity":round(max(0,required-cut_total),6),"reservation_id":reservation.id if reservation else None})
    return {"job":{"id":job.id,"job_number":job.job_number,"project_id":job.project_id,
        "project_line_id":job.project_line_id,"release_snapshot_id":job.project_release_snapshot_id,
        "stage":next((x.stage_name for x in db.query(MesJobRouteStep).filter_by(job_id=job.id).all() if "lazer" in str(x.stage_name or "").lower()),"LAZER")},"requirements":rows}


def create_issue_from_requirement(db: Session, username: str, job_id: int, job_bom_id: int,
                                  material_bom_id: int, operation_key: str) -> dict:
    context=job_material_requirements(db,job_id)
    row=next((x for x in context["requirements"] if x["source_job_bom_line_id"]==job_bom_id and x["source_material_bom_line_id"]==material_bom_id),None)
    if not row: fail("material_requirement_not_found", "Canonical job material requirement not found", 404)
    if row["remaining_quantity"] <= EPS: fail("material_requirement_completed", "Material requirement is already completed", 409)
    return create_issue_document(db,username,{"material_id":row["material_id"],"quantity":row["remaining_quantity"],
        "planned_required_quantity":row["remaining_quantity"],"operation_key":operation_key,
        "project_id":row["project_id"],"project_line_id":row["project_line_id"],"job_id":job_id,
        "release_snapshot_id":row["release_snapshot_id"],"material_reservation_id":row["reservation_id"],
        "source_job_bom_line_id":job_bom_id,"source_material_bom_line_id":material_bom_id,
        "operation_stage":"LAZER","reference":f"{row['job_number']} / {row['detail_code']} / {row['material_code']}"})
