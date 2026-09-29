from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, JSON
from sqlalchemy.orm import relationship

from database import Base


def utcnow():
    return datetime.utcnow()


# Display Center is intentionally isolated from the ERP domain models.  JSON
# payloads keep widgets/templates forward-compatible without schema churn.
class Display(Base):
    __tablename__ = "display_center_displays"
    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    code = Column(String(64), nullable=False, unique=True, index=True)
    location = Column(String(255), default="")
    description = Column(Text, default="")
    ip_address = Column(String(64), default="")
    resolution = Column(String(32), default="1920x1080")
    orientation = Column(String(16), default="landscape")
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(24), default="offline", index=True)
    playlist_id = Column(Integer, ForeignKey("display_center_playlists.id"), nullable=True)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DisplayMediaFolder(Base):
    __tablename__ = "display_center_media_folders"
    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    parent_id = Column(Integer, ForeignKey("display_center_media_folders.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class DisplayMediaAsset(Base):
    __tablename__ = "display_center_media_assets"
    id = Column(Integer, primary_key=True)
    folder_id = Column(Integer, ForeignKey("display_center_media_folders.id"), nullable=True)
    name = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    media_type = Column(String(24), nullable=False, index=True)
    content_type = Column(String(120), default="")
    path = Column(String(500), nullable=False)
    thumbnail_path = Column(String(500), default="")
    size_bytes = Column(Integer, default=0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class DisplayWidget(Base):
    __tablename__ = "display_center_widgets"
    id = Column(Integer, primary_key=True)
    key = Column(String(80), nullable=False, unique=True, index=True)
    name = Column(String(160), nullable=False)
    widget_type = Column(String(64), nullable=False, index=True)
    settings_json = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DisplayPlaylist(Base):
    __tablename__ = "display_center_playlists"
    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    description = Column(Text, default="")
    template_key = Column(String(64), default="custom")
    template_id = Column(Integer, ForeignKey("display_center_templates.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DisplayTemplate(Base):
    __tablename__ = "display_center_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    category = Column(String(64), default="factory")
    canvas_json = Column(JSON, default=lambda: {"width": 1920, "height": 1080, "grid": 20})
    layout_json = Column(JSON, default=lambda: {"widgets": []})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DisplayPlaylistItem(Base):
    __tablename__ = "display_center_playlist_items"
    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("display_center_playlists.id", ondelete="CASCADE"), nullable=False, index=True)
    item_type = Column(String(32), nullable=False)
    widget_id = Column(Integer, ForeignKey("display_center_widgets.id"), nullable=True)
    media_id = Column(Integer, ForeignKey("display_center_media_assets.id"), nullable=True)
    settings_json = Column(JSON, default=dict)
    position = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Integer, default=15)
    transition = Column(String(48), default="fade")
    repeat = Column(Boolean, default=True)


class DisplaySchedule(Base):
    __tablename__ = "display_center_schedules"
    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("display_center_playlists.id", ondelete="CASCADE"), nullable=False)
    display_id = Column(Integer, ForeignKey("display_center_displays.id", ondelete="CASCADE"), nullable=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    weekdays_json = Column(JSON, default=list)
    start_time = Column(String(8), default="00:00")
    end_time = Column(String(8), default="23:59")
    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DisplayHeartbeat(Base):
    __tablename__ = "display_center_heartbeats"
    id = Column(Integer, primary_key=True)
    display_id = Column(Integer, ForeignKey("display_center_displays.id", ondelete="CASCADE"), nullable=False, index=True)
    browser = Column(String(255), default="")
    cpu_percent = Column(Float, nullable=True)
    ram_percent = Column(Float, nullable=True)
    connection = Column(String(64), default="")
    resolution = Column(String(32), default="")
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


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


class UserIdentityProfile(Base):
    __tablename__ = "user_identity_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    full_name = Column(String(160), default="")
    employee_id = Column(String(80), default="", index=True)
    position = Column(String(120), default="")
    phone = Column(String(64), default="")
    email = Column(String(160), default="")
    telegram = Column(String(100), default="")
    avatar_url = Column(String(500), default="")
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class UserIdentityActivity(Base):
    __tablename__ = "user_identity_activity"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    details = Column(Text, default="")
    actor_username = Column(String(100), default="")
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)


class UserIdentitySession(Base):
    __tablename__ = "user_identity_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device = Column(String(160), default="")
    browser = Column(String(160), default="")
    ip_address = Column(String(64), default="")
    location = Column(String(160), default="")
    is_active = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


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
    llp_document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
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
    old_value = Column(Text, default="")
    new_value = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)


# --- Super Admin CMS ---


class UiSetting(Base):
    __tablename__ = "ui_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, default="")
    category = Column(String, default="general", index=True)
    updated_by = Column(String, default="")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class NavigationItem(Base):
    __tablename__ = "navigation_items"

    id = Column(Integer, primary_key=True, index=True)
    nav_key = Column(String, unique=True, index=True, nullable=False)
    label = Column(String, nullable=False)
    icon = Column(String, default="")
    emoji = Column(String, default="")
    path = Column(String, default="/")
    color = Column(String, default="")
    sort_order = Column(Integer, default=0, index=True)
    parent_id = Column(Integer, ForeignKey("navigation_items.id"), nullable=True, index=True)
    visible = Column(Boolean, default=True)
    hidden = Column(Boolean, default=False)
    permissions_json = Column(Text, default="[]")
    module_key = Column(String, default="", index=True)
    config_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    parent = relationship("NavigationItem", remote_side=[id], backref="children")


class PermissionDefinition(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    perm_key = Column(String, unique=True, index=True, nullable=False)
    label = Column(String, nullable=False)
    module = Column(String, default="", index=True)
    description = Column(Text, default="")
    action = Column(String, default="")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    role_key = Column(String, unique=True, index=True, nullable=False)
    label = Column(String, nullable=False)
    description = Column(Text, default="")
    is_system = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)

    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), index=True, nullable=False)
    permission_key = Column(String, index=True, nullable=False)
    enabled = Column(Boolean, default=True)

    role = relationship("Role", back_populates="permissions")

    __table_args__ = (UniqueConstraint("role_id", "permission_key", name="uq_role_permission"),)


class Widget(Base):
    __tablename__ = "widgets"

    id = Column(Integer, primary_key=True, index=True)
    widget_key = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    widget_type = Column(String, default="stat")
    enabled = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0, index=True)
    color = Column(String, default="")
    layout_json = Column(Text, default="{}")
    config_json = Column(Text, default="{}")


class Theme(Base):
    __tablename__ = "themes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, index=True)
    is_dark = Column(Boolean, default=False)
    config_json = Column(Text, default="{}")


class ModuleSetting(Base):
    __tablename__ = "module_settings"

    id = Column(Integer, primary_key=True, index=True)
    module_key = Column(String, unique=True, index=True, nullable=False)
    enabled = Column(Boolean, default=True)
    label = Column(String, nullable=False)
    icon = Column(String, default="")
    color = Column(String, default="")
    url = Column(String, default="/")
    permissions_json = Column(Text, default="[]")
    sort_order = Column(Integer, default=0)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    flag_key = Column(String, unique=True, index=True, nullable=False)
    enabled = Column(Boolean, default=False)
    description = Column(Text, default="")
    config_json = Column(Text, default="{}")


class UiConfigVersion(Base):
    __tablename__ = "ui_config_versions"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, default="")
    snapshot_json = Column(Text, default="{}")
    created_by = Column(String, default="")
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
    # Additive professional material-master metadata.  Legacy rows remain valid
    # because every new field is nullable or has a backward-compatible default.
    material_type = Column(String(32), default="CONSUMABLE", nullable=False, index=True)
    purchase_unit = Column(String(24), default="dona", nullable=False)
    profile_type = Column(String(32), nullable=True, index=True)
    steel_grade = Column(String(80), default="")
    description = Column(Text, default="")
    image_url = Column(String(500), nullable=True)
    width_mm = Column(Float, nullable=True)
    height_mm = Column(Float, nullable=True)
    diameter_mm = Column(Float, nullable=True)
    thickness_mm = Column(Float, nullable=True)
    inner_radius_mm = Column(Float, nullable=True)
    length_mm = Column(Float, nullable=True)
    theoretical_weight_kg_per_m = Column(Float, nullable=True)
    density_kg_m3 = Column(Float, nullable=True)
    default_kerf_mm = Column(Float, nullable=True)
    min_reusable_offcut_m = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    category = relationship("MaterialCategory", back_populates="materials")
    length_lots = relationship("MaterialStockLengthLot", back_populates="material")


