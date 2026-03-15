from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.core.enums import BatchStatus


class TimestampedModel(SQLModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BatchRecord(TimestampedModel, table=True):
    batch_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    uploader: str | None = None
    status: BatchStatus = Field(default=BatchStatus.UPLOADED)
    completed_at: datetime | None = None
    summary_counts: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class FileRecord(TimestampedModel, table=True):
    file_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    batch_id: UUID = Field(index=True)
    file_name: str
    storage_uri: str
    storage_key: str
    checksum: str
    page_count: int | None = None
    doc_type: str | None = None
    primary_group: str | None = None
    related_groups: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    confidence: float | None = None
    classification_evidence: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))


class ExtractionRecord(TimestampedModel, table=True):
    extraction_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    file_id: UUID = Field(index=True)
    schema_name: str
    schema_version: str
    raw_model_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    validated_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    confidence: float
    errors: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class ProjectProfile(TimestampedModel, table=True):
    project_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    batch_id: UUID = Field(index=True)
    project_name: str | None = None
    section_name: str | None = None
    contractor_name: str | None = None
    contract_no: str | None = None
    start_date: date | None = None
    planned_end_date: date | None = None
    risk_level: str | None = None


class PersonMaster(TimestampedModel, table=True):
    person_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    batch_id: UUID = Field(index=True)
    name: str
    id_no_hash: str
    role: str | None = None
    certs: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    medical_validity: date | None = None
    insurance_status: str | None = None
    employment_links: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class EquipmentMaster(TimestampedModel, table=True):
    equipment_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    batch_id: UUID = Field(index=True)
    name: str
    model: str | None = None
    serial: str | None = None
    inspection_dates: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    operator_links: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    material_links: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class RuleDefinition(TimestampedModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    rule_id: str = Field(index=True, unique=True)
    clause_id: str
    rule_name: str
    audit_group: str
    audit_object: str
    checkpoint: str
    evidence_required: int
    logic_type: str
    severity: str
    issue_template: str
    rectification_template: str
    enabled: bool = True
    version: str


class EvidenceItem(TimestampedModel, table=True):
    evidence_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    batch_id: UUID = Field(index=True)
    file_id: UUID = Field(index=True)
    file_name: str
    page: int
    snippet: str
    locator: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    field_path: str
    rule_id: str
    clause_id: str


class RuleExecutionResult(TimestampedModel, table=True):
    execution_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    batch_id: UUID = Field(index=True)
    rule_id: str = Field(index=True)
    hit: bool
    confidence: float
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    related_file_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    related_pages: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    generated_issue_text: str | None = None


class AuditIssue(TimestampedModel, table=True):
    issue_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    batch_id: UUID = Field(index=True)
    rule_id: str
    clause_id: str
    audit_group: str
    audit_object: str
    checkpoint: str
    result: str
    severity: str
    issue_description: str
    rectification_suggestion: str | None = None
    confidence: float
    evidence_chain: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    contradiction_flags: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    review_status: str = "PENDING"
    review_comment: str | None = None


class AuditReport(TimestampedModel, table=True):
    report_id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    batch_id: UUID = Field(index=True, unique=True)
    audit_version: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    issue_list: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    statistics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    export_links: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
