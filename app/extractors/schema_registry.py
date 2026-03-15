from __future__ import annotations

from typing import Any

HIGH_VALUE_DOC_TYPES: set[str] = {
    "construction_contract",
    "personnel_qualification_review_form",
    "entry_permit",
    "safety_education_training_record",
    "jsa",
    "construction_plan",
    "emergency_plan",
    "equipment_inspection",
    "material_inspection",
}

MEDIUM_VALUE_DOC_TYPES: set[str] = {
    "training_material",
    "training_record",
    "technical_briefing",
    "key_role_form",
    "all_staff_commitment",
    "insurance",
    "medical_exam",
    "social_security",
    "labor_contract",
    "appointment_letter",
    "commencement_report",
    "access_assessment",
    "qualification_review_record",
    "contractor_certificate",
    "qualification_form",
    "emergency_drill_plan",
    "emergency_drill_record",
    "hse_commitment",
}

LOW_VALUE_DOC_TYPES: set[str] = {
    "exam_record",
    "hse_guidance",
    "hse_plan",
    "regulation",
}

DOC_TYPE_VALUE_TIER: dict[str, str] = {
    **{doc_type: "high" for doc_type in HIGH_VALUE_DOC_TYPES},
    **{doc_type: "medium" for doc_type in MEDIUM_VALUE_DOC_TYPES},
    **{doc_type: "low" for doc_type in LOW_VALUE_DOC_TYPES},
}


def _build_json_schema(
    *,
    properties: dict[str, dict[str, Any]],
    required_fields: list[str],
    additional_properties: bool = True,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required_fields,
        "additionalProperties": additional_properties,
    }


def _schema(
    *,
    schema_name: str,
    properties: dict[str, dict[str, Any]],
    required_fields: list[str] | None = None,
    field_aliases: dict[str, str] | None = None,
    required_any_of: list[list[str]] | None = None,
    core_fields: list[str] | None = None,
) -> dict[str, Any]:
    req = required_fields or []
    schema_core_fields = core_fields or sorted(properties.keys())
    return {
        "schema_name": schema_name,
        "schema_version": "1.2.0",
        "required_fields": req,
        "required_any_of": required_any_of or [],
        "core_fields": schema_core_fields,
        "field_aliases": field_aliases or {},
        "json_schema": _build_json_schema(properties=properties, required_fields=req, additional_properties=True),
    }


ARR_STR = {"type": "array", "items": {"type": "string"}}
ARR_OBJ = {"type": "array", "items": {"type": "object"}}
STR = {"type": "string"}

