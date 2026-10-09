from uuid import UUID
from sqlalchemy.orm import Session
from app.crud.event_logs_repository import EventLogRepository
from app.schemas.event_logs import EventLogResponse
from app.schemas.enums import EventType, AggregateType
from app.core.logger import get_logger

logger = get_logger(__name__)


class EventLogService:
    def __init__(self, db: Session):
        self.repo = EventLogRepository(db)

    def log_event(
        self,
        event_type: EventType,
        aggregate_type: AggregateType,
        aggregate_id: UUID,
        payload: dict,
    ) -> EventLogResponse:
        return self.repo.create_event(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
        )

    def get_history(
        self,
        aggregate_type: AggregateType,
        aggregate_id: UUID,
    ) -> list[EventLogResponse]:
        return self.repo.get_by_aggregate(aggregate_type, aggregate_id)

    def get_by_type(
        self,
        event_type: EventType,
        skip: int = 0,
        limit: int = 100,
    ) -> list[EventLogResponse]:
        return self.repo.get_by_type(event_type, skip=skip, limit=limit)
