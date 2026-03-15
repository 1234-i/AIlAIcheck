from __future__ import annotations

from datetime import date
from typing import Any

from app.rule_engine.contracts import RuleDefinitionSchema, RuleExecutionResultSchema
from app.rule_engine.evidence import build_evidence

DOC_TYPE_EQUIVALENCE: dict[str, set[str]] = {
    "safety_education_training_record": {"safety_education_training_record", "training_record"},
    "training_record": {"safety_education_training_record", "training_record"},
}


def _doc_entries(context: dict[str, Any], doc_type: str) -> list[dict[str, Any]]:
    index = context.get("doc_type_index", {})
    equiv = DOC_TYPE_EQUIVALENCE.get(doc_type)
    if not equiv:
        return index.get(doc_type, [])
    merged: list[dict[str, Any]] = []
    for item in equiv:
        merged.extend(index.get(item, []))
    return merged


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return "".join(str(value).lower().split())


def _jsa_low_specificity(entry_data: dict[str, Any]) -> bool:
    hazards = entry_data.get("hazards") or []
    controls = entry_data.get("controls") or []
    if not isinstance(hazards, list) or not isinstance(controls, list):
        return True
    generic_h = {"作业风险", "风险", "危害"}
    generic_c = {"落实安全控制措施", "控制措施", "防控措施"}
    norm_h = {str(x).strip() for x in hazards if str(x).strip()}
    norm_c = {str(x).strip() for x in controls if str(x).strip()}
    flag_weak = bool(entry_data.get("weak_recovered")) or bool(entry_data.get("low_specificity"))
    if flag_weak:
        return True
    return (not norm_h or norm_h.issubset(generic_h)) or (not norm_c or norm_c.issubset(generic_c))


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _presence(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    required_doc_type = str(rule.params.get("required_doc_type", "")).strip()
    entries = _doc_entries(context, required_doc_type)
    hit = len(entries) == 0

    evidence: list[dict[str, Any]] = []
    if hit and context.get("evidence"):
        source = context["evidence"][0]
        evidence = [
            build_evidence(
                source_file_id=source["source_file_id"],
                source_file_name=source["source_file_name"],
                page=source["page"],
                snippet=f"Missing required document type: {required_doc_type}",
                field_path="doc_presence_scan",
                extracted_field_source="classification",
                rule_id=rule.rule_id,
                clause_id=rule.clause_id,
            )
        ]

    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.96 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _required_field(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    doc_type = str(rule.params.get("doc_type", "")).strip()
    field_name = str(rule.params.get("field_name", "")).strip()
    entries = _doc_entries(context, doc_type)
    missing = [entry for entry in entries if not entry.get("data", {}).get(field_name)]
    hit = len(missing) > 0

    evidence: list[dict[str, Any]] = []
    for entry in missing:
        evidence.append(
            build_evidence(
                source_file_id=entry["file_id"],
                source_file_name=entry["file_name"],
                page=1,
                snippet=f"Missing field '{field_name}' in {entry['file_name']}",
                field_path=f"validated_json.{field_name}",
                extracted_field_source="extraction",
                rule_id=rule.rule_id,
                clause_id=rule.clause_id,
            )
        )

    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.94 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _date_not_expired(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    doc_type = str(rule.params.get("doc_type", "")).strip()
    field_name = str(rule.params.get("field_name", "")).strip()
    entries = _doc_entries(context, doc_type)

    expired: list[dict[str, Any]] = []
    for entry in entries:
        target_date = _to_date(entry.get("data", {}).get(field_name))
        if target_date and target_date < date.today():
            expired.append(entry)

    evidence = [
        build_evidence(
            source_file_id=entry["file_id"],
            source_file_name=entry["file_name"],
            page=1,
            snippet=f"Date field '{field_name}' expired in {entry['file_name']}",
            field_path=f"validated_json.{field_name}",
            extracted_field_source="extraction",
            rule_id=rule.rule_id,
            clause_id=rule.clause_id,
        )
        for entry in expired
    ]

    hit = len(expired) > 0
    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.92 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _person_role_consistency(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    people = context.get("persons", [])
    mismatches = []
    for person in people:
        role_qual = person.get("roles_by_source", {}).get("qualification")
        role_permit = person.get("roles_by_source", {}).get("permit")
        if role_qual and role_permit and _normalize_text(role_qual) != _normalize_text(role_permit):
            mismatches.append(person)

    evidence: list[dict[str, Any]] = []
    for person in mismatches:
        file_name = person.get("source_file_names", ["unknown"])[0]
        file_id = person.get("source_file_ids", ["unknown"])[0]
        evidence.append(
            build_evidence(
                source_file_id=file_id,
                source_file_name=file_name,
                page=1,
                snippet=(
                    f"Person '{person['person_name']}' has inconsistent roles: "
                    f"qualification={person.get('roles_by_source', {}).get('qualification')} vs "
                    f"permit={person.get('roles_by_source', {}).get('permit')}"
                ),
                field_path="normalized_person.roles_by_source",
                extracted_field_source="normalization",
                rule_id=rule.rule_id,
                clause_id=rule.clause_id,
            )
        )

    hit = len(mismatches) > 0
    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.91 if hit else 0.98,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _person_training_closure(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    people = context.get("persons", [])
    offenders = [
        person
        for person in people
        if person.get("chain_flags", {}).get("permit") and not person.get("chain_flags", {}).get("training")
    ]

    evidence: list[dict[str, Any]] = []
    for person in offenders:
        file_name = person.get("source_file_names", ["unknown"])[0]
        file_id = person.get("source_file_ids", ["unknown"])[0]
        evidence.append(
            build_evidence(
                source_file_id=file_id,
                source_file_name=file_name,
                page=1,
                snippet=f"Permit exists but no training record found for {person['person_name']}",
                field_path="normalized_person.chain_flags",
                extracted_field_source="normalization",
                rule_id=rule.rule_id,
                clause_id=rule.clause_id,
            )
        )

    hit = len(offenders) > 0
    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.93 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _project_name_consistency(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    project_names = sorted({_normalize_text(x) for x in context.get("project_names", []) if x})
    hit = len(project_names) > 1

    evidence: list[dict[str, Any]] = []
    if hit:
        for entry in context.get("evidence", [])[:2]:
            evidence.append(
                build_evidence(
                    source_file_id=entry["source_file_id"],
                    source_file_name=entry["source_file_name"],
                    page=entry["page"],
                    snippet=f"Project names conflict across documents: {', '.join(project_names)}",
                    field_path="validated_json.project_name",
                    extracted_field_source="normalization",
                    rule_id=rule.rule_id,
                    clause_id=rule.clause_id,
                )
            )

    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.9 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _contractor_name_consistency(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    contractor_names = sorted({_normalize_text(x) for x in context.get("contractor_names", []) if x})
    hit = len(contractor_names) > 1
    evidence: list[dict[str, Any]] = []
    if hit:
        for entry in context.get("evidence", [])[:2]:
            evidence.append(
                build_evidence(
                    source_file_id=entry["source_file_id"],
                    source_file_name=entry["source_file_name"],
                    page=entry["page"],
                    snippet=f"Contractor names conflict across documents: {', '.join(contractor_names)}",
                    field_path="validated_json.contractor_name",
                    extracted_field_source="normalization",
                    rule_id=rule.rule_id,
                    clause_id=rule.clause_id,
                )
            )

    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.9 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _date_order(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    first_doc = str(rule.params.get("first_doc_type", "")).strip()
    first_field = str(rule.params.get("first_field", "")).strip()
    second_doc = str(rule.params.get("second_doc_type", "")).strip()
    second_field = str(rule.params.get("second_field", "")).strip()

    first_dates = []
    for entry in _doc_entries(context, first_doc):
        d = _to_date(entry.get("data", {}).get(first_field))
        if d:
            first_dates.append((entry, d))

    second_dates = []
    for entry in _doc_entries(context, second_doc):
        d = _to_date(entry.get("data", {}).get(second_field))
        if d:
            second_dates.append((entry, d))

    hit = False
    evidence: list[dict[str, Any]] = []
    if first_dates and second_dates:
        first_latest = max(first_dates, key=lambda x: x[1])
        second_earliest = min(second_dates, key=lambda x: x[1])
        if first_latest[1] > second_earliest[1]:
            hit = True
            evidence.append(
                build_evidence(
                    source_file_id=first_latest[0]["file_id"],
                    source_file_name=first_latest[0]["file_name"],
                    page=1,
                    snippet=f"Date order violated: {first_field}={first_latest[1]} later than {second_field}={second_earliest[1]}",
                    field_path=f"validated_json.{first_field}",
                    extracted_field_source="extraction",
                    rule_id=rule.rule_id,
                    clause_id=rule.clause_id,
                )
            )
            evidence.append(
                build_evidence(
                    source_file_id=second_earliest[0]["file_id"],
                    source_file_name=second_earliest[0]["file_name"],
                    page=1,
                    snippet=f"Date order violated against this date: {second_field}={second_earliest[1]}",
                    field_path=f"validated_json.{second_field}",
                    extracted_field_source="extraction",
                    rule_id=rule.rule_id,
                    clause_id=rule.clause_id,
                )
            )

    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.9 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _jsa_control_completeness(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    entries = _doc_entries(context, "jsa")
    offenders = []
    for entry in entries:
        data = entry.get("data", {}) or {}
        hazards = data.get("hazards") or []
        controls = data.get("controls") or []
        if not isinstance(hazards, list) or not isinstance(controls, list):
            offenders.append(entry)
            continue
        if len(hazards) == 0 or len(controls) == 0 or len(controls) < len(hazards) or _jsa_low_specificity(data):
            offenders.append(entry)

    evidence = [
        build_evidence(
            source_file_id=entry["file_id"],
            source_file_name=entry["file_name"],
            page=1,
            snippet="JSA hazards/controls mapping is incomplete",
            field_path="validated_json.hazards|controls",
            extracted_field_source="extraction",
            rule_id=rule.rule_id,
            clause_id=rule.clause_id,
        )
        for entry in offenders
    ]
    hit = len(offenders) > 0
    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.88 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def _person_chain_missing_links(rule: RuleDefinitionSchema, context: dict[str, Any]) -> RuleExecutionResultSchema:
    chain_gaps = context.get("person_chain_gaps", [])
    evidence: list[dict[str, Any]] = []

    for gap in chain_gaps:
        source_file_id = gap.get("source_file_ids", ["unknown"])[0]
        source_file_name = gap.get("source_file_names", ["unknown"])[0]
        evidence.append(
            build_evidence(
                source_file_id=source_file_id,
                source_file_name=source_file_name,
                page=1,
                snippet=f"Missing chain links for {gap['person_name']}: {', '.join(gap['missing_links'])}",
                field_path="normalized_person.missing_chain_links",
                extracted_field_source="normalization",
                rule_id=rule.rule_id,
                clause_id=rule.clause_id,
            )
        )

    hit = len(chain_gaps) > 0
    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=hit,
        severity=rule.severity,
        confidence=0.9 if hit else 0.99,
        generated_issue_text=rule.issue_template if hit else None,
        evidence_items=evidence,
        related_file_ids=[item["source_file_id"] for item in evidence],
        related_pages=[item["page"] for item in evidence],
    )


def evaluate_rule(rule: RuleDefinitionSchema, fact_context: dict[str, Any]) -> RuleExecutionResultSchema:
    logic_type = rule.logic_type

    if logic_type == "require_doc_type":
        return _presence(rule, fact_context)
    if logic_type == "require_field":
        return _required_field(rule, fact_context)
    if logic_type == "date_not_expired":
        return _date_not_expired(rule, fact_context)
    if logic_type == "person_role_consistency":
        return _person_role_consistency(rule, fact_context)
    if logic_type == "person_training_closure":
        return _person_training_closure(rule, fact_context)
    if logic_type == "project_name_consistency":
        return _project_name_consistency(rule, fact_context)
    if logic_type == "contractor_name_consistency":
        return _contractor_name_consistency(rule, fact_context)
    if logic_type == "date_order":
        return _date_order(rule, fact_context)
    if logic_type == "jsa_control_completeness":
        return _jsa_control_completeness(rule, fact_context)
    if logic_type == "person_chain_missing_links":
        return _person_chain_missing_links(rule, fact_context)

    return RuleExecutionResultSchema(
        rule_id=rule.rule_id,
        clause_id=rule.clause_id,
        hit=False,
        severity=rule.severity,
        confidence=0.5,
        generated_issue_text=None,
        evidence_items=[],
        related_file_ids=[],
        related_pages=[],
    )
