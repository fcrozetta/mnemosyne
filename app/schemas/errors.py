from typing import Any

from pydantic import Field

from app.schemas.common import SchemaModel


class ErrorDetail(SchemaModel):
    """Single error detail entry returned by the API."""

    field: str | None = None
    message: str
    code: str
    context: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(SchemaModel):
    """Standard error payload shared across API endpoints."""

    error: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str | None = None


__all__ = ["ErrorDetail", "ErrorResponse"]
