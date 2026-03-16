from __future__ import annotations

import re
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


LOCALIZATION_MAP: dict[str, str] = {
    "Construction contract is missing.": "缺少施工合同文件。",
    "Upload construction contract.": "请补充上传施工合同。",
    "Personnel qualification form is missing.": "缺少人员资质审查表。",
    "Upload qualification form.": "请补充上传人员资质审查表。",
    "Entry permit is missing.": "缺少入场许可证文件。",
    "Upload entry permit.": "请补充上传入场许可证。",
    "Training record is missing.": "缺少安全培训记录。",
    "Upload training record.": "请补充上传安全培训记录。",
    "Contract number is missing.": "合同编号缺失。",
    "Fill contract number.": "请补充合同编号。",
    "Contract project name is missing.": "合同中的项目名称缺失。",
    "Fill project name in contract.": "请在合同中补充项目名称。",
    "Qualification person name is missing.": "资质表中的人员姓名缺失。",
    "Fill person name in qualification form.": "请在资质表中补充人员姓名。",
    "Qualification ID is missing.": "资质表中的身份证号缺失。",
    "Fill ID number in qualification form.": "请在资质表中补充身份证号。",
    "Qualification role is missing.": "资质表中的岗位信息缺失。",
    "Fill role in qualification form.": "请在资质表中补充岗位信息。",
    "Qualification certificate number is missing.": "资质证书编号缺失。",
    "Fill certificate number.": "请补充资质证书编号。",
    "Qualification certificate validity date is missing.": "资质证书有效期缺失。",
    "Fill certificate validity date.": "请补充资质证书有效期。",
    "Permit person name is missing.": "入场许可中的人员姓名缺失。",
    "Fill person name in permit.": "请在入场许可中补充人员姓名。",
    "Permit ID number is missing.": "入场许可中的身份证号缺失。",
    "Fill ID number in permit.": "请在入场许可中补充身份证号。",
    "Permit role is missing.": "入场许可中的岗位信息缺失。",
    "Fill role in permit.": "请在入场许可中补充岗位信息。",
    "Permit number is missing.": "入场许可编号缺失。",
    "Fill permit number.": "请补充入场许可编号。",
    "Permit date is missing.": "入场许可日期缺失。",
    "Fill permit date.": "请补充入场许可日期。",
    "Training person name is missing.": "培训记录中的人员姓名缺失。",
    "Fill person name in training record.": "请在培训记录中补充人员姓名。",
    "Training ID number is missing.": "培训记录中的身份证号缺失。",
    "Fill ID number in training record.": "请在培训记录中补充身份证号。",
    "Training date is missing.": "培训日期缺失。",
    "Fill training date.": "请补充培训日期。",
    "Trainer name is missing.": "培训讲师姓名缺失。",
    "Fill trainer name.": "请补充培训讲师姓名。",
    "Qualification certificate is expired.": "资质证书已过期。",
    "Provide valid certificate.": "请提供有效证书。",
    "Training date is later than permit date.": "培训日期晚于许可日期。",
    "Ensure training completed before permit issuance.": "请确保培训完成时间早于许可签发时间。",
    "Person role mismatch between qualification and permit.": "资质文件与入场许可中的岗位信息不一致。",
    "Unify role across documents.": "请统一各文档中的岗位信息。",
    "Permit holder has no training record.": "许可持有人未匹配到培训记录。",
    "Add matching training record.": "请补充对应的培训记录。",
    "Project name inconsistency detected.": "检测到项目名称跨文档不一致。",
    "Align project name across files.": "请统一各文件中的项目名称。",
    "Contractor name inconsistency detected.": "检测到承包商名称跨文档不一致。",
    "Align contractor name across files.": "请统一各文件中的承包商名称。",
    "Personnel chain has missing links.": "人员资质-许可-培训链条存在缺失。",
    "Close missing chain links.": "请补齐人员链条缺失资料。",
    "JSA risk-control mapping is incomplete.": "JSA风险与控制措施匹配不完整。",
    "Complete control measures for all hazards.": "请补充各风险对应的控制措施。",
}

