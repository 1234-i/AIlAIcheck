from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import AuditGroup, BatchStatus, RuleResult, Severity


class EvidenceSchema(BaseModel):
    evidence_id: str | None = None
    source_file_id: UUID
    source_file_name: str
    page: int = Field(ge=1)
    snippet: str
    field_path: str
    extracted_field_source: str
    locator: dict[str, Any] | None = None
    rule_id: str
    clause_id: str


class BatchSummary(BaseModel):
    batch_id: UUID
    status: BatchStatus
    created_at: datetime
    completed_at: datetime | None = None
    summary_counts: dict[str, Any] = {}


class ClassificationResult(BaseModel):
    file_id: UUID
    doc_type: str
    primary_group: AuditGroup
    related_groups: list[AuditGroup] = []
    confidence: float = Field(ge=0, le=1)
    classification_evidence: list[EvidenceSchema] = []


class ExtractionResult(BaseModel):
    file_id: UUID
    schema_name: str
    schema_version: str
    validated_json: dict[str, Any]
    raw_model_json: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    validation_errors: list[str] = []


class RuleResultSchema(BaseModel):
    rule_id: str
    clause_id: str
    hit: bool
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    generated_issue_text: str | None = None
    evidence_items: list[EvidenceSchema] = []


class AuditIssueSchema(BaseModel):
    issue_id: UUID
    batch_id: UUID
    rule_id: str
    clause_id: str
    audit_group: AuditGroup
    audit_object: str
    checkpoint: str
    result: RuleResult
    severity: Severity
    issue_description: str
    rectification_suggestion: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence_chain: list[EvidenceSchema]
    flags: dict[str, Any] = {}


class ReportItem(BaseModel):
    index: int
    audit_group: AuditGroup
    audit_object: str
    checkpoint: str
    result: RuleResult
    issue_description: str
    clause_reference: str
    evidence_source: str
    severity: Severity
    rectification_suggestion: str | None = None
    confidence: float = Field(ge=0, le=1)


class AuditReportSchema(BaseModel):
    report_id: UUID
    batch_id: UUID
    audit_version: str
    generated_at: datetime
    summary: dict[str, Any]
    items: list[ReportItem]
