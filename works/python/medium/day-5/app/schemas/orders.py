from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.enums import OrderStatus


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    product_id: UUID
    quantity: int
    unit_price: float       # price at time of order — snapshot, not current product price
    subtotal: float


class OrderCreate(BaseModel):
    user_id: UUID
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: OrderStatus
    total_amount: float
    discount_amount: float
    final_amount: float
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    line_items: list[OrderItemResponse] = []
