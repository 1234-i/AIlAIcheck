from __future__ import annotations

import json

from app.extractors.schema_registry import SUPPORTED_MVP_DOC_TYPES
from app.llm.prompts.version import PROMPT_VERSION


def _json_guardrail() -> str:
    return (
        "Return strict JSON only. No markdown code fences. "
        "No commentary. No extra keys outside required schema."
    )


def _extraction_doc_hint(schema_name: str) -> str:
    hints = {
        "training_record": "重点提取 date、instructor、attendees、training_content。若识别到签到名单，attendees 至少返回可辨识姓名子集，避免空 data。",
        "training_material": "从培训签到/教育记录页提取 training_date、location、instructor、attendees_signatures；姓名保持原文，不要臆造。",
        "key_role_form": "必须优先提取 data.personnel（数组对象，每项含 name 和 role）及 contractor_signature；如果可识别任一岗位人员，不要返回空 data。",
        "all_staff_commitment": "从承诺书签名区提取 signatures（姓名数组）和 date；若可识别姓名则返回可识别子集。",
        "emergency_plan": "提取 hazards_identified 与 emergency_materials，优先具体条目（如人身伤害、设备故障、创口贴、温度计、灭火器）。",
        "construction_plan": "在施工组织设计的风险/应急章节提取 project_scope、emergency_contact_list、emergency_materials。",
        "hse_guidance": "弱抽取模式下仅提取存在性锚点：doc_type、document_present、anchor_terms、notes。",
    }
    return hints.get(schema_name, "")


def classification_prompt(file_name: str, hints: dict | None = None) -> str:
    hint_text = json.dumps(hints or {}, ensure_ascii=False)
    allowed_doc_types = sorted(SUPPORTED_MVP_DOC_TYPES) + ["unsupported_document"]
    schema = {
        "doc_type": "string",
        "primary_group": "string",
        "related_groups": ["string"],
        "confidence": "float[0,1]",
        "classification_evidence": [{"page": "int", "snippet": "string"}],
        "prompt_version": PROMPT_VERSION,
    }
    return (
        "You classify contractor HSE PDFs for audit. "
        f"Allowed doc_type values: {allowed_doc_types}. "
        f"Filename hint: {file_name}. Additional hints: {hint_text}. "
        f"Output schema: {json.dumps(schema, ensure_ascii=False)}. "
        + _json_guardrail()
    )


def extraction_prompt(file_name: str, schema_name: str, schema_definition: dict, prompt_hint: str | None = None) -> str:
    schema_text = json.dumps(schema_definition, ensure_ascii=False)
    properties = schema_definition.get("json_schema", {}).get("properties", {})
    canonical_fields = sorted(properties.keys())
    required_fields = schema_definition.get("required_fields", []) or []
    required_any_of = schema_definition.get("required_any_of", []) or []
    core_fields = schema_definition.get("core_fields", canonical_fields) or canonical_fields
    value_tier = str(schema_definition.get("value_tier", "medium"))
    extraction_strategy = str(schema_definition.get("extraction_strategy", "light"))
    output_schema = {
        "schema_name": schema_name,
        "schema_version": "string",
        "data": "object",
        "confidence": "float[0,1]",
        "prompt_version": PROMPT_VERSION,
    }
    doc_hint = _extraction_doc_hint(schema_name)
    tier_instruction = {
        "high": (
            "Value tier=HIGH (strong extraction). Prioritize required/core fields first, "
            "then fill secondary fields only when clearly grounded. "
            "Do not leave required fields empty when reliable evidence exists."
        ),
        "medium": (
            "Value tier=MEDIUM (light extraction). Prioritize core fields only. "
            "Do not over-extract long lists or low-value details."
        ),
        "low": (
            "Value tier=LOW (weak extraction / existence evidence). "
            "Only output minimal existence anchors and core evidence fields. "
            "Do not attempt deep parsing, full lists, or complex structure reconstruction."
        ),
    }.get(value_tier, "Value tier=MEDIUM (light extraction). Prioritize core fields.")
    return (
        "Extract structured fields from this contractor HSE PDF. "
        f"Filename hint: {file_name}. "
        f"Target schema definition: {schema_text}. "
        f"Extraction strategy: {extraction_strategy}. "
        f"Use canonical data keys only: {canonical_fields}. "
        f"Core fields: {core_fields}. Required fields: {required_fields}. Required-any-of groups: {required_any_of}. "
        f"{tier_instruction} "
        "Extract only fields that can be reliably grounded from PDF content and filename hint; "
        "if PDF content is unreadable, infer only low-risk facts from filename tokens (names, counts, amount markers, dates). "
        "Do not fabricate uncertain values, and do not return empty data when filename already contains reliable clues. "
        f"{('Doc-specific priority: ' + doc_hint + ' ') if doc_hint else ''}"
        f"{('Rescue instruction: ' + prompt_hint + ' ') if prompt_hint else ''}"
        f"Output schema: {json.dumps(output_schema, ensure_ascii=False)}. "
        "If a field is missing, set it to null explicitly. "
        + _json_guardrail()
    )


def rule_draft_prompt(policy_text: str) -> str:
    return (
        "Convert policy into structured audit rules under the predefined rule schema. "
        "Return JSON with key 'rules'. "
        + _json_guardrail()
        + f" Policy: {policy_text}"
    )


def conflict_prompt(normalized_facts: dict) -> str:
    fact_text = json.dumps(normalized_facts, ensure_ascii=False)
    return (
        "Detect cross-document contradictions and anomaly signals from normalized facts. "
        "Return JSON with key 'conflicts'. "
        + _json_guardrail()
        + f" Facts: {fact_text}"
    )


def report_phrase_prompt(report_payload: dict) -> str:
    payload_text = json.dumps(report_payload, ensure_ascii=False)
    return (
        "Refine audit issue wording in human auditor style without changing factual conclusions. "
        "Return JSON with keys: report_text, items. "
        + _json_guardrail()
        + f" Payload: {payload_text}"
    )
