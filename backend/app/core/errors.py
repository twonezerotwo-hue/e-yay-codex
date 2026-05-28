from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Any | None = None
    request_id: str


class AppError(Exception):
    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        details: Any | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details
        self.status_code = status_code

__all__ = [name for name in globals() if not name.startswith('_')]

__all__ = [name for name in globals() if not name.startswith('_')]
