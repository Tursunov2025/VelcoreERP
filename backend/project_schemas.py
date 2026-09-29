from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    project_code: str = Field(min_length=1, max_length=100)
    project_name: str = Field(min_length=1, max_length=255)
    customer_id: Optional[int] = None
    customer_name_snapshot: str = Field(min_length=1, max_length=255)
    destination_region: str = ""
    destination_city: str = ""
    site_name: str = ""
    full_address: str = ""
    contact_person: str = ""
    contact_phone: str = ""
    planned_start_date: Optional[datetime] = None
    required_delivery_date: Optional[datetime] = None
    priority: str = "normal"
    notes: str = ""


class ProjectUpdate(BaseModel):
    expected_version: int = Field(gt=0)
    project_name: Optional[str] = None
    customer_id: Optional[int] = None
    customer_name_snapshot: Optional[str] = None
    destination_region: Optional[str] = None
    destination_city: Optional[str] = None
    site_name: Optional[str] = None
    full_address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    planned_start_date: Optional[datetime] = None
    required_delivery_date: Optional[datetime] = None
    priority: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ProjectLineCreate(BaseModel):
    product_id: int
    quantity: float = Field(gt=0)
    line_reference: str = ""
    priority: str = "normal"
    required_date_override: Optional[datetime] = None
    notes: str = ""


class ProjectLineUpdate(BaseModel):
    expected_version: int = Field(gt=0)
    quantity: Optional[float] = Field(default=None, gt=0)
    line_reference: Optional[str] = None
    priority: Optional[str] = None
    required_date_override: Optional[datetime] = None
    notes: Optional[str] = None


class ProjectLineMerge(BaseModel):
    product_id: int
    additional_quantity: float = Field(gt=0)
    expected_project_version: int = Field(gt=0)


class ProjectReleaseRequest(BaseModel):
    expected_version: int = Field(gt=0)
    idempotency_key: str = Field(min_length=8, max_length=160)


class ProjectCancelRequest(BaseModel):
    expected_version: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=1000)
