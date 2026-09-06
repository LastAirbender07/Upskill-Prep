from sqlalchemy.orm import Session
from api.events.models.events import EventMetadata as EventModel
from api.events.schemas.events import EventMetadata as EventSchema


def create_event_metadata(db: Session, event: EventSchema) -> EventModel:
    db_event = EventModel(
        event_id=event.event_id,
        user_id=event.user_id,
        event_type=event.event_type,
        source=event.source,
        event_metadata=event.metadata,
    )

    db.add(db_event)  # stagging
    db.commit()  # write to postgres
    db.refresh(db_event)  # reload

    return db_event


def get_event(db: Session, event_id: int) -> EventModel | None:
    return db.query(EventModel).filter(EventModel.event_id == event_id).first()
