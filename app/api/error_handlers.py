from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import DomainError, EntityNotFoundError, ExternalServiceError, ImportInProgressError

_logger = logging.getLogger("app")


def _error_response(status_code: int, detail: str, error_code: str) -> JSONResponse:
    """Builds a JSON error response with a consistent shape.

    Args:
        status_code: HTTP status code to respond with.
        detail: Human-readable error message.
        error_code: Machine-readable error code for clients to branch on.
    """
    return JSONResponse(status_code=status_code, content={"detail": detail, "error_code": error_code})


def register_exception_handlers(app: FastAPI) -> None:
    """Registers handlers that translate domain exceptions into HTTP
    responses, keeping HTTP concerns out of the domain/service layers.

    Args:
        app: The FastAPI application to register handlers on.
    """

    @app.exception_handler(EntityNotFoundError)
    async def not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
        """Maps `EntityNotFoundError` to `404 Not Found`."""
        return _error_response(status.HTTP_404_NOT_FOUND, str(exc), "ENTITY_NOT_FOUND")

    @app.exception_handler(ExternalServiceError)
    async def external_service_handler(request: Request, exc: ExternalServiceError) -> JSONResponse:
        """Maps `ExternalServiceError` (e.g. SWAPI exhausted retries) to `502 Bad Gateway`."""
        _logger.error("external_service_error error=%s", exc)
        return _error_response(status.HTTP_502_BAD_GATEWAY, str(exc), "EXTERNAL_SERVICE_ERROR")

    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        """Maps any other `DomainError` to `400 Bad Request`."""
        return _error_response(status.HTTP_400_BAD_REQUEST, str(exc), "DOMAIN_ERROR")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all: maps any unhandled exception to `500 Internal Server Error`."""
        _logger.error("unhandled_exception error=%s error_type=%s", exc, type(exc).__name__)
        return _error_response(status.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.", "INTERNAL_SERVER_ERROR")

    @app.exception_handler(ImportInProgressError)
    async def import_in_progress_handler(request: Request, exc: ImportInProgressError) -> JSONResponse:
        return _error_response(status.HTTP_409_CONFLICT, str(exc), "IMPORT_IN_PROGRESS")
