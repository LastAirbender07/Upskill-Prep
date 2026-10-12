from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from app.schemas.enums import AccountStatus


class UserBase(BaseModel):
    full_name: str = Field(description="full name of the user")
    phone_number: Optional[str] = Field(default=None, description="phone number of the user")


class UserCreate(UserBase):
    email: EmailStr = Field(description="email of the user")


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, description="full name of the user")
    phone_number: Optional[str] = Field(default=None, description="phone number of the user")

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    status: AccountStatus
    registration_date: datetime
    last_login: Optional[datetime] = None
    total_spent: Decimal = Field(default=0, description="total lifetime spend")


class OrderSummary(BaseModel):
    order_count: int
    pending_count: int
    last_order_date: Optional[datetime] = None


class UserProfileResponse(BaseModel):
    user: UserResponse
    orders: OrderSummary


class SuspendRequest(BaseModel):
    reason: str
