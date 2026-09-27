from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.enums import OrderStatus


class OrderItemCreate(BaseModel):
    # what the client sends per item in a create order request
    product_id: UUID
    quantity: int = Field(ge=1)


class OrderItemInternal(BaseModel):
    # what the service passes to CRUD after looking up prices and computing subtotals
    # client never sends unit_price or subtotal — service snapshots them from the product
    product_id: UUID
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    product_id: UUID
    quantity: int
    unit_price: float
    subtotal: float


class OrderCreate(BaseModel):
    # what the client sends — no amounts, no prices
    user_id: UUID
    items: list[OrderItemCreate] = Field(min_length=1)
    notes: Optional[str] = None


class OrderCreateInternal(BaseModel):
    # what the service passes to CRUD after validating user, checking stock, computing totals
    # CRUD accepts this — never the raw OrderCreate
    user_id: UUID
    items: list[OrderItemInternal]
    total_amount: Decimal
    discount_amount: Decimal = Decimal("0")
    final_amount: Decimal
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
