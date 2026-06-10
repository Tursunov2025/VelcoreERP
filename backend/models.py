from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from database import Base


def utcnow():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    role = Column(String, default="operator")
    department = Column(String, default="Kesish")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    telegram_username = Column(String, nullable=True)
    telegram_id = Column(String, nullable=True)
    telegram_link_code = Column(String, nullable=True)
    telegram_link_code_expires = Column(DateTime, nullable=True)
    ui_language = Column(String, nullable=True)
    ui_theme = Column(String, nullable=True)
    ui_clock_format = Column(String, nullable=True)

    permissions = relationship(
        "UserPermission", back_populates="user", cascade="all, delete-orphan"
    )


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    module = Column(String, nullable=False, index=True)
    enabled = Column(Boolean, default=True)

    user = relationship("User", back_populates="permissions")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    client = Column(String, nullable=False)
    phone = Column(String, default="")
    amount = Column(String, default="0")
    comment = Column(Text, default="")
    destination = Column(String, default="")
    status = Column(String, default="Kesish")
    currency = Column(String, default="UZS")
    operator_id = Column(Integer, nullable=True)
    image_url = Column(String, nullable=True)
    in_warehouse = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    estimated_finish_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    history = relationship("OrderHistory", back_populates="order", cascade="all, delete-orphan")
    images = relationship("OrderImage", back_populates="order", cascade="all, delete-orphan")


class OrderHistory(Base):
    __tablename__ = "order_history"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True, nullable=False)
    stage = Column(String, nullable=False)
    operator_username = Column(String, nullable=False)
    action = Column(String, default="completed")
    comment = Column(Text, default="")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, default=utcnow)

    order = relationship("Order", back_populates="history")


class OrderImage(Base):
    __tablename__ = "order_images"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True, nullable=False)
    url = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    order = relationship("Order", back_populates="images")


class WarehouseItem(Base):
    __tablename__ = "warehouse_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), unique=True, index=True)
    client = Column(String, nullable=False)
    phone = Column(String, default="")
    amount = Column(String, default="0")
    destination = Column(String, default="")
    quantity = Column(Integer, default=1)
    stored_at = Column(DateTime, default=utcnow)
    comment = Column(Text, default="")


class ShipmentGroup(Base):
    __tablename__ = "shipment_groups"

    id = Column(Integer, primary_key=True, index=True)
    destination = Column(String, default="")
    comment = Column(Text, default="")
    shipped_at = Column(DateTime, default=utcnow)
    warehouse_operator = Column(String, nullable=False)
    responsible_operator = Column(String, default="")
    total_products_count = Column(Integer, default=0)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    items = relationship(
        "ShipmentItem",
        back_populates="shipment_group",
        cascade="all, delete-orphan",
    )


class ShipmentItem(Base):
    __tablename__ = "shipment_items"

    id = Column(Integer, primary_key=True, index=True)
    shipment_group_id = Column(Integer, ForeignKey("shipment_groups.id"), index=True)
    order_id = Column(Integer, nullable=True)
    client = Column(String, nullable=False)
    phone = Column(String, default="")
    amount = Column(String, default="0")
    product_destination = Column(String, default="")
    quantity = Column(Integer, default=1)

    shipment_group = relationship("ShipmentGroup", back_populates="items")


class ShipmentArchive(Base):
    """Legacy per-product archive — kept for compatibility."""
    __tablename__ = "shipment_archive"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, index=True, nullable=True)
    client = Column(String, nullable=False)
    destination = Column(String, default="")
    amount = Column(String, default="0")
    shipped_at = Column(DateTime, default=utcnow)
    operator_username = Column(String, nullable=False)
    comment = Column(Text, default="")


