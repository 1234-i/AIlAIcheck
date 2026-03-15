from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TriggerResponse(BaseModel):
    batch_id: str
    task_name: str
    status: str


class UploadResponse(BaseModel):
    batch_id: str
    file_ids: list[str]
    status: str


class IssueReviewRequest(BaseModel):
    action: str
    comment: str | None = None
    updated_fields: dict[str, Any] = {}


class RuleApproveRequest(BaseModel):
    rules: list[dict[str, Any]]


class PaginatedIssueResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