CHECKPOINT_MAP: dict[str, str] = {
    "Construction contract exists": "施工合同已提供",
    "Qualification form exists": "人员资质表已提供",
    "Entry permit exists": "入场许可已提供",
    "Training record exists": "培训记录已提供",
    "Contract no. not empty": "合同编号不能为空",
    "Project name not empty": "项目名称不能为空",
    "Person name not empty": "人员姓名不能为空",
    "ID number not empty": "身份证号不能为空",
    "Role not empty": "岗位信息不能为空",
    "Certificate number not empty": "证书编号不能为空",
    "Certificate valid-until not empty": "证书有效期不能为空",
    "Permit number not empty": "许可编号不能为空",
    "Permit date not empty": "许可日期不能为空",
    "Training date not empty": "培训日期不能为空",
    "Trainer not empty": "培训讲师不能为空",
    "Certificate date valid": "证书有效期需在有效范围内",
    "Training date should not be after permit date": "培训日期不得晚于许可日期",
    "Contract effective date should not be later than permit date": "合同生效日期不得晚于许可日期",
    "Qualification role equals permit role": "资质岗位与许可岗位需一致",
    "Permit holder must have training record": "许可持有人需具备培训记录",
    "Project name is consistent": "项目名称需跨文档一致",
    "Contractor name is consistent": "承包商名称需跨文档一致",
    "Qualification->Permit->Training chain complete": "资质-许可-培训链条需完整",
    "Each hazard has adequate controls": "每项作业风险均需配置对应控制措施",
}

RULE_CHECKPOINT_OVERRIDE: dict[str, str] = {
    "R-V2-022": "《国家管网集团承包商安全监督管理规定》第三十六条（第八项）",
    "R-V2-030": "《国家管网集团承包商安全监督管理规定》第三十五条、第三十六条；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-031": "《国家管网集团承包商安全监督管理规定》第三十五条、第三十六条；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-032": "《国家管网集团承包商安全监督管理规定》第三十五条、第三十六条；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-033": "《国家管网集团承包商安全监督管理规定》第三十五条、第三十六条；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-034": "《国家管网集团承包商安全监督管理规定》第三十五条、第三十六条；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-035": "《国家管网集团承包商安全监督管理规定》第三十五条、第三十六条；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-036": "《国家管网集团承包商安全监督管理规定》第三十六条（第七项）；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-037": "《国家管网集团承包商安全监督管理规定》第三十六条（第七项）；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-038": "《国家管网集团承包商安全监督管理规定》第三十六条（第八项、第十一项）",
    "R-V2-039": "《国家管网集团承包商安全监督管理规定》第三十六条（第十三项）、第四十条",
    "R-V2-040": "《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
    "R-V2-041": "《国家管网集团承包商安全监督管理规定》第三十六条（第四项、第十二项）",
    "R-V2-042": "《国家管网集团承包商安全监督管理规定》第三十六条（第四项）",
    "R-V2-043": "《国家管网集团承包商安全监督管理规定》第三十六条（第八项）、第三十七条；《5.4.6.1-P-承包商开工前及过程安全管理流程说明文件》003承包商HSE文件及作业条件审查。",
}

DOC_TYPE_LABEL_MAP: dict[str, str] = {
    "construction_contract": "施工合同",
    "personnel_qualification_review_form": "人员资质审查表",
    "entry_permit": "入场许可证",
    "safety_education_training_record": "安全教育培训记录",
    "training_record": "培训记录",
    "jsa": "作业安全分析",
}

CHAIN_LINK_LABEL_MAP: dict[str, str] = {
    "qualification": "资质",
    "permit": "许可",
    "training": "培训",
}

FIELD_LABEL_MAP: dict[str, str] = {
    "contract_no": "合同编号",
    "project_name": "项目名称",
    "person_name": "人员姓名",
    "id_no": "身份证号",
    "role": "岗位信息",
    "certificate_no": "证书编号",
    "certificate_valid_until": "证书有效期",
    "permit_no": "许可编号",
    "permit_date": "许可日期",
    "training_date": "培训日期",
    "trainer_name": "培训讲师",
    "risk_items": "风险识别项",
    "emergency_materials": "应急物资",
    "equipment_plan": "设备机具计划",
    "hazards_identified": "风险识别",
    "equipment": "设备清单",
    "materials": "材料清单",
    "personnel": "关键岗位人员信息",
    "attendees_signatures": "参训人员签名",
    "items": "检查项",
    "signatures": "签署信息",
    "attendees": "参与人员",
}


