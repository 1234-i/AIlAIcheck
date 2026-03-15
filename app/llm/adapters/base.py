from __future__ import annotations

from typing import Protocol

from app.llm.schemas.contracts import (
    ClassificationOutput,
    ConflictOutput,
    ExtractionOutput,
    ReportPhraseOutput,
    RuleDraftOutput,
)


class LLMProvider(Protocol):
    async def classify_pdf(self, file_name: str, pdf_bytes: bytes, hints: dict | None = None) -> ClassificationOutput:
        ...

    async def extract_structured(
        self,
        file_name: str,
        pdf_bytes: bytes,
        schema_name: str,
        schema_definition: dict,
        prompt_hint: str | None = None,
    ) -> ExtractionOutput:
        ...

    async def extract_rules_from_policy(self, policy_text: str) -> RuleDraftOutput:
        ...

    async def detect_cross_doc_conflicts(self, normalized_facts: dict) -> ConflictOutput:
        ...

    async def generate_audit_report(self, report_payload: dict) -> ReportPhraseOutput:
        ...
