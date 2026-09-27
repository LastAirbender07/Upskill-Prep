from uuid import UUID
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.enums import ShipmentCarrier, ShipmentStatus


class ShipmentCreate(BaseModel):
    order_id: UUID
    carrier: ShipmentCarrier
    estimated_delivery_date: date
    shipping_address: str       # snapshot of address at time of shipment — plain string


class ShipmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    carrier: ShipmentCarrier
    status: ShipmentStatus
    tracking_number: Optional[str] = None
    estimated_delivery_date: date
    actual_delivery_date: Optional[date] = None
    shipping_address: str
    created_at: datetime
    updated_at: datetime
