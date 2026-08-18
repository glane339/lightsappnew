"""HTTP mapping for authoring errors. Handlers stay out of the route modules."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from authoring.service import (
    AuthoringConflict,
    AuthoringError,
    AuthoringInvalid,
    AuthoringNotFound,
)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthoringError, _authoring_error)


async def _authoring_error(_request: Request, exc: AuthoringError) -> JSONResponse:
    if isinstance(exc, AuthoringNotFound):
        status_code, code = 404, "not_found"
    elif isinstance(exc, AuthoringConflict):
        status_code, code = 409, "conflict"
    elif isinstance(exc, AuthoringInvalid):
        status_code, code = 400, "invalid"
    else:
        status_code, code = 400, "invalid"
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": exc.message}},
    )
