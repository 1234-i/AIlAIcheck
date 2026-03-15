from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlmodel import Session, select

from app.core.config import get_settings
from app.extractors.doc_type_aliases import normalize_doc_type
from app.extractors.doc_taxonomy import filename_classify
from app.extractors.schema_registry import SUPPORTED_MVP_DOC_TYPES
from app.llm.adapters.base import LLMProvider
from app.llm.errors import LLMProviderError
from app.llm.prompts.version import PROMPT_VERSION
from app.models import BatchRecord, FileRecord
from app.services.result_cache import (
    ResultCache,
    build_result_cache_key,
    provider_model_signature,
    provider_model_signatures_for_file,
)
from app.storage.base import StorageBackend


def _file_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _obs_snippet(obs: dict) -> str:
    return f"observability: {json.dumps(obs, ensure_ascii=False, sort_keys=True)}"


async def _classify_payload(
    *,
    storage: StorageBackend,
    llm_provider: LLMProvider,
    file_record: FileRecord,
    filename_confidence_threshold: float,
    semaphore: asyncio.Semaphore,
    cache: ResultCache,
    model_signature: str,
    pipeline_version: str,
) -> dict:
    pdf_bytes = storage.read_bytes(file_record.storage_key)
    file_size_bytes = len(pdf_bytes)
    file_hash = _file_hash(pdf_bytes)

    doc_type, primary_group, related_groups, confidence = filename_classify(file_record.file_name)

    evidence: list[dict] = []
    if doc_type and confidence >= filename_confidence_threshold:
        evidence = [{"page": 1, "snippet": f"Filename signal: {file_record.file_name}"}]
        obs = {
            "provider_selected": "filename_rule",
            "provider_route_reason": "filename_high_confidence",
            "provider_escalated": False,
            "provider_escalation_reason": None,
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 4),
            "cache_hit": False,
            "cache_source_provider": None,
            "cache_source_model": None,
            "file_hash": file_hash,
            "model_name": "filename_rule",
            "model_selected": "filename_rule",
            "prompt_version": PROMPT_VERSION,
            "schema_version": "classification-v1",
            "pipeline_version": pipeline_version,
            "key_page_strategy_used": False,
            "raw_response_status": "filename_rule",
            "parse_error_category": None,
            "timeout_retry_count": 0,
        }
        evidence.append({"page": 1, "snippet": _obs_snippet(obs)})
        return {
            "doc_type": doc_type,
            "primary_group": primary_group,
            "related_groups": related_groups,
            "confidence": confidence,
            "classification_evidence": evidence,
            "cache_hit": False,
            "observability": obs,
        }

    try:
        signature_candidates = provider_model_signatures_for_file(
            llm_provider,
            file_size_bytes=file_size_bytes,
            stage="classification",
        )
        for signature in signature_candidates:
            cache_key = build_result_cache_key(
                stage="classification",
                file_bytes=pdf_bytes,
                model_signature=signature,
                prompt_version=PROMPT_VERSION,
                schema_version="classification-v1",
                pipeline_version=pipeline_version,
                extra={"file_name": file_record.file_name},
            )
            cached = cache.load(stage="classification", cache_key=cache_key)
            if cached:
                obs = dict(cached.get("observability") or {})
                obs["cache_hit"] = True
                obs["cache_source_provider"] = obs.get("provider_selected")
                obs["cache_source_model"] = obs.get("model_selected") or obs.get("model_name")
                obs["cache_signature"] = signature
                cached["cache_hit"] = True
                cached["observability"] = obs
                return cached

        async with semaphore:
            llm_result = await llm_provider.classify_pdf(file_name=file_record.file_name, pdf_bytes=pdf_bytes)

        selected_signature = model_signature
        llm_meta = dict(getattr(llm_result, "meta", {}) or {})
        if hasattr(llm_provider, "model_signature"):
            try:
                selected_signature = llm_provider.model_signature(
                    llm_meta.get("provider_selected"),
                    llm_meta.get("model_selected") or llm_meta.get("model_name"),
                )
            except Exception:
                selected_signature = model_signature

        payload = {
            "doc_type": llm_result.doc_type,
            "primary_group": llm_result.primary_group,
            "related_groups": llm_result.related_groups,
            "confidence": llm_result.confidence,
            "classification_evidence": [item.model_dump() for item in llm_result.classification_evidence],
            "cache_hit": False,
            "observability": {
                **llm_meta,
                "cache_hit": False,
                "cache_source_provider": None,
                "cache_source_model": None,
                "file_size_bytes": file_size_bytes,
                "file_size_mb": round(file_size_bytes / (1024 * 1024), 4),
                "file_hash": file_hash,
                "model_selected": llm_meta.get("model_selected") or llm_meta.get("model_name"),
                "prompt_version": PROMPT_VERSION,
                "schema_version": "classification-v1",
                "pipeline_version": pipeline_version,
                "key_page_strategy_used": False,
                "page_count": file_record.page_count,
                "cache_created_at": datetime.utcnow().isoformat(),
            },
        }
        cache_key = build_result_cache_key(
            stage="classification",
            file_bytes=pdf_bytes,
            model_signature=selected_signature,
            prompt_version=PROMPT_VERSION,
            schema_version="classification-v1",
            pipeline_version=pipeline_version,
            extra={"file_name": file_record.file_name},
        )
        cache.save(stage="classification", cache_key=cache_key, payload=payload)
        return payload
    except LLMProviderError as exc:
        obs = {
            "provider_selected": "relay_or_official",
            "provider_route_reason": "classification_exception",
            "provider_escalated": False,
            "provider_escalation_reason": None,
            "file_size_bytes": file_size_bytes,
            "file_size_mb": round(file_size_bytes / (1024 * 1024), 4),
            "cache_hit": False,
            "cache_source_provider": None,
            "cache_source_model": None,
            "file_hash": file_hash,
            "model_name": model_signature,
            "model_selected": model_signature,
            "prompt_version": PROMPT_VERSION,
            "schema_version": "classification-v1",
            "pipeline_version": pipeline_version,
            "key_page_strategy_used": False,
            "raw_response_status": "error",
            "parse_error_category": exc.code,
            "timeout_retry_count": 0,
        }
        return {
            "doc_type": "classification_error",
            "primary_group": "CROSS_DOCUMENT_CONFLICT_SCAN",
            "related_groups": [],
            "confidence": 0.0,
            "classification_evidence": [
                {"page": 1, "snippet": f"classification_error: {exc.code}: {exc}"},
                {"page": 1, "snippet": _obs_snippet(obs)},
            ],
            "cache_hit": False,
            "observability": obs,
        }