class ExportShipment(Base):
    __tablename__ = "export_shipments"

    id = Column(Integer, primary_key=True, index=True)
    shipment_number = Column(String, unique=True, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    customer = Column(String, nullable=False)
    country = Column(String, default="Kazakhstan")
    contract_number = Column(String, default="")
    currency = Column(String, default="KZT")
    shipment_date = Column(DateTime, default=utcnow)
    status = Column(String, default="Draft", index=True)
    total_quantity = Column(Float, default=0)
    total_weight = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    notes = Column(Text, default="")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    order = relationship("Order")
    items = relationship(
        "ExportShipmentItem", back_populates="shipment", cascade="all, delete-orphan"
    )
    documents = relationship(
        "ExportShipmentDocument", back_populates="shipment", cascade="all, delete-orphan"
    )


class ExportShipmentItem(Base):
    __tablename__ = "export_shipment_items"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("export_shipments.id"), index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    product_name = Column(String, nullable=False)
    description = Column(Text, default="")
    quantity = Column(Float, default=1)
    unit = Column(String, default="pcs")
    weight_kg = Column(Float, default=0)
    unit_price = Column(Float, default=0)
    total_amount = Column(Float, default=0)
    sort_order = Column(Integer, default=0)

    shipment = relationship("ExportShipment", back_populates="items")
    order = relationship("Order")


class ExportShipmentDocument(Base):
    __tablename__ = "export_shipment_documents"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("export_shipments.id"), index=True, nullable=False)
    document_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    filename = Column(String, default="")
    content_type = Column(String, default="")
    file_size = Column(Integer, default=0)
    llp_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    generated_by = Column(String, nullable=False)
    generated_at = Column(DateTime, default=utcnow)

    shipment = relationship("ExportShipment", back_populates="documents")
    llp_document = relationship("Document")


class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    room_type = Column(String, default="department")
    department = Column(String, nullable=True)
    participant_a = Column(String, nullable=True)
    participant_b = Column(String, nullable=True)
    created_by = Column(String, default="system")
    created_at = Column(DateTime, default=utcnow)

    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), index=True)
    sender_username = Column(String, nullable=False)
    sender_department = Column(String, default="")
    content = Column(Text, default="")
    message_type = Column(String, default="text")
    attachment_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    room = relationship("ChatRoom", back_populates="messages")


class ChatReadState(Base):
    __tablename__ = "chat_read_state"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, index=True, nullable=False)
    username = Column(String, index=True, nullable=False)
    last_read_message_id = Column(Integer, default=0)
    last_read_at = Column(DateTime, default=utcnow)


class ChatNotification(Base):
    __tablename__ = "chat_notifications"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    room_id = Column(Integer, index=True, nullable=False)
    message_id = Column(Integer, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)


class OperatorActivity(Base):
    __tablename__ = "operator_activity"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    username = Column(String, nullable=False)
    department = Column(String, nullable=False)
    is_online = Column(Boolean, default=True)
    last_activity = Column(DateTime, default=utcnow)
    login_at = Column(DateTime, nullable=True)
    active_orders_count = Column(Integer, default=0)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)


class MigrationHistory(Base):
    __tablename__ = "migration_history"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)  # export | import | rollback
    status = Column(String, default="pending")  # pending | completed | failed | rolled_back
    bundle_name = Column(String, default="")
    manifest_version = Column(Integer, default=1)
    summary_json = Column(Text, default="{}")
    backup_path = Column(String, default="")
    source_env = Column(String, default="")
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)


class MaterialCategory(Base):
    __tablename__ = "material_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    code = Column(String, unique=True, index=True, nullable=True)
    description = Column(Text, default="")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    materials = relationship("Material", back_populates="category")


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, unique=True, nullable=False)
    unit = Column(String, default="dona")
    category_id = Column(Integer, ForeignKey("material_categories.id"), nullable=True, index=True)
    quantity = Column(Float, default=0)
    min_quantity = Column(Float, default=5)
    unit_cost = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    category = relationship("MaterialCategory", back_populates="materials")


class MaterialReceipt(Base):
    __tablename__ = "material_receipts"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    quantity = Column(Float, nullable=False)
    unit_cost = Column(Float, default=0.0)
    reference = Column(String, default="")
    notes = Column(Text, default="")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    material = relationship("Material")


class MaterialIssue(Base):
    __tablename__ = "material_issues"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    quantity = Column(Float, nullable=False)
    reason = Column(String, default="")
    reference = Column(String, default="")
    notes = Column(Text, default="")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    material = relationship("Material")


class MaterialAdjustment(Base):
    __tablename__ = "material_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    quantity_before = Column(Float, default=0.0)
    quantity_after = Column(Float, default=0.0)
    adjustment_delta = Column(Float, nullable=False)
    reason = Column(String, default="")
    notes = Column(Text, default="")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    material = relationship("Material")


