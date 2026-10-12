from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.logger import get_logger

logger = get_logger(__name__)


def global_exception_handler(request: Request, e: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url}: {e}")
    return JSONResponse(
        status_code=500, content={"detail": f"Internal server Error"}
    )


class NotFoundError(ValueError):
    """Resource does not exist → 404"""


class ConflictError(ValueError):
    """Request conflicts with existing state (duplicate) → 409"""


class BusinessRuleError(ValueError):
    """Request is valid but violates a business rule → 422"""
