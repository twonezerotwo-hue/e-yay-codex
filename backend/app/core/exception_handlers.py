from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.errors import AppError, ErrorResponse
from app.core.logging import get_logger, get_request_id
from app.services import audit_service as audit_service_module


logger = get_logger("errors")


def _build_error_response(
    *,
    error_code: str,
    message: str,
    details: object | None,
    request_id: str,
    status_code: int,
) -> JSONResponse:
    payload = ErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        request_id=request_id,
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def _write_exception_audit_event(
    *,
    request: Request,
    event_type: str,
    message: str,
    details_json: dict[str, object | None],
    request_id: str,
) -> None:
    settings = get_settings()

    if not settings.database_url:
        logger.warning(
            "audit.skipped",
            extra={
                "event": "audit.skipped",
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": 0,
            },
        )
        return

    try:
        audit_service_module.persist_audit_log(
            database_url=settings.database_url,
            event_type=event_type,
            message=message,
            details_json=details_json,
            request_id=request_id,
        )
    except Exception:
        logger.exception(
            "audit.write_failed",
            extra={
                "event": "audit.write_failed",
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "status_code": 0,
            },
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = get_request_id()
    logger.warning(
        "request.app_error",
        extra={
            "event": "request.app_error",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
        },
    )
    _write_exception_audit_event(
        request=request,
        event_type="app_error",
        message=exc.message,
        details_json={
            "error_code": exc.error_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
        },
        request_id=request_id,
    )
    return _build_error_response(
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        request_id=request_id,
        status_code=exc.status_code,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id()
    logger.exception(
        "request.unhandled_exception",
        extra={
            "event": "request.unhandled_exception",
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "status_code": 500,
        },
    )
    _write_exception_audit_event(
        request=request,
        event_type="unhandled_exception",
        message=str(exc) or "Unhandled exception",
        details_json={
            "exception_type": exc.__class__.__name__,
            "path": request.url.path,
            "method": request.method,
            "status_code": 500,
        },
        request_id=request_id,
    )
    return _build_error_response(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.",
        details=None,
        request_id=request_id,
        status_code=500,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

__all__ = [name for name in globals() if not name.startswith('_')]
