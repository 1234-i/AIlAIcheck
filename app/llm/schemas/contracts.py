from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LLMEvidence(BaseModel):
    page: int = Field(ge=1)
    snippet: str


class ClassificationOutput(BaseModel):
    doc_type: str
    primary_group: str
    related_groups: list[str] = []
    confidence: float = Field(ge=0, le=1)
    classification_evidence: list[LLMEvidence] = []
    prompt_version: str | None = None
    meta: dict[str, Any] = {}


class ExtractionOutput(BaseModel):
    schema_name: str
    schema_version: str
    data: dict[str, Any]
    confidence: float = Field(ge=0, le=1)
    prompt_version: str | None = None
    meta: dict[str, Any] = {}


class RuleDraftOutput(BaseModel):
    rules: list[dict[str, Any]]


class ConflictOutput(BaseModel):
    conflicts: list[dict[str, Any]]


class ReportPhraseOutput(BaseModel):
    report_text: str
    items: list[dict[str, Any]] = []
