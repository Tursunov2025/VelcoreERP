from sqlalchemy import func, update

from models import WarehouseStock, WarehouseTransaction, MesProductPart, Material

def _tx(db, stock, qty, operation, user, order_id=None, reason="", before=None, after=None):
    db.add(WarehouseTransaction(stock_id=stock.id, detail_id=stock.detail_id, quantity=qty, operation=operation, order_id=order_id, operator=user, reason=reason, quantity_before=stock.quantity if before is None else before, quantity_after=stock.quantity if after is None else after))

def _status(stock):
    return "RESERVED" if stock.reserved_quantity >= stock.quantity and stock.quantity > 0 else ("READY" if stock.quantity > 0 else "USED")

def add_surplus(db, line, job_id, qty, user):
    if qty <= 0: raise ValueError("Quantity must be positive")
    claimed = db.execute(
        update(type(line))
        .where(
            type(line).id == line.id,
            type(line).completed_quantity
            - type(line).allocated_quantity
            - func.coalesce(type(line).surplus_stocked_quantity, 0)
            >= qty,
        )
        .values(surplus_stocked_quantity=func.coalesce(type(line).surplus_stocked_quantity, 0) + qty)
    ).rowcount
    if claimed != 1:
        raise ValueError("Surplus was already added or quantity is no longer available")
    db.expire(line)
    db.refresh(line)
    part = db.query(MesProductPart).filter(MesProductPart.id == line.part_id).first()
    material = db.query(Material).filter(Material.id == part.material_id).first() if part and part.material_id else None
    stock = WarehouseStock(detail_id=line.part_id, detail_code=line.part_number, detail_name=line.part_name, material=material.name if material else "", quantity=qty, unit=line.unit, source_order_id=job_id, source_cutting_id=line.id, status="READY")
    db.add(stock); db.flush(); _tx(db, stock, qty, "IN", user, job_id, "Cutting surplus", 0, qty)
    return stock

def reserve_for_job(db, job, user="system"):
    """Atomic per-row reservation; DB row locks prevent double allocation on supported DBs."""
    for line in job.bom_lines:
        required = float(line.allocated_quantity or 0)
        remaining = required
        rows = db.query(WarehouseStock).with_for_update().filter(WarehouseStock.detail_id == line.part_id, WarehouseStock.status == "READY", WarehouseStock.quantity > WarehouseStock.reserved_quantity).order_by(WarehouseStock.created_at).all()
        for stock in rows:
            take = min(remaining, stock.quantity - stock.reserved_quantity)
            if take <= 0: continue
            try:
                change_stock(db, stock.id, take, "RESERVE", user, job.id, "MES job release")
            except ValueError:
                # Another transaction consumed this row after the candidate list was read.
                continue
            remaining -= take
            if remaining <= 0: break
        line.stock_reserved_quantity = required - remaining
        line.production_required_quantity = remaining
    db.flush()

