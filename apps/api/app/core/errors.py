import logging
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("fitia.errors")


@dataclass(frozen=True)
class FieldError:
    field: str
    code: str


class AppError(Exception):
    """Error de negocio que se serializa con el formato uniforme de la API."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: list[FieldError] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields or []
        self.headers = headers


def error_body(code: str, message: str, fields: list[FieldError] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "fields": [{"field": f.field, "code": f.code} for f in fields or []],
        }
    }


_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    429: "RATE_LIMITED",
}

_PYDANTIC_CODES = {"missing": "REQUIRED", "json_invalid": "INVALID_JSON"}


def _field_from_loc(loc: tuple[Any, ...]) -> str:
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header", "cookie")]
    return ".".join(parts) or "body"


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.fields),
        headers=exc.headers,
    )


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields = [
        FieldError(_field_from_loc(tuple(err.get("loc", ()))), _PYDANTIC_CODES.get(err.get("type", ""), "INVALID"))
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=error_body("VALIDATION_ERROR", "Revisa los campos indicados.", fields),
    )


async def _http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else code
    return JSONResponse(status_code=exc.status_code, content=error_body(code, message), headers=exc.headers)


async def _unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_error", extra={"error_type": type(exc).__name__})
    # Los 500 los emite ServerErrorMiddleware, por fuera del middleware de no-store.
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_ERROR", "Ocurrió un error inesperado."),
        headers={"Cache-Control": "no-store"},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
