from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.event_logs import EventLog
from app.schemas.event_logs import EventLogResponse
from app.schemas.enums import EventType, AggregateType
from app.core.logger import get_logger

logger = get_logger(__name__)


class EventLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_event(
        self,
        event_type: EventType,
        aggregate_type: AggregateType,
        aggregate_id: UUID,
        payload: dict,
    ) -> EventLogResponse:
        event_orm = EventLog(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
        )
        self.db.add(event_orm)
        self.db.commit()
        self.db.refresh(event_orm)

        logger.info(f"Logged event {event_type} for {aggregate_type} {aggregate_id}")
        return EventLogResponse.model_validate(event_orm)

    def get_by_aggregate(
        self,
        aggregate_type: AggregateType,
        aggregate_id: UUID,
    ) -> list[EventLogResponse]:
        # fetch the full history of events for a specific entity
        # e.g. all events for order X — uses the composite index (aggregate_type, aggregate_id)
        events = (
            self.db.query(EventLog)
            .filter(
                EventLog.aggregate_type == aggregate_type,
                EventLog.aggregate_id == aggregate_id,
            )
            .order_by(EventLog.occurred_at.asc())
            .all()
        )
        return [EventLogResponse.model_validate(e) for e in events]

    def get_by_type(
        self,
        event_type: EventType,
        skip: int = 0,
        limit: int = 100,
    ) -> list[EventLogResponse]:
        events = (
            self.db.query(EventLog)
            .filter(EventLog.event_type == event_type)
            .order_by(EventLog.occurred_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [EventLogResponse.model_validate(e) for e in events]
