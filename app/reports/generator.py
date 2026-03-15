from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Session, delete, select

from app.models import AuditIssue, AuditReport


def generate_report(session: Session, batch_id: str, audit_version: str = "0.1.0") -> AuditReport:
    batch_uuid = UUID(str(batch_id))
    session.exec(delete(AuditReport).where(AuditReport.batch_id == batch_uuid))
    issues = list(session.exec(select(AuditIssue).where(AuditIssue.batch_id == batch_uuid)).all())

    items = []
    for idx, issue in enumerate(issues, start=1):
        evidence = issue.evidence_chain[0] if issue.evidence_chain else {}
        item = {
            "index": idx,
            "audit_group": issue.audit_group,
            "audit_object": issue.audit_object,
            "checkpoint": issue.checkpoint,
            "result": issue.result,
            "issue_description": issue.issue_description,
            "clause_reference": issue.clause_id,
            "evidence_source": f"{evidence.get('source_file_name', 'N/A')} p.{evidence.get('page', 'N/A')}",
            "severity": issue.severity,
            "rectification_suggestion": issue.rectification_suggestion,
            "confidence": issue.confidence,
            "internal": {
                "triggered_rule": issue.rule_id,
                "evidence_locator": evidence.get("locator"),
                "contradiction_flag": issue.contradiction_flags,
                "audit_version": audit_version,
                "evidence_chain": issue.evidence_chain,
            },
        }
        items.append(item)

    summary = {
        "total_issues": len(items),
        "critical": sum(1 for i in items if i["severity"] == "CRITICAL"),
        "high": sum(1 for i in items if i["severity"] == "HIGH"),
        "medium": sum(1 for i in items if i["severity"] == "MEDIUM"),
        "low": sum(1 for i in items if i["severity"] == "LOW"),
    }

    report = AuditReport(
        report_id=uuid4(),
        batch_id=batch_uuid,
        audit_version=audit_version,
        generated_at=datetime.utcnow(),
        issue_list=items,
        statistics=summary,
        export_links={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report