class MaterialReceipt(Base):
    __tablename__ = "material_receipts"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), index=True, nullable=False)
    quantity = Column(Float, nullable=False)
    unit_cost = Column(Float, default=0.0)
    reference = Column(String, default="")
    notes = Column(Text, default="")
    receipt_number = Column(String(100), nullable=True, unique=True, index=True)
    operation_key = Column(String(180), nullable=True, unique=True, index=True)
    confirm_key = Column(String(180), nullable=True, unique=True, index=True)
    reverse_key = Column(String(180), nullable=True, unique=True, index=True)
    status = Column(String(24), nullable=False, default="CONFIRMED", index=True)
    supplier_name = Column(String(180), default="")
    supplier_invoice = Column(String(180), default="")
    warehouse_name = Column(String(120), default="")
    location_code = Column(String(120), default="")
    lot_number = Column(String(120), default="")
    purchase_unit = Column(String(24), default="")
    base_unit = Column(String(24), default="")
    price_basis = Column(String(24), default="PER_UNIT")
    currency = Column(String(8), default="UZS")
    total_pieces = Column(Integer, default=0)
    total_weight_kg = Column(Float, nullable=True)
    total_amount = Column(Float, default=0.0)
    profile_rows_json = Column(Text, default="[]")
    stock_applied = Column(Boolean, nullable=False, default=True)
    version = Column(Integer, nullable=False, default=1)
    received_at = Column(DateTime, default=utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    confirmed_by = Column(String(100), nullable=True)
    reversed_at = Column(DateTime, nullable=True)
    reversed_by = Column(String(100), nullable=True)
    reversal_reason = Column(Text, default="")
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

    document_number = Column(String(100), nullable=True, unique=True, index=True)
    operation_key = Column(String(180), nullable=True, unique=True, index=True)
    status = Column(String(24), nullable=False, default="COMPLETED", index=True)
    project_id = Column(Integer, nullable=True, index=True)
    project_line_id = Column(Integer, nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), nullable=True, index=True)
    release_snapshot_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=True, index=True)
    material_reservation_id = Column(Integer, ForeignKey("material_reservations.id"), nullable=True, index=True)
    source_material_bom_line_id = Column(Integer, ForeignKey("material_bom_lines.id"), nullable=True, index=True)
    source_job_bom_line_id = Column(Integer, ForeignKey("mes_job_bom_lines.id"), nullable=True, index=True)
    planned_required_quantity = Column(Float, nullable=True)
    operation_stage = Column(String(80), default="LAZER")
    warehouse_name = Column(String(120), default="")
    responsible_employee = Column(String(120), default="")
    version = Column(Integer, nullable=False, default=1)
    issued_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

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


