from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from schemas.enums import EventType, AggregateType


# No EventLogCreate — events are written internally by the service layer, never by API clients.
class EventLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: EventType
    aggregate_type: AggregateType   # which entity this event is about: order, payment, etc.
    aggregate_id: UUID              # the ID of that specific entity
    payload: dict                   # full snapshot of what happened — no joins needed to read history
    occurred_at: datetime
