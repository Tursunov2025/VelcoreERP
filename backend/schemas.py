from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from constants import DEPARTMENTS, PRODUCTION_STAGES


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    username: str
    role: str
    department: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"
    department: str = "Kesish"


class UserPublic(BaseModel):
    id: int
    username: str
    role: str
    department: str

    class Config:
        from_attributes = True


class OrderHistoryResponse(BaseModel):
    id: int
    order_id: int
    stage: str
    operator_username: str
    action: str
    comment: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderImageResponse(BaseModel):
    id: int
    url: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    client: str
    phone: str = ""
    amount: str = "0"
    comment: str = ""
    destination: str = ""
    image_url: Optional[str] = None
    image_urls: Optional[List[str]] = None
    estimated_finish_at: Optional[datetime] = None


class OrderUpdate(BaseModel):
    client: Optional[str] = None
    phone: Optional[str] = None
    amount: Optional[str] = None
    comment: Optional[str] = None
    destination: Optional[str] = None
    estimated_finish_at: Optional[datetime] = None


class OrderResponse(BaseModel):
    id: int
    client: str
    phone: str
    amount: str
    comment: str
    destination: str
    status: str
    operator_id: Optional[int] = None
    image_url: Optional[str] = None
    images: List[OrderImageResponse] = []
    history: List[OrderHistoryResponse] = []
    in_warehouse: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    estimated_finish_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CompleteStageRequest(BaseModel):
    comment: str = ""


class VerifyOrderRequest(BaseModel):
    comment: str = ""


class WarehouseItemResponse(BaseModel):
    id: int
    order_id: int
    client: str
    phone: str
    amount: str
    destination: str
    quantity: int
    stored_at: Optional[datetime] = None
    comment: str

    class Config:
        from_attributes = True


class ShipmentRequest(BaseModel):
    warehouse_item_ids: List[int]
    destination: str = ""
    comment: str = ""


class ShipmentArchiveResponse(BaseModel):
    id: int
    order_id: Optional[int] = None
    client: str
    destination: str
    amount: str
    shipped_at: Optional[datetime] = None
    operator_username: str
    comment: str

    class Config:
        from_attributes = True


class OperatorOnlineResponse(BaseModel):
    username: str
    department: str
    is_online: bool
    last_activity: Optional[datetime] = None
    active_orders_count: int


class MaterialCreate(BaseModel):
    name: str
    unit: str = "dona"
    quantity: float = 0
    min_quantity: float = 5


class MaterialResponse(BaseModel):
    id: int
    name: str
    unit: str
    quantity: float
    min_quantity: float
    low_stock: bool = False

    class Config:
        from_attributes = True


class StockMovementCreate(BaseModel):
    material_id: int
    movement_type: str
    quantity: float
    note: str = ""


class StockMovementResponse(BaseModel):
    id: int
    material_id: int
    movement_type: str
    quantity: float
    note: str
    created_by: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str = "general"


class IncomeCreate(BaseModel):
    title: str
    amount: float
    source: str = "manual"


class FinanceRecord(BaseModel):
    id: int
    title: str
    amount: float
    type: str
    category: str
    created_at: Optional[datetime] = None


class FinanceSummary(BaseModel):
    total_income: float
    total_expenses: float
    net_profit: float


class UserAdminResponse(BaseModel):
    id: int
    username: str
    role: str
    department: str
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminUserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"
    department: str = "Kesish"
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordResetRequest(BaseModel):
    password: str


class AdminOrderUpdate(BaseModel):
    client: Optional[str] = None
    phone: Optional[str] = None
    amount: Optional[str] = None
    comment: Optional[str] = None
    destination: Optional[str] = None
    status: Optional[str] = None
    estimated_finish_at: Optional[datetime] = None


class SystemSettingsUpdate(BaseModel):
    company_phone: Optional[str] = None
    jwt_access_minutes: Optional[str] = None
    jwt_refresh_days: Optional[str] = None
    auto_backup_enabled: Optional[str] = None
    auto_backup_interval_hours: Optional[str] = None


class BrandingSettingsUpdate(BaseModel):
    app_name: Optional[str] = None
    tagline: Optional[str] = None
    logo_main: Optional[str] = None
    logo_login: Optional[str] = None
    logo_sidebar: Optional[str] = None
    favicon: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    color_background: Optional[str] = None
    color_sidebar: Optional[str] = None
    color_button: Optional[str] = None
    color_success: Optional[str] = None
    color_warning: Optional[str] = None
    color_danger: Optional[str] = None
    button_radius: Optional[str] = None
    button_shadow: Optional[str] = None
    button_style: Optional[str] = None
    animations_enabled: Optional[str] = None
    anim_page_transitions: Optional[str] = None
    anim_modals: Optional[str] = None
    anim_loading: Optional[str] = None
    emoji_enabled: Optional[str] = None
    emoji_dashboard: Optional[str] = None
    emoji_production: Optional[str] = None
    emoji_orders: Optional[str] = None
    emoji_warehouse: Optional[str] = None
    emoji_shipping: Optional[str] = None
    emoji_chat: Optional[str] = None
    emoji_tasks: Optional[str] = None
    emoji_operators: Optional[str] = None
    emoji_analytics: Optional[str] = None
    emoji_finance: Optional[str] = None
    emoji_settings: Optional[str] = None
    theme_mode: Optional[str] = None
    language: Optional[str] = None
    clock_format: Optional[str] = None
    clock_timezone: Optional[str] = None


class UserUiPreferencesUpdate(BaseModel):
    ui_language: Optional[str] = None
    ui_theme: Optional[str] = None
    ui_clock_format: Optional[str] = None


class TelegramSettingsUpdate(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_notifications_enabled: Optional[str] = None
    notifications_enabled: Optional[str] = None


class NotificationSettingsUpdate(BaseModel):
    notifications_enabled: Optional[str] = None
    telegram_notifications_enabled: Optional[str] = None
    notify_new_order: Optional[str] = None
    notify_order_completed: Optional[str] = None
    notify_new_task: Optional[str] = None
    notify_task_accepted: Optional[str] = None
    notify_task_completed: Optional[str] = None
    notify_task_overdue: Optional[str] = None
    notify_shipment_dispatched: Optional[str] = None
    notify_warehouse_events: Optional[str] = None
    notify_chat_messages: Optional[str] = None
    notify_llp_important: Optional[str] = None


class PermissionsUpdate(BaseModel):
    permissions: dict[str, bool]


class TelegramVerifyLink(BaseModel):
    code: str
    telegram_id: str
    telegram_username: str = ""


class AdminTelegramLink(BaseModel):
    telegram_id: str
    telegram_username: str = ""


class AuditLogResponse(BaseModel):
    id: int
    username: str
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
