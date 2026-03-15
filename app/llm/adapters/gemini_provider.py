from __future__ import annotations

import os
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.extractors.schema_registry import LOW_VALUE_DOC_TYPES
from app.llm.adapters.base import LLMProvider
from app.llm.errors import LLMParseError, LLMProviderError, LLMValidationError
from app.llm.gemini_client import GeminiClient
from app.llm.json_utils import parse_json_object_strict
from app.llm.prompts.builders import (
    classification_prompt,
    conflict_prompt,
    extraction_prompt,
    report_phrase_prompt,
    rule_draft_prompt,
)
from app.llm.schemas.contracts import (
    ClassificationOutput,
    ConflictOutput,
    ExtractionOutput,
    ReportPhraseOutput,
    RuleDraftOutput,
)

CLASSIFICATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {"type": "string"},
        "primary_group": {"type": "string"},
        "related_groups": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "classification_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page": {"type": "integer"},
                    "snippet": {"type": "string"},
                },
                "required": ["page", "snippet"],
            },
        },
        "prompt_version": {"type": "string"},
    },
    "required": ["doc_type", "primary_group", "related_groups", "confidence", "classification_evidence"],
}

EXTRACTION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_name": {"type": "string"},
        "schema_version": {"type": "string"},
        "data": {"type": "object"},
        "confidence": {"type": "number"},
        "prompt_version": {"type": "string"},
    },
    "required": ["schema_name", "schema_version", "data", "confidence"],
}

RULE_DRAFT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["rules"],
}

CONFLICT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "conflicts": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["conflicts"],
}

