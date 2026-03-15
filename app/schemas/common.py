from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class APIResponse(BaseModel):
    request_id: str
    data: dict[str, Any] | list[Any] | None
    error: ErrorBody | None = None
