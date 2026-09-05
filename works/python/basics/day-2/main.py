import uvicorn
from fastapi import FastAPI
from schema import EventMetadata, events_metadata_1, handlePrint

USER_ID = 177 # Usually got from the jwt session -> get from decorator

app = FastAPI(
    title="Learning Backend",
)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.post("/events/metadata/")
async def create_event_metadata(event_metadata: EventMetadata):
    # transform
    # sql alchemy ???
    # save to db
    return {"message": "Event metadata created successfully", "event_metadata": event_metadata.model_dump()}


@app.get("/events/metadata/{id}")
async def get_event_metadata(id: int):
    handlePrint(events_metadata_1)
    return {"id": id, "result": events_metadata_1}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8081, reload=True)
