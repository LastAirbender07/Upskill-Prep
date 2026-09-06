from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Optional
from pydantic import BaseModel, Field

# --- Enums ---


class EventType(StrEnum):
    click = "click"
    add_to_cart = "add_to_cart"
    proceed_to_order = "proceed_to_order"
    checkout = "checkout"
    payment_initiated = "payment_initiated"
    payment_processing = "payment_processing"
    payment_completed = "payment_completed"
    order_successful = "order_successful"
    delivered = "delivered"
    return_item = "return_item"


# --- Request model ---


class EventMetadata(BaseModel):
    event_id: int = Field(gt=0, description="Unique id of the event")
    event_type: EventType = Field(
        description="Type of event, defaults to 'click'",
        default=EventType.click,
    )
    user_id: int = Field(gt=0, description="Unique id of the user")
    created_timestamp: datetime = Field(
        description="Event timestamp (UTC)",
        # FIX: zero-arg lambda. Day-2 had `lambda t:` which is wrong — default_factory takes no args.
        default_factory=lambda: datetime.now(tz=timezone.utc),
    )
    processed_at: Optional[datetime] = None
    source: Optional[str] = None
    metadata: dict[str, Any] = Field(
        description="Other relevant metadata (key-value pairs)",
        default_factory=dict,
    )


# --- Response model ---


class EventMetadataResponse(BaseModel):
    message: str
    event_metadata: EventMetadata
