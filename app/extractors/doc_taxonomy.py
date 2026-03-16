from __future__ import annotations

from app.core.enums import AuditGroup

DOC_TYPE_TAXONOMY: dict[str, dict[str, object]] = {
    "emergency_drill_record": {
        "keywords": ["emergency_drill_record", "应急演练记录", "演练记录"],
        "primary_group": AuditGroup.HSE_RISK_DOCUMENTS.value,
        "related_groups": [AuditGroup.TRAINING_PERMIT_CLOSURE.value],
    },
    "emergency_drill_plan": {
        "keywords": ["emergency_drill_plan", "应急演练计划", "演练计划"],
        "primary_group": AuditGroup.HSE_RISK_DOCUMENTS.value,
        "related_groups": [AuditGroup.TRAINING_PERMIT_CLOSURE.value],
    },
    "emergency_plan": {
        "keywords": ["emergency_plan", "应急预案"],
        "primary_group": AuditGroup.HSE_RISK_DOCUMENTS.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "material_inspection": {
        "keywords": ["material_inspection", "物资、材料进场报验", "材料进场报验", "材料报验"],
        "primary_group": AuditGroup.EQUIPMENT_TOOLS_MATERIALS.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "equipment_inspection": {
        "keywords": ["equipment_inspection", "入场机具报验", "设备、器具进场报审", "设备器具进场报审", "机具报验"],
        "primary_group": AuditGroup.EQUIPMENT_TOOLS_MATERIALS.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "medical_exam": {
        "keywords": ["medical_exam", "体检"],
        "primary_group": AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "insurance": {
        "keywords": ["insurance", "保险"],
        "primary_group": AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "hse_guidance": {
        "keywords": ["hse_guidance", "作业指导书", "操作规程"],
        "primary_group": AuditGroup.HSE_RISK_DOCUMENTS.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "hse_plan": {
        "keywords": ["hse_plan", "作业计划书", "保护费使用计划"],
        "primary_group": AuditGroup.HSE_RISK_DOCUMENTS.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "hse_commitment": {
        "keywords": ["hse_commitment", "工程项目hse承诺书", "项目hse承诺书"],
        "primary_group": AuditGroup.PROJECT_ADMISSION_LEGAL.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "all_staff_commitment": {
        "keywords": ["all_staff_commitment", "全员安全承诺书"],
        "primary_group": AuditGroup.PROJECT_ADMISSION_LEGAL.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "regulation": {
        "keywords": ["regulation", "监督管理规定"],
        "primary_group": AuditGroup.PROJECT_ADMISSION_LEGAL.value,
        "related_groups": [AuditGroup.HSE_RISK_DOCUMENTS.value],
    },
    "commencement_report": {
        "keywords": ["commencement_report", "开工报告"],
        "primary_group": AuditGroup.PROJECT_ADMISSION_LEGAL.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "construction_plan": {
        "keywords": ["construction_plan", "施工组织设计方案", "施工组织设计"],
        "primary_group": AuditGroup.HSE_RISK_DOCUMENTS.value,
        "related_groups": [AuditGroup.EQUIPMENT_TOOLS_MATERIALS.value],
    },
    "technical_briefing": {
        "keywords": ["technical_briefing", "安全技术交底", "技术交底"],
        "primary_group": AuditGroup.TRAINING_PERMIT_CLOSURE.value,
        "related_groups": [AuditGroup.HSE_RISK_DOCUMENTS.value],
    },
    "training_material": {
        "keywords": ["training_material", "安全教育培训资料", "培训资料"],
        "primary_group": AuditGroup.TRAINING_PERMIT_CLOSURE.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "training_record": {
        "keywords": ["training_record", "培训记录", "培训签到"],
        "primary_group": AuditGroup.TRAINING_PERMIT_CLOSURE.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "exam_record": {
        "keywords": ["exam_record", "考试卷"],
        "primary_group": AuditGroup.TRAINING_PERMIT_CLOSURE.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "contractor_certificate": {
        "keywords": ["contractor_certificate", "承包商合格证", "合格证"],
        "primary_group": AuditGroup.PROJECT_ADMISSION_LEGAL.value,
        "related_groups": [AuditGroup.TRAINING_PERMIT_CLOSURE.value],
    },
    "access_assessment": {
        "keywords": ["access_assessment", "能力准入评估表", "准入评估表"],
        "primary_group": AuditGroup.PROJECT_ADMISSION_LEGAL.value,
        "related_groups": [AuditGroup.TRAINING_PERMIT_CLOSURE.value],
    },
    "appointment_letter": {
        "keywords": ["appointment_letter", "任命书"],
        "primary_group": AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "qualification_review_record": {
        "keywords": ["qualification_review_record", "资质审查记录"],
        "primary_group": AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "key_role_form": {
        "keywords": ["key_role_form", "关键岗位人员报审表"],
        "primary_group": AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "social_security": {
        "keywords": ["social_security", "社保"],
        "primary_group": AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "labor_contract": {
        "keywords": ["labor_contract", "劳动合同"],
        "primary_group": AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "construction_contract": {
        "keywords": ["construction_contract", "contract", "施工合同"],
        "primary_group": AuditGroup.PROJECT_ADMISSION_LEGAL.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "personnel_qualification_review_form": {
        "keywords": [
            "personnel_qualification",
            "qualification",
            "人员资质报审表",
            "资质报审表",
            "资质",
            "审查",
        ],
        "primary_group": AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "entry_permit": {
        "keywords": ["entry_permit", "permit", "入场许可证", "入场许可"],
        "primary_group": AuditGroup.TRAINING_PERMIT_CLOSURE.value,
        "related_groups": [AuditGroup.PERSONNEL_CONSISTENCY_QUALIFICATION.value],
    },
    "safety_education_training_record": {
        "keywords": ["safety_education_training_record", "safety_training", "作业人员安全教育记录", "安全教育记录", "安全教育培训"],
        "primary_group": AuditGroup.TRAINING_PERMIT_CLOSURE.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
    "jsa": {
        "keywords": ["jsa", "job_safety_analysis", "job safety analysis", "作业安全分析表", "作业安全分析", "安全分析表", "风险分析"],
        "primary_group": AuditGroup.HSE_RISK_DOCUMENTS.value,
        "related_groups": [AuditGroup.CROSS_DOCUMENT_CONFLICT_SCAN.value],
    },
}


def filename_classify(file_name: str) -> tuple[str | None, str | None, list[str], float]:
    lower_name = file_name.lower()
    best_doc_type = None
    best_score = 0
    for doc_type, config in DOC_TYPE_TAXONOMY.items():
        keywords = config["keywords"]
        score = sum(1 for kw in keywords if str(kw).lower() in lower_name)
        if score > best_score:
            best_score = score
            best_doc_type = doc_type

    if not best_doc_type:
        return None, None, [], 0.0

    config = DOC_TYPE_TAXONOMY[best_doc_type]
    confidence = min(0.6 + best_score * 0.15, 0.97)
    return (
        best_doc_type,
        str(config["primary_group"]),
        [str(g) for g in config["related_groups"]],
        confidence,
    )