class MaterialStockLengthLot(Base):
    """Physical profile/sheet stock identity layered over canonical base quantity.

    ``Material.quantity`` remains the authoritative stock quantity in the
    material's base unit.  This row preserves the physical bar length and piece
    count needed by a future cutting/allocation workflow.
    """

    __tablename__ = "material_stock_length_lots"
    __table_args__ = (
        CheckConstraint("length_m > 0", name="ck_material_length_lot_length_positive"),
        CheckConstraint("pieces_on_hand >= 0", name="ck_material_length_lot_pieces_nonnegative"),
        CheckConstraint("pieces_reserved >= 0 AND pieces_reserved <= pieces_on_hand", name="ck_material_length_lot_reserved_balance"),
        CheckConstraint("total_meters >= 0", name="ck_material_length_lot_meters_nonnegative"),
        CheckConstraint("version > 0", name="ck_material_length_lot_version_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    receipt_id = Column(Integer, ForeignKey("material_receipts.id"), nullable=True, unique=True, index=True)
    # Additive multi-row receipt link. ``receipt_id`` remains the legacy
    # one-receipt/one-lot compatibility link and is intentionally retained.
    receipt_document_id = Column(Integer, ForeignKey("material_receipts.id"), nullable=True, index=True)
    length_m = Column(Float, nullable=False)
    pieces_on_hand = Column(Integer, nullable=False)
    pieces_reserved = Column(Integer, default=0, nullable=False)
    total_meters = Column(Float, nullable=False)
    pieces_received = Column(Integer, default=0, nullable=False)
    meters_received = Column(Float, default=0.0, nullable=False)
    status = Column(String(24), default="ACTIVE", nullable=False, index=True)
    warehouse_name = Column(String(120), default="")
    location_code = Column(String(120), default="")
    lot_number = Column(String(120), default="", index=True)
    supplier_name = Column(String(180), default="")
    supplier_invoice = Column(String(180), default="")
    source_reference = Column(String(180), default="")
    notes = Column(Text, default="")
    unit_cost = Column(Float, default=0.0)
    version = Column(Integer, default=1, nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    material = relationship("Material", back_populates="length_lots")
    receipt = relationship("MaterialReceipt", foreign_keys=[receipt_id])
    receipt_document = relationship("MaterialReceipt", foreign_keys=[receipt_document_id])


class MaterialStockPiece(Base):
    """One traceable physical profile bar or reusable offcut."""
    __tablename__ = "material_stock_pieces"
    __table_args__ = (
        CheckConstraint("original_length_m > 0", name="ck_material_piece_original_positive"),
        CheckConstraint("current_length_m >= 0", name="ck_material_piece_current_nonnegative"),
        CheckConstraint("version > 0", name="ck_material_piece_version_positive"),
    )
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    source_length_lot_id = Column(Integer, ForeignKey("material_stock_length_lots.id"), nullable=True, index=True)
    source_receipt_id = Column(Integer, ForeignKey("material_receipts.id"), nullable=True, index=True)
    parent_piece_id = Column(Integer, ForeignKey("material_stock_pieces.id"), nullable=True, index=True)
    source_cut_id = Column(Integer, nullable=True, index=True)
    original_length_m = Column(Float, nullable=False)
    current_length_m = Column(Float, nullable=False)
    status = Column(String(24), nullable=False, default="AVAILABLE", index=True)
    warehouse_name = Column(String(120), default="")
    location_code = Column(String(120), default="")
    lot_number = Column(String(120), default="")
    reserved_issue_id = Column(Integer, nullable=True, index=True)
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class MaterialIssuePiece(Base):
    __tablename__ = "material_issue_pieces"
    __table_args__ = (UniqueConstraint("issue_id", "piece_id", name="uq_material_issue_piece"),)
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey("material_issues.id"), nullable=False, index=True)
    piece_id = Column(Integer, ForeignKey("material_stock_pieces.id"), nullable=False, index=True)
    reserved_length_m = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class MaterialCutOperation(Base):
    __tablename__ = "material_cut_operations"
    id = Column(Integer, primary_key=True)
    operation_key = Column(String(180), nullable=False, unique=True, index=True)
    issue_id = Column(Integer, ForeignKey("material_issues.id"), nullable=False, index=True)
    source_piece_id = Column(Integer, ForeignKey("material_stock_pieces.id"), nullable=False, index=True)
    offcut_piece_id = Column(Integer, ForeignKey("material_stock_pieces.id"), nullable=True, index=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=True, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=True, index=True)
    release_snapshot_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), nullable=True, index=True)
    source_material_bom_line_id = Column(Integer, ForeignKey("material_bom_lines.id"), nullable=True, index=True)
    source_job_bom_line_id = Column(Integer, ForeignKey("mes_job_bom_lines.id"), nullable=True, index=True)
    length_before_m = Column(Float, nullable=False)
    planned_cut_length_m = Column(Float, nullable=False)
    actual_cut_length_m = Column(Float, nullable=False)
    kerf_m = Column(Float, nullable=False, default=0)
    remainder_m = Column(Float, nullable=False)
    scrap_length_m = Column(Float, nullable=False, default=0)
    operator = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class MaterialScrap(Base):
    __tablename__ = "material_scrap"
    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False, index=True)
    source_piece_id = Column(Integer, ForeignKey("material_stock_pieces.id"), nullable=False, index=True)
    cut_operation_id = Column(Integer, ForeignKey("material_cut_operations.id"), nullable=True, index=True)
    scrap_length_m = Column(Float, nullable=False)
    theoretical_weight_kg = Column(Float, nullable=True)
    reason = Column(String(255), default="")
    operator = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class WarehouseStock(Base):
    """Reusable cut-detail stock; separate from raw materials and finished goods."""
    __tablename__ = "warehouse_stock"
    id = Column(Integer, primary_key=True)
    detail_id = Column(Integer, ForeignKey("mes_product_parts.id"), nullable=False, index=True)
    detail_code = Column(String(100), nullable=False, index=True)
    detail_name = Column(String(255), nullable=False)
    dimensions = Column(String(255), default="")
    material = Column(String(255), default="")
    thickness = Column(String(64), default="")
    quantity = Column(Float, nullable=False, default=0)
    reserved_quantity = Column(Float, nullable=False, default=0)
    unit = Column(String(32), default="dona")
    source_order_id = Column(Integer, ForeignKey("mes_production_jobs.id"), nullable=True, index=True)
    source_cutting_id = Column(Integer, ForeignKey("mes_job_bom_lines.id"), nullable=True, index=True)
    status = Column(String(16), default="READY", index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class WarehouseTransaction(Base):
    __tablename__ = "warehouse_transactions"
    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("warehouse_stock.id"), nullable=False, index=True)
    detail_id = Column(Integer, ForeignKey("mes_product_parts.id"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    operation = Column(String(16), nullable=False, index=True)
    reason = Column(String(255), default="")
    order_id = Column(Integer, ForeignKey("mes_production_jobs.id"), nullable=True, index=True)
    operator = Column(String(100), default="")
    quantity_before = Column(Float, default=0)
    quantity_after = Column(Float, default=0)
    created_at = Column(DateTime, default=utcnow)


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



class FinanceAccount(Base):
    __tablename__ = "finance_accounts"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(40), nullable=False, unique=True, index=True)
    name_uz = Column(String(160), nullable=False)
    name_ru = Column(String(160), nullable=False)
    account_type = Column(String(24), nullable=False, index=True)
    currency_code = Column(String(8), nullable=False, default="UZS")
    opening_balance = Column(Numeric(18, 2), nullable=False, default=0)
    current_balance = Column(Numeric(18, 2), nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class FinanceCategory(Base):
    __tablename__ = "finance_categories"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), nullable=False, unique=True, index=True)
    name_uz = Column(String(160), nullable=False)
    name_ru = Column(String(160), nullable=False)
    category_type = Column(String(24), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("finance_categories.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class FinanceCounterparty(Base):
    __tablename__ = "finance_counterparties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    counterparty_type = Column(String(24), nullable=False, default="other")
    tax_id = Column(String(64), default="")
    phone = Column(String(64), default="")
    email = Column(String(160), default="")
    address = Column(Text, default="")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class FinanceTransaction(Base):
    __tablename__ = "finance_transactions"

    id = Column(Integer, primary_key=True, index=True)
    document_no = Column(String(64), nullable=False, unique=True, index=True)
    transaction_type = Column(String(24), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("finance_accounts.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("finance_categories.id"), nullable=True)
    counterparty_id = Column(Integer, ForeignKey("finance_counterparties.id"), nullable=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency_code = Column(String(8), nullable=False, default="UZS")
    exchange_rate = Column(Numeric(18, 6), nullable=False, default=1)
    amount_uzs = Column(Numeric(18, 2), nullable=False, default=0)
    description = Column(Text, default="")
    project_id = Column(Integer, nullable=True, index=True)
    status = Column(String(24), nullable=False, default="posted")
    transaction_date = Column(DateTime, nullable=False)
    created_by = Column(String(100), default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class FinanceTransfer(Base):
    __tablename__ = "finance_transfers"

    id = Column(Integer, primary_key=True, index=True)
    document_no = Column(String(64), nullable=False, unique=True, index=True)
    from_account_id = Column(Integer, ForeignKey("finance_accounts.id"), nullable=False)
    to_account_id = Column(Integer, ForeignKey("finance_accounts.id"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    commission_amount = Column(Numeric(18, 2), nullable=False, default=0)
    description = Column(Text, default="")
    transfer_date = Column(DateTime, nullable=False)
    created_by = Column(String(100), default="")
    created_at = Column(DateTime, default=utcnow)


class FinanceObligation(Base):
    __tablename__ = "finance_obligations"

    id = Column(Integer, primary_key=True, index=True)
    obligation_type = Column(String(16), nullable=False, index=True)
    counterparty_id = Column(Integer, ForeignKey("finance_counterparties.id"), nullable=False)
    project_id = Column(Integer, nullable=True)
    document_no = Column(String(64), default="")
    original_amount = Column(Numeric(18, 2), nullable=False)
    paid_amount = Column(Numeric(18, 2), nullable=False, default=0)
    currency_code = Column(String(8), nullable=False, default="UZS")
    due_date = Column(DateTime, nullable=True)
    status = Column(String(24), nullable=False, default="open")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class FinanceObligationPayment(Base):
    __tablename__ = "finance_obligation_payments"

    id = Column(Integer, primary_key=True, index=True)
    obligation_id = Column(
        Integer,
        ForeignKey("finance_obligations.id"),
        nullable=False,
        index=True,
    )
    account_id = Column(
        Integer,
        ForeignKey("finance_accounts.id"),
        nullable=True,
    )
    transaction_id = Column(
        Integer,
        ForeignKey("finance_transactions.id"),
        nullable=True,
    )
    amount = Column(Numeric(18, 2), nullable=False)
    currency_code = Column(String(8), nullable=False, default="UZS")
    payment_date = Column(DateTime, nullable=False, default=utcnow)
    payment_method = Column(String(32), default="")
    document_no = Column(String(64), default="")
    description = Column(Text, default="")
    created_by = Column(String(100), default="")
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


# --- Multi-product production projects ---


class ProductionProject(Base):
    __tablename__ = "production_projects"

    id = Column(Integer, primary_key=True, index=True)
    project_code = Column(String(100), nullable=False, unique=True, index=True)
    project_name = Column(String(255), nullable=False)
    customer_id = Column(Integer, nullable=True, index=True)
    customer_name_snapshot = Column(String(255), nullable=False)
    destination_region = Column(String(160), default="")
    destination_city = Column(String(160), default="", index=True)
    site_name = Column(String(255), default="")
    full_address = Column(Text, default="")
    contact_person = Column(String(160), default="")
    contact_phone = Column(String(64), default="")
    planned_start_date = Column(DateTime, nullable=True)
    required_delivery_date = Column(DateTime, nullable=True, index=True)
    priority = Column(String(24), default="normal", nullable=False, index=True)
    notes = Column(Text, default="")
    status = Column(String(32), default="draft", nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    release_revision = Column(Integer, default=0, nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    released_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    lines = relationship("ProductionProjectLine", back_populates="project", cascade="all, delete-orphan")
    releases = relationship("ProjectReleaseSnapshot", back_populates="project")


class ProductionProjectLine(Base):
    __tablename__ = "production_project_lines"
    __table_args__ = (
        UniqueConstraint("project_id", "product_id", name="uq_project_product_line"),
        CheckConstraint("quantity > 0", name="ck_project_line_quantity_positive"),
        CheckConstraint("produced_quantity >= 0 AND produced_quantity <= quantity", name="ck_project_line_produced"),
        CheckConstraint("quality_approved_quantity >= 0 AND quality_approved_quantity <= quantity", name="ck_project_line_quality"),
        CheckConstraint("packaged_quantity >= 0 AND packaged_quantity <= quantity", name="ck_project_line_packaged"),
        CheckConstraint("shipped_quantity >= 0 AND shipped_quantity <= quantity", name="ck_project_line_shipped"),
        CheckConstraint("delivered_quantity >= 0 AND delivered_quantity <= quantity", name="ck_project_line_delivered"),
        CheckConstraint("accepted_quantity >= 0 AND accepted_quantity <= quantity", name="ck_project_line_accepted"),
        CheckConstraint("damaged_quantity >= 0 AND missing_quantity >= 0", name="ck_project_line_delivery_exceptions"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("mes_product_templates.id"), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    line_reference = Column(String(100), default="")
    priority = Column(String(24), default="normal", nullable=False)
    required_date_override = Column(DateTime, nullable=True)
    notes = Column(Text, default="")
    bom_revision = Column(String(64), default="")
    produced_quantity = Column(Float, default=0.0, nullable=False)
    quality_approved_quantity = Column(Float, default=0.0, nullable=False)
    packaged_quantity = Column(Float, default=0.0, nullable=False)
    shipped_quantity = Column(Float, default=0.0, nullable=False)
    delivered_quantity = Column(Float, default=0.0, nullable=False)
    accepted_quantity = Column(Float, default=0.0, nullable=False)
    damaged_quantity = Column(Float, default=0.0, nullable=False)
    missing_quantity = Column(Float, default=0.0, nullable=False)
    status = Column(String(32), default="draft", nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    project = relationship("ProductionProject", back_populates="lines")
    product = relationship("MesProductTemplate")


class ProjectReleaseSnapshot(Base):
    __tablename__ = "project_release_snapshots"
    __table_args__ = (
        UniqueConstraint("project_id", "revision", name="uq_project_release_revision"),
        UniqueConstraint("idempotency_key", name="uq_project_release_idempotency"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    source_project_version = Column(Integer, nullable=False)
    idempotency_key = Column(String(160), nullable=False, index=True)
    checksum = Column(String(64), nullable=False)
    status = Column(String(32), default="released", nullable=False)
    released_by = Column(String(100), nullable=False)
    released_at = Column(DateTime, default=utcnow, nullable=False)

    project = relationship("ProductionProject", back_populates="releases")
    line_bom_snapshots = relationship("ProjectLineBomSnapshot", back_populates="release", cascade="all, delete-orphan")
    detail_requirements = relationship("ProjectDetailRequirement", back_populates="release", cascade="all, delete-orphan")


class ProjectLineBomSnapshot(Base):
    __tablename__ = "project_line_bom_snapshots"
    __table_args__ = (CheckConstraint("source_quantity > 0 AND gross_quantity > 0", name="ck_project_bom_positive"),)

    id = Column(Integer, primary_key=True, index=True)
    release_id = Column(Integer, ForeignKey("project_release_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("mes_product_templates.id"), nullable=False, index=True)
    source_bom_line_id = Column(Integer, ForeignKey("mes_bom_lines.id"), nullable=False, index=True)
    detail_id = Column(Integer, ForeignKey("mes_product_parts.id"), nullable=False, index=True)
    product_code = Column(String(100), nullable=False)
    product_name = Column(String(255), nullable=False)
    detail_code = Column(String(100), nullable=False)
    detail_name = Column(String(255), nullable=False)
    unit = Column(String(32), nullable=False)
    source_quantity = Column(Float, nullable=False)
    product_quantity = Column(Float, nullable=False)
    gross_quantity = Column(Float, nullable=False)
    bom_revision = Column(String(64), default="")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    release = relationship("ProjectReleaseSnapshot", back_populates="line_bom_snapshots")


class ProjectDetailRequirement(Base):
    __tablename__ = "project_detail_requirements"
    __table_args__ = (
        UniqueConstraint("release_id", "detail_id", name="uq_project_release_detail"),
        CheckConstraint("gross_required_quantity > 0", name="ck_project_requirement_positive"),
        CheckConstraint("stock_reserved_quantity >= 0 AND production_required_quantity >= 0", name="ck_project_requirement_nonnegative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    release_id = Column(Integer, ForeignKey("project_release_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    detail_id = Column(Integer, ForeignKey("mes_product_parts.id"), nullable=False, index=True)
    detail_code = Column(String(100), nullable=False)
    detail_name = Column(String(255), nullable=False)
    unit = Column(String(32), nullable=False)
    gross_required_quantity = Column(Float, nullable=False)
    stock_reserved_quantity = Column(Float, default=0.0, nullable=False)
    production_required_quantity = Column(Float, default=0.0, nullable=False)
    consumed_quantity = Column(Float, default=0.0, nullable=False)
    released_quantity = Column(Float, default=0.0, nullable=False)
    status = Column(String(32), default="production_required", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    release = relationship("ProjectReleaseSnapshot", back_populates="detail_requirements")
    allocations = relationship("ProjectStockAllocation", back_populates="requirement", cascade="all, delete-orphan")


class ProjectStockAllocation(Base):
    __tablename__ = "project_stock_allocations"
    __table_args__ = (
        CheckConstraint("reserved_quantity > 0", name="ck_project_allocation_positive"),
        CheckConstraint("consumed_quantity >= 0 AND released_quantity >= 0", name="ck_project_allocation_nonnegative"),
        CheckConstraint("consumed_quantity + released_quantity <= reserved_quantity", name="ck_project_allocation_balance"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=False, index=True)
    release_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey("project_detail_requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("warehouse_stock.id"), nullable=False, index=True)
    reserve_transaction_id = Column(Integer, ForeignKey("warehouse_transactions.id"), nullable=False, unique=True)
    consuming_job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), nullable=True, index=True)
    consuming_job_line_id = Column(Integer, ForeignKey("mes_job_bom_lines.id"), nullable=True, index=True)
    reserved_quantity = Column(Float, nullable=False)
    consumed_quantity = Column(Float, default=0.0, nullable=False)
    released_quantity = Column(Float, default=0.0, nullable=False)
    status = Column(String(32), default="reserved", nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    requirement = relationship("ProjectDetailRequirement", back_populates="allocations")


class ProjectProductionOperation(Base):
    __tablename__ = "project_production_operations"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_project_operation_idempotency"),
        UniqueConstraint("source_record_type", "source_record_id", "operation_type", "source_version", name="uq_project_operation_source"),
        CheckConstraint("quantity > 0", name="ck_project_operation_quantity_positive"),
        CheckConstraint("accepted_quantity >= 0 AND rejected_quantity >= 0 AND rework_quantity >= 0", name="ck_project_operation_results_nonnegative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=False, index=True)
    release_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=False, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), nullable=False, index=True)
    job_line_id = Column(Integer, ForeignKey("mes_job_bom_lines.id"), nullable=True, index=True)
    route_step_id = Column(Integer, ForeignKey("mes_job_route_steps.id"), nullable=True, index=True)
    stage_id = Column(Integer, ForeignKey("mes_production_stages.id"), nullable=True, index=True)
    operation_type = Column(String(40), nullable=False, index=True)
    result = Column(String(32), default="completed", nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    accepted_quantity = Column(Float, default=0.0, nullable=False)
    rejected_quantity = Column(Float, default=0.0, nullable=False)
    rework_quantity = Column(Float, default=0.0, nullable=False)
    operator = Column(String(100), nullable=False, index=True)
    terminal = Column(String(80), default="")
    source_record_type = Column(String(80), nullable=False)
    source_record_id = Column(Integer, nullable=False)
    source_version = Column(String(100), nullable=False)
    idempotency_key = Column(String(180), nullable=False, index=True)
    occurred_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    notes = Column(Text, default="")
    # Nullable correction metadata keeps backward/reopen evidence in the
    # existing append-only project operation ledger.  Normal stage operations
    # remain unchanged and historical completion rows are never deleted.
    source_stage = Column(String(40), nullable=True, index=True)
    destination_stage = Column(String(40), nullable=True, index=True)
    reason_code = Column(String(64), nullable=True)
    comment = Column(Text, default="")
    original_completed_at = Column(DateTime, nullable=True)
    reopened_at = Column(DateTime, nullable=True)
    reopened_by = Column(String(100), nullable=True)
    brigade_id = Column(
        Integer,
        ForeignKey("mes_terminal_brigades.id"),
        nullable=True,
        index=True,
    )

    brigade = relationship("MesTerminalBrigade", foreign_keys=[brigade_id])
    participants = relationship(
        "ProjectProductionOperationParticipant",
        back_populates="operation",
        cascade="all, delete-orphan",
    )


class MesTerminalBrigade(Base):
    __tablename__ = "mes_terminal_brigades"

    id = Column(Integer, primary_key=True, index=True)
    stage_id = Column(
        Integer,
        ForeignKey("mes_production_stages.id"),
        nullable=True,
        index=True,
    )
    name = Column(String(120), nullable=False)
    brigadier_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(100), default="", nullable=False)
    updated_by = Column(String(100), default="", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Legacy stage_id is kept only for backward compatibility.
    # The source of truth for terminal assignment is assignments.
    stage = relationship("MesProductionStage")
    brigadier = relationship("User", foreign_keys=[brigadier_user_id])
    assignments = relationship(
        "MesTerminalBrigadeAssignment",
        back_populates="brigade",
        cascade="all, delete-orphan",
    )
    members = relationship(
        "MesTerminalBrigadeMember",
        back_populates="brigade",
        cascade="all, delete-orphan",
    )


class MesTerminalBrigadeAssignment(Base):
    __tablename__ = "mes_terminal_brigade_assignments"
    __table_args__ = (
        UniqueConstraint(
            "brigade_id",
            "stage_id",
            name="uq_mes_terminal_brigade_assignment",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    brigade_id = Column(
        Integer,
        ForeignKey("mes_terminal_brigades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage_id = Column(
        Integer,
        ForeignKey("mes_production_stages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(String(100), default="", nullable=False)
    updated_by = Column(String(100), default="", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    brigade = relationship("MesTerminalBrigade", back_populates="assignments")
    stage = relationship("MesProductionStage", foreign_keys=[stage_id])


class MesTerminalBrigadeMember(Base):
    __tablename__ = "mes_terminal_brigade_members"
    __table_args__ = (
        UniqueConstraint(
            "brigade_id",
            "user_id",
            name="uq_mes_terminal_brigade_member",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    brigade_id = Column(
        Integer,
        ForeignKey("mes_terminal_brigades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    brigade = relationship("MesTerminalBrigade", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])


class ProjectProductionOperationParticipant(Base):
    __tablename__ = "project_production_operation_participants"
    __table_args__ = (
        UniqueConstraint(
            "operation_id",
            "user_id",
            "participation_role",
            name="uq_operation_participant_user_role",
        ),
        CheckConstraint(
            "participation_role IN ('brigadier', 'worker')",
            name="ck_operation_participant_role",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(
        Integer,
        ForeignKey(
            "project_production_operations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    participation_role = Column(String(20), nullable=False)
    full_name_snapshot = Column(String(160), default="", nullable=False)
    employee_id_snapshot = Column(String(80), default="", nullable=False)
    position_snapshot = Column(String(120), default="", nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    operation = relationship(
        "ProjectProductionOperation",
        back_populates="participants",
    )
    user = relationship("User", foreign_keys=[user_id])


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
    yigish_lines = relationship(
        "MesYigishLine", back_populates="template", cascade="all, delete-orphan"
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


class MesYigishLine(Base):
    __tablename__ = "mes_yigish_lines"
    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "part_id",
            name="uq_mes_yigish_template_part",
        ),
        UniqueConstraint(
            "template_id",
            "material_id",
            name="uq_mes_yigish_template_material",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(
        Integer,
        ForeignKey("mes_product_templates.id"),
        index=True,
        nullable=False,
    )
    part_id = Column(
        Integer,
        ForeignKey("mes_product_parts.id"),
        index=True,
        nullable=True,
    )
    material_id = Column(
        Integer,
        ForeignKey("materials.id"),
        index=True,
        nullable=True,
    )
    required_quantity = Column(Float, default=1.0, nullable=False)
    unit = Column(String, nullable=True)
    notes = Column(Text, default="")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    template = relationship(
        "MesProductTemplate",
        back_populates="yigish_lines",
    )
    part = relationship("MesProductPart")
    material = relationship("Material")


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
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=True, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=True, index=True)
    project_release_snapshot_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=True, index=True)

    template = relationship("MesProductTemplate")
    route = relationship("MesProductionRoute")
    bom_lines = relationship(
        "MesJobBomLine", back_populates="job", cascade="all, delete-orphan"
    )
    yigish_lines = relationship(
        "MesJobYigishLine",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="MesJobYigishLine.sort_order",
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
    project = relationship("ProductionProject", foreign_keys=[project_id])
    project_line = relationship("ProductionProjectLine", foreign_keys=[project_line_id])
    project_release_snapshot = relationship("ProjectReleaseSnapshot", foreign_keys=[project_release_snapshot_id])


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
    stock_reserved_quantity = Column(Float, default=0.0, nullable=False)
    production_required_quantity = Column(Float, default=0.0, nullable=False)
    surplus_stocked_quantity = Column(Float, default=0.0, nullable=False)
    completed_quantity = Column(Float, default=0.0)
    painted_quantity = Column(Float, default=0.0)
    paint_accepted_quantity = Column(Float, default=0.0, nullable=False)
    paint_rejected_quantity = Column(Float, default=0.0, nullable=False)
    accepted_quantity = Column(Float, default=0.0)
    rejected_quantity = Column(Float, default=0.0)
    rework_quantity = Column(Float, default=0.0)
    qc_accepted_quantity = Column(Float, default=0.0, nullable=False)
    qc_rejected_quantity = Column(Float, default=0.0, nullable=False)
    qc_rework_quantity = Column(Float, default=0.0, nullable=False)
    notes = Column(Text, default="")
    drawing_url = Column(String, nullable=True)
    sort_order = Column(Integer, default=0)
    project_line_bom_snapshot_id = Column(Integer, ForeignKey("project_line_bom_snapshots.id"), nullable=True, index=True)

    job = relationship("MesProductionJob", back_populates="bom_lines")
    part = relationship("MesProductPart")


class MesJobYigishLine(Base):
    __tablename__ = "mes_job_yigish_lines"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(
        Integer,
        ForeignKey("mes_production_jobs.id"),
        index=True,
        nullable=False,
    )
    source_yigish_line_id = Column(
        Integer,
        ForeignKey("mes_yigish_lines.id"),
        nullable=True,
        index=True,
    )
    part_id = Column(
        Integer,
        ForeignKey("mes_product_parts.id"),
        index=True,
        nullable=True,
    )
    material_id = Column(
        Integer,
        ForeignKey("materials.id"),
        index=True,
        nullable=True,
    )
    part_number = Column(String, nullable=False)
    part_name = Column(String, nullable=False)
    unit = Column(String, default="dona")
    allocated_quantity = Column(Float, default=0.0, nullable=False)
    completed_quantity = Column(Float, default=0.0, nullable=False)
    accepted_quantity = Column(Float, default=0.0, nullable=False)
    rejected_quantity = Column(Float, default=0.0, nullable=False)
    notes = Column(Text, default="")
    sort_order = Column(Integer, default=0)

    job = relationship("MesProductionJob", back_populates="yigish_lines")
    part = relationship("MesProductPart")
    material = relationship("Material")
    source_yigish_line = relationship("MesYigishLine")


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

    brigade_id = Column(
        Integer,
        ForeignKey("mes_terminal_brigades.id"),
        nullable=True,
        index=True,
    )
    accepted_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    job = relationship("MesProductionJob", back_populates="route_steps")
    brigade = relationship(
        "MesTerminalBrigade",
        foreign_keys=[brigade_id],
    )
    accepted_by_user = relationship(
        "User",
        foreign_keys=[accepted_by_user_id],
    )
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
    quantity = Column(Float, default=1.0, nullable=False)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=True, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=True, index=True)
    project_release_snapshot_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=True, index=True)
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
    product_passports = relationship("ProductPassport", back_populates="package")


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


class ProductPassportSequence(Base):
    """Transactional serial allocator for finished-product passports."""

    __tablename__ = "product_passport_sequences"

    year = Column(Integer, primary_key=True)
    next_value = Column(Integer, nullable=False, default=1)


class ProductPassport(Base):
    """One traceable physical finished-product unit.

    Packaging, jobs, projects and shipments remain authoritative; this table is
    only the unit identity/QR index linking a physical unit to those ledgers.
    """

    __tablename__ = "product_passports"
    __table_args__ = (
        UniqueConstraint("package_id", "unit_index", name="uq_product_passport_package_unit"),
        CheckConstraint("unit_index > 0", name="ck_product_passport_unit_index_positive"),
        CheckConstraint("unit_quantity > 0", name="ck_product_passport_unit_quantity_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String(40), unique=True, nullable=False, index=True)
    qr_token = Column(String(80), unique=True, nullable=False, index=True)
    qr_data = Column(Text, default="", nullable=False)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("mes_production_jobs.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=True, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=True, index=True)
    template_id = Column(Integer, ForeignKey("mes_product_templates.id"), nullable=False, index=True)
    unit_index = Column(Integer, nullable=False)
    unit_quantity = Column(Float, nullable=False, default=1.0)
    status = Column(String(32), nullable=False, default="finished", index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    finalized_at = Column(DateTime, nullable=True)
    created_by = Column(String(100), nullable=False)

    package = relationship("MesJobPackage", back_populates="product_passports")
    job = relationship("MesProductionJob")
    project = relationship("ProductionProject")
    project_line = relationship("ProductionProjectLine")
    template = relationship("MesProductTemplate")


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
    segment_code = Column(String(64), default="", nullable=False)
    location_type = Column(String(24), default="bin", nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("mes_warehouse_locations.id"), nullable=True, index=True)
    description = Column(String, default="")
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_by = Column(String, nullable=False)

    parent = relationship("MesWarehouseLocation", remote_side=[id], backref="children")

    __table_args__ = (
        UniqueConstraint("parent_id", "segment_code", name="uq_mes_warehouse_location_parent_segment"),
        CheckConstraint("version > 0", name="ck_mes_warehouse_location_version_positive"),
    )


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

    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=True, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=True, index=True)
    project_release_snapshot_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=True, index=True)

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


class MesFinishedGoodsPlacement(Base):
    """Current placement claim; history remains append-only in inventory movements."""

    __tablename__ = "mes_finished_goods_placements"
    __table_args__ = (
        UniqueConstraint("inventory_id", name="uq_finished_goods_placement_inventory"),
        UniqueConstraint("package_id", name="uq_finished_goods_placement_package"),
        CheckConstraint("quantity > 0", name="ck_finished_goods_placement_quantity_positive"),
        CheckConstraint("version > 0", name="ck_finished_goods_placement_version_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(Integer, ForeignKey("mes_finished_goods_inventory.id"), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("mes_warehouse_locations.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=True, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=True, index=True)
    template_id = Column(Integer, ForeignKey("mes_product_templates.id"), nullable=False, index=True)
    release_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=True, index=True)
    quantity = Column(Float, nullable=False)
    status = Column(String(32), default="placed", nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    placed_by = Column(String(100), nullable=False)
    placed_at = Column(DateTime, default=utcnow, nullable=False)
    updated_by = Column(String(100), nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    inventory = relationship("MesFinishedGoodsInventory")
    package = relationship("MesJobPackage")
    location = relationship("MesWarehouseLocation")


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
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=True, index=True)
    destination_city = Column(String(160), default="")
    site_name = Column(String(255), default="")
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=True, index=True)

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


class MesVehicle(Base):
    __tablename__ = "mes_vehicles"
    __table_args__ = (
        CheckConstraint("max_payload_kg > 0", name="ck_mes_vehicle_payload_positive"),
        CheckConstraint("internal_length_mm > 0 AND internal_width_mm > 0 AND internal_height_mm > 0", name="ck_mes_vehicle_dimensions_positive"),
        CheckConstraint("max_volume_m3 IS NULL OR max_volume_m3 > 0", name="ck_mes_vehicle_volume_positive"),
        CheckConstraint("version > 0", name="ck_mes_vehicle_version_positive"),
        CheckConstraint("operational_state IN ('AVAILABLE', 'SERVICE', 'INACTIVE')", name="ck_mes_vehicle_operational_state"),
    )

    id = Column(Integer, primary_key=True, index=True)
    vehicle_type = Column(String(64), nullable=False)
    registration_number = Column(String(32), unique=True, nullable=False, index=True)
    internal_code = Column(String(64), default="", nullable=False)
    model = Column(String(120), default="", nullable=False)
    driver_name = Column(String(160), default="")
    driver_phone = Column(String(64), default="")
    max_payload_kg = Column(Float, nullable=False)
    internal_length_mm = Column(Float, nullable=False)
    internal_width_mm = Column(Float, nullable=False)
    internal_height_mm = Column(Float, nullable=False)
    max_volume_m3 = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    operational_state = Column(String(16), default="AVAILABLE", nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    notes = Column(Text, default="", nullable=False)
    created_by = Column(String(100), nullable=False)
    updated_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class MesGpsDevice(Base):
    """Canonical physical GPS identity bound to one MesVehicle.

    Device identity is intentionally separate from tracking sessions: a
    reconnect keeps the same binding while each trip/session remains an
    append-only operational record.
    """

    __tablename__ = "mes_gps_devices"
    __table_args__ = (
        UniqueConstraint("device_identifier", name="uq_mes_gps_device_identifier"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_mes_gps_device_status"),
        CheckConstraint("protocol IN ('custom_http', 'teltonika_avl', 'sinotrack_h02')", name="ck_mes_gps_device_protocol"),
        CheckConstraint("version > 0", name="ck_mes_gps_device_version_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    device_identifier = Column(String(180), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("mes_vehicles.id"), nullable=False, index=True)
    driver_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    status = Column(String(16), default="active", nullable=False, index=True)
    protocol = Column(String(32), default="custom_http", nullable=False, index=True)
    last_latitude = Column(Float, nullable=True)
    last_longitude = Column(Float, nullable=True)
    last_speed_kmh = Column(Float, nullable=True)
    last_heading_deg = Column(Float, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_captured_at = Column(DateTime, nullable=True, index=True)
    notes = Column(Text, default="", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_by = Column(String(100), nullable=False)
    updated_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    vehicle = relationship("MesVehicle")
    driver_user = relationship("User", foreign_keys=[driver_user_id])


class MesTrip(Base):
    __tablename__ = "mes_trips"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_mes_trip_version_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_number = Column(String(80), unique=True, nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("mes_vehicles.id"), nullable=True, index=True)
    driver_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=False, index=True)
    release_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=False, index=True)
    driver_name_snapshot = Column(String(160), default="")
    driver_phone_snapshot = Column(String(64), default="")
    destination_city = Column(String(160), nullable=False)
    destination_site = Column(String(255), nullable=False)
    destination_address = Column(String(500), nullable=False)
    planned_loading_at = Column(DateTime, nullable=True)
    planned_departure_at = Column(DateTime, nullable=True)
    delivery_deadline_at = Column(DateTime, nullable=True)
    actual_departure_at = Column(DateTime, nullable=True)
    arrived_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="draft", nullable=False, index=True)
    notes = Column(Text, default="")
    evidence_policy = Column(String(24), default="required", nullable=False)
    completeness_required = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_by = Column(String(100), nullable=False)
    updated_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    vehicle = relationship("MesVehicle")
    driver_user = relationship("User", foreign_keys=[driver_user_id])
    project = relationship("ProductionProject")
    release = relationship("ProjectReleaseSnapshot")
    dispatches = relationship("MesDispatch", foreign_keys="MesDispatch.trip_id")


class MesTripRoute(Base):
    """Canonical planned route owned by an existing logistics trip."""
    __tablename__ = "mes_trip_routes"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'active', 'completed', 'cancelled')", name="ck_mes_trip_route_status"),
        CheckConstraint("version > 0", name="ck_mes_trip_route_version_positive"),
    )
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    status = Column(String(16), default="draft", nullable=False, index=True)
    origin_name = Column(String(255), nullable=False)
    origin_lat = Column(Float, nullable=False)
    origin_lon = Column(Float, nullable=False)
    destination_name = Column(String(255), nullable=False)
    destination_lat = Column(Float, nullable=False)
    destination_lon = Column(Float, nullable=False)
    planned_distance_m = Column(Float, nullable=True)
    planned_duration_s = Column(Integer, nullable=True)
    provider = Column(String(64), default="manual_straight_line", nullable=False)
    geometry_json = Column(JSON, default=list, nullable=False)
    created_by = Column(String(100), nullable=False)
    updated_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    trip = relationship("MesTrip", backref="routes")


class MesTripRouteStop(Base):
    __tablename__ = "mes_trip_route_stops"
    __table_args__ = (
        UniqueConstraint("route_id", "sequence", name="uq_mes_trip_route_stop_sequence"),
        CheckConstraint("sequence > 0", name="ck_mes_trip_route_stop_sequence_positive"),
    )
    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("mes_trip_routes.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    stop_type = Column(String(32), default="waypoint", nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(500), default="", nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    planned_arrival_at = Column(DateTime, nullable=True)
    notes = Column(Text, default="", nullable=False)
    route = relationship("MesTripRoute", backref="stops")


class MesShipmentItem(Base):
    __tablename__ = "mes_shipment_items"
    __table_args__ = (
        UniqueConstraint("trip_id", "placement_id", name="uq_mes_shipment_trip_placement"),
        UniqueConstraint("trip_id", "package_id", name="uq_mes_shipment_trip_package"),
        CheckConstraint("planned_quantity > 0", name="ck_mes_shipment_planned_positive"),
        CheckConstraint("assigned_quantity >= 0 AND assigned_quantity <= planned_quantity", name="ck_mes_shipment_assigned_balance"),
        CheckConstraint("loaded_quantity >= 0 AND loaded_quantity <= assigned_quantity", name="ck_mes_shipment_loaded_balance"),
        CheckConstraint("delivered_quantity >= 0 AND delivered_quantity <= loaded_quantity", name="ck_mes_shipment_delivered_balance"),
        CheckConstraint("accepted_quantity >= 0 AND damaged_quantity >= 0 AND missing_quantity >= 0", name="ck_mes_shipment_delivery_nonnegative"),
        CheckConstraint("ABS(delivered_quantity - accepted_quantity - damaged_quantity - missing_quantity) < 0.0001", name="ck_mes_shipment_delivery_disposition"),
        CheckConstraint("gross_weight_kg IS NULL OR gross_weight_kg > 0", name="ck_mes_shipment_weight_positive"),
        CheckConstraint("(length_mm IS NULL AND width_mm IS NULL AND height_mm IS NULL) OR (length_mm > 0 AND width_mm > 0 AND height_mm > 0)", name="ck_mes_shipment_dimensions_complete"),
        CheckConstraint("version > 0", name="ck_mes_shipment_version_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    dispatch_id = Column(Integer, ForeignKey("mes_dispatches.id"), nullable=True, index=True)
    placement_id = Column(Integer, ForeignKey("mes_finished_goods_placements.id"), nullable=False, index=True)
    inventory_id = Column(Integer, ForeignKey("mes_finished_goods_inventory.id"), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=False, index=True)
    project_line_id = Column(Integer, ForeignKey("production_project_lines.id"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("mes_product_templates.id"), nullable=False, index=True)
    release_id = Column(Integer, ForeignKey("project_release_snapshots.id"), nullable=False, index=True)
    planned_quantity = Column(Float, nullable=False)
    assigned_quantity = Column(Float, default=0.0, nullable=False)
    loaded_quantity = Column(Float, default=0.0, nullable=False)
    delivered_quantity = Column(Float, default=0.0, nullable=False)
    accepted_quantity = Column(Float, default=0.0, nullable=False)
    damaged_quantity = Column(Float, default=0.0, nullable=False)
    missing_quantity = Column(Float, default=0.0, nullable=False)
    gross_weight_kg = Column(Float, nullable=True)
    length_mm = Column(Float, nullable=True)
    width_mm = Column(Float, nullable=True)
    height_mm = Column(Float, nullable=True)
    shortage_resolved = Column(Boolean, default=False, nullable=False)
    recipient_name = Column(String(160), default="")
    delivery_notes = Column(Text, default="")
    delivered_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    # The row remains as immutable assignment history after a load correction.
    # Quantities describe the current physical claim; correction events explain
    # every transition without deleting the original shipment item.
    assignment_status = Column(String(24), default="active", nullable=False, index=True)
    version = Column(Integer, default=1, nullable=False)
    created_by = Column(String(100), nullable=False)
    updated_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    trip = relationship("MesTrip", backref="shipment_items")
    dispatch = relationship("MesDispatch")
    placement = relationship("MesFinishedGoodsPlacement")
    inventory = relationship("MesFinishedGoodsInventory")
    package = relationship("MesJobPackage")
    project_line = relationship("ProductionProjectLine")
    template = relationship("MesProductTemplate")


class MesLoadCorrection(Base):
    """Append-only audit ledger for pre-dispatch cargo corrections."""

    __tablename__ = "mes_load_corrections"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_mes_load_correction_idempotency"),
        CheckConstraint(
            "action IN ('UNLOADED', 'RETURNED_TO_WAREHOUSE', 'TRANSFERRED', 'REPLACED', 'RELOADED')",
            name="ck_mes_load_correction_action",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    target_trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=True, index=True)
    shipment_item_id = Column(Integer, ForeignKey("mes_shipment_items.id"), nullable=False, index=True)
    target_shipment_item_id = Column(Integer, ForeignKey("mes_shipment_items.id"), nullable=True, index=True)
    package_id = Column(Integer, ForeignKey("mes_job_packages.id"), nullable=False, index=True)
    replacement_package_id = Column(Integer, ForeignKey("mes_job_packages.id"), nullable=True, index=True)
    action = Column(String(40), nullable=False, index=True)
    reason = Column(String(40), nullable=False, index=True)
    notes = Column(Text, default="", nullable=False)
    payload_hash = Column(String(64), nullable=False)
    result_json = Column(JSON, default=dict, nullable=False)
    idempotency_key = Column(String(180), nullable=False, index=True)
    actor = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    trip = relationship("MesTrip", foreign_keys=[trip_id])
    target_trip = relationship("MesTrip", foreign_keys=[target_trip_id])
    shipment_item = relationship("MesShipmentItem", foreign_keys=[shipment_item_id])
    target_shipment_item = relationship("MesShipmentItem", foreign_keys=[target_shipment_item_id])
    package = relationship("MesJobPackage", foreign_keys=[package_id])
    replacement_package = relationship("MesJobPackage", foreign_keys=[replacement_package_id])


class MesTripDocumentSnapshot(Base):
    """Immutable generated trip document version for a specific cargo state."""

    __tablename__ = "mes_trip_document_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "trip_id", "document_type", "scope_project_id", "cargo_hash",
            name="uq_mes_trip_document_cargo_version",
        ),
        CheckConstraint("version > 0", name="ck_mes_trip_document_version_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    document_type = Column(String(40), nullable=False, index=True)
    scope_project_id = Column(Integer, default=0, nullable=False, index=True)
    cargo_hash = Column(String(64), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(120), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)
    storage_relative_path = Column(String(500), nullable=False, unique=True)
    generated_by = Column(String(100), nullable=False)
    generated_at = Column(DateTime, default=utcnow, nullable=False, index=True)

    trip = relationship("MesTrip")


class MesLoadingPlanPlacement(Base):
    __tablename__ = "mes_loading_plan_placements"
    __table_args__ = (
        UniqueConstraint("trip_id", "shipment_item_id", name="uq_mes_loading_plan_trip_item"),
        UniqueConstraint("trip_id", "loading_sequence", name="uq_mes_loading_plan_sequence"),
        CheckConstraint("x_mm >= 0 AND y_mm >= 0", name="ck_mes_loading_plan_coordinates_nonnegative"),
        CheckConstraint("placed_width_mm > 0 AND placed_length_mm > 0", name="ck_mes_loading_plan_dimensions_positive"),
        CheckConstraint("rotation IN (0, 90)", name="ck_mes_loading_plan_rotation"),
        CheckConstraint("loading_sequence > 0", name="ck_mes_loading_plan_sequence_positive"),
        CheckConstraint("version > 0", name="ck_mes_loading_plan_version_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    shipment_item_id = Column(Integer, ForeignKey("mes_shipment_items.id"), nullable=False, index=True)
    x_mm = Column(Float, nullable=False)
    y_mm = Column(Float, nullable=False)
    placed_width_mm = Column(Float, nullable=False)
    placed_length_mm = Column(Float, nullable=False)
    rotation = Column(Integer, default=0, nullable=False)
    loading_sequence = Column(Integer, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_by = Column(String(100), nullable=False)
    updated_by = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    trip = relationship("MesTrip", backref="loading_plan")
    shipment_item = relationship("MesShipmentItem")


class MesTripCommand(Base):
    __tablename__ = "mes_trip_commands"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_mes_trip_command_idempotency"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    command_type = Column(String(40), nullable=False, index=True)
    idempotency_key = Column(String(180), nullable=False, index=True)
    payload_hash = Column(String(64), nullable=False)
    result_json = Column(JSON, default=dict, nullable=False)
    actor = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    trip = relationship("MesTrip")


class MesTripEvidence(Base):
    __tablename__ = "mes_trip_evidence"
    __table_args__ = (
        CheckConstraint("file_size > 0", name="ck_mes_trip_evidence_size_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("production_projects.id"), nullable=False, index=True)
    evidence_type = Column(String(40), nullable=False, index=True)
    actor = Column(String(100), nullable=False)
    occurred_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    note = Column(Text, default="")
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(80), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False, index=True)
    storage_relative_path = Column(String(500), nullable=False, unique=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    trip = relationship("MesTrip", backref="evidence")


class MesTripTrackingSession(Base):
    """A driver-owned GPS session attached to the canonical shipment trip."""

    __tablename__ = "mes_trip_tracking_sessions"
    __table_args__ = (
        UniqueConstraint("client_session_id", name="uq_mes_trip_tracking_client_session"),
        CheckConstraint("status IN ('active', 'stopped', 'revoked')", name="ck_mes_trip_tracking_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("mes_vehicles.id"), nullable=False, index=True)
    driver_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("mes_gps_devices.id"), nullable=True, index=True)
    client_session_id = Column(String(180), nullable=False, index=True)
    status = Column(String(16), default="active", nullable=False, index=True)
    started_at = Column(DateTime, default=utcnow, nullable=False)
    stopped_at = Column(DateTime, nullable=True)
    last_received_at = Column(DateTime, nullable=True, index=True)
    last_contact_at = Column(DateTime, nullable=True, index=True)
    authorization_hash = Column(String(64), nullable=True)
    authorization_expires_at = Column(DateTime, nullable=True, index=True)
    revoked_at = Column(DateTime, nullable=True)
    revoked_by = Column(String(100), nullable=True)
    health_state = Column(String(40), default="active", nullable=False, index=True)
    queued_point_count = Column(Integer, default=0, nullable=False)
    latest_accuracy_m = Column(Float, nullable=True)
    latest_battery_level = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    trip = relationship("MesTrip", backref="tracking_sessions")
    vehicle = relationship("MesVehicle")
    driver_user = relationship("User")
    device = relationship("MesGpsDevice")


class MesTripLocation(Base):
    """Append-only GPS evidence uploaded online or from the offline queue."""

    __tablename__ = "mes_trip_locations"
    __table_args__ = (
        UniqueConstraint("session_id", "client_point_id", name="uq_mes_trip_location_client_point"),
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_mes_trip_location_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_mes_trip_location_longitude"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("mes_trip_tracking_sessions.id"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("mes_trips.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("mes_vehicles.id"), nullable=False, index=True)
    driver_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    client_point_id = Column(String(180), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_m = Column(Float, nullable=True)
    speed_kmh = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    captured_at = Column(DateTime, nullable=False, index=True)
    received_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    was_queued = Column(Boolean, default=False, nullable=False)

    session = relationship("MesTripTrackingSession", backref="locations")


class MesTripLatestLocation(Base):
    __tablename__ = "mes_trip_latest_locations"

    trip_id = Column(Integer, ForeignKey("mes_trips.id"), primary_key=True)
    session_id = Column(Integer, ForeignKey("mes_trip_tracking_sessions.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("mes_vehicles.id"), nullable=False, index=True)
    driver_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("mes_trip_locations.id"), nullable=False, unique=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_m = Column(Float, nullable=True)
    speed_kmh = Column(Float, nullable=True)
    heading_deg = Column(Float, nullable=True)
    battery_level = Column(Float, nullable=True)
    captured_at = Column(DateTime, nullable=False, index=True)
    received_at = Column(DateTime, nullable=False)

    trip = relationship("MesTrip")


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


# --- Phase 12: GPS Fleet Tracking ---


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String, unique=True, index=True, nullable=False)
    model = Column(String, default="")
    status = Column(String, default="active", index=True)
    created_at = Column(DateTime, default=utcnow)

    locations = relationship("GpsLocation", back_populates="vehicle")
    trips = relationship("TripRoute", back_populates="vehicle")


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    phone = Column(String, default="")
    telegram_username = Column(String, default="")
    driver_type = Column(String, default="internal", index=True)  # internal | external
    user_username = Column(String, default="", index=True)
    login_code = Column(String, default="", unique=True, index=True)
    password_hash = Column(String, default="")
    default_vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True, index=True)
    status = Column(String, default="active", index=True)
    created_at = Column(DateTime, default=utcnow)

    default_vehicle = relationship("Vehicle", foreign_keys=[default_vehicle_id])
    locations = relationship("GpsLocation", back_populates="driver")
    trips = relationship("TripRoute", back_populates="driver")
    current_location = relationship(
        "DriverLocation", back_populates="driver", uselist=False, cascade="all, delete-orphan"
    )


class DriverLocation(Base):
    """Haydovchining joriy joylashuvi — bitta qator haydovchi uchun (upsert)."""

    __tablename__ = "driver_locations"

    driver_id = Column(Integer, ForeignKey("drivers.id"), primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, default="active", index=True)
    last_updated = Column(DateTime, default=utcnow, index=True)

    driver = relationship("Driver", back_populates="current_location")


class GpsLocation(Base):
    __tablename__ = "gps_locations"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True, nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), index=True, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float, default=0)
    battery_level = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=utcnow, index=True)

    vehicle = relationship("Vehicle", back_populates="locations")
    driver = relationship("Driver", back_populates="locations")


class GpsVehicleStop(Base):
    """Persistent vehicle stop detected from GPS history."""

    __tablename__ = "gps_vehicle_stops"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, nullable=False, index=True)
    start_at = Column(DateTime, nullable=False, index=True)
    end_at = Column(DateTime, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(Text, default="")
    road = Column(Text, default="")
    house_number = Column(Text, default="")
    city = Column(Text, default="")
    state = Column(Text, default="")
    country = Column(Text, default="")
    point_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, index=True)


class TripRoute(Base):
    __tablename__ = "trip_routes"

    id = Column(Integer, primary_key=True, index=True)
    transport_id = Column(Integer, ForeignKey("transports.id"), nullable=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True, nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"), index=True, nullable=True)
    origin = Column(String, default="")
    destination = Column(String, default="")
    status = Column(String, default="Planned", index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    transport = relationship("Transport")
    vehicle = relationship("Vehicle", back_populates="trips")
    driver = relationship("Driver", back_populates="trips")


class TransportTask(Base):
    """GPS monitoring work assignment — vehicle + driver + route task."""

    __tablename__ = "transport_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True, nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), index=True, nullable=True)
    transport_id = Column(Integer, ForeignKey("transports.id"), index=True, nullable=True)

    # Canonical driver-task linkage
    driver_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    mes_vehicle_id = Column(Integer, ForeignKey("mes_vehicles.id"), index=True, nullable=True)

    origin = Column(String, default="")
    destination = Column(String, default="")

    customer_name = Column(String, default="")
    customer_phone = Column(String, default="")
    cargo_description = Column(Text, default="")
    destination_latitude = Column(Float, nullable=True)
    destination_longitude = Column(Float, nullable=True)
    origin_latitude = Column(Float, nullable=True)
    origin_longitude = Column(Float, nullable=True)

    # Driver task pickup/delivery confirmation GPS
    pickup_latitude = Column(Float, nullable=True)
    pickup_longitude = Column(Float, nullable=True)
    pickup_address = Column(String, default="")

    delivery_latitude = Column(Float, nullable=True)
    delivery_longitude = Column(Float, nullable=True)
    delivery_address = Column(String, default="")

    status = Column(String, default="assigned", index=True)
    tracking_active = Column(Boolean, default=False)

    picked_up_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    completion_photo_url = Column(String, default="")
    completion_note = Column(Text, default="")

    started_at = Column(DateTime, nullable=True)
    created_by = Column(String, default="")
    created_at = Column(DateTime, default=utcnow)

    vehicle = relationship("Vehicle")
    driver = relationship("Driver")
    transport = relationship("Transport")


class TransportTaskEvent(Base):
    """Audit timeline for driver task pickup/delivery events."""

    __tablename__ = "transport_task_events"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(
        Integer,
        ForeignKey("transport_tasks.id"),
        nullable=False,
        index=True,
    )
    event_type = Column(String, nullable=False, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_username = Column(String, default="")

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String, default="")
    photo_url = Column(String, default="")
    note = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow, index=True)

    task = relationship("TransportTask")
    actor_user = relationship("User")


class GpsAlertState(Base):
    geofence_enabled = Column(Integer, default=0)
    geofence_latitude = Column(Float, nullable=True)
    geofence_longitude = Column(Float, nullable=True)
    geofence_radius_m = Column(Float, nullable=True)
    geofence_outside_alert_sent = Column(Integer, default=0)
    geofence_telegram_alert_sent = Column(Integer, default=0)
    """Per-vehicle alert dedup state for Telegram GPS notifications."""

    __tablename__ = "gps_alert_state"

    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), primary_key=True)
    last_city = Column(String, default="")
    last_country = Column(String, default="")
    offline_alert_sent = Column(Integer, default=0)
    destination_alert_sent = Column(Integer, default=0)
    border_alert_sent = Column(Integer, default=0)
    speed_limit_kmh = Column(Float, nullable=True)
    overspeed_alert_sent = Column(Integer, default=0)
    overspeed_telegram_alert_sent = Column(Integer, default=0)
    updated_at = Column(DateTime, nullable=True)


# --- Logistics (finished goods warehouse + loading shipments) ---

FINISHED_PRODUCT_STATUSES = ("Available", "Reserved", "Loaded", "Delivered")
LOADING_SHIPMENT_STATUSES = ("planned", "loading", "in_transit", "delivered", "cancelled")


class LogisticsFinishedProduct(Base):
    __tablename__ = "logistics_finished_products"

    id = Column(Integer, primary_key=True, index=True)
    product_code = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False)
    order_number = Column(String, default="", index=True)
    quantity = Column(Float, default=1)
    warehouse_location = Column(String, default="")
    status = Column(String, default="Available", index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True, nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), index=True, nullable=True)
    barcode = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    vehicle = relationship("Vehicle")
    driver = relationship("Driver")
    shipment_items = relationship("LogisticsLoadingShipmentItem", back_populates="product")


class LogisticsLoadingShipment(Base):
    __tablename__ = "logistics_loading_shipments"

    id = Column(Integer, primary_key=True, index=True)
    shipment_no = Column(String, unique=True, index=True, nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True, nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), index=True, nullable=True)
    transport_id = Column(Integer, ForeignKey("transports.id"), index=True, nullable=True)
    destination = Column(String, default="")
    status = Column(String, default="planned", index=True)
    created_by = Column(String, default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    departed_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    vehicle = relationship("Vehicle")
    driver = relationship("Driver")
    transport = relationship("Transport")
    items = relationship(
        "LogisticsLoadingShipmentItem",
        back_populates="shipment",
        cascade="all, delete-orphan",
    )


class LogisticsLoadingShipmentItem(Base):
    __tablename__ = "logistics_loading_shipment_items"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(
        Integer, ForeignKey("logistics_loading_shipments.id"), index=True, nullable=False
    )
    product_id = Column(
        Integer, ForeignKey("logistics_finished_products.id"), index=True, nullable=False
    )
    qty = Column(Float, default=1)
    loaded_at = Column(DateTime, default=utcnow)
    loaded_by = Column(String, default="")

    shipment = relationship("LogisticsLoadingShipment", back_populates="items")
    product = relationship("LogisticsFinishedProduct", back_populates="shipment_items")


class MesGpsCommandQueue(Base):
    __tablename__ = "mes_gps_command_queue"
    __table_args__ = (
        CheckConstraint(
            "action IN ('BLOCK', 'UNBLOCK')",
            name="ck_mes_gps_command_action",
        ),
        CheckConstraint(
            "status IN ('pending', 'armed', 'ready', 'sent', 'acked', 'failed', 'cancelled')",
            name="ck_mes_gps_command_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("mes_vehicles.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("mes_gps_devices.id"), nullable=False, index=True)

    action = Column(String(16), nullable=False)
    status = Column(String(16), default="pending", nullable=False, index=True)

    requested_by = Column(String(100), nullable=False)
    speed_at_request_kmh = Column(Float, nullable=True)
    requires_stop = Column(Boolean, default=True, nullable=False)

    requested_at = Column(DateTime, default=utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    acked_at = Column(DateTime, nullable=True)

    error_message = Column(Text, default="", nullable=False)

    vehicle = relationship("MesVehicle")
    device = relationship("MesGpsDevice")