class MaterialStockMovement(Base):
    __tablename__ = "material_stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    movement_type = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    balance_after = Column(Float, default=0.0)
    unit_cost = Column(Float, default=0.0)
    reference_type = Column(String, nullable=True)
    reference_id = Column(Integer, nullable=True)
    notes = Column(Text, default="")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    material = relationship("Material")


class MaterialBomLine(Base):
    """Raw material consumption per MES part (P4-A2)."""

    __tablename__ = "material_bom_lines"
    __table_args__ = (
        UniqueConstraint("part_id", "material_id", name="uq_material_bom_part_material"),
    )

    id = Column(Integer, primary_key=True, index=True)
    part_id = Column(Integer, ForeignKey("mes_product_parts.id"), index=True, nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    quantity_per_part = Column(Float, nullable=False, default=0.0)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    part = relationship("MesProductPart", back_populates="material_bom_lines")
    material = relationship("Material")


class MaterialReservation(Base):
    """Planned material need for a released production job (no stock deduction)."""

    __tablename__ = "material_reservations"
    __table_args__ = (
        UniqueConstraint("job_id", "material_id", name="uq_material_res_job_material"),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    required_quantity = Column(Float, nullable=False, default=0.0)
    reserved_quantity = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    job = relationship("MesProductionJob", back_populates="material_reservations")
    material = relationship("Material")


class MaterialConsumptionRule(Base):
    """Which materials are auto-issued when a production stage starts (P4-A3)."""

    __tablename__ = "material_consumption_rules"
    __table_args__ = (
        UniqueConstraint("material_id", "consuming_stage", name="uq_material_cons_rule"),
    )

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    consuming_stage = Column(String, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    material = relationship("Material")


class MaterialConsumption(Base):
    """Automatic material issue tied to a job stage start (P4-A3)."""

    __tablename__ = "material_consumptions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=False)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    quantity = Column(Float, nullable=False)
    stage = Column(String, nullable=False, index=True)
    movement_id = Column(Integer, ForeignKey("material_stock_movements.id"), nullable=True, index=True)
    consumed_at = Column(DateTime, default=utcnow)

    job = relationship("MesProductionJob", back_populates="material_consumptions")
    material = relationship("Material")
    movement = relationship("MaterialStockMovement")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, index=True, nullable=False)
    movement_type = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    note = Column(String, default="")
    created_by = Column(String, default="system")
    created_at = Column(DateTime, default=utcnow)


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, default="general")
    created_at = Column(DateTime, default=utcnow)


class Income(Base):
    __tablename__ = "incomes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    source = Column(String, default="order")
    created_at = Column(DateTime, default=utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    priority = Column(String, default="normal")  # normal | important | urgent
    deadline = Column(DateTime, nullable=True)
    created_by = Column(String, nullable=False)
    assign_all = Column(Boolean, default=False)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    assignments = relationship(
        "TaskAssignment", back_populates="task", cascade="all, delete-orphan"
    )
    comments = relationship(
        "TaskComment", back_populates="task", cascade="all, delete-orphan"
    )
    attachments = relationship(
        "TaskAttachment", back_populates="task", cascade="all, delete-orphan"
    )


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True, nullable=False)
    operator_username = Column(String, index=True, nullable=False)
    status = Column(String, default="new")  # new|accepted|in_progress|completed|cancelled
    accepted_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    task = relationship("Task", back_populates="assignments")


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True, nullable=False)
    assignment_id = Column(Integer, nullable=True)
    username = Column(String, nullable=False)
    content = Column(Text, default="")
    kind = Column(String, default="comment")  # comment | status
    status_value = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    task = relationship("Task", back_populates="comments")


class TaskAttachment(Base):
    __tablename__ = "task_attachments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), index=True, nullable=False)
    uploaded_by = Column(String, nullable=False)
    url = Column(String, nullable=False)
    filename = Column(String, default="")
    content_type = Column(String, default="")
    kind = Column(String, default="task")  # task | result
    created_at = Column(DateTime, default=utcnow)

    task = relationship("Task", back_populates="attachments")


# Legacy alias
ProductionLog = OrderHistory