REPORT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "report_text": {"type": "string"},
        "items": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["report_text", "items"],
}


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        self.settings = get_settings()
        relay_base = self.settings.relay_gemini_base_url or self.settings.gemini_base_url
        relay_key = self.settings.relay_gemini_api_key or self.settings.gemini_api_key
        relay_model = self.settings.relay_gemini_model or self.settings.gemini_audit_model

        official_key = self.settings.official_gemini_api_key or self.settings.org_gemini_api_key or os.getenv("ORG_GEMINI_API_KEY")
        official_base = self.settings.official_gemini_base_url or relay_base
        official_parse_model = self.settings.official_gemini_parse_model or self.settings.official_gemini_model or relay_model
        official_complex_model = self.settings.official_gemini_complex_model or self.settings.official_gemini_model or relay_model

        self.relay_client = GeminiClient(
            base_url=relay_base,
            api_key=relay_key,
            model=relay_model,
            provider_name="relay",
        )
        self.official_parse_client = GeminiClient(
            base_url=official_base,
            api_key=official_key,
            model=official_parse_model,
            provider_name="official",
        )
        self.official_complex_client = GeminiClient(
            base_url=official_base,
            api_key=official_key,
            model=official_complex_model,
            provider_name="official",
        )
        self.official_enabled = bool(official_key)
        self.threshold_bytes = int(float(self.settings.pdf_provider_size_threshold_mb) * 1024 * 1024)
        self.enable_escalation = bool(self.settings.enable_provider_escalation)
        self.enable_official_complex_escalation = bool(self.settings.enable_official_complex_escalation)
        self.official_complex_escalation_min_confidence = float(self.settings.official_complex_escalation_min_confidence)
        self.official_complex_escalation_doc_types = {
            item.strip() for item in (self.settings.official_complex_escalation_doc_types or "").split(",") if item.strip()
        }

    def cache_model_signatures(self, *, file_size_bytes: int, stage: str) -> list[str]:
        signatures: list[str] = []
        if self.official_enabled:
            signatures.append(f"{type(self).__name__}:{self.official_parse_client.signature}")
            if self.enable_official_complex_escalation:
                signatures.append(f"{type(self).__name__}:{self.official_complex_client.signature}")
        signatures.append(f"{type(self).__name__}:{self.relay_client.signature}")
        return signatures

    def model_signature(self, provider_name: str | None = None, model_name: str | None = None) -> str:
        if provider_name == "relay":
            return f"{type(self).__name__}:{self.relay_client.signature}"
        if provider_name == "official" and self.official_enabled:
            if model_name and model_name == self.official_complex_client.model:
                return f"{type(self).__name__}:{self.official_complex_client.signature}"
            return f"{type(self).__name__}:{self.official_parse_client.signature}"
        if provider_name and model_name:
            return f"{type(self).__name__}:{provider_name}:{model_name}"
        if provider_name == "official" and self.official_enabled:
            return f"{type(self).__name__}:{self.official_parse_client.signature}"
        if provider_name == "relay":
            return f"{type(self).__name__}:{self.relay_client.signature}"
        if self.official_enabled:
            return f"{type(self).__name__}:{self.official_parse_client.signature}"
        return f"{type(self).__name__}:{self.relay_client.signature}"

    def _route_primary(self, file_size_bytes: int) -> tuple[GeminiClient, str]:
        if file_size_bytes > self.threshold_bytes and self.official_enabled:
            return self.official_parse_client, "file_size_over_threshold"
        return self.relay_client, "default_cost_priority"

    def _should_escalate_on_error(self, exc: LLMProviderError) -> tuple[bool, str]:
        if not (self.official_enabled and self.enable_escalation):
            return False, ""
        code = getattr(exc, "code", "")
        msg = str(exc).lower()
        if code == "llm_timeout":
            return True, "timeout"
        if code == "llm_parse_error":
            return True, "parse_failed"
        if code == "llm_transport_error":
            if "413" in msg or "payload too large" in msg:
                return True, "http_413_payload_too_large"
            return True, "transport_error"
        return False, ""

    def _should_escalate_on_extraction_quality(self, parsed: dict[str, Any]) -> tuple[bool, str]:
        if not (self.official_enabled and self.enable_escalation):
            return False, ""
        data = parsed.get("data")
        confidence = parsed.get("confidence", 0.0)
        is_empty = (not isinstance(data, dict)) or (len(data) == 0)
        if is_empty and float(confidence or 0.0) <= 0.5:
            return True, "extraction_empty_low_confidence"
        if is_empty:
            return True, "extraction_empty"
        return False, ""

    async def _call_client(
        self,
        *,
        client: GeminiClient,
        request_tag: str,
        prompt: str,
        pdf_bytes: bytes | None,
        response_schema: dict | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        parts: list[dict[str, Any]] = [{"text": prompt}]
        if pdf_bytes is not None:
            parts.append(client.build_pdf_part(pdf_bytes))
        contents = [{"parts": parts}]

        response, transport_meta = await client.generate_content_with_meta(
            contents=contents,
            request_tag=request_tag,
            response_schema=response_schema,
        )
        text = client.extract_text(response)
        if not text:
            raise LLMParseError(f"empty text response for {request_tag}")
        parsed = parse_json_object_strict(text)

        meta = {
            "provider_selected": client.provider_name,
            "model_name": client.model,
            "model_selected": client.model,
            "provider_endpoint": client.base_url,
            "raw_response_status": transport_meta.get("raw_response_status"),
            "timeout_retry_count": transport_meta.get("timeout_retry_count", 0),
            "parse_error_category": None,
        }
        return parsed, meta

    async def _invoke_json(
        self,
        *,
        request_tag: str,
        prompt: str,
        pdf_bytes: bytes | None = None,
        response_schema: dict | None = None,
        enforce_extraction_quality: bool = False,
        schema_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        file_size_bytes = len(pdf_bytes or b"")
        primary_client, route_reason = self._route_primary(file_size_bytes)
        secondary_client = self.official_parse_client if primary_client.provider_name == "relay" and self.official_enabled else None

        meta = {
            "provider_selected": primary_client.provider_name,
            "provider_route_reason": route_reason,
            "provider_escalated": False,
            "provider_escalation_reason": None,
            "relay_base_url": self.relay_client.base_url,
            "provider_endpoint": primary_client.base_url,
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 4),
            "raw_response_status": None,
            "parse_error_category": None,
            "timeout_retry_count": 0,
            "model_name": primary_client.model,
            "model_selected": primary_client.model,
        }

        try:
            parsed, call_meta = await self._call_client(
                client=primary_client,
                request_tag=request_tag,
                prompt=prompt,
                pdf_bytes=pdf_bytes,
                response_schema=response_schema,
            )
            meta.update(call_meta)
            escalate_quality, escalate_reason = self._should_escalate_on_extraction_quality(parsed) if enforce_extraction_quality else (False, "")
            if escalate_quality and secondary_client is not None:
                parsed, call_meta = await self._call_client(
                    client=secondary_client,
                    request_tag=f"{request_tag}_escalated",
                    prompt=prompt,
                    pdf_bytes=pdf_bytes,
                    response_schema=response_schema,
                )
                meta.update(call_meta)
                meta["provider_selected"] = secondary_client.provider_name
                meta["model_name"] = secondary_client.model
                meta["model_selected"] = secondary_client.model
                meta["provider_endpoint"] = secondary_client.base_url
                meta["provider_escalated"] = True
                meta["provider_escalation_reason"] = escalate_reason
            if (
                self.official_enabled
                and self.enable_official_complex_escalation
                and primary_client.provider_name == "official"
                and request_tag.startswith("extract_")
                and (
                    (schema_name and schema_name in self.official_complex_escalation_doc_types)
                    or float(parsed.get("confidence", 0.0) or 0.0) < self.official_complex_escalation_min_confidence
                )
                and (not schema_name or schema_name not in LOW_VALUE_DOC_TYPES)
                and self.official_complex_client.model != meta.get("model_selected")
            ):
                parsed, call_meta = await self._call_client(
                    client=self.official_complex_client,
                    request_tag=f"{request_tag}_official_complex",
                    prompt=prompt,
                    pdf_bytes=pdf_bytes,
                    response_schema=response_schema,
                )
                meta.update(call_meta)
                meta["provider_selected"] = "official"
                meta["model_name"] = self.official_complex_client.model
                meta["model_selected"] = self.official_complex_client.model
                meta["provider_endpoint"] = self.official_complex_client.base_url
                meta["provider_escalated"] = True
                if schema_name and schema_name in self.official_complex_escalation_doc_types:
                    meta["provider_escalation_reason"] = "official_parse_to_complex_doc_type"
                else:
                    meta["provider_escalation_reason"] = "official_parse_to_complex_low_confidence"
            return parsed, meta
        except LLMProviderError as exc:
            should_escalate, escalate_reason = self._should_escalate_on_error(exc)
            if should_escalate and secondary_client is not None:
                parsed, call_meta = await self._call_client(
                    client=secondary_client,
                    request_tag=f"{request_tag}_escalated",
                    prompt=prompt,
                    pdf_bytes=pdf_bytes,
                    response_schema=response_schema,
                )
                meta.update(call_meta)
                meta["provider_selected"] = secondary_client.provider_name
                meta["model_name"] = secondary_client.model
                meta["model_selected"] = secondary_client.model
                meta["provider_endpoint"] = secondary_client.base_url
                meta["provider_escalated"] = True
                meta["provider_escalation_reason"] = escalate_reason
                return parsed, meta
            meta["parse_error_category"] = getattr(exc, "code", "llm_error")
            raise

    async def classify_pdf(self, file_name: str, pdf_bytes: bytes, hints: dict | None = None) -> ClassificationOutput:
        prompt = classification_prompt(file_name=file_name, hints=hints)
        parsed, meta = await self._invoke_json(
            request_tag="classify_pdf",
            prompt=prompt,
            pdf_bytes=pdf_bytes,
            response_schema=CLASSIFICATION_RESPONSE_SCHEMA,
        )
        try:
            output = ClassificationOutput.model_validate(parsed)
            output.meta = {
                **output.meta,
                **meta,
            }
            return output
        except ValidationError as exc:
            raise LLMValidationError(f"classification schema validation failed: {exc}") from exc

    async def extract_structured(
        self,
        file_name: str,
        pdf_bytes: bytes,
        schema_name: str,
        schema_definition: dict,
        prompt_hint: str | None = None,
    ) -> ExtractionOutput:
        prompt = extraction_prompt(
            file_name=file_name,
            schema_name=schema_name,
            schema_definition=schema_definition,
            prompt_hint=prompt_hint,
        )
        parsed, meta = await self._invoke_json(
            request_tag=f"extract_{schema_name}",
            prompt=prompt,
            pdf_bytes=pdf_bytes,
            response_schema=EXTRACTION_RESPONSE_SCHEMA,
            enforce_extraction_quality=True,
            schema_name=schema_name,
        )
        try:
            output = ExtractionOutput.model_validate(parsed)
            output.meta = {
                **output.meta,
                **meta,
            }
            return output
        except ValidationError as exc:
            raise LLMValidationError(f"extraction schema validation failed: {exc}") from exc

    async def extract_rules_from_policy(self, policy_text: str) -> RuleDraftOutput:
        prompt = rule_draft_prompt(policy_text=policy_text)
        parsed, _ = await self._invoke_json(
            request_tag="extract_rules",
            prompt=prompt,
            response_schema=RULE_DRAFT_RESPONSE_SCHEMA,
        )
        try:
            return RuleDraftOutput.model_validate(parsed)
        except ValidationError as exc:
            raise LLMValidationError(f"rule draft schema validation failed: {exc}") from exc

    async def detect_cross_doc_conflicts(self, normalized_facts: dict) -> ConflictOutput:
        prompt = conflict_prompt(normalized_facts=normalized_facts)
        parsed, _ = await self._invoke_json(
            request_tag="cross_doc_conflicts",
            prompt=prompt,
            response_schema=CONFLICT_RESPONSE_SCHEMA,
        )
        try:
            return ConflictOutput.model_validate(parsed)
        except ValidationError as exc:
            raise LLMValidationError(f"conflict schema validation failed: {exc}") from exc

    async def generate_audit_report(self, report_payload: dict) -> ReportPhraseOutput:
        prompt = report_phrase_prompt(report_payload=report_payload)
        parsed, _ = await self._invoke_json(
            request_tag="generate_report",
            prompt=prompt,
            response_schema=REPORT_RESPONSE_SCHEMA,
        )
        try:
            return ReportPhraseOutput.model_validate(parsed)
        except ValidationError as exc:
            raise LLMValidationError(f"report phrasing schema validation failed: {exc}") from exc
