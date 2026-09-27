from uuid import UUID
from datetime import datetime
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
    total_spent: int = Field(default=0, description="total lifetime spend in cents")