class DocumentFolder(Base):
    __tablename__ = "document_folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("document_folders.id"), nullable=True, index=True)
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    documents = relationship("Document", back_populates="folder", cascade="all, delete-orphan")
    children = relationship("DocumentFolder")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("document_folders.id"), index=True, nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    url = Column(String, nullable=False)
    filename = Column(String, default="")
    original_filename = Column(String, default="")
    content_type = Column(String, default="")
    file_size = Column(Integer, default=0)
    is_important = Column(Boolean, default=False)
    uploaded_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    folder = relationship("DocumentFolder", back_populates="documents")
    read_statuses = relationship(
        "DocumentReadStatus", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentReadStatus(Base):
    __tablename__ = "document_read_status"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), index=True, nullable=False)
    username = Column(String, index=True, nullable=False)
    read_at = Column(DateTime, default=utcnow)

    document = relationship("Document", back_populates="read_statuses")


# --- MES (Production Pro) ---


class MesProductCategory(Base):
    __tablename__ = "mes_product_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, default="")
    parent_id = Column(Integer, ForeignKey("mes_product_categories.id"), nullable=True, index=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    created_by = Column(String, nullable=False)

    parent = relationship("MesProductCategory", remote_side=[id], backref="children")
    templates = relationship("MesProductTemplate", back_populates="category")


class MesProductPart(Base):
    __tablename__ = "mes_product_parts"

    id = Column(Integer, primary_key=True, index=True)
    part_number = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    unit = Column(String, default="dona")
    description = Column(Text, default="")
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, nullable=False)

    material = relationship("Material")
    bom_lines = relationship("MesBomLine", back_populates="part")
    material_bom_lines = relationship(
        "MaterialBomLine", back_populates="part", cascade="all, delete-orphan"
    )


class MesProductionStage(Base):
    """Configurable route stages (not limited to legacy PRODUCTION_STAGES)."""

    __tablename__ = "mes_production_stages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    department = Column(String, default="Admin")
    sort_order = Column(Integer, default=0)
    color = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    route_steps = relationship("MesRouteStep", back_populates="stage")


