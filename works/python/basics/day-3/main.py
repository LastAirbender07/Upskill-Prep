"""
Day-3 FastAPI app — improved version of day-2.

Changes from day-2:
  1. Response model (EventMetadataResponse) — API output is validated + documented
  2. status_code=201 on POST — HTTP convention for resource creation
  3. Path param named `event_id` instead of `id` — avoids shadowing Python built-in
  4. No side effects on import — sample data is in sample_data.py
  5. Imports from `models` not `schema` — better naming
"""

import uvicorn
from fastapi import FastAPI

from models import EventMetadata, EventMetadataResponse, debug_event
from sample_data import event_1

app = FastAPI(
    title="Day 3 — Learning Backend",
    description="Event Ingestion API with proper patterns",
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post(
    "/events/metadata/",
    response_model=EventMetadataResponse,  # Tells FastAPI (and /docs) exactly what the response looks like
    status_code=201,  # 201 Created — not 200 OK. POST that creates a resource should return 201.
)
async def create_event_metadata(event_metadata: EventMetadata):
    # Try sending {"id": 0, "user_id": 42, "metadata": {}} via /docs
    # You'll get a 422 automatically because id must be > 0 (gt=0 in the model)
    return EventMetadataResponse(
        message="Event metadata created successfully",
        event_metadata=event_metadata,
    )


@app.get("/events/metadata/{event_id}")  # event_id not id — don't shadow built-in
async def get_event_metadata(event_id: int):
    debug_event(event_1)
    return {"event_id": event_id, "result": event_1}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
