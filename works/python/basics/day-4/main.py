import logging
import uvicorn
from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from database.database import engine
from database.base import Base
from api.events.routes.events import router as event_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = 8081
app = FastAPI(
    title="Day 4 - Learning Backend",
    description="Event Ingestion API",
)

Base.metadata.create_all(bind=engine)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root():
    return {"message": f"App is running at port: {PORT}"}


api_router = APIRouter(prefix="/v1")
api_router.include_router(event_router)

app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