class MesProductTemplate(Base):
    __tablename__ = "mes_product_templates"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("mes_product_categories.id"), nullable=True, index=True)
    description = Column(Text, default="")
    unit = Column(String, default="dona")
    length_mm = Column(Float, nullable=True)
    width_mm = Column(Float, nullable=True)
    height_mm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    image_url = Column(String, nullable=True)
    qr_prefix = Column(String, nullable=True)
    default_route_id = Column(Integer, ForeignKey("mes_production_routes.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, nullable=False)

    category = relationship("MesProductCategory", back_populates="templates")
    bom_lines = relationship(
        "MesBomLine", back_populates="template", cascade="all, delete-orphan"
    )
    routes = relationship(
        "MesProductionRoute",
        back_populates="template",
        cascade="all, delete-orphan",
        foreign_keys="MesProductionRoute.template_id",
    )
    drawings = relationship(
        "MesProductDrawing", back_populates="template", cascade="all, delete-orphan"
    )
    default_route = relationship(
        "MesProductionRoute",
        foreign_keys=[default_route_id],
        post_update=True,
    )


class MesBomLine(Base):
    __tablename__ = "mes_bom_lines"
    __table_args__ = (UniqueConstraint("template_id", "part_id", name="uq_mes_bom_template_part"),)

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("mes_product_templates.id"), index=True, nullable=False)
    part_id = Column(Integer, ForeignKey("mes_product_parts.id"), index=True, nullable=False)
    required_quantity = Column(Float, default=1.0, nullable=False)
    produced_quantity = Column(Float, default=0.0)
    accepted_quantity = Column(Float, default=0.0)
    rejected_quantity = Column(Float, default=0.0)
    unit = Column(String, nullable=True)
    notes = Column(Text, default="")
    drawing_url = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    template = relationship("MesProductTemplate", back_populates="bom_lines")
    part = relationship("MesProductPart", back_populates="bom_lines")


class MesProductionRoute(Base):
    __tablename__ = "mes_production_routes"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("mes_product_templates.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    version = Column(Integer, default=1)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    created_by = Column(String, nullable=False)

    template = relationship(
        "MesProductTemplate",
        back_populates="routes",
        foreign_keys=[template_id],
    )
    steps = relationship(
        "MesRouteStep",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="MesRouteStep.step_order",
    )


class MesRouteStep(Base):
    __tablename__ = "mes_route_steps"
    __table_args__ = (UniqueConstraint("route_id", "step_order", name="uq_mes_route_step_order"),)

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("mes_production_routes.id"), index=True, nullable=False)
    stage_id = Column(Integer, ForeignKey("mes_production_stages.id"), index=True, nullable=False)
    step_order = Column(Integer, nullable=False)
    department = Column(String, nullable=True)
    responsible_role = Column(String, nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    required_parts_count = Column(Integer, default=0)
    completed_parts_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    instructions = Column(Text, default="")
    is_required = Column(Boolean, default=True)

    route = relationship("MesProductionRoute", back_populates="steps")
    stage = relationship("MesProductionStage", back_populates="route_steps")


class MesProductDrawing(Base):
    __tablename__ = "mes_product_drawings"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("mes_product_templates.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    file_size = Column(Integer, default=0)
    revision = Column(String, default="A")
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    uploaded_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    template = relationship("MesProductTemplate", back_populates="drawings")


class MesProductionJob(Base):
    __tablename__ = "mes_production_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_number = Column(String, unique=True, index=True, nullable=False)
    customer_name = Column(String, default="")
    order_reference = Column(String, default="")
    template_id = Column(Integer, ForeignKey("mes_product_templates.id"), index=True, nullable=False)
    route_id = Column(Integer, ForeignKey("mes_production_routes.id"), nullable=True, index=True)
    quantity = Column(Float, default=1.0, nullable=False)
    priority = Column(String, default="normal")
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="draft", index=True)
    paint_color_name = Column(String, default="")
    paint_ral_code = Column(String, default="")
    paint_type = Column(String, default="")
    paint_batch_number = Column(String, default="")
    package_type = Column(String, default="")
    package_count = Column(Integer, default=0)
    packaging_net_weight_kg = Column(Float, default=0.0)
    packaging_gross_weight_kg = Column(Float, default=0.0)
    packaging_notes = Column(Text, default="")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, nullable=False)

    template = relationship("MesProductTemplate")
    route = relationship("MesProductionRoute")
    bom_lines = relationship(
        "MesJobBomLine", back_populates="job", cascade="all, delete-orphan"
    )
    route_steps = relationship(
        "MesJobRouteStep",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="MesJobRouteStep.step_order",
    )
    packages = relationship(
        "MesJobPackage",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="MesJobPackage.id",
    )
    material_reservations = relationship(
        "MaterialReservation",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    material_consumptions = relationship(
        "MaterialConsumption",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class MesJobBomLine(Base):
    __tablename__ = "mes_job_bom_lines"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=False)
    source_bom_line_id = Column(Integer, ForeignKey("mes_bom_lines.id"), nullable=True)
    part_id = Column(Integer, ForeignKey("mes_product_parts.id"), index=True, nullable=False)
    part_number = Column(String, nullable=False)
    part_name = Column(String, nullable=False)
    unit = Column(String, default="dona")
    allocated_quantity = Column(Float, default=0.0, nullable=False)
    completed_quantity = Column(Float, default=0.0)
    painted_quantity = Column(Float, default=0.0)
    accepted_quantity = Column(Float, default=0.0)
    rejected_quantity = Column(Float, default=0.0)
    rework_quantity = Column(Float, default=0.0)
    notes = Column(Text, default="")
    drawing_url = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)

    job = relationship("MesProductionJob", back_populates="bom_lines")
    part = relationship("MesProductPart")


class MesJobRouteStep(Base):
    __tablename__ = "mes_job_route_steps"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=False)
    source_route_step_id = Column(Integer, ForeignKey("mes_route_steps.id"), nullable=True)
    stage_id = Column(Integer, ForeignKey("mes_production_stages.id"), index=True, nullable=False)
    stage_name = Column(String, nullable=False)
    step_order = Column(Integer, nullable=False)
    department = Column(String, nullable=True)
    responsible_role = Column(String, nullable=True)
    estimated_minutes = Column(Integer, nullable=True)
    required_parts_count = Column(Integer, default=0)
    completed_parts_count = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    drying_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    instructions = Column(Text, default="")
    is_required = Column(Boolean, default=True)

    job = relationship("MesProductionJob", back_populates="route_steps")
    stage = relationship("MesProductionStage")


