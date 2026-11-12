from __future__ import annotations

from typing import Any

from fastapi import HTTPException


class ApiError(HTTPException):
    """Structured application error that never exposes stack traces or PHI."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message
        self.details = details or {}


def unauthorized(message: str = "Demo session required.") -> ApiError:
    return ApiError(401, "authentication_required", message)


def forbidden(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(403, "access_denied", message, details)


def not_found(resource: str = "Resource") -> ApiError:
    return ApiError(404, "not_found", f"{resource} was not found.")


def conflict(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(409, "conflict", message, details)


def validation_error(message: str, details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(422, "validation_failed", message, details)
