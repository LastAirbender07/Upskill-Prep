from datetime import datetime, timezone
from api.events.schemas.events import EventMetadata


def enrich_event_metadata(event_metadata: EventMetadata) -> EventMetadata:
    event_metadata.processed_at = datetime.now(tz=timezone.utc)
    event_metadata.source = "web"
    return event_metadata