class MesQcRejectionReason(Base):
    __tablename__ = "mes_qc_rejection_reasons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class MesJobRework(Base):
    __tablename__ = "mes_job_reworks"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=False)
    bom_line_id = Column(Integer, ForeignKey("mes_job_bom_lines.id"), index=True, nullable=False)
    rejection_reason_id = Column(
        Integer, ForeignKey("mes_qc_rejection_reasons.id"), nullable=True, index=True
    )
    quantity = Column(Float, default=0.0, nullable=False)
    status = Column(String, default="pending", index=True)
    notes = Column(Text, default="")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(String, nullable=True)

    job = relationship("MesProductionJob")
    bom_line = relationship("MesJobBomLine")
    rejection_reason = relationship("MesQcRejectionReason")


class MesJobPackage(Base):
    __tablename__ = "mes_job_packages"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=False)
    package_number = Column(String, unique=True, index=True, nullable=False)
    package_type = Column(String, default="")
    net_weight_kg = Column(Float, default=0.0)
    gross_weight_kg = Column(Float, default=0.0)
    status = Column(String, default="pending", index=True)
    location_id = Column(Integer, ForeignKey("mes_warehouse_locations.id"), nullable=True, index=True)
    received_at = Column(DateTime, nullable=True)
    placed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    job = relationship("MesProductionJob", back_populates="packages")
    location = relationship("MesWarehouseLocation")
    label = relationship("PackageLabel", back_populates="package", uselist=False)
    storage_location = relationship("PackageLocation", back_populates="package", uselist=False)
    print_jobs = relationship("PrintJob", back_populates="package", cascade="all, delete-orphan")


class PackageLabel(Base):
    __tablename__ = "package_labels"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), unique=True, index=True, nullable=False)
    label_code = Column(String, unique=True, index=True, nullable=False)
    qr_data = Column(Text, default="")
    barcode_data = Column(String, default="")
    printed_at = Column(DateTime, nullable=True)
    printer_name = Column(String, default="")
    created_at = Column(DateTime, default=utcnow)

    package = relationship("MesJobPackage", back_populates="label")


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), index=True, nullable=False)
    label_code = Column(String, index=True, nullable=False)
    printer_name = Column(String, default="", index=True)
    status = Column(String, default="pending", index=True)
    created_at = Column(DateTime, default=utcnow)
    printed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, default="")

    package = relationship("MesJobPackage", back_populates="print_jobs")


class PrintAgentHeartbeat(Base):
    __tablename__ = "print_agent_heartbeats"

    printer_name = Column(String, primary_key=True)
    last_seen_at = Column(DateTime, default=utcnow)
    hostname = Column(String, default="")
    agent_version = Column(String, default="")


class PackageLocation(Base):
    __tablename__ = "package_locations"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), unique=True, index=True, nullable=False)
    warehouse_zone = Column(String, default="")
    rack = Column(String, default="")
    shelf = Column(String, default="")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    package = relationship("MesJobPackage", back_populates="storage_location")


class MesWarehouseLocation(Base):
    __tablename__ = "mes_warehouse_locations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, default="")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, nullable=False)


class MesFinishedGoodsInventory(Base):
    __tablename__ = "mes_finished_goods_inventory"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=False)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), unique=True, index=True, nullable=False)
    template_id = Column(Integer, ForeignKey("mes_product_templates.id"), index=True, nullable=False)
    product_code = Column(String, nullable=False)
    product_name = Column(String, nullable=False)
    location_id = Column(Integer, ForeignKey("mes_warehouse_locations.id"), index=True, nullable=False)
    quantity = Column(Float, default=1.0, nullable=False)
    unit = Column(String, default="dona")
    status = Column(String, default="in_stock", index=True)
    received_at = Column(DateTime, nullable=True)
    placed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, nullable=False)

    job = relationship("MesProductionJob")
    package = relationship("MesJobPackage")
    template = relationship("MesProductTemplate")
    location = relationship("MesWarehouseLocation")


class MesInventoryMovement(Base):
    __tablename__ = "mes_inventory_movements"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("mes_finished_goods_inventory.id"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=True)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), nullable=True, index=True)
    movement_type = Column(String, nullable=False, index=True)
    from_location_id = Column(Integer, ForeignKey("mes_warehouse_locations.id"), nullable=True)
    to_location_id = Column(Integer, ForeignKey("mes_warehouse_locations.id"), nullable=True)
    quantity = Column(Float, default=1.0, nullable=False)
    performed_by = Column(String, nullable=False)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)

    inventory = relationship("MesFinishedGoodsInventory")
    from_location = relationship("MesWarehouseLocation", foreign_keys=[from_location_id])
    to_location = relationship("MesWarehouseLocation", foreign_keys=[to_location_id])


