from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


PRODUCTION_STAGES = [
    "Yangi",
    "Kesish",
    "Svarka",
    "Kraska",
    "Upakovka",
    "Tayyor",
]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    username: str
    role: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "operator"


class UserPublic(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    client: str
    phone: str = ""
    amount: str = "0"
    image_url: Optional[str] = None


class OrderUpdate(BaseModel):
    client: Optional[str] = None
    phone: Optional[str] = None
    amount: Optional[str] = None
    status: Optional[str] = None
    image_url: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    client: str
    phone: str
    amount: str
    status: str
    operator_id: Optional[int] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductionLogResponse(BaseModel):
    id: int
    order_id: int
    stage: str
    changed_by: str
    notes: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


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
    source: str = "order"


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
