from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.enums import PaymentStatus, PaymentMethod


class PaymentCreate(BaseModel):
    # what the client sends — no amount, service derives it from the order
    order_id: UUID
    method: PaymentMethod


class PaymentCreateInternal(BaseModel):
    # what the service passes to CRUD after looking up the order's final_amount
    order_id: UUID
    amount: Decimal
    method: PaymentMethod


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    amount: float
    status: PaymentStatus
    method: PaymentMethod
    transaction_ref: Optional[str] = None      # set by payment gateway, not client
    failure_reason: Optional[str] = None       # only populated when status is failed
    created_at: datetime
    processed_at: Optional[datetime] = None
