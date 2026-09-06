from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database.database import get_db
from api.events.schemas.events import EventMetadata, EventMetadataResponse
from api.events.services import enrich_event_metadata
from api.events import crud

router = APIRouter()


@router.post(
    "/events/metadata/",
    response_model=EventMetadataResponse,
    status_code=201,
)
async def create_event_metadata(
    event_metadata: EventMetadata, db: Session = Depends(get_db)
):
    try:
        enriched_event = enrich_event_metadata(event_metadata)
        crud.create_event_metadata(db, enriched_event)
        return EventMetadataResponse(
            message="Event metadata created successfully",
            event_metadata=enriched_event,
        )
    except IntegrityError as e:
        db.rollback()
        # FK violation — referenced user_id doesn't exist
        if "ForeignKeyViolation" in str(e.orig):
            raise HTTPException(
                status_code=422,
                detail=f"user_id={event_metadata.user_id} does not exist",
            )
        # Duplicate primary key
        if "UniqueViolation" in str(e.orig):
            raise HTTPException(
                status_code=409,
                detail=f"event_id={event_metadata.event_id} already exists",
            )
        raise HTTPException(status_code=500, detail="Database integrity error")


@router.get("/events/metadata/{event_id}")
async def get_event_metadata(event_id: int, db: Session = Depends(get_db)):
    result = crud.get_event(db, event_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"event_id={event_id} not found",
        )
    return result
