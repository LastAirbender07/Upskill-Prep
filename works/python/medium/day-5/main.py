import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi.responses import JSONResponse
from app.api.execption import global_exception_handler
from dotenv import load_dotenv

load_dotenv()

PORT = 8081
app = FastAPI(
    title = "Learning Backend",
    description = "Event Handler"
)

app.add_exception_handler(Exception, global_exception_handler)

@app.get("/")
async def root():
    return JSONResponse(
        status_code=200,
        content={"message": f"App is running at port: {PORT}"}
    )

api_router = APIRouter(prefix="/v1")
app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
