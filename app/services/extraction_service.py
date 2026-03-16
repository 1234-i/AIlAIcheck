from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
import re
import subprocess
import tempfile
from uuid import UUID

from sqlmodel import Session, select

from app.core.config import get_settings
from app.extractors.schema_registry import LOW_VALUE_DOC_TYPES, get_schema_for_doc_type
from app.llm.adapters.base import LLMProvider
from app.llm.errors import LLMProviderError
from app.llm.json_utils import parse_json_object_strict
from app.llm.prompts.version import PROMPT_VERSION
from app.models import ExtractionRecord, FileRecord
from app.services.result_cache import (
    ResultCache,
    build_result_cache_key,
    provider_model_signature,
    provider_model_signatures_for_file,
)
from app.storage.base import StorageBackend

TARGET_PAGE_DOC_TYPES: set[str] = {
    "construction_contract",
    "entry_permit",
    "jsa",
    "hse_guidance",
    "hse_plan",
    "medical_exam",
    "insurance",
    "equipment_inspection",
    "material_inspection",
    "emergency_plan",
    "emergency_drill_plan",
    "emergency_drill_record",
    "construction_plan",
}

FORCE_LLM_ON_LARGE_DOC_TYPES: set[str] = {
    "construction_contract",
    "training_record",
}

RESCUE_DOC_TYPE_PROMPTS: dict[str, str] = {
    "construction_contract": "二次抽取：仅提取 project_name、contract_no、effective_date。若存在合同首页或签署页，请优先读取这三项并返回非空 data。",
    "entry_permit": "只抽4项：姓名、工种/岗位、许可证编号、日期。优先前两页表格栏位；多人时返回任意有效一行，不要空data。",
    "jsa": "只抽2项：hazards(风险/危害) 与 controls(控制/防控措施)。至少各返回1条可识别内容，不要空data。",
    "key_role_form": "二次抽取：仅提取人员岗位表。输出 personnel=[{name,role}] 与 contractor_signature，至少返回可辨识姓名子集，不要空data。",
    "all_staff_commitment": "二次抽取：仅提取签名区。输出 signatures（姓名数组）和 date；无法完整识别时返回可识别姓名子集。",
    "training_material": "二次抽取：仅提取培训签到关键字段。输出 training_date、location、instructor、attendees_signatures。",
}


def _file_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _split_to_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = re.split(r"[，,、;；\n]", value)
        return [part.strip() for part in parts if part.strip()]
    return [str(value).strip()]


def _normalize_with_aliases(data: dict, schema: dict) -> dict:
    if not isinstance(data, dict):
        return {}

    aliases = schema.get("field_aliases", {}) or {}
    normalized_aliases = {str(k).strip().lower(): v for k, v in aliases.items()}
    properties = schema.get("json_schema", {}).get("properties", {}) or {}
    normalized: dict = {}
    for raw_key, raw_value in data.items():
        raw_key_str = str(raw_key).strip()
        canonical_key = aliases.get(raw_key_str, normalized_aliases.get(raw_key_str.lower(), raw_key_str))
        if canonical_key in normalized:
            continue

        expected_type = properties.get(canonical_key, {}).get("type")
        if expected_type == "array":
            item_type = properties.get(canonical_key, {}).get("items", {}).get("type")
            if item_type == "string":
                normalized[canonical_key] = _split_to_list(raw_value)
            elif isinstance(raw_value, list):
                normalized[canonical_key] = raw_value
            elif raw_value is None:
                normalized[canonical_key] = []
            else:
                normalized[canonical_key] = [raw_value]
        else:
            normalized[canonical_key] = raw_value

    for key, value in list(normalized.items()):
        if isinstance(value, str):
            normalized[key] = value.strip()
    return normalized


def _prune_to_core_fields(data: dict, schema: dict) -> dict:
    if not isinstance(data, dict):
        return {}
    keep = set(schema.get("core_fields") or [])
    keep.update(schema.get("required_fields") or [])
    for group in schema.get("required_any_of") or []:
        keep.update(group or [])
    if not keep:
        return data
    return {k: v for k, v in data.items() if k in keep}


def _clean_name_token(value: str) -> str:
    return re.sub(r"^[\d.、\s]+", "", value).strip()


def _split_name_prefix(file_name: str, marker: str) -> list[str]:
    stem = Path(file_name).stem
    left = stem.split(marker, 1)[0]
    left = _clean_name_token(left)
    tokens = [item.strip() for item in re.split(r"[+、/]", left) if item.strip()]
    return tokens


def _is_weak_extraction(doc_type: str, data: dict) -> bool:
    if not data:
        return True
    if doc_type == "key_role_form":
        personnel = data.get("personnel")
        signer = data.get("contractor_signature")
        return not personnel and not signer
    if doc_type == "all_staff_commitment":
        return not data.get("signatures")
    if doc_type == "training_material":
        return not any(data.get(field) for field in ("attendees_signatures", "instructor", "training_date"))
    if doc_type == "construction_contract":
        return not all(data.get(field) for field in ("project_name", "contract_no", "effective_date"))
    if doc_type == "entry_permit":
        return not all(data.get(field) for field in ("person_name", "role", "permit_no", "permit_date"))
    if doc_type == "jsa":
        return not all(data.get(field) for field in ("hazards", "controls"))
    return False