async def classify_batch(
    session: Session,
    storage: StorageBackend,
    llm_provider: LLMProvider,
    batch_id: str,
    *,
    include_file_names: set[str] | None = None,
) -> list[FileRecord]:
    settings = get_settings()
    batch_uuid = UUID(str(batch_id))
    batch = session.exec(select(BatchRecord).where(BatchRecord.batch_id == batch_uuid)).first()
    if not batch:
        raise ValueError(f"batch {batch_id} not found")

    file_records = list(session.exec(select(FileRecord).where(FileRecord.batch_id == batch_uuid)).all())
    if include_file_names is not None:
        file_records = [f for f in file_records if f.file_name in include_file_names]

    semaphore = asyncio.Semaphore(max(1, int(settings.llm_classify_max_concurrency)))
    cache = ResultCache()
    model_signature = provider_model_signature(llm_provider)

    tasks = [
        _classify_payload(
            storage=storage,
            llm_provider=llm_provider,
            file_record=file_record,
            filename_confidence_threshold=0.75,
            semaphore=semaphore,
            cache=cache,
            model_signature=model_signature,
            pipeline_version=settings.pipeline_version,
        )
        for file_record in file_records
    ]
    payloads = await asyncio.gather(*tasks)

    updated: list[FileRecord] = []
    for file_record, result in zip(file_records, payloads):
        doc_type = normalize_doc_type(result.get("doc_type"))
        if doc_type == "training_record" and any(token in file_record.file_name for token in ("安全教育记录", "作业人员安全教育记录")):
            doc_type = "safety_education_training_record"
        primary_group = result.get("primary_group")
        related_groups = result.get("related_groups") or []
        confidence = float(result.get("confidence", 0.0))
        evidence = result.get("classification_evidence") or []
        obs = result.get("observability") or {}

        if doc_type not in SUPPORTED_MVP_DOC_TYPES and doc_type != "classification_error":
            doc_type = "unsupported_document"
            primary_group = primary_group or "CROSS_DOCUMENT_CONFLICT_SCAN"
            related_groups = related_groups or []
            confidence = min(confidence, 0.5)

        if result.get("cache_hit"):
            evidence = list(evidence) + [{"page": 1, "snippet": "cache_hit: classification"}]
        if obs:
            evidence = list(evidence) + [{"page": 1, "snippet": _obs_snippet(obs)}]

        file_record.doc_type = doc_type
        file_record.primary_group = primary_group
        file_record.related_groups = related_groups
        file_record.confidence = confidence
        file_record.classification_evidence = evidence
        file_record.updated_at = datetime.utcnow()
        session.add(file_record)
        updated.append(file_record)

    session.commit()
    for file_record in updated:
        session.refresh(file_record)
    return updated
