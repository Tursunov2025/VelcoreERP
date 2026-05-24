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
