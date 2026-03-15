from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    source_file_id: str
    source_file_name: str
    page: int = Field(ge=1)
    snippet: str
    locator: dict[str, Any] | None = None
    field_path: str
    extracted_field_source: str
    rule_id: str
    clause_id: str


def build_evidence(
    *,
    source_file_id: str,
    source_file_name: str,
    page: int,
    snippet: str,
    field_path: str,
    extracted_field_source: str,
    rule_id: str,
    clause_id: str,
    locator: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return EvidenceRef(
        source_file_id=source_file_id,
        source_file_name=source_file_name,
        page=page,
        snippet=snippet,
        locator=locator,
        field_path=field_path,
        extracted_field_source=extracted_field_source,
        rule_id=rule_id,
        clause_id=clause_id,
    ).model_dump()