def change_stock(db, stock_id, quantity, operation, user, order_id=None, reason=""):
    """Change one detail-stock row without allowing concurrent over-allocation.

    PostgreSQL serializes this through ``FOR UPDATE``.  The conditional UPDATE is
    also intentional: SQLite does not implement ``FOR UPDATE``, and the predicate
    makes a stale concurrent reader fail safely instead of taking stock below zero.
    """
    stock = db.query(WarehouseStock).with_for_update().filter(WarehouseStock.id == stock_id).first()
    if not stock: raise ValueError("Stock item not found")
    quantity = float(quantity)
    if quantity <= 0: raise ValueError("Quantity must be positive")
    if operation == "OUT":
        changed = db.execute(
            update(WarehouseStock)
            .where(WarehouseStock.id == stock_id, WarehouseStock.quantity - WarehouseStock.reserved_quantity >= quantity)
            .values(quantity=WarehouseStock.quantity - quantity)
        ).rowcount
        if changed != 1: raise ValueError("Insufficient available stock")
        db.expire(stock); db.refresh(stock)
        before = stock.quantity + quantity
        stock.status = _status(stock); _tx(db, stock, quantity, "OUT", user, order_id, reason, before, stock.quantity)
    elif operation == "RESERVE":
        changed = db.execute(
            update(WarehouseStock)
            .where(WarehouseStock.id == stock_id, WarehouseStock.quantity - WarehouseStock.reserved_quantity >= quantity)
            .values(reserved_quantity=WarehouseStock.reserved_quantity + quantity)
        ).rowcount
        if changed != 1: raise ValueError("Insufficient available stock")
        db.expire(stock); db.refresh(stock)
        before = stock.quantity - stock.reserved_quantity + quantity
        stock.status = _status(stock); _tx(db, stock, quantity, "RESERVE", user, order_id, reason, before, stock.quantity-stock.reserved_quantity)
    elif operation == "RELEASE":
        changed = db.execute(
            update(WarehouseStock)
            .where(WarehouseStock.id == stock_id, WarehouseStock.reserved_quantity >= quantity)
            .values(reserved_quantity=WarehouseStock.reserved_quantity - quantity)
        ).rowcount
        if changed != 1: raise ValueError("Cannot release more than reserved")
        db.expire(stock); db.refresh(stock)
        before = stock.quantity - stock.reserved_quantity - quantity
        stock.status = _status(stock); _tx(db, stock, quantity, "RELEASE", user, order_id, reason, before, stock.quantity-stock.reserved_quantity)
    elif operation == "ADJUSTMENT":
        before = stock.quantity; stock.quantity = quantity; stock.reserved_quantity = min(stock.reserved_quantity, stock.quantity); stock.status = _status(stock); _tx(db, stock, quantity-before, "ADJUSTMENT", user, order_id, reason, before, stock.quantity)
    else: raise ValueError("Invalid stock operation")
    db.flush(); return stock

def consume_reserved_stock(db, stock_id, quantity, user, order_id=None, reason=""):
    """Atomically issue stock that was already reserved.

    Quantity and reservation are reduced together so neither a concurrent issue
    nor an ordinary OUT can observe the reserved units as available stock.
    """
    stock = db.query(WarehouseStock).with_for_update().filter(WarehouseStock.id == stock_id).first()
    if not stock: raise ValueError("Stock item not found")
    quantity = float(quantity)
    if quantity <= 0: raise ValueError("Quantity must be positive")
    changed = db.execute(
        update(WarehouseStock)
        .where(
            WarehouseStock.id == stock_id,
            WarehouseStock.quantity >= quantity,
            WarehouseStock.reserved_quantity >= quantity,
        )
        .values(
            quantity=WarehouseStock.quantity - quantity,
            reserved_quantity=WarehouseStock.reserved_quantity - quantity,
        )
    ).rowcount
    if changed != 1: raise ValueError("Insufficient reserved stock")
    db.expire(stock); db.refresh(stock)
    before = stock.quantity + quantity
    stock.status = _status(stock)
    _tx(db, stock, quantity, "OUT", user, order_id, reason, before, stock.quantity)
    db.flush()
    return stock

def release_job_reservations(db, job, user):
    for line in job.bom_lines:
        remaining = float(line.stock_reserved_quantity or 0)
        if remaining <= 0: continue
        rows = db.query(WarehouseTransaction).filter(WarehouseTransaction.order_id == job.id, WarehouseTransaction.detail_id == line.part_id, WarehouseTransaction.operation == "RESERVE").order_by(WarehouseTransaction.id).all()
        for tx in rows:
            if remaining <= 0: break
            stock = db.query(WarehouseStock).with_for_update().filter(WarehouseStock.id == tx.stock_id).first()
            take = min(remaining, stock.reserved_quantity)
            if take: change_stock(db, stock.id, take, "RELEASE", user, job.id, "Job cancelled") ; remaining -= take
        line.stock_reserved_quantity = 0; line.production_required_quantity = float(line.allocated_quantity or 0)
