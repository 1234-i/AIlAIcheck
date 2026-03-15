from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import Severity


class RuleDefinitionSchema(BaseModel):
    rule_id: str
    clause_id: str
    rule_name: str
    audit_group: str
    audit_object: str
    checkpoint: str
    evidence_required: int = Field(ge=1)
    logic_type: str
    severity: Severity
    issue_template: str
    rectification_template: str
    enabled: bool = True
    version: str
    params: dict[str, Any] = {}


class RuleExecutionResultSchema(BaseModel):
    rule_id: str
    clause_id: str
    hit: bool
    severity: Severity
    confidence: float
    generated_issue_text: str | None = None
    evidence_items: list[dict[str, Any]] = []
    related_file_ids: list[str] = []
    related_pages: list[int] = []
