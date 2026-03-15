from __future__ import annotations

from sqlmodel import Session

from app.rule_engine.executor import run_rule_engine
from app.services.normalization_service import normalize_batch_facts


def run_batch_audit(session: Session, batch_id: str) -> dict:
    fact_context = normalize_batch_facts(session=session, batch_id=batch_id)
    issues = run_rule_engine(session=session, batch_id=batch_id, fact_context=fact_context)
    return {
        "batch_id": batch_id,
        "issue_count": len(issues),
        "status": "AUDITED",
    }
