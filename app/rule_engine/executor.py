from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import Session

from app.core.enums import RuleResult
from app.models import AuditIssue, EvidenceItem, RuleExecutionResult
from app.rule_engine.evaluator import evaluate_rule
from app.rule_engine.evidence import EvidenceRef
from app.rule_engine.loader import load_rules
from app.services.normalization_service import normalize_batch_facts


def _safe_uuid(value: str) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


def run_rule_engine(
    session: Session,
    batch_id: str,
    rule_path: str = "examples/rules_v2_high_value.json",
    fact_context: dict[str, Any] | None = None,
) -> list[AuditIssue]:
    batch_uuid = UUID(str(batch_id))
    context = fact_context or normalize_batch_facts(session=session, batch_id=batch_id)
    rules = load_rules(rule_path)
    issues: list[AuditIssue] = []

    for rule in rules:
        result = evaluate_rule(rule, context)
        execution = RuleExecutionResult(
            batch_id=batch_uuid,
            rule_id=result.rule_id,
            hit=result.hit,
            confidence=result.confidence,
            evidence_ids=[str(uuid4()) for _ in result.evidence_items],
            related_file_ids=result.related_file_ids,
            related_pages=result.related_pages,
            generated_issue_text=result.generated_issue_text,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(execution)

        if not result.hit:
            continue

        validated_evidence = [EvidenceRef.model_validate(item).model_dump() for item in result.evidence_items]
        if len(validated_evidence) < rule.evidence_required:
            continue

        evidence_chain: list[dict[str, Any]] = []
        for item in validated_evidence:
            file_uuid = _safe_uuid(item["source_file_id"])
            if not file_uuid:
                continue

            evidence_model = EvidenceItem(
                batch_id=batch_uuid,
                file_id=file_uuid,
                file_name=item["source_file_name"],
                page=item["page"],
                snippet=item["snippet"],
                locator=item.get("locator"),
                field_path=item["field_path"],
                rule_id=rule.rule_id,
                clause_id=rule.clause_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(evidence_model)
            evidence_chain.append(item)

        if not evidence_chain:
            continue

        issue = AuditIssue(
            batch_id=batch_uuid,
            rule_id=rule.rule_id,
            clause_id=rule.clause_id,
            audit_group=rule.audit_group,
            audit_object=rule.audit_object,
            checkpoint=rule.checkpoint,
            result=RuleResult.FAIL.value,
            severity=rule.severity.value,
            issue_description=result.generated_issue_text or rule.issue_template,
            rectification_suggestion=rule.rectification_template,
            confidence=result.confidence,
            evidence_chain=evidence_chain,
            contradiction_flags={"cross_document": "consistency" in rule.logic_type},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(issue)
        issues.append(issue)

    session.commit()
    for issue in issues:
        session.refresh(issue)
    return issues