def _safe_uuid(value: str) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _localize_text(text: str | None) -> str | None:
    if text is None:
        return None
    normalized = " ".join(str(text).split())
    if not normalized:
        return normalized
    if normalized in LOCALIZATION_MAP:
        return LOCALIZATION_MAP[normalized]

    m = re.match(r"^Missing field '([^']+)' in (.+)$", normalized)
    if m:
        field_key = m.group(1)
        field_label = FIELD_LABEL_MAP.get(field_key, field_key)
        return f"文件“{m.group(2)}”缺少字段“{field_label}”。"

    m = re.match(r"^Date field '([^']+)' expired in (.+)$", normalized)
    if m:
        field_key = m.group(1)
        field_label = FIELD_LABEL_MAP.get(field_key, field_key)
        return f"字段“{field_label}”在文件“{m.group(2)}”中已过期。"

    m = re.match(r"^Person '([^']+)' has inconsistent roles: qualification=(.+) vs permit=(.+)$", normalized)
    if m:
        return f"人员“{m.group(1)}”在资质与许可中的岗位不一致（资质：{m.group(2)}，许可：{m.group(3)}）。"

    m = re.match(r"^Missing required document type: (.+)$", normalized)
    if m:
        raw_doc_type = m.group(1).strip()
        doc_type = DOC_TYPE_LABEL_MAP.get(raw_doc_type, raw_doc_type)
        return f"缺少必需文档类型：{doc_type}。"

    m = re.match(r"^Permit exists but no training record found for (.+)$", normalized)
    if m:
        return f"人员“{m.group(1)}”已存在入场许可，但未匹配到培训记录。"

    m = re.match(r"^Project names conflict across documents: (.+)$", normalized)
    if m:
        return f"跨文档项目名称不一致：{m.group(1)}。"

    m = re.match(r"^Contractor names conflict across documents: (.+)$", normalized)
    if m:
        return f"跨文档承包商名称不一致：{m.group(1)}。"

    m = re.match(r"^Date order violated: ([^=]+)=([^ ]+) later than ([^=]+)=(.+)$", normalized)
    if m:
        return f"日期先后关系异常：{m.group(1)}={m.group(2)} 晚于 {m.group(3)}={m.group(4)}。"

    m = re.match(r"^Date order violated against this date: ([^=]+)=(.+)$", normalized)
    if m:
        return f"日期对比基准：{m.group(1)}={m.group(2)}。"

    if normalized == "JSA hazards/controls mapping is incomplete":
        return "JSA风险与控制措施映射不完整。"

    m = re.match(r"^Missing chain links for (.+): (.+)$", normalized)
    if m:
        missing_links = ", ".join(
            CHAIN_LINK_LABEL_MAP.get(item.strip(), item.strip())
            for item in m.group(2).split(",")
            if item.strip()
        )
        return f"人员“{m.group(1)}”存在链路缺失：{missing_links}。"

    m = re.match(r"^Normalized data from (.+)$", normalized)
    if m:
        return f"来自文件“{m.group(1)}”的标准化数据。"

    return normalized


def _localize_checkpoint(checkpoint: str) -> str:
    normalized = " ".join(str(checkpoint).split())
    return CHECKPOINT_MAP.get(normalized, normalized)

def _resolve_checkpoint(rule_id: str, checkpoint: str) -> str:
    override = RULE_CHECKPOINT_OVERRIDE.get(rule_id)
    if override:
        return override
    return _localize_checkpoint(checkpoint)


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

            localized_snippet = _localize_text(item.get("snippet")) or str(item.get("snippet", ""))
            item["snippet"] = localized_snippet

            evidence_model = EvidenceItem(
                batch_id=batch_uuid,
                file_id=file_uuid,
                file_name=item["source_file_name"],
                page=item["page"],
                snippet=localized_snippet,
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
            checkpoint=_resolve_checkpoint(rule.rule_id, rule.checkpoint),
            result=RuleResult.FAIL.value,
            severity=rule.severity.value,
            issue_description=_localize_text(result.generated_issue_text or rule.issue_template)
            or (result.generated_issue_text or rule.issue_template),
            rectification_suggestion=_localize_text(rule.rectification_template),
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
