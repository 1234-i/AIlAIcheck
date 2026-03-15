from __future__ import annotations

import hashlib
from datetime import date

from app.llm.adapters.base import LLMProvider
from app.llm.prompts.version import PROMPT_VERSION
from app.llm.schemas.contracts import (
    ClassificationOutput,
    ConflictOutput,
    ExtractionOutput,
    LLMEvidence,
    ReportPhraseOutput,
    RuleDraftOutput,
)


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def _classify_by_filename(file_name: str) -> tuple[str, str]:
    lowered = file_name.lower()
    if "jsa" in lowered or "job_safety" in lowered:
        return "jsa", "HSE_RISK_DOCUMENTS"
    if "contract" in lowered:
        return "construction_contract", "PROJECT_ADMISSION_LEGAL"
    if "qualification" in lowered or "personnel" in lowered:
        return "personnel_qualification_review_form", "PERSONNEL_CONSISTENCY_QUALIFICATION"
    if "permit" in lowered or "entry" in lowered:
        return "entry_permit", "TRAINING_PERMIT_CLOSURE"
    if "training" in lowered or "education" in lowered:
        return "safety_education_training_record", "TRAINING_PERMIT_CLOSURE"
    return "unsupported_document", "CROSS_DOCUMENT_CONFLICT_SCAN"


def _person_from_filename(file_name: str) -> tuple[str, str]:
    lowered = file_name.lower()
    if "zhang" in lowered:
        return "Zhang San", "A-10001"
    if "li" in lowered:
        return "Li Si", "A-20002"
    return "Wang Wu", "A-30003"


class MockProvider(LLMProvider):
    async def classify_pdf(self, file_name: str, pdf_bytes: bytes, hints: dict | None = None) -> ClassificationOutput:
        doc_type, primary_group = _classify_by_filename(file_name)
        confidence = 0.91 + (_seed(file_name) % 8) / 1000.0
        return ClassificationOutput(
            doc_type=doc_type,
            primary_group=primary_group,
            related_groups=["CROSS_DOCUMENT_CONFLICT_SCAN"],
            confidence=min(confidence, 0.99),
            classification_evidence=[LLMEvidence(page=1, snippet=f"Mock classification for {file_name}")],
            prompt_version=PROMPT_VERSION,
            meta={
                "provider_selected": "mock",
                "provider_route_reason": "llm_mode=mock",
                "provider_escalated": False,
                "cache_source_provider": "mock",
                "timeout_retry_count": 0,
            },
        )

    async def extract_structured(
        self,
        file_name: str,
        pdf_bytes: bytes,
        schema_name: str,
        schema_definition: dict,
        prompt_hint: str | None = None,
    ) -> ExtractionOutput:
        project_name = "Alpha LNG Upgrade"
        contractor_name = "ACME EPC Co."
        person_name, id_no = _person_from_filename(file_name)
        lowered = file_name.lower()

        if schema_name == "construction_contract":
            data = {
                "project_name": project_name,
                "contractor_name": contractor_name,
                "contract_no": "HT-2026-001",
                "effective_date": "2026-01-01",
            }
        elif schema_name == "personnel_qualification_review_form":
            data = {
                "project_name": project_name,
                "person_name": person_name,
                "id_no": id_no,
                "role": "scaffolder",
                "certificate_no": "CERT-ZS-001",
                "certificate_valid_until": "2025-12-31",
                "contractor_name": contractor_name,
            }
        elif schema_name == "entry_permit":
            data = {
                "project_name": project_name,
                "person_name": person_name,
                "id_no": id_no,
                "role": "supervisor" if "supervisor" in lowered else "scaffolder",
                "permit_no": "EP-2026-009",
                "permit_date": "2026-02-10",
                "contractor_name": contractor_name,
            }
        elif schema_name == "safety_education_training_record":
            data = {
                "project_name": project_name,
                "person_name": person_name,
                "id_no": id_no,
                "training_topic": "Entry Safety Briefing",
                "training_date": str(date(2026, 2, 5)),
                "trainer": "Safety Officer Chen",
                "contractor_name": contractor_name,
            }
        elif schema_name == "jsa":
            data = {
                "project_name": project_name,
                "activity": "Hot work in confined area",
                "hazards": ["fire", "toxic gas"],
                "controls": ["gas detector", "fire watch", "permit to work"],
                "prepared_by": "Safety Engineer Lin",
            }
        else:
            data = {
                "project_name": project_name,
                "file_name": file_name,
                "note": "unsupported schema in mock mode",
            }

        return ExtractionOutput(
            schema_name=schema_name,
            schema_version="1.0.0",
            data=data,
            confidence=0.94,
            prompt_version=PROMPT_VERSION,
            meta={
                "provider_selected": "mock",
                "provider_route_reason": "llm_mode=mock",
                "provider_escalated": False,
                "cache_source_provider": "mock",
                "timeout_retry_count": 0,
            },
        )

    async def extract_rules_from_policy(self, policy_text: str) -> RuleDraftOutput:
        rules = [
            {
                "rule_id": "R-MVP-001",
                "clause_id": "CL-MVP-001",
                "rule_name": "Construction contract present",
                "audit_group": "PROJECT_ADMISSION_LEGAL",
                "audit_object": "Document Package",
                "checkpoint": "Construction contract exists",
                "evidence_required": 1,
                "logic_type": "require_doc_type",
                "severity": "HIGH",
                "issue_template": "Construction contract is missing.",
                "rectification_template": "Upload a valid construction contract.",
                "enabled": True,
                "version": "1.0.0",
            }
        ]
        return RuleDraftOutput(rules=rules)

    async def detect_cross_doc_conflicts(self, normalized_facts: dict) -> ConflictOutput:
        return ConflictOutput(
            conflicts=[
                {
                    "type": "person_role_mismatch",
                    "severity": "HIGH",
                    "description": "Role differs between qualification form and entry permit",
                }
            ]
        )

    async def generate_audit_report(self, report_payload: dict) -> ReportPhraseOutput:
        return ReportPhraseOutput(
            report_text="Mock audit report generated for local development.",
            items=report_payload.get("items", []),
        )
