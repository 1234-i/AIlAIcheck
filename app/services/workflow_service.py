from __future__ import annotations

from sqlmodel import Session

from app.llm.adapters.base import LLMProvider
from app.services.audit_service import run_batch_audit
from app.services.classification_service import classify_batch
from app.services.extraction_service import extract_batch
from app.services.report_service import build_report
from app.storage.base import StorageBackend


async def run_full_pipeline(session: Session, storage: StorageBackend, provider: LLMProvider, batch_id: str) -> dict:
    await classify_batch(session=session, storage=storage, llm_provider=provider, batch_id=batch_id)
    await extract_batch(session=session, storage=storage, llm_provider=provider, batch_id=batch_id)
    run_batch_audit(session=session, batch_id=batch_id)
    report = build_report(session=session, batch_id=batch_id)
    return {"batch_id": batch_id, "status": "COMPLETED", "report": report}
