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


# Legacy alias
ProductionLog = OrderHistory