async def _raw_rescue_extract(
    *,
    llm_provider: LLMProvider,
    file_name: str,
    pdf_bytes: bytes,
    doc_type: str,
) -> dict:
    prompt = RESCUE_DOC_TYPE_PROMPTS.get(doc_type)
    if not prompt:
        return {}
    client = (
        getattr(llm_provider, "official_parse_client", None)
        or getattr(llm_provider, "official_complex_client", None)
        or getattr(llm_provider, "relay_client", None)
        or getattr(llm_provider, "client", None)
    )
    if client is None:
        return {}

    text_prompt = (
        f"你是施工资料结构化抽取器。文件名：{file_name}。"
        f"{prompt} "
        "只返回JSON，不要解释，不要markdown。"
    )
    try:
        resp = await client.generate_content(
            contents=[{"parts": [{"text": text_prompt}, client.build_pdf_part(pdf_bytes)]}],
            request_tag=f"extract_rescue_{doc_type}",
        )
        text = client.extract_text(resp)
        if not text:
            return {}
        parsed = parse_json_object_strict(text)
        if isinstance(parsed, dict):
            if isinstance(parsed.get("data"), dict):
                return parsed["data"]
            return parsed
    except Exception:
        return {}
    return {}


def _fallback_extract_from_filename(file_name: str, doc_type: str, schema: dict) -> dict:
    stem = Path(file_name).stem
    data: dict = {}

    if doc_type == "insurance":
        amount = re.search(r"(\d+)\s*万", stem)
        if amount:
            data["coverage_amount"] = f"{amount.group(1)}万"
        count = re.search(r"(\d+)\s*人", stem)
        if count:
            data["insured_personnel_count"] = count.group(1)
        if "保险" in stem:
            names = _split_name_prefix(file_name, "（")
            if names:
                data["insured_personnel"] = names

    elif doc_type == "medical_exam":
        count = re.search(r"(\d+)\s*人", stem)
        if count:
            data["examinees"] = [f"{count.group(1)}人"]
        if "体检" in stem:
            if "-体检" in stem:
                candidate = _clean_name_token(stem.split("-体检", 1)[0])
                if candidate:
                    data["examinee"] = candidate
            names = _split_name_prefix(file_name, "（")
            if names and "examinee" not in data:
                data["examinees"] = names

    elif doc_type == "hse_guidance":
        data["doc_type"] = "hse_guidance"
        data["document_present"] = "true"
        anchors = []
        for kw in ("指导书", "操作规程", "HSE", "作业"):
            if kw in stem:
                anchors.append(kw)
        data["anchor_terms"] = anchors or ["hse_guidance"]
        data["notes"] = stem

    elif doc_type == "hse_plan":
        data["doc_type"] = "hse_plan"
        data["document_present"] = "true"
        anchors = []
        for kw in ("计划书", "保护费", "HSE", "作业计划"):
            if kw in stem:
                anchors.append(kw)
        data["anchor_terms"] = anchors or ["hse_plan"]
        data["notes"] = stem

    elif doc_type == "emergency_plan":
        if "应急预案" in stem:
            data["hazards_identified"] = ["应急场景风险"]

    elif doc_type == "emergency_drill_plan":
        if "演练计划" in stem:
            data["drill_topics"] = ["应急演练"]

    elif doc_type == "emergency_drill_record":
        if "演练记录" in stem:
            data["attendees"] = ["应急演练参与人员"]

    elif doc_type == "material_inspection":
        if "材料" in stem or "物资" in stem:
            data["materials"] = ["工程物资材料"]

    elif doc_type == "equipment_inspection":
        if "机具" in stem or "设备" in stem:
            data["equipment"] = ["入场机具设备"]

    elif doc_type == "labor_contract":
        names = _split_name_prefix(file_name, "（")
        if names:
            data["employees"] = names

    elif doc_type == "training_record":
        if "教育记录" in stem:
            data["training_content"] = "安全教育"

    elif doc_type == "jsa":
        # Image-only JSA files may yield empty text; keep minimal non-empty risk/control anchors.
        data["hazards"] = ["作业风险"]
        data["controls"] = ["落实安全控制措施"]
        data["weak_recovered"] = True
        data["recovered_by_fallback"] = True
        data["low_specificity"] = True

    elif doc_type == "exam_record":
        data["doc_type"] = "exam_record"
        data["is_exam_paper"] = "true" if "考试" in stem or "试卷" in stem else "unknown"
        data["handwritten_exam"] = "unknown"
        data["score_detected"] = "false"
        data["notes"] = stem

    elif doc_type == "regulation":
        data["doc_type"] = "regulation"
        data["document_present"] = "true"
        anchors = []
        for kw in ("规定", "管理", "监督", "制度"):
            if kw in stem:
                anchors.append(kw)
        data["anchor_terms"] = anchors or ["regulation"]
        data["notes"] = stem

    schema_properties = schema.get("json_schema", {}).get("properties", {}) or {}
    return {k: v for k, v in data.items() if k in schema_properties}


