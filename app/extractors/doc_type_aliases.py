from __future__ import annotations

import re


# actual_output_doc_type -> canonical_supported_doc_type
DOC_TYPE_ALIAS_TO_CANONICAL: dict[str, str] = {
    # canonical passthrough (runtime)
    "construction_contract": "construction_contract",
    "personnel_qualification_review_form": "personnel_qualification_review_form",
    "entry_permit": "entry_permit",
    "safety_education_training_record": "safety_education_training_record",
    "jsa": "jsa",
    "hse_guidance": "hse_guidance",
    "hse_plan": "hse_plan",
    "medical_exam": "medical_exam",
    "insurance": "insurance",
    "equipment_inspection": "equipment_inspection",
    "material_inspection": "material_inspection",
    "emergency_plan": "emergency_plan",
    "emergency_drill_plan": "emergency_drill_plan",
    "emergency_drill_record": "emergency_drill_record",
    "hse_commitment": "hse_commitment",
    "all_staff_commitment": "all_staff_commitment",
    "regulation": "regulation",
    "commencement_report": "commencement_report",
    "construction_plan": "construction_plan",
    "labor_contract": "labor_contract",
    "training_record": "training_record",
    "training_material": "training_material",
    "technical_briefing": "technical_briefing",
    "exam_record": "exam_record",
    "contractor_certificate": "contractor_certificate",
    "access_assessment": "access_assessment",
    "qualification_review_record": "qualification_review_record",
    "appointment_letter": "appointment_letter",
    "qualification_form": "qualification_form",
    "key_role_form": "key_role_form",
    "social_security": "social_security",
    # english aliases
    "contract": "construction_contract",
    "constructioncontract": "construction_contract",
    "qualification_review_form": "personnel_qualification_review_form",
    "personnel_qualification": "personnel_qualification_review_form",
    "personnelqualificationreviewform": "personnel_qualification_review_form",
    "permit": "entry_permit",
    "entrypermit": "entry_permit",
    "training": "safety_education_training_record",
    "training_records": "safety_education_training_record",
    "safety_training_record": "safety_education_training_record",
    "job_safety_analysis": "jsa",
    "jobsafetyanalysis": "jsa",
    "hse_instruction": "hse_guidance",
    "hse_work_guidance": "hse_guidance",
    "hse_work_plan": "hse_plan",
    "health_exam": "medical_exam",
    "medicalexamination": "medical_exam",
    "work_injury_insurance": "insurance",
    "equipment_report": "equipment_inspection",
    "equipment_check": "equipment_inspection",
    "material_report": "material_inspection",
    "material_check": "material_inspection",
    "emergency_response_plan": "emergency_plan",
    "drill_plan": "emergency_drill_plan",
    "drill_record": "emergency_drill_record",
    "hse_promise": "hse_commitment",
    "all_staff_hse_commitment": "all_staff_commitment",
    "policy_regulation": "regulation",
    "start_report": "commencement_report",
    "organization_plan": "construction_plan",
    "work_plan": "construction_plan",
    "certificate": "contractor_certificate",
    "access_assessment_form": "access_assessment",
    "qualification_review": "qualification_review_record",
    "appointment": "appointment_letter",
    "key_role_review": "key_role_form",
    "social_insurance": "social_security",
    "social_security_record": "social_security",
    # chinese aliases
    "施工合同": "construction_contract",
    "人员资质报审表": "personnel_qualification_review_form",
    "资质报审": "personnel_qualification_review_form",
    "入场许可证": "entry_permit",
    "作业许可证": "entry_permit",
    "安全教育培训": "safety_education_training_record",
    "作业安全分析": "jsa",
    "作业指导书": "hse_guidance",
    "操作规程": "hse_guidance",
    "作业计划书": "hse_plan",
    "体检": "medical_exam",
    "保险": "insurance",
    "机具报验": "equipment_inspection",
    "设备报验": "equipment_inspection",
    "材料报验": "material_inspection",
    "应急预案": "emergency_plan",
    "应急演练计划": "emergency_drill_plan",
    "应急演练记录": "emergency_drill_record",
    "hse承诺书": "hse_commitment",
    "全员安全承诺书": "all_staff_commitment",
    "监督管理规定": "regulation",
    "开工报告": "commencement_report",
    "施工组织设计": "construction_plan",
    "劳动合同": "labor_contract",
    "安全教育记录": "safety_education_training_record",
    "培训资料": "training_material",
    "安全技术交底": "technical_briefing",
    "考试卷": "exam_record",
    "合格证": "contractor_certificate",
    "准入评估表": "access_assessment",
    "资质审查记录": "qualification_review_record",
    "任命书": "appointment_letter",
    "关键岗位人员报审表": "key_role_form",
    "社保": "social_security",
}


def _normalize_token(value: str) -> str:
    lowered = value.strip().lower().replace("-", "_").replace(" ", "_")
    lowered = re.sub(r"_+", "_", lowered)
    return lowered


def normalize_doc_type(value: str | None) -> str | None:
    if not value:
        return value

    token = _normalize_token(value)
    if token in DOC_TYPE_ALIAS_TO_CANONICAL:
        return DOC_TYPE_ALIAS_TO_CANONICAL[token]

    # Retry with separators removed for variants like constructioncontract
    compact = token.replace("_", "")
    return DOC_TYPE_ALIAS_TO_CANONICAL.get(compact, value)
