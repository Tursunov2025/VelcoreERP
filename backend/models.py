from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
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


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    unit = Column(String, default="dona")
    quantity = Column(Float, default=0)
    min_quantity = Column(Float, default=5)
    created_at = Column(DateTime, default=utcnow)


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