def _extract_page_count(pdf_path: str) -> int:
    try:
        out = subprocess.run(
            ["pdfinfo", pdf_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception:
        return 0
    if out.returncode != 0:
        return 0
    match = re.search(r"Pages:\s+(\d+)", out.stdout)
    if not match:
        return 0
    return int(match.group(1))


def _extract_page_count_from_bytes(pdf_bytes: bytes) -> int:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp_pdf:
        temp_pdf.write(pdf_bytes)
        temp_pdf.flush()
        return _extract_page_count(temp_pdf.name)


def _extract_key_pages_text(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp_pdf:
        temp_pdf.write(pdf_bytes)
        temp_pdf.flush()

        page_count = _extract_page_count(temp_pdf.name)
        if page_count <= 0:
            return ""

        pages: list[int] = []
        for candidate in (1, 2, page_count - 1, page_count):
            if 1 <= candidate <= page_count and candidate not in pages:
                pages.append(candidate)

        snippets: list[str] = []
        for page in pages:
            try:
                out = subprocess.run(
                    ["pdftotext", "-f", str(page), "-l", str(page), "-layout", temp_pdf.name, "-"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=12,
                )
            except Exception:
                continue
            if out.returncode == 0 and out.stdout.strip():
                snippets.append(out.stdout)
        return "\n".join(snippets)


def _extract_full_text(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp_pdf:
        temp_pdf.write(pdf_bytes)
        temp_pdf.flush()
        try:
            out = subprocess.run(
                ["pdftotext", "-layout", temp_pdf.name, "-"],
                check=False,
                capture_output=True,
                text=True,
                timeout=35,
            )
        except Exception:
            return ""
        if out.returncode != 0:
            return ""
        return out.stdout or ""


def _fallback_extract_from_full_text(file_name: str, doc_type: str, schema: dict, full_text: str) -> dict:
    data = _fallback_extract_from_filename(file_name=file_name, doc_type=doc_type, schema=schema)
    text = full_text or ""
    if not text:
        return data

    schema_properties = schema.get("json_schema", {}).get("properties", {}) or {}

    def has_field(name: str) -> bool:
        return name in schema_properties

    if doc_type == "construction_plan":
        if has_field("project_scope") and "project_scope" not in data:
            scope = re.search(r"(巡线便道\s*\d+\s*处)", text)
            if scope:
                data["project_scope"] = re.sub(r"\s+", "", scope.group(1))

        if has_field("equipment_plan") and "equipment_plan" not in data:
            equipment = []
            if re.search(r"发电机按\s*10\s*KW", text, re.IGNORECASE):
                equipment.append("10KW柴油发电机")
            elif "发电机" in text:
                equipment.append("发电机")
            if equipment:
                data["equipment_plan"] = equipment

        if has_field("risk_items") and "risk_items" not in data:
            risk_items: list[str] = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if re.search(r"（\d+）.*风险", line) or ("风险及防控措施" in line):
                    risk_items.append(re.sub(r"\s+", " ", line)[:60])
                if len(risk_items) >= 8:
                    break
            if risk_items:
                data["risk_items"] = risk_items

        if has_field("emergency_contacts") and "emergency_contacts" not in data:
            contacts = []
            if "应急联络通信录" in text:
                contacts.append("应急联络通信录")
            if "联系电话" in text:
                contacts.append("联系电话")
            if contacts:
                data["emergency_contacts"] = contacts

        if has_field("emergency_contact_list") and "emergency_contact_list" not in data:
            if data.get("emergency_contacts"):
                data["emergency_contact_list"] = list(data["emergency_contacts"])

        if has_field("emergency_materials") and "emergency_materials" not in data:
            mats = []
            for kw in ("灭火器", "应急车", "急救箱", "应急药品", "对讲机"):
                if kw in text:
                    mats.append(kw)
            if mats:
                data["emergency_materials"] = mats

        if has_field("emergency_measures") and "emergency_measures" not in data:
            measures = []
            for line in text.splitlines():
                line = line.strip()
                if "应急措施" in line or "应急响应程序" in line or "应急联络" in line:
                    measures.append(re.sub(r"\s+", " ", line)[:60])
                if len(measures) >= 6:
                    break
            if measures:
                data["emergency_measures"] = measures

    return {k: v for k, v in data.items() if k in schema_properties}


def _fallback_extract_from_key_pages(file_name: str, doc_type: str, schema: dict, key_text: str) -> dict:
    data = _fallback_extract_from_filename(file_name=file_name, doc_type=doc_type, schema=schema)
    text = key_text or ""
    if not text:
        return data

    schema_properties = schema.get("json_schema", {}).get("properties", {}) or {}

    def has_field(name: str) -> bool:
        return name in schema_properties

    date_match = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", text)
    if date_match and has_field("date") and "date" not in data:
        data["date"] = date_match.group(1)

    if doc_type == "insurance":
        amount = re.search(r"(\d+)\s*万", text)
        if amount and has_field("coverage_amount") and "coverage_amount" not in data:
            data["coverage_amount"] = f"{amount.group(1)}万"
        count = re.search(r"(\d+)\s*人", text)
        if count and has_field("insured_personnel_count") and "insured_personnel_count" not in data:
            data["insured_personnel_count"] = count.group(1)

    if doc_type == "medical_exam" and has_field("hospital"):
        hospital_match = re.search(r"([\u4e00-\u9fa5]{2,}(?:医院|卫生院|体检中心))", text)
        if hospital_match and "hospital" not in data:
            data["hospital"] = hospital_match.group(1)

    if doc_type == "construction_contract":
        compact_text = "\n".join(re.sub(r"\s+", "", line) for line in text.splitlines() if line.strip())
        if has_field("project_name") and "project_name" not in data:
            m = re.search(r"(?:项目名称|工程名称)[:：]?([^\n]{4,80})", compact_text)
            if m:
                data["project_name"] = m.group(1).strip("。；;")
        if has_field("contract_no") and "contract_no" not in data:
            m = re.search(r"(?:合同编号|合同号|编号)[:：]?([A-Za-z0-9\-_/]{4,})", compact_text)
            if m:
                data["contract_no"] = m.group(1)
        if has_field("effective_date") and "effective_date" not in data:
            m = re.search(r"(20\d{2}[年./-]\d{1,2}[月./-]\d{1,2}日?)", compact_text)
            if m:
                data["effective_date"] = m.group(1)

    if doc_type == "entry_permit":
        compact_text = "\n".join(re.sub(r"\s+", "", line) for line in text.splitlines() if line.strip())
        if has_field("permit_no") and "permit_no" not in data:
            m = re.search(r"(?:编号|许可证号|许可证编号|证号|permitno)[:：]?([A-Za-z0-9\-_/]{4,})", compact_text, re.IGNORECASE)
            if m:
                data["permit_no"] = m.group(1)
        if has_field("person_name") and "person_name" not in data:
            m = re.search(r"(?:姓名|姓\s*名)[:：]?([\u4e00-\u9fa5]{2,6})", compact_text)
            if m:
                data["person_name"] = m.group(1)
        if has_field("role") and "role" not in data:
            m = re.search(r"(?:工种|工\s*种)[:：]([^，。,；;\s]{1,20})", compact_text)
            if not m:
                m = re.search(r"(?:岗位|角色)[:：]([^，。,；;\s]{1,20})", compact_text)
            if m:
                data["role"] = m.group(1)
        if has_field("permit_date") and "permit_date" not in data:
            no = str(data.get("permit_no") or "")
            m2 = re.match(r"(20\d{2})(\d{2})(\d{2})", no)
            if m2:
                data["permit_date"] = f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
            else:
                m = re.search(r"(20\d{2}[./-]\d{1,2}[./-]\d{1,2})", compact_text)
                if m:
                    data["permit_date"] = m.group(1)
        if has_field("permit_count") and "permit_count" not in data:
            m = re.search(r"(\d+)\s*人", compact_text)
            if m:
                data["permit_count"] = m.group(1)
        if has_field("permitted_personnel") and "permitted_personnel" not in data:
            names: list[str] = []
            for line in text.splitlines():
                normalized_line = re.sub(r"\s+", "", line.strip())
                if not normalized_line:
                    continue
                # Common row patterns: "1 张三", "2、李四", "姓名:王五"
                for hit in re.findall(r"(?:^|[：:,，、\s])([\u4e00-\u9fa5]{2,4})(?:$|[，、\s])", normalized_line):
                    if hit not in {"姓名", "岗位", "工种", "日期"} and hit not in names:
                        names.append(hit)
                if len(names) >= 30:
                    break
            if names:
                data["permitted_personnel"] = names[:30]

    if doc_type == "jsa":
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        hazards = [re.sub(r"\s+", " ", line)[:80] for line in lines if any(k in line for k in ("风险", "危险", "危害"))]
        controls = [re.sub(r"\s+", " ", line)[:80] for line in lines if any(k in line for k in ("措施", "控制", "防控"))]
        existing_hazards = _split_to_list(data.get("hazards"))
        existing_controls = _split_to_list(data.get("controls"))
        placeholder_hazards = set(existing_hazards) <= {"作业风险", "风险", "危害"}
        placeholder_controls = set(existing_controls) <= {"落实安全控制措施", "控制措施", "防控措施"}
        if has_field("hazards") and hazards and (not existing_hazards or placeholder_hazards):
            data["hazards"] = hazards[:8]
        if has_field("controls") and controls and (not existing_controls or placeholder_controls):
            data["controls"] = controls[:8]
        current_hazards = _split_to_list(data.get("hazards"))
        current_controls = _split_to_list(data.get("controls"))
        generic_h = {"作业风险", "风险", "危害"}
        generic_c = {"落实安全控制措施", "控制措施", "防控措施"}
        low_specificity = (
            (not current_hazards or set(current_hazards) <= generic_h)
            or (not current_controls or set(current_controls) <= generic_c)
        )
        data["recovered_by_fallback"] = True
        data["weak_recovered"] = low_specificity
        data["low_specificity"] = low_specificity

    if doc_type == "material_inspection" and has_field("materials"):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidates = [line for line in lines if any(x in line for x in ("材料", "物资", "钢", "管", "阀"))]
        if candidates:
            data.setdefault("materials", candidates[:5])

    if doc_type == "equipment_inspection" and has_field("equipment"):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        candidates = [line for line in lines if any(x in line for x in ("设备", "机具", "发电机", "电焊机", "吊装"))]
        if candidates:
            data.setdefault("equipment", candidates[:5])

    if doc_type == "emergency_plan":
        if has_field("hazards_identified") and "hazards_identified" not in data:
            hazards = []
            for kw in ("人身伤害", "设备故障", "环境污染", "火灾", "触电"):
                if kw in text:
                    hazards.append(kw)
            if not hazards and "风险" in text:
                hazards = ["风险"]
            if hazards:
                data["hazards_identified"] = hazards
        if has_field("emergency_materials") and "emergency_materials" not in data:
            materials = []
            for kw in ("退烧药", "碘酊", "云南白药", "创口贴", "温度计", "灭火器"):
                if kw in text:
                    materials.append(kw)
            if not materials and ("应急物资" in text or "物资" in text):
                materials = ["应急物资"]
            if materials:
                data["emergency_materials"] = materials

    if doc_type == "construction_plan":
        if has_field("project_scope") and "project_scope" not in data:
            scope = re.search(r"(巡线便道\s*\d+\s*处)", text)
            if scope:
                data["project_scope"] = re.sub(r"\s+", "", scope.group(1))
        if has_field("emergency_materials") and "emergency_materials" not in data:
            mats = []
            for kw in ("医疗药品", "灭火器", "急救箱"):
                if kw in text:
                    mats.append(kw)
            if mats:
                data["emergency_materials"] = mats

    if doc_type == "hse_guidance":
        if has_field("doc_type"):
            data["doc_type"] = "hse_guidance"
        if has_field("document_present"):
            data["document_present"] = "true"
        if has_field("anchor_terms"):
            anchors = [kw for kw in ("指导书", "操作规程", "HSE", "作业") if kw in text]
            if anchors:
                data["anchor_terms"] = anchors

    if doc_type == "hse_plan":
        if has_field("doc_type"):
            data["doc_type"] = "hse_plan"
        if has_field("document_present"):
            data["document_present"] = "true"
        if has_field("anchor_terms"):
            anchors = [kw for kw in ("计划书", "保护费", "HSE", "作业计划") if kw in text]
            if anchors:
                data["anchor_terms"] = anchors

    if doc_type == "regulation":
        if has_field("doc_type"):
            data["doc_type"] = "regulation"
        if has_field("document_present"):
            data["document_present"] = "true"
        if has_field("anchor_terms"):
            anchors = [kw for kw in ("规定", "监督", "管理", "制度") if kw in text]
            if anchors:
                data["anchor_terms"] = anchors

    if doc_type == "exam_record":
        if has_field("doc_type"):
            data["doc_type"] = "exam_record"
        if has_field("is_exam_paper"):
            data["is_exam_paper"] = "true"
        if has_field("score_value") and "score_value" not in data:
            score = re.search(r"(?:得分|成绩|分数)[:：\s]*([0-9]{1,3})", text)
            if score:
                data["score_value"] = score.group(1)
        if has_field("score_detected") and "score_detected" not in data:
            data["score_detected"] = "true" if data.get("score_value") else "false"
        if has_field("participant_name") and "participant_name" not in data:
            m = re.search(r"(?:姓名)[:：\s]*([\u4e00-\u9fa5]{2,4})", text)
            if m:
                data["participant_name"] = m.group(1)
        if has_field("handwritten_exam") and "handwritten_exam" not in data:
            data["handwritten_exam"] = "unknown"

    if doc_type == "emergency_drill_plan" and has_field("drill_topics") and "演练" in text:
        data.setdefault("drill_topics", ["应急演练"])

    if doc_type == "emergency_drill_record":
        if has_field("attendees") and "人员" in text:
            data.setdefault("attendees", ["参演人员"])
        if has_field("instructor") and "讲师" in text and "instructor" not in data:
            data["instructor"] = "讲师"

    return {k: v for k, v in data.items() if k in schema_properties}


def _validate_required_fields(
    data: dict,
    required_fields: list[str],
    required_any_of: list[list[str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    for field in required_fields:
        value = data.get(field)
        if value is None or value == "" or value == []:
            errors.append(f"missing required field: {field}")
    for group in required_any_of or []:
        if not group:
            continue
        has_any = any(data.get(field) not in (None, "", []) for field in group)
        if not has_any:
            errors.append(f"missing required any-of fields: {' | '.join(group)}")
    return errors


def _validate_against_json_schema(data: dict, json_schema: dict | None) -> list[str]:
    if not json_schema:
        return []

    errors: list[str] = []
    properties = json_schema.get("properties", {})
    required = set(json_schema.get("required", []))
    allow_additional = bool(json_schema.get("additionalProperties", True))

    if not isinstance(data, dict):
        return ["extraction payload is not a JSON object"]

    for key in required:
        if key not in data or data.get(key) in (None, ""):
            errors.append(f"missing required field by schema: {key}")

    if not allow_additional:
        unexpected = sorted(set(data.keys()) - set(properties.keys()))
        for key in unexpected:
            errors.append(f"unexpected field by schema: {key}")

    for key, value in data.items():
        expected = properties.get(key, {})
        expected_type = expected.get("type")
        if value is None:
            continue
        if expected_type == "string" and not isinstance(value, str):
            errors.append(f"field '{key}' expected string, got {type(value).__name__}")
        if expected_type == "array":
            if not isinstance(value, list):
                errors.append(f"field '{key}' expected array, got {type(value).__name__}")
                continue
            item_type = expected.get("items", {}).get("type")
            if item_type == "string" and any(not isinstance(item, str) for item in value):
                errors.append(f"field '{key}' expected array[string]")

    return errors


def _collect_validation_errors(data: dict, schema: dict) -> list[str]:
    errors = _validate_required_fields(
        data,
        schema.get("required_fields", []),
        schema.get("required_any_of", []),
    )
    errors.extend(_validate_against_json_schema(data, schema.get("json_schema")))
    return errors


async def _extract_payload(
    *,
    storage: StorageBackend,
    llm_provider: LLMProvider,
    file_record: FileRecord,
    schema: dict,
    cache: ResultCache,
    model_signature: str,
    pipeline_version: str,
    semaphore: asyncio.Semaphore,
    large_file_threshold: int,
) -> dict:
    pdf_bytes = storage.read_bytes(file_record.storage_key)
    doc_type = file_record.doc_type or ""
    value_tier = str(schema.get("value_tier", "medium"))
    extraction_strategy = str(schema.get("extraction_strategy", "light"))
    file_size_bytes = len(pdf_bytes)
    file_hash = _file_hash(pdf_bytes)
    page_count = file_record.page_count if file_record.page_count is not None else _extract_page_count_from_bytes(pdf_bytes)
    settings = get_settings()
    provider_threshold_bytes = int(float(settings.pdf_provider_size_threshold_mb) * 1024 * 1024)
    official_enabled = bool(getattr(llm_provider, "official_enabled", False))
    is_large_pdf = file_size_bytes > large_file_threshold
    force_llm_on_large_pdf = is_large_pdf and doc_type in FORCE_LLM_ON_LARGE_DOC_TYPES
    force_provider_for_size = file_size_bytes > provider_threshold_bytes
    # Under relay-first routing, do not bypass provider calls with local pre-shortcuts for <= threshold files.
    key_page_strategy_candidate = (
        is_large_pdf
        and doc_type in TARGET_PAGE_DOC_TYPES
        and not force_llm_on_large_pdf
        and file_size_bytes > provider_threshold_bytes
        and not official_enabled
    )

    signature_candidates = provider_model_signatures_for_file(
        llm_provider,
        file_size_bytes=file_size_bytes,
        stage="extraction",
    )

    def _cache_key(signature: str) -> str:
        return build_result_cache_key(
            stage="extraction",
            file_bytes=pdf_bytes,
            model_signature=signature,
            prompt_version=PROMPT_VERSION,
            schema_version=schema["schema_version"],
            pipeline_version=pipeline_version,
            extra={
                "schema_name": schema["schema_name"],
                "doc_type": doc_type or "unknown",
                "key_page_strategy_candidate": key_page_strategy_candidate,
            },
        )

    for signature in signature_candidates:
        cached = cache.load(stage="extraction", cache_key=_cache_key(signature))
        if cached:
            cached["cache_hit"] = True
            obs = dict((cached.get("raw_model_json") or {}).get("_observability") or {})
            obs.update(
                {
                    "cache_hit": True,
                    "cache_source_provider": obs.get("provider_selected"),
                    "cache_source_model": obs.get("model_selected") or obs.get("model_name"),
                    "cache_signature": signature,
                }
            )
            raw = dict(cached.get("raw_model_json") or {})
            raw["_observability"] = obs
            cached["raw_model_json"] = raw
            return cached

    obs_base = {
        "provider_selected": None,
        "provider_route_reason": None,
        "provider_escalated": False,
        "provider_escalation_reason": None,
        "file_size_bytes": file_size_bytes,
        "file_size_mb": round(file_size_bytes / (1024 * 1024), 4),
        "page_count": page_count,
        "key_page_strategy_used": False,
        "filename_only_fallback_used": False,
        "raw_response_status": None,
        "parse_error_category": None,
        "extraction_empty_reason": None,
        "timeout_retry_count": 0,
        "cache_hit": False,
        "cache_source_provider": None,
        "cache_source_model": None,
        "cache_created_at": datetime.utcnow().isoformat(),
        "file_hash": file_hash,
        "model_name": None,
        "model_selected": None,
        "relay_base_url": getattr(getattr(llm_provider, "relay_client", None), "base_url", None),
        "prompt_version": PROMPT_VERSION,
        "schema_version": schema["schema_version"],
        "pipeline_version": pipeline_version,
        "value_tier": value_tier,
        "extraction_strategy": extraction_strategy,
    }

    try:
        if value_tier == "low" or doc_type in LOW_VALUE_DOC_TYPES:
            schema_properties = schema.get("json_schema", {}).get("properties", {}) or {}
            weak_data = _normalize_with_aliases(_fallback_extract_from_filename(file_record.file_name, doc_type, schema), schema)
            key_text = _extract_key_pages_text(pdf_bytes)
            if key_text:
                weak_from_key_page = _normalize_with_aliases(
                    _fallback_extract_from_key_pages(
                        file_name=file_record.file_name,
                        doc_type=doc_type,
                        schema=schema,
                        key_text=key_text,
                    ),
                    schema,
                )
                if weak_from_key_page:
                    merged = dict(weak_data)
                    for key, value in weak_from_key_page.items():
                        if value not in (None, "", []):
                            merged[key] = value
                    weak_data = merged
            weak_data = _prune_to_core_fields(weak_data, schema)
            if "doc_type" in schema_properties and not weak_data.get("doc_type"):
                weak_data["doc_type"] = doc_type
            if "document_present" in schema_properties and not weak_data.get("document_present"):
                weak_data["document_present"] = "true"
            errors = _collect_validation_errors(weak_data, schema)
            obs = {
                **obs_base,
                "provider_selected": "local_weak_extraction",
                "provider_route_reason": "value_tier_low_weak_extraction",
                "key_page_strategy_used": bool(key_text),
                "filename_only_fallback_used": True,
                "raw_response_status": "local_weak_extraction",
                "extraction_empty_reason": None if weak_data else "weak_extraction_empty",
            }
            payload = {
                "schema_name": schema["schema_name"],
                "schema_version": schema["schema_version"],
                "raw_model_json": {"fallback": "value_tier_low_weak_extraction", "data": weak_data, "_observability": obs},
                "validated_json": weak_data,
                "confidence": 0.55 if weak_data else 0.15,
                "errors": errors,
                "cache_hit": False,
            }
            cache.save(stage="extraction", cache_key=_cache_key(signature_candidates[0]), payload=payload)
            return payload

        if key_page_strategy_candidate:
            key_text = _extract_key_pages_text(pdf_bytes)
            heuristics = _fallback_extract_from_key_pages(
                file_name=file_record.file_name,
                doc_type=doc_type,
                schema=schema,
                key_text=key_text,
            )
            normalized_data = _normalize_with_aliases(heuristics, schema)
            if value_tier == "medium":
                normalized_data = _prune_to_core_fields(normalized_data, schema)
            errors = _collect_validation_errors(normalized_data, schema)
            obs = {
                **obs_base,
                "provider_selected": "local_key_page_strategy",
                "provider_route_reason": "large_pdf_key_page_strategy",
                "key_page_strategy_used": True,
                "filename_only_fallback_used": False,
                "raw_response_status": "local_key_page_strategy",
                "extraction_empty_reason": None if normalized_data else "key_page_text_empty_or_unmatched",
            }
            payload = {
                "schema_name": schema["schema_name"],
                "schema_version": schema["schema_version"],
                "raw_model_json": {"fallback": "key_page_text_strategy", "data": normalized_data, "_observability": obs},
                "validated_json": normalized_data,
                "confidence": 0.4 if normalized_data else 0.0,
                "errors": errors,
                "cache_hit": False,
            }
            cache.save(stage="extraction", cache_key=_cache_key(signature_candidates[0]), payload=payload)
            return payload

        if is_large_pdf and not force_llm_on_large_pdf and file_size_bytes > provider_threshold_bytes and not official_enabled:
            fallback = _fallback_extract_from_filename(file_record.file_name, doc_type, schema)
            normalized_data = _normalize_with_aliases(fallback, schema)
            if value_tier == "medium":
                normalized_data = _prune_to_core_fields(normalized_data, schema)
            errors = _collect_validation_errors(normalized_data, schema)
            obs = {
                **obs_base,
                "provider_selected": "local_filename_fallback",
                "provider_route_reason": "large_pdf_guardrail_under_provider_threshold",
                "key_page_strategy_used": False,
                "filename_only_fallback_used": True,
                "raw_response_status": "local_filename_fallback",
                "extraction_empty_reason": None if normalized_data else "filename_only_fallback_empty",
            }
            payload = {
                "schema_name": schema["schema_name"],
                "schema_version": schema["schema_version"],
                "raw_model_json": {"fallback": "filename_only_due_to_pdf_size", "data": normalized_data, "_observability": obs},
                "validated_json": normalized_data,
                "confidence": 0.35 if normalized_data else 0.0,
                "errors": errors,
                "cache_hit": False,
            }
            cache.save(stage="extraction", cache_key=_cache_key(signature_candidates[0]), payload=payload)
            return payload

        async with semaphore:
            output = await llm_provider.extract_structured(
                file_name=file_record.file_name,
                pdf_bytes=pdf_bytes,
                schema_name=schema["schema_name"],
                schema_definition=schema,
            )

        llm_meta = dict(getattr(output, "meta", {}) or {})
        normalized_data = _normalize_with_aliases(output.data, schema)
        used_rescue_pass = False
        if doc_type in RESCUE_DOC_TYPE_PROMPTS and _is_weak_extraction(doc_type, normalized_data):
            try:
                async with semaphore:
                    rescue_output = await llm_provider.extract_structured(
                        file_name=file_record.file_name,
                        pdf_bytes=pdf_bytes,
                        schema_name=schema["schema_name"],
                        schema_definition=schema,
                        prompt_hint=RESCUE_DOC_TYPE_PROMPTS[doc_type],
                    )
                rescue_data = _normalize_with_aliases(rescue_output.data, schema)
                if rescue_data:
                    merged = dict(normalized_data)
                    for key, value in rescue_data.items():
                        if value not in (None, "", []):
                            merged[key] = value
                    normalized_data = merged
                    used_rescue_pass = True
                    rescue_meta = dict(getattr(rescue_output, "meta", {}) or {})
                    if rescue_meta:
                        llm_meta.update(rescue_meta)
            except LLMProviderError:
                pass
            if _is_weak_extraction(doc_type, normalized_data):
                raw_rescue_data = await _raw_rescue_extract(
                    llm_provider=llm_provider,
                    file_name=file_record.file_name,
                    pdf_bytes=pdf_bytes,
                    doc_type=doc_type,
                )
                raw_rescue_normalized = _normalize_with_aliases(raw_rescue_data, schema)
                if raw_rescue_normalized:
                    merged = dict(normalized_data)
                    for key, value in raw_rescue_normalized.items():
                        if value not in (None, "", []):
                            merged[key] = value
                    normalized_data = merged
                    used_rescue_pass = True

        if not normalized_data:
            key_text = _extract_key_pages_text(pdf_bytes) if doc_type in TARGET_PAGE_DOC_TYPES else ""
            if key_text:
                heuristics = _fallback_extract_from_key_pages(
                    file_name=file_record.file_name,
                    doc_type=doc_type,
                    schema=schema,
                    key_text=key_text,
                )
                normalized_data = _normalize_with_aliases(heuristics, schema)
        if not normalized_data and doc_type == "construction_plan":
            full_text = _extract_full_text(pdf_bytes)
            if full_text:
                heuristics = _fallback_extract_from_full_text(
                    file_name=file_record.file_name,
                    doc_type=doc_type,
                    schema=schema,
                    full_text=full_text,
                )
                normalized_data = _normalize_with_aliases(heuristics, schema)
        if not normalized_data:
            fallback = _fallback_extract_from_filename(file_record.file_name, doc_type, schema)
            normalized_data = _normalize_with_aliases(fallback, schema)

        if value_tier == "medium":
            normalized_data = _prune_to_core_fields(normalized_data, schema)

        jsa_low_specificity = False
        if doc_type == "jsa":
            hazards = set(_split_to_list(normalized_data.get("hazards")))
            controls = set(_split_to_list(normalized_data.get("controls")))
            generic_h = {"作业风险", "风险", "危害"}
            generic_c = {"落实安全控制措施", "控制措施", "防控措施"}
            jsa_low_specificity = bool(hazards and controls and hazards.issubset(generic_h) and controls.issubset(generic_c))

        errors = _collect_validation_errors(normalized_data, schema)

        obs = {
            **obs_base,
            **llm_meta,
            "provider_selected": llm_meta.get("provider_selected"),
            "provider_route_reason": llm_meta.get("provider_route_reason"),
            "provider_escalated": bool(llm_meta.get("provider_escalated")),
            "provider_escalation_reason": llm_meta.get("provider_escalation_reason"),
            "raw_response_status": llm_meta.get("raw_response_status"),
            "parse_error_category": llm_meta.get("parse_error_category"),
            "timeout_retry_count": llm_meta.get("timeout_retry_count", 0),
            "model_name": llm_meta.get("model_name"),
            "model_selected": llm_meta.get("model_selected") or llm_meta.get("model_name"),
            "key_page_strategy_used": False,
            "filename_only_fallback_used": False,
            "extraction_empty_reason": None if normalized_data else "llm_empty_then_fallback_empty",
            "weak_recovered": jsa_low_specificity,
            "recovered_by_fallback": jsa_low_specificity,
            "low_specificity": jsa_low_specificity,
        }

        payload = {
            "schema_name": schema["schema_name"],
            "schema_version": schema["schema_version"],
            "raw_model_json": (
                {
                    "first_pass": output.data,
                    "rescue_pass_used": used_rescue_pass,
                    "data": normalized_data,
                    "_observability": obs,
                }
                if used_rescue_pass
                else (
                    (
                        {**output.data, "_observability": obs}
                        if output.data
                        else {"fallback": "filename_only_due_to_empty_llm_data", "data": normalized_data, "_observability": obs}
                    )
                )
            ),
            "validated_json": normalized_data,
            "confidence": output.confidence,
            "errors": errors,
            "cache_hit": False,
        }
        selected_signature = signature_candidates[0]
        if hasattr(llm_provider, "model_signature"):
            try:
                selected_signature = llm_provider.model_signature(
                    obs.get("provider_selected"),
                    obs.get("model_selected") or obs.get("model_name"),
                )
            except Exception:
                selected_signature = signature_candidates[0]
        cache.save(stage="extraction", cache_key=_cache_key(selected_signature), payload=payload)
        return payload
    except LLMProviderError as exc:
        if exc.code == "llm_transport_error" and "413" in str(exc):
            fallback = _fallback_extract_from_filename(file_record.file_name, doc_type, schema)
            normalized_data = _normalize_with_aliases(fallback, schema)
            if value_tier == "medium":
                normalized_data = _prune_to_core_fields(normalized_data, schema)
            errors = _collect_validation_errors(normalized_data, schema)
            obs = {
                **obs_base,
                "provider_selected": "relay_or_official",
                "provider_route_reason": "provider_exception",
                "provider_escalated": False,
                "provider_escalation_reason": None,
                "filename_only_fallback_used": True,
                "raw_response_status": "error_413",
                "parse_error_category": exc.code,
                "extraction_empty_reason": None if normalized_data else "filename_only_due_to_413_empty",
            }
            payload = {
                "schema_name": schema["schema_name"],
                "schema_version": schema["schema_version"],
                "raw_model_json": {
                    "fallback": "filename_only_due_to_413",
                    "error": str(exc),
                    "error_code": exc.code,
                    "data": normalized_data,
                    "_observability": obs,
                },
                "validated_json": normalized_data,
                "confidence": 0.25 if normalized_data else 0.0,
                "errors": errors,
                "cache_hit": False,
            }
            cache.save(stage="extraction", cache_key=_cache_key(signature_candidates[0]), payload=payload)
            return payload

        obs = {
            **obs_base,
            "provider_selected": "relay_or_official",
            "provider_route_reason": "provider_exception",
            "provider_escalated": False,
            "provider_escalation_reason": None,
            "raw_response_status": "error",
            "parse_error_category": exc.code,
            "extraction_empty_reason": "provider_exception",
        }
        return {
            "schema_name": schema["schema_name"],
            "schema_version": schema["schema_version"],
            "raw_model_json": {"error": str(exc), "error_code": exc.code, "_observability": obs},
            "validated_json": {},
            "confidence": 0.0,
            "errors": [f"{exc.code}: {exc}"],
            "cache_hit": False,
        }


async def extract_batch(
    session: Session,
    storage: StorageBackend,
    llm_provider: LLMProvider,
    batch_id: str,
    *,
    include_file_names: set[str] | None = None,
    include_doc_types: set[str] | None = None,
    only_failed: bool = False,
    only_timeout: bool = False,
) -> list[ExtractionRecord]:
    settings = get_settings()
    batch_uuid = UUID(str(batch_id))
    file_records = list(session.exec(select(FileRecord).where(FileRecord.batch_id == batch_uuid)).all())

    if include_file_names is not None:
        file_records = [record for record in file_records if record.file_name in include_file_names]
    if include_doc_types is not None:
        file_records = [record for record in file_records if (record.doc_type or "") in include_doc_types]

    if not file_records:
        return []

    existing_records = list(
        session.exec(select(ExtractionRecord).where(ExtractionRecord.file_id.in_([record.file_id for record in file_records]))).all()
    )
    existing_by_file: dict[UUID, ExtractionRecord] = {}
    for rec in existing_records:
        prior = existing_by_file.get(rec.file_id)
        if prior is None or rec.updated_at > prior.updated_at:
            existing_by_file[rec.file_id] = rec

    if only_failed:
        file_records = [
            record
            for record in file_records
            if existing_by_file.get(record.file_id) and (existing_by_file[record.file_id].errors or [])
        ]
    if only_timeout:
        file_records = [
            record
            for record in file_records
            if existing_by_file.get(record.file_id)
            and any("llm_timeout" in err for err in (existing_by_file[record.file_id].errors or []))
        ]

    if not file_records:
        return []

    semaphore = asyncio.Semaphore(max(1, int(settings.llm_extract_max_concurrency)))
    cache = ResultCache()
    model_signature = provider_model_signature(llm_provider)

    tasks: list[asyncio.Task] = []
    run_list: list[tuple[FileRecord, dict]] = []
    for file_record in file_records:
        if not file_record.doc_type:
            continue
        schema = get_schema_for_doc_type(file_record.doc_type)
        if not schema:
            continue
        run_list.append((file_record, schema))
        tasks.append(
            asyncio.create_task(
                _extract_payload(
                    storage=storage,
                    llm_provider=llm_provider,
                    file_record=file_record,
                    schema=schema,
                    cache=cache,
                    model_signature=model_signature,
                    pipeline_version=settings.pipeline_version,
                    semaphore=semaphore,
                    large_file_threshold=int(settings.large_pdf_keypage_threshold_bytes),
                )
            )
        )

    if not tasks:
        return []

    payloads = await asyncio.gather(*tasks)

    outputs: list[ExtractionRecord] = []
    for (file_record, schema), payload in zip(run_list, payloads):
        existing = existing_by_file.get(file_record.file_id)
        errors = list(payload.get("errors") or [])
        if payload.get("cache_hit"):
            errors.append("cache_hit: extraction")

        if existing and existing.schema_name == schema["schema_name"]:
            existing.schema_version = schema["schema_version"]
            existing.raw_model_json = payload.get("raw_model_json") or {}
            existing.validated_json = payload.get("validated_json") or {}
            existing.confidence = float(payload.get("confidence", 0.0))
            existing.errors = errors
            existing.updated_at = datetime.utcnow()
            session.add(existing)
            outputs.append(existing)
            continue

        record = ExtractionRecord(
            file_id=file_record.file_id,
            schema_name=schema["schema_name"],
            schema_version=schema["schema_version"],
            raw_model_json=payload.get("raw_model_json") or {},
            validated_json=payload.get("validated_json") or {},
            confidence=float(payload.get("confidence", 0.0)),
            errors=errors,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(record)
        outputs.append(record)

    session.commit()
    for record in outputs:
        session.refresh(record)
    return outputs
