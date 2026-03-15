from __future__ import annotations

import asyncio

from sqlmodel import Session

from app.db.session import get_runtime_engine
from app.llm.provider_factory import get_llm_provider
from app.services.audit_service import run_batch_audit
from app.services.classification_service import classify_batch
from app.services.extraction_service import extract_batch
from app.services.normalization_service import normalize_batch_facts
from app.services.report_service import build_report
from app.storage.factory import get_storage_backend
from app.tasks.celery_app import celery_app


@celery_app.task(name="pipeline.classify_batch")
def classify_batch_task(batch_id: str) -> dict:
    with Session(get_runtime_engine()) as session:
        storage = get_storage_backend()
        provider = get_llm_provider()
        asyncio.run(classify_batch(session=session, storage=storage, llm_provider=provider, batch_id=batch_id))
    return {"batch_id": batch_id, "status": "CLASSIFIED"}


@celery_app.task(name="pipeline.extract_batch")
def extract_batch_task(batch_id: str) -> dict:
    with Session(get_runtime_engine()) as session:
        storage = get_storage_backend()
        provider = get_llm_provider()
        asyncio.run(extract_batch(session=session, storage=storage, llm_provider=provider, batch_id=batch_id))
    return {"batch_id": batch_id, "status": "EXTRACTED"}


@celery_app.task(name="pipeline.normalize_batch")
def normalize_batch_task(batch_id: str) -> dict:
    with Session(get_runtime_engine()) as session:
        return normalize_batch_facts(session=session, batch_id=batch_id)


@celery_app.task(name="pipeline.audit_batch")
def audit_batch_task(batch_id: str) -> dict:
    with Session(get_runtime_engine()) as session:
        return run_batch_audit(session=session, batch_id=batch_id)


@celery_app.task(name="pipeline.report_batch")
def report_batch_task(batch_id: str) -> dict:
    with Session(get_runtime_engine()) as session:
        return build_report(session=session, batch_id=batch_id)
