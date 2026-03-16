from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, delete

from app.models import AuditIssue, AuditReport, EvidenceItem, RuleExecutionResult

from app.rule_engine.executor import run_rule_engine
from app.services.normalization_service import normalize_batch_facts


def _reset_batch_audit_artifacts(session: Session, batch_id: str) -> None:
    """Keep audit idempotent for the same batch by clearing stale artifacts first."""
    batch_uuid = UUID(str(batch_id))
    session.exec(delete(AuditIssue).where(AuditIssue.batch_id == batch_uuid))
    session.exec(delete(EvidenceItem).where(EvidenceItem.batch_id == batch_uuid))
    session.exec(delete(RuleExecutionResult).where(RuleExecutionResult.batch_id == batch_uuid))
    session.exec(delete(AuditReport).where(AuditReport.batch_id == batch_uuid))
    session.commit()


def run_batch_audit(session: Session, batch_id: str) -> dict:
    _reset_batch_audit_artifacts(session=session, batch_id=batch_id)
    fact_context = normalize_batch_facts(session=session, batch_id=batch_id)
    issues = run_rule_engine(session=session, batch_id=batch_id, fact_context=fact_context)
    return {
        "batch_id": batch_id,
        "issue_count": len(issues),
        "status": "AUDITED",
    }
