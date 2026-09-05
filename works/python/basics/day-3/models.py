"""
Pydantic models for the Event Ingestion API.

Improvements over day-2/schema.py:
  1. StrEnum instead of Enum — serializes cleanly as plain strings
  2. Fixed lambda: default_factory takes zero-arg callable (was `lambda t:` — wrong)
  3. UTC-aware datetimes — no more naive datetimes
  4. `metadata` typed as dict[str, Any] instead of bare `dict`
  5. Field constraints — id > 0, user_id > 0
  6. Separate response model — input ≠ output
  7. snake_case function names (Python convention)
  8. No code runs on import — sample data moved to sample_data.py
"""

import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class EventType(StrEnum):
    """
    StrEnum (Python 3.11+) — each member IS a string.
    So EventType.click == "click" is True, and Pydantic serializes it as "click" not "EventType.click".
    
    Compare with day-2's `class TypeEnum(Enum)` where TypeEnum.click != "click".
    """
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
    """
    Input model for POST /events/metadata/
    
    Field constraints:
      - id and user_id must be > 0 (gt=0)
      - type defaults to "click"
      - timestamp defaults to UTC now (not naive!)
      - metadata is dict[str, Any] — explicit about key/value types
    """
    id: int = Field(gt=0, description="Unique id of the event")
    type: EventType = Field(
        description="Type of event, defaults to 'click'",
        default=EventType.click,
    )
    user_id: int = Field(gt=0, description="Unique id of the user")
    timestamp: datetime = Field(
        description="Event timestamp (UTC)",
        # FIX: zero-arg lambda. Day-2 had `lambda t:` which is wrong — default_factory takes no args.
        default_factory=lambda: datetime.now(tz=timezone.utc),
    )
    metadata: dict[str, Any] = Field(
        description="Other relevant metadata (key-value pairs)",
        default_factory=dict,
    )


# --- Response model ---

class EventMetadataResponse(BaseModel):
    """
    Output model — controls what the API actually returns.
    
    Why separate from input?
      - You might not want to expose internal fields
      - You might want to add computed fields (e.g., "created_at")
      - Input validation rules ≠ output shape
    """
    message: str
    event_metadata: EventMetadata


# --- Utility ---

def debug_event(incoming_event: dict[str, Any]) -> None:
    """
    Parse and pretty-print an event dict.
    
    Improvements over day-2's handlePrint:
      - snake_case name (Python convention, not camelCase)
      - Does NOT swallow exceptions — validation errors propagate so you actually see them
      - Fixed double-serialization: uses model_dump_json(indent=4) directly
        Day-2 did json.dumps(model_dump_json()) which double-encodes (string inside string)
    """
    event = EventMetadata(**incoming_event)
    print(f"Event ID: {event.id}")
    print(f"Parsed:   {event.model_dump()}")
    print(f"JSON:\n{event.model_dump_json(indent=4)}")
    print("-" * 50 + "\n")