DOC_TYPE_SCHEMA_REGISTRY: dict[str, dict[str, Any]] = {
    # Rule-engine critical doc types (keep canonical names stable)
    "construction_contract": _schema(
        schema_name="construction_contract",
        properties={
            "project_name": STR,
            "contractor_name": STR,
            "contract_no": STR,
            "effective_date": STR,
            "party_a": STR,
            "party_b": STR,
            "contract_price": STR,
            "project_scope": STR,
        },
        required_fields=["project_name", "contract_no", "effective_date"],
        field_aliases={
            "project": "project_name",
            "projectName": "project_name",
            "项目名称": "project_name",
            "contract_number": "contract_no",
            "合同编号": "contract_no",
            "合同号": "contract_no",
            "contract_date": "effective_date",
            "签订日期": "effective_date",
            "甲方": "party_a",
            "乙方": "party_b",
        },
    ),
    "personnel_qualification_review_form": _schema(
        schema_name="personnel_qualification_review_form",
        properties={
            "project_name": STR,
            "person_name": STR,
            "id_no": STR,
            "role": STR,
            "certificate_no": STR,
            "certificate_valid_until": STR,
            "contractor_name": STR,
            "personnel_details": ARR_STR,
        },
        required_fields=["person_name", "role", "certificate_no", "certificate_valid_until"],
        field_aliases={
            "name": "person_name",
            "person": "person_name",
            "姓名": "person_name",
            "身份证号": "id_no",
            "岗位": "role",
            "certificate_number": "certificate_no",
            "证书编号": "certificate_no",
            "证书有效期": "certificate_valid_until",
        },
    ),
    "entry_permit": _schema(
        schema_name="entry_permit",
        properties={
            "project_name": STR,
            "person_name": STR,
            "id_no": STR,
            "role": STR,
            "permit_no": STR,
            "permit_date": STR,
            "contractor_name": STR,
            "permitted_personnel": ARR_STR,
            "permit_count": STR,
        },
        required_fields=["person_name", "role", "permit_no", "permit_date"],
        field_aliases={
            "name": "person_name",
            "姓名": "person_name",
            "身份证号": "id_no",
            "工种": "role",
            "岗位": "role",
            "角色": "role",
            "permit_number": "permit_no",
            "许可证编号": "permit_no",
            "许可证号": "permit_no",
            "证号": "permit_no",
            "编号": "permit_no",
            "date": "permit_date",
            "日期": "permit_date",
            "发证日期": "permit_date",
            "办证日期": "permit_date",
        },
    ),
    "safety_education_training_record": _schema(
        schema_name="safety_education_training_record",
        properties={
            "project_name": STR,
            "person_name": STR,
            "id_no": STR,
            "training_topic": STR,
            "training_date": STR,
            "trainer": STR,
            "contractor_name": STR,
            "attendees": ARR_STR,
            "attendees_signatures": ARR_STR,
        },
        required_fields=["person_name", "training_date", "trainer"],
        field_aliases={
            "topic": "training_topic",
            "培训主题": "training_topic",
            "date": "training_date",
            "日期": "training_date",
            "instructor": "trainer",
            "讲师": "trainer",
        },
    ),
    "jsa": _schema(
        schema_name="jsa",
        properties={
            "project_name": STR,
            "activity": STR,
            "hazards": ARR_STR,
            "controls": ARR_STR,
            "prepared_by": STR,
            "identified_risks": ARR_STR,
            "control_measures": ARR_STR,
        },
        required_fields=["hazards", "controls"],
        field_aliases={
            "task_description": "activity",
            "作业内容": "activity",
            "major_risks": "hazards",
            "risks": "hazards",
            "风险": "hazards",
            "control_actions": "controls",
            "措施": "controls",
            "控制措施": "controls",
            "防控措施": "controls",
            "author": "prepared_by",
        },
    ),

    # Round-2 extraction priority doc types
    "hse_guidance": _schema(
        schema_name="hse_guidance",
        properties={
            "doc_type": STR,
            "document_present": STR,
            "anchor_terms": ARR_STR,
            "notes": STR,
        },
        required_fields=[],
        field_aliases={
            "项目名称": "notes",
            "地点": "anchor_terms",
            "location": "anchor_terms",
            "编制": "anchor_terms",
            "审核": "anchor_terms",
            "批准": "anchor_terms",
            "规程": "anchor_terms",
        },
        core_fields=["doc_type", "document_present", "anchor_terms", "notes"],
    ),
    "hse_plan": _schema(
        schema_name="hse_plan",
        properties={
            "doc_type": STR,
            "document_present": STR,
            "anchor_terms": ARR_STR,
            "notes": STR,
        },
        required_fields=[],
        field_aliases={
            "项目名称": "notes",
            "地点": "anchor_terms",
            "location": "anchor_terms",
            "费用项": "anchor_terms",
        },
        core_fields=["doc_type", "document_present", "anchor_terms", "notes"],
    ),
    "medical_exam": _schema(
        schema_name="medical_exam",
        properties={
            "examinee": STR,
            "examinees": ARR_STR,
            "date": STR,
            "hospital": STR,
            "result": STR,
            "notes": STR,
        },
        required_fields=[],
        field_aliases={
            "name": "examinee",
            "person_name": "examinee",
            "姓名": "examinee",
            "人员": "examinees",
            "persons": "examinees",
            "exam_date": "date",
            "检查日期": "date",
            "hospital_name": "hospital",
            "体检机构": "hospital",
            "exam_result": "result",
            "结论": "result",
        },
        core_fields=["examinee", "examinees", "date", "hospital", "result"],
    ),
    "insurance": _schema(
        schema_name="insurance",
        properties={
            "insurance_company": STR,
            "insured_personnel": ARR_STR,
            "insured_personnel_count": STR,
            "coverage_amount": STR,
            "notes": STR,
        },
        required_fields=[],
        field_aliases={
            "company": "insurance_company",
            "insurer": "insurance_company",
            "保险公司": "insurance_company",
            "insured_people": "insured_personnel",
            "insured_persons": "insured_personnel",
            "人员": "insured_personnel",
            "count": "insured_personnel_count",
            "人数": "insured_personnel_count",
            "coverage": "coverage_amount",
            "保额": "coverage_amount",
        },
        core_fields=["insurance_company", "insured_personnel_count", "coverage_amount", "insured_personnel"],
    ),
    "equipment_inspection": _schema(
        schema_name="equipment_inspection",
        properties={
            "auditor": STR,
            "date": STR,
            "equipment": ARR_STR,
        },
        required_fields=["equipment"],
        field_aliases={
            "reviewer": "auditor",
            "检查人": "auditor",
            "inspection_date": "date",
            "日期": "date",
            "equipment_list": "equipment",
            "机具": "equipment",
            "设备": "equipment",
        },
    ),
    "material_inspection": _schema(
        schema_name="material_inspection",
        properties={
            "date": STR,
            "materials": ARR_STR,
            "signed_by": ARR_STR,
        },
        required_fields=["materials"],
        field_aliases={
            "inspection_date": "date",
            "日期": "date",
            "material_list": "materials",
            "物资": "materials",
            "签字": "signed_by",
            "signatures": "signed_by",
        },
    ),
    "emergency_plan": _schema(
        schema_name="emergency_plan",
        properties={
            "emergency_materials": ARR_STR,
            "hazards_identified": ARR_STR,
        },
        required_fields=["emergency_materials", "hazards_identified"],
        field_aliases={
            "materials": "emergency_materials",
            "应急物资": "emergency_materials",
            "major_risks": "hazards_identified",
            "hazards": "hazards_identified",
            "风险": "hazards_identified",
        },
    ),
    "emergency_drill_plan": _schema(
        schema_name="emergency_drill_plan",
        properties={
            "drill_topics": ARR_STR,
            "planned_dates": ARR_STR,
        },
        required_fields=[],
        field_aliases={
            "topics": "drill_topics",
            "演练科目": "drill_topics",
            "dates": "planned_dates",
            "计划日期": "planned_dates",
        },
    ),
    "emergency_drill_record": _schema(
        schema_name="emergency_drill_record",
        properties={
            "attendees": ARR_STR,
            "date": STR,
            "instructor": STR,
        },
        required_fields=[],
        field_aliases={
            "participants": "attendees",
            "参演人员": "attendees",
            "drill_date": "date",
            "日期": "date",
            "trainer": "instructor",
            "讲师": "instructor",
        },
    ),

    # High-frequency non-priority but easy-win doc types
    "hse_commitment": _schema(
        schema_name="hse_commitment",
        properties={
            "project_name": STR,
            "contractor_name": STR,
            "contractor_signature": STR,
            "date": STR,
        },
        required_fields=[],
    ),
    "all_staff_commitment": _schema(
        schema_name="all_staff_commitment",
        properties={
            "date": STR,
            "signatures": ARR_STR,
        },
        required_fields=[],
        field_aliases={
            "signed_by": "signatures",
            "签字": "signatures",
            "签名": "signatures",
        },
    ),
    "regulation": _schema(
        schema_name="regulation",
        properties={
            "doc_type": STR,
            "document_present": STR,
            "anchor_terms": ARR_STR,
            "notes": STR,
        },
        required_fields=[],
        core_fields=["doc_type", "document_present", "anchor_terms", "notes"],
    ),
    "commencement_report": _schema(
        schema_name="commencement_report",
        properties={
            "project_name": STR,
            "planned_start_date": STR,
            "project_manager": STR,
            "date": STR,
        },
        required_fields=[],
    ),
    "construction_plan": _schema(
        schema_name="construction_plan",
        properties={
            "project_scope": STR,
            "equipment_plan": ARR_STR,
            "risk_items": ARR_STR,
            "emergency_contacts": ARR_STR,
            "emergency_contact_list": ARR_STR,
            "emergency_materials": ARR_STR,
            "emergency_measures": ARR_STR,
        },
        required_fields=["risk_items", "emergency_materials", "equipment_plan"],
        required_any_of=[["emergency_contacts", "emergency_contact_list"]],
        field_aliases={
            "scope": "project_scope",
            "工程范围": "project_scope",
            "风险项": "risk_items",
            "risks": "risk_items",
            "risk_items": "risk_items",
            "contacts": "emergency_contacts",
            "应急联系人": "emergency_contact_list",
            "应急联系电话": "emergency_contact_list",
            "emergency_contacts": "emergency_contact_list",
            "materials": "emergency_materials",
            "应急物资": "emergency_materials",
            "measures": "emergency_measures",
            "应急措施": "emergency_measures",
        },
        core_fields=[
            "project_scope",
            "equipment_plan",
            "risk_items",
            "emergency_contacts",
            "emergency_contact_list",
            "emergency_materials",
            "emergency_measures",
        ],
    ),
    "labor_contract": _schema(
        schema_name="labor_contract",
        properties={
            "employer": STR,
            "employees": ARR_STR,
            "location": STR,
        },
        required_fields=[],
    ),
    "training_record": _schema(
        schema_name="training_record",
        properties={
            "date": STR,
            "attendees": ARR_STR,
            "instructor": STR,
            "training_content": STR,
        },
        required_fields=[],
        field_aliases={
            "training_date": "date",
            "日期": "date",
            "trainer": "instructor",
            "讲师": "instructor",
            "content": "training_content",
        },
        core_fields=["date", "attendees", "instructor", "training_content"],
    ),
    "training_material": _schema(
        schema_name="training_material",
        properties={
            "training_date": STR,
            "location": STR,
            "instructor": STR,
            "attendees_signatures": ARR_STR,
            "training_content": ARR_STR,
        },
        required_fields=[],
        field_aliases={
            "date": "training_date",
            "日期": "training_date",
            "attendees": "attendees_signatures",
            "signed_by": "attendees_signatures",
            "signatures": "attendees_signatures",
            "参训人员签名": "attendees_signatures",
            "培训地点": "location",
        },
        core_fields=["training_date", "instructor", "attendees_signatures", "location"],
    ),
    "technical_briefing": _schema(
        schema_name="technical_briefing",
        properties={
            "date": STR,
            "instructor": STR,
            "receiver_signatures": ARR_STR,
            "identified_risks": ARR_STR,
            "control_measures": ARR_STR,
        },
        required_fields=[],
    ),
    "exam_record": _schema(
        schema_name="exam_record",
        properties={
            "doc_type": STR,
            "is_exam_paper": STR,
            "handwritten_exam": STR,
            "score_detected": STR,
            "score_value": STR,
            "participant_name": STR,
            "notes": STR,
        },
        required_fields=[],
        core_fields=[
            "doc_type",
            "is_exam_paper",
            "handwritten_exam",
            "score_detected",
            "score_value",
            "participant_name",
            "notes",
        ],
    ),
    "contractor_certificate": _schema(
        schema_name="contractor_certificate",
        properties={
            "certificate_date": STR,
            "contractor": STR,
        },
        required_fields=[],
    ),
    "access_assessment": _schema(
        schema_name="access_assessment",
        properties={
            "date": STR,
            "auditor": STR,
            "result": STR,
            "items": ARR_STR,
        },
        required_fields=[],
    ),
    "qualification_review_record": _schema(
        schema_name="qualification_review_record",
        properties={
            "date": STR,
            "reviewer": STR,
            "personnel_details": ARR_STR,
            "result": STR,
        },
        required_fields=[],
    ),
    "appointment_letter": _schema(
        schema_name="appointment_letter",
        properties={
            "appointed_person": STR,
            "role": STR,
            "appointer": STR,
            "date": STR,
        },
        required_fields=[],
    ),
    "qualification_form": _schema(
        schema_name="qualification_form",
        properties={
            "personnel_details": ARR_STR,
            "date": STR,
        },
        required_fields=[],
    ),
    "key_role_form": _schema(
        schema_name="key_role_form",
        properties={
            "personnel": ARR_OBJ,
            "contractor_signature": STR,
            "date": STR,
        },
        required_fields=[],
        field_aliases={
            "key_personnel": "personnel",
            "岗位人员": "personnel",
            "承包商签字": "contractor_signature",
            "签字": "contractor_signature",
        },
    ),
    "social_security": _schema(
        schema_name="social_security",
        properties={
            "personnel": ARR_STR,
            "date": STR,
            "company_name": STR,
        },
        required_fields=[],
    ),
}

for doc_type, schema in DOC_TYPE_SCHEMA_REGISTRY.items():
    value_tier = DOC_TYPE_VALUE_TIER.get(doc_type, "medium")
    schema["value_tier"] = value_tier
    schema["extraction_strategy"] = {
        "high": "strong",
        "medium": "light",
        "low": "weak",
    }.get(value_tier, "light")
    schema.setdefault("core_fields", sorted((schema.get("json_schema", {}).get("properties", {}) or {}).keys()))
    schema.setdefault("required_any_of", [])

SUPPORTED_MVP_DOC_TYPES: set[str] = set(DOC_TYPE_SCHEMA_REGISTRY.keys())


def get_schema_for_doc_type(doc_type: str) -> dict[str, Any] | None:
    return DOC_TYPE_SCHEMA_REGISTRY.get(doc_type)