class MesDispatch(Base):
    __tablename__ = "mes_dispatches"

    id = Column(Integer, primary_key=True, index=True)
    dispatch_number = Column(String, unique=True, index=True, nullable=False)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), index=True, nullable=False)
    customer_name = Column(String, default="")
    package_count = Column(Integer, default=0)
    vehicle_number = Column(String, default="")
    driver_name = Column(String, default="")
    driver_phone = Column(String, default="")
    transport_company = Column(String, default="")
    status = Column(String, default="pending", index=True)
    ship_date = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, nullable=False)

    job = relationship("MesProductionJob")
    packages = relationship(
        "MesDispatchPackage",
        back_populates="dispatch",
        cascade="all, delete-orphan",
    )


class MesDispatchPackage(Base):
    __tablename__ = "mes_dispatch_packages"

    id = Column(Integer, primary_key=True, index=True)
    dispatch_id = Column(Integer, ForeignKey("mes_dispatches.id"), index=True, nullable=False)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), unique=True, index=True, nullable=False)
    inventory_id = Column(Integer, ForeignKey("mes_finished_goods_inventory.id"), nullable=True, index=True)
    status = Column(String, default="pending", index=True)
    loaded_by = Column(String, nullable=True)
    loaded_at = Column(DateTime, nullable=True)
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    dispatch = relationship("MesDispatch", back_populates="packages")
    package = relationship("MesJobPackage")
    inventory = relationship("MesFinishedGoodsInventory")


class MobileAppVersion(Base):
    """Published Android APK releases for in-app auto-update."""

    __tablename__ = "mobile_app_versions"

    id = Column(Integer, primary_key=True, index=True)
    version_name = Column(String, nullable=False, index=True)
    version_code = Column(Integer, nullable=False, index=True)
    apk_url = Column(String, nullable=False, default="")
    release_notes = Column(Text, default="")
    force_update = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)


# --- Phase 11B: Multi Currency ---


class Currency(Base):
    __tablename__ = "currencies"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    symbol = Column(String, default="")
    is_base = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


class ExchangeRate(Base):
    """Rate to base currency (UZS): 1 unit of currency_code = rate_to_base UZS."""

    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    currency_code = Column(String, index=True, nullable=False)
    rate_to_base = Column(Float, nullable=False)
    rate_date = Column(DateTime, default=utcnow, index=True)
    created_by = Column(String, default="system")
    created_at = Column(DateTime, default=utcnow)


# --- Phase 11B: Transport Management ---


class Transport(Base):
    __tablename__ = "transports"

    id = Column(Integer, primary_key=True, index=True)
    export_shipment_id = Column(
        Integer, ForeignKey("export_shipments.id"), nullable=True, index=True
    )
    vehicle = Column(String, nullable=False)
    driver_name = Column(String, default="")
    driver_phone = Column(String, default="")
    shipment_weight_kg = Column(Float, default=0)
    departure_date = Column(DateTime, nullable=True)
    arrival_date = Column(DateTime, nullable=True)
    status = Column(String, default="Draft", index=True)
    notes = Column(Text, default="")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    export_shipment = relationship("ExportShipment")
    events = relationship(
        "TransportEvent", back_populates="transport", cascade="all, delete-orphan"
    )


class TransportEvent(Base):
    """Status timeline entry for a transport."""

    __tablename__ = "transport_events"

    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(Integer, ForeignKey("transports.id"), index=True, nullable=False)
    status = Column(String, nullable=False)
    comment = Column(Text, default="")
    created_by = Column(String, default="system")
    created_at = Column(DateTime, default=utcnow)

    transport = relationship("Transport", back_populates="events")


# --- Phase 11B: Customer Debt Tracking ---


class CustomerPayment(Base):
    __tablename__ = "customer_payments"

    id = Column(Integer, primary_key=True, index=True)
    customer = Column(String, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="UZS")
    notes = Column(Text, default="")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)
