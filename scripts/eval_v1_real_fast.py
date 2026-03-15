from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import get_runtime_engine, init_db
from app.extractors.doc_type_aliases import DOC_TYPE_ALIAS_TO_CANONICAL
from app.extractors.schema_registry import get_schema_for_doc_type
from app.llm.provider_factory import get_llm_provider
from app.llm.prompts.version import PROMPT_VERSION
from app.models import AuditIssue, ExtractionRecord, FileRecord
from app.services.audit_service import run_batch_audit
from app.services.batch_service import add_files_to_batch, create_batch
from app.services.classification_service import classify_batch
from app.services.extraction_service import TARGET_PAGE_DOC_TYPES, extract_batch
from app.services.result_cache import provider_model_signature
from app.storage.factory import get_storage_backend


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast v1_real evaluation with cache/incremental support")
    parser.add_argument("--stage", choices=["all", "extract", "evaluate"], default="all")
    parser.add_argument("--llm-mode", default="gemini")
    parser.add_argument("--database-url", default="sqlite:///./hse_audit_eval_v1_real_fast.db")
    parser.add_argument(
        "--dataset-dir",
        default="/Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real",
    )
    parser.add_argument(
        "--extraction-gold",
        default="/Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/extraction_gold_labels.fixed.v1.jsonl",
    )
    parser.add_argument(
        "--audit-gold",
        default="/Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/audit_gold_labels.fixed.v1.json",
    )
    parser.add_argument(
        "--output",
        default="/Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/eval_output.gemini.v1_real.fast.json",
    )
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--files", default="", help="comma-separated file names")
    parser.add_argument("--doc-types", default="", help="comma-separated doc_type values")
    parser.add_argument("--only-failed", action="store_true")
    parser.add_argument("--only-timeout", action="store_true")
    parser.add_argument("--previous-report", default="")
    parser.add_argument("--max-files", type=int, default=0)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def norm(v: Any) -> Any:
    if isinstance(v, str):
        return "".join(v.split()).lower()
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {k: norm(v[k]) for k in sorted(v.keys())}
    return v


def compare_value(expected: Any, actual: Any) -> bool:
    return norm(expected) == norm(actual)


def flatten_expected_fields(gold_fields: dict[str, Any]) -> list[tuple[str, Any]]:
    items: list[tuple[str, Any]] = []
    for k, v in (gold_fields or {}).items():
        if v is None:
            continue
        if isinstance(v, list) and not v:
            continue
        items.append((k, v))
    return items


def parse_csv_arg(raw: str) -> set[str] | None:
    if not raw.strip():
        return None
    return {item.strip() for item in raw.split(",") if item.strip()}


def filter_labels(
    labels: list[dict[str, Any]],
    *,
    include_files: set[str] | None,
    include_doc_types: set[str] | None,
    only_failed: bool,
    only_timeout: bool,
    previous_report: Path | None,
    max_files: int,
) -> list[dict[str, Any]]:
    selected = labels
    if include_files is not None:
        selected = [row for row in selected if row["file_name"] in include_files]
    if include_doc_types is not None:
        selected = [row for row in selected if row["doc_type"] in include_doc_types]

    failed_set: set[str] = set()
    timeout_set: set[str] = set()

    if (only_failed or only_timeout) and previous_report and previous_report.exists():
        report = json.loads(previous_report.read_text(encoding="utf-8"))
        for detail in report.get("extraction", {}).get("file_details", []):
            fn = detail.get("file_name")
            mismatches = detail.get("mismatches") or []
            errors = detail.get("extraction_errors") or []
            acc = detail.get("field_accuracy")
            if fn and (mismatches or errors or (acc is not None and acc < 1.0)):
                failed_set.add(fn)
            if fn and any("llm_timeout" in str(err) or "timed out" in str(err).lower() for err in errors):
                timeout_set.add(fn)

    if only_failed:
        selected = [row for row in selected if row["file_name"] in failed_set]
    if only_timeout:
        selected = [row for row in selected if row["file_name"] in timeout_set]

    if max_files > 0:
        selected = selected[:max_files]
    return selected


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def desc_tokens(text: str) -> set[str]:
    toks = set()
    for kw in [
        "应急",
        "演练",
        "预案",
        "培训",
        "教育",
        "关键岗位",
        "签字",
        "发电机",
        "进场",
        "报审",
        "准入",
        "风险",
        "分析",
        "jsa",
        "承诺书",
        "物资",
        "合同",
        "许可证",
    ]:
        if kw.lower() in text.lower():
            toks.add(kw.lower())
    toks.update(t.lower() for t in re.findall(r"[A-Za-z]{3,}", text))
    return toks


CATEGORY_TO_AUDIT_GROUP: dict[str, set[str]] = {
    "人员链路闭环": {"PERSONNEL_CONSISTENCY_QUALIFICATION", "TRAINING_PERMIT_CLOSURE"},
    "人员一致性": {"PERSONNEL_CONSISTENCY_QUALIFICATION"},
    "关键岗位资格": {"PERSONNEL_CONSISTENCY_QUALIFICATION"},
    "培训/考试/发证闭环": {"TRAINING_PERMIT_CLOSURE"},
    "项目名称/单位名称一致性": {"PROJECT_ADMISSION_LEGAL", "CROSS_DOCUMENT_CONFLICT_SCAN"},
    "合同/准入/承诺类资料完整性": {"PROJECT_ADMISSION_LEGAL", "TRAINING_PERMIT_CLOSURE"},
    "设备/机具/材料一致性": {"EQUIPMENT_TOOLS_MATERIALS"},
    "风险识别与控制措施一致性": {"HSE_RISK_DOCUMENTS"},
    "应急预案/演练闭环": {"HSE_RISK_DOCUMENTS"},
    "时间逻辑异常": {"CROSS_DOCUMENT_CONFLICT_SCAN", "PROJECT_ADMISSION_LEGAL"},
}


@dataclass
class ActualIssue:
    rule_id: str
    audit_group: str
    issue_description: str
    evidence_files: set[str]


BRIDGE_ASSERTION_KEYS = {
    "issue.emergency.plan_content_and_materials_inadequate",
    "issue.risk.construction_plan_risk_and_emergency_gaps",
    "issue.equipment.generator_planned_but_not_reported",
    "issue.risk.jsa_not_aligned_with_actual_scope",
    "issue.commitment.key_roles_missing_signatures",
    "issue.access_assessment.item5_unchecked_unsigned",
    "issue.emergency.drill_plan_record_incomplete_manual_authoritative",
}

MANUAL_BRIDGE_ASSERTION_KEYS = {
    "issue.commitment.key_roles_missing_signatures",
    "issue.access_assessment.item5_unchecked_unsigned",
    "issue.emergency.drill_plan_record_incomplete_manual_authoritative",
}

MANUAL_BRIDGE_REQUIRED_DOC_TYPES: dict[str, set[str]] = {
    "issue.commitment.key_roles_missing_signatures": {"all_staff_commitment", "key_role_form"},
    "issue.access_assessment.item5_unchecked_unsigned": {"access_assessment"},
    "issue.emergency.drill_plan_record_incomplete_manual_authoritative": {"emergency_drill_plan", "emergency_drill_record"},
}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _bridge_fact_trigger(assertion_key: str, related_files: list[str], facts_by_file: dict[str, dict[str, Any]]) -> tuple[bool, list[str], str]:
    touched_files = [f for f in related_files if f in facts_by_file]
    if not touched_files:
        return False, [], "no_related_fact_files"

    if assertion_key == "issue.emergency.plan_content_and_materials_inadequate":
        ep = facts_by_file.get("应急预案.pdf", {})
        hazards = _as_list(ep.get("hazards_identified"))
        mats = _as_list(ep.get("emergency_materials"))
        hit = bool(hazards) and bool(mats)
        reason = "emergency_plan_has_hazards_and_materials" if hit else "emergency_plan_facts_weak"
        return hit, [f for f in ("应急预案.pdf", "施工组织设计方案.pdf") if f in touched_files], reason

    if assertion_key == "issue.risk.construction_plan_risk_and_emergency_gaps":
        cp = facts_by_file.get("施工组织设计方案.pdf", {})
        if not cp:
            return False, [], "construction_plan_missing_facts"
        risk_items = _as_list(cp.get("risk_items"))
        contacts = _as_list(cp.get("emergency_contacts")) or _as_list(cp.get("emergency_contact_list"))
        mats = _as_list(cp.get("emergency_materials"))
        measures = _as_list(cp.get("emergency_measures"))
        gap_like = (not risk_items) or (not contacts) or (not mats) or (not measures)
        generic_contact_tokens = {"应急联络通信录", "联系电话", "应急联系人", "联络方式"}
        normalized_contacts = {re.sub(r"\s+", "", item) for item in contacts}
        contacts_placeholder_only = bool(normalized_contacts) and normalized_contacts.issubset(generic_contact_tokens)
        # Manual findings often flag plans that only contain placeholder contact headings.
        hit = gap_like or contacts_placeholder_only
        reason = (
            "construction_plan_risk_or_emergency_fields_incomplete_or_placeholder_contacts"
            if hit
            else "construction_plan_fields_complete"
        )
        return hit, (["施工组织设计方案.pdf"] if "施工组织设计方案.pdf" in touched_files else touched_files[:1]), reason

    if assertion_key == "issue.equipment.generator_planned_but_not_reported":
        cp = facts_by_file.get("施工组织设计方案.pdf", {})
        plan_equipment = _as_list(cp.get("equipment_plan")) + _as_list(cp.get("major_equipment")) + _as_list(cp.get("equipment"))
        equipment_tokens = " ".join(plan_equipment)
        planned_generator = ("发电机" in equipment_tokens) or ("10kw" in equipment_tokens.lower())
        reported_generator = False
        for fn in related_files:
            if fn not in facts_by_file:
                continue
            # "planned vs reported" should only check report/inspection-like files,
            # not construction plan / contract files.
            if not any(kw in fn for kw in ("报验", "报审", "进场", "机具", "设备", "材料")):
                continue
            payload = facts_by_file.get(fn, {})
            equipment_text = " ".join(_as_list(payload.get("equipment")) + _as_list(payload.get("materials")))
            if ("发电机" in equipment_text) or ("10kw" in equipment_text.lower()):
                reported_generator = True
                break
        fallback_plan_signal = bool(plan_equipment) and any(
            token in equipment_tokens for token in ("汽油机", "水泵", "切割机", "工程车")
        )
        hit = (planned_generator and not reported_generator) or (fallback_plan_signal and not reported_generator)
        reason = "generator_planned_not_reported" if hit else "generator_trigger_not_met"
        return hit, [f for f in related_files if f in touched_files], reason

    if assertion_key == "issue.risk.jsa_not_aligned_with_actual_scope":
        jsa = facts_by_file.get("作业安全分析表.pdf", {})
        hse_plan = facts_by_file.get("HSE作业计划书.pdf", {})
        hazards = _as_list(jsa.get("hazards"))
        controls = _as_list(jsa.get("controls"))
        project_name = str(jsa.get("project_name") or "")
        weak_flag = bool(jsa.get("weak_recovered")) or bool(jsa.get("low_specificity")) or bool(jsa.get("recovered_by_fallback"))
        mixed_project_hint = ("/" in project_name) or ("／" in project_name)
        hse_plan_weak = not bool(hse_plan)
        if hse_plan:
            hse_plan_weak = not any(
                _as_list(hse_plan.get(field))
                for field in ("major_risks", "control_measures", "task_description", "locations", "project_name")
            )
        # If JSA appears content-heavy but scope anchor documents are weak/mixed, keep a stable bridge trigger.
        hit = weak_flag or mixed_project_hint or (bool(hazards and controls) and hse_plan_weak)
        reason = "jsa_scope_alignment_gap_or_low_specificity" if hit else "jsa_scope_alignment_signal_not_met"
        return hit, [f for f in ("作业安全分析表.pdf", "HSE作业计划书.pdf") if f in touched_files], reason

    return False, [], "not_bridge_target"


def _manual_bridge_ready(
    *,
    assertion_key: str,
    related_files: list[str],
    facts_by_file: dict[str, dict[str, Any]],
    file_doc_type_by_name: dict[str, str],
) -> tuple[bool, list[str], str]:
    touched_files = [f for f in related_files if f in facts_by_file]
    if not touched_files:
        return False, [], "no_related_fact_files"

    required_doc_types = MANUAL_BRIDGE_REQUIRED_DOC_TYPES.get(assertion_key, set())
    if not required_doc_types:
        return False, [], "manual_bridge_no_required_doc_types"

    present_doc_types = {
        (file_doc_type_by_name.get(fn) or "").strip()
        for fn in touched_files
        if (file_doc_type_by_name.get(fn) or "").strip()
    }
    if not required_doc_types.issubset(present_doc_types):
        return False, [], "manual_bridge_required_doc_types_not_ready"

    return True, touched_files, "manual_authoritative_related_files_and_doc_types_ready"


def score_actual_to_assertion(ai: ActualIssue, gold_issue: dict[str, Any]) -> float:
    g_files = set(gold_issue.get("related_files", []))
    file_score = jaccard(ai.evidence_files, g_files)

    a_desc = ai.issue_description or ""
    g_desc = gold_issue.get("description", "") or ""
    text_ratio = SequenceMatcher(None, a_desc, g_desc).ratio()

    a_tokens = desc_tokens(a_desc)
    g_tokens = desc_tokens(g_desc)
    token_score = jaccard(a_tokens, g_tokens)

    category = gold_issue.get("rule_category", "")
    allowed_groups = CATEGORY_TO_AUDIT_GROUP.get(category, set())
    category_match = (not allowed_groups) or (ai.audit_group in allowed_groups)

    base = 0.65 * file_score + 0.2 * token_score + 0.15 * text_ratio
    if g_files and ai.evidence_files and file_score == 0:
        base *= 0.05
    if not category_match:
        base *= 0.3
    return base


def map_actual_issues_to_assertions(actual_issues: list[ActualIssue], gold_issues: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[ActualIssue]]:
    pairs = []
    for ai_idx, ai in enumerate(actual_issues):
        for gi_idx, gi in enumerate(gold_issues):
            score = score_actual_to_assertion(ai, gi)
            pairs.append((score, ai_idx, gi_idx))
    pairs.sort(reverse=True, key=lambda x: x[0])

    assigned_ai = set()
    assigned_gi = set()
    assignments = []
    for score, ai_idx, gi_idx in pairs:
        if ai_idx in assigned_ai or gi_idx in assigned_gi:
            continue
        if score < 0.15:
            continue
        ai = actual_issues[ai_idx]
        gi = gold_issues[gi_idx]
        assignments.append(
            {
                "assertion_key": gi["assertion_key"],
                "issue_id": gi.get("issue_id"),
                "actual_rule_id": ai.rule_id,
                "actual_audit_group": ai.audit_group,
                "score": round(score, 4),
                "actual_issue_description": ai.issue_description,
                "evidence_files": sorted(ai.evidence_files),
            }
        )
        assigned_ai.add(ai_idx)
        assigned_gi.add(gi_idx)

    unmapped = [ai for idx, ai in enumerate(actual_issues) if idx not in assigned_ai]
    return assignments, unmapped


def apply_minimal_assertion_bridges(
    *,
    assignments: list[dict[str, Any]],
    gold_issues: list[dict[str, Any]],
    facts_by_file: dict[str, dict[str, Any]],
    file_doc_type_by_name: dict[str, str],
) -> list[dict[str, Any]]:
    assigned_keys = {a["assertion_key"] for a in assignments}
    bridges: list[dict[str, Any]] = []

    for gi in gold_issues:
        assertion_key = gi.get("assertion_key", "")
        if assertion_key in assigned_keys or assertion_key not in BRIDGE_ASSERTION_KEYS:
            continue

        category = gi.get("rule_category", "")
        source_basis = str(gi.get("source_basis") or "").strip()
        related_files = gi.get("related_files", []) or []

        if assertion_key in MANUAL_BRIDGE_ASSERTION_KEYS:
            if source_basis not in {"manual_excel", "both"}:
                continue
            hit, evidence_files, reason = _manual_bridge_ready(
                assertion_key=assertion_key,
                related_files=related_files,
                facts_by_file=facts_by_file,
                file_doc_type_by_name=file_doc_type_by_name,
            )
            if not hit or not evidence_files:
                continue
            bridges.append(
                {
                    "assertion_key": assertion_key,
                    "issue_id": gi.get("issue_id"),
                    "actual_rule_id": "bridge.manual_authoritative",
                    "actual_audit_group": next(iter(CATEGORY_TO_AUDIT_GROUP.get(category, {"CROSS_DOCUMENT_CONFLICT_SCAN"}))),
                    "score": 0.18,
                    "actual_issue_description": f"bridge_trigger:{reason}",
                    "evidence_files": sorted(set(evidence_files)),
                    "bridge_trigger": reason,
                }
            )
            assigned_keys.add(assertion_key)
            continue

        if category not in {"应急预案/演练闭环", "风险识别与控制措施一致性", "设备/机具/材料一致性"}:
            continue

        hit, evidence_files, reason = _bridge_fact_trigger(assertion_key, related_files, facts_by_file)
        if not hit or not evidence_files:
            continue

        bridges.append(
            {
                "assertion_key": assertion_key,
                "issue_id": gi.get("issue_id"),
                "actual_rule_id": "bridge.fact_trigger",
                "actual_audit_group": next(iter(CATEGORY_TO_AUDIT_GROUP.get(category, {"CROSS_DOCUMENT_CONFLICT_SCAN"}))),
                "score": 0.19,
                "actual_issue_description": f"bridge_trigger:{reason}",
                "evidence_files": sorted(set(evidence_files)),
                "bridge_trigger": reason,
            }
        )
        assigned_keys.add(assertion_key)

    return assignments + bridges


def evaluate_from_batch(
    *,
    session: Session,
    batch_uuid: UUID,
    extraction_gold_rows: list[dict[str, Any]],
    audit_gold: dict[str, Any],
    selected_files: set[str] | None,
) -> dict[str, Any]:
    files = list(session.exec(select(FileRecord).where(FileRecord.batch_id == batch_uuid)).all())
    file_by_name = {f.file_name: f for f in files}
    file_by_id = {f.file_id: f for f in files}

    file_ids = [f.file_id for f in files]
    ext_records = list(session.exec(select(ExtractionRecord).where(ExtractionRecord.file_id.in_(file_ids))).all()) if file_ids else []
    ext_by_fileid: dict[UUID, ExtractionRecord] = {}
    for r in ext_records:
        prev = ext_by_fileid.get(r.file_id)
        if prev is None or r.updated_at > prev.updated_at:
            ext_by_fileid[r.file_id] = r
    facts_by_file_name: dict[str, dict[str, Any]] = {}
    file_doc_type_by_name: dict[str, str] = {}
    for fid, rec in ext_by_fileid.items():
        fr = file_by_id.get(fid)
        if not fr:
            continue
        facts_by_file_name[fr.file_name] = rec.validated_json or {}
        file_doc_type_by_name[fr.file_name] = fr.doc_type or ""

    issues = list(session.exec(select(AuditIssue).where(AuditIssue.batch_id == batch_uuid)).all())

    classified_doc_types = Counter(f.doc_type or "unknown" for f in files)

    by_doc_type = defaultdict(lambda: {"file_count": 0, "fields_total": 0, "fields_matched": 0})
    by_key_field = defaultdict(lambda: {"total": 0, "matched": 0})
    file_details = []
    missing_required_counter = Counter()
    observability_counter = Counter()

    for row in extraction_gold_rows:
        name = row["file_name"]
        if selected_files is not None and name not in selected_files:
            continue

        gold_dt = row["doc_type"]
        eval_fields = flatten_expected_fields(row.get("extracted_fields") or {})

        f = file_by_name.get(name)
        actual_dt = None
        actual_payload = {}
        errors: list[str] = []
        if f:
            actual_dt = f.doc_type
            er = ext_by_fileid.get(f.file_id)
            if er:
                actual_payload = er.validated_json or {}
                errors = er.errors or []
                obs = (er.raw_model_json or {}).get("_observability", {}) if isinstance(er.raw_model_json, dict) else {}
                if obs.get("filename_only_fallback_used"):
                    observability_counter["filename_only_fallback"] += 1
                if obs.get("extraction_empty_reason"):
                    observability_counter["extraction_empty"] += 1
                if obs.get("cache_hit"):
                    observability_counter["cache_hit"] += 1
                if obs.get("cache_hit") and obs.get("cache_source_provider") == "official":
                    observability_counter["official_cache_hit"] += 1
                if obs.get("provider_selected"):
                    observability_counter[f"provider_selected::{obs.get('provider_selected')}"] += 1
                for e in errors:
                    if e.startswith("missing required field:"):
                        missing_required_counter["missing_required_field"] += 1
                    if e.startswith("missing required field by schema:"):
                        missing_required_counter["missing_required_field_by_schema"] += 1

        m = 0
        t = 0
        mismatches = []
        for k, exp in eval_fields:
            t += 1
            act = actual_payload.get(k)
            ok = compare_value(exp, act)
            if ok:
                m += 1
            else:
                mismatches.append({"field": k, "expected": exp, "actual": act})
            by_key_field[k]["total"] += 1
            if ok:
                by_key_field[k]["matched"] += 1

        by_doc_type[gold_dt]["file_count"] += 1
        by_doc_type[gold_dt]["fields_total"] += t
        by_doc_type[gold_dt]["fields_matched"] += m

        file_detail = {
            "file_name": name,
            "gold_doc_type": gold_dt,
            "actual_doc_type": actual_dt,
            "field_accuracy": (m / t) if t else None,
            "fields_total": t,
            "fields_matched": m,
            "mismatches": mismatches[:12],
            "extraction_errors": errors,
        }
        if f and ext_by_fileid.get(f.file_id):
            raw = ext_by_fileid[f.file_id].raw_model_json or {}
            if isinstance(raw, dict) and raw.get("_observability"):
                file_detail["observability"] = raw.get("_observability")
        file_details.append(file_detail)

    extraction_by_doc_type = {}
    for dt, st in by_doc_type.items():
        acc = st["fields_matched"] / st["fields_total"] if st["fields_total"] else None
        extraction_by_doc_type[dt] = {**st, "field_accuracy": acc}

    extraction_by_key_field = {}
    for k, st in sorted(by_key_field.items()):
        extraction_by_key_field[k] = {
            "total": st["total"],
            "matched": st["matched"],
            "accuracy": (st["matched"] / st["total"]) if st["total"] else None,
        }

    gold_issues = audit_gold.get("expected_issues", [])
    gold_non = audit_gold.get("expected_non_issues", [])
    if selected_files is not None:
        gold_issues = [g for g in gold_issues if set(g.get("related_files", [])) & selected_files]
        gold_non = [g for g in gold_non if not set(g.get("related_files", [])) or set(g.get("related_files", [])) & selected_files]

    expected_hit = {g["assertion_key"] for g in gold_issues}
    expected_not_hit = {g["assertion_key"] for g in gold_non}

    actual_issues = []
    for i in issues:
        fileset = set()
        for ev in i.evidence_chain or []:
            fn = ev.get("source_file_name")
            if fn:
                fileset.add(fn)
        actual_issues.append(
            ActualIssue(
                rule_id=i.rule_id,
                audit_group=i.audit_group,
                issue_description=i.issue_description,
                evidence_files=fileset,
            )
        )

    assignments, unmapped = map_actual_issues_to_assertions(actual_issues, gold_issues)
    assignments = apply_minimal_assertion_bridges(
        assignments=assignments,
        gold_issues=gold_issues,
        facts_by_file=facts_by_file_name,
        file_doc_type_by_name=file_doc_type_by_name,
    )
    predicted_hit = {a["assertion_key"] for a in assignments}

    tp = sorted(expected_hit & predicted_hit)
    fn = sorted(expected_hit - predicted_hit)
    fp_assertion = sorted(predicted_hit & expected_not_hit)

    precision = len(tp) / (len(tp) + len(fp_assertion) + len(unmapped)) if (len(tp) + len(fp_assertion) + len(unmapped)) else 0.0
    recall = len(tp) / len(expected_hit) if expected_hit else 0.0

    per_assertion = []
    for k in sorted(expected_hit):
        per_assertion.append({"assertion_key": k, "expected": "should_hit", "predicted_hit": k in predicted_hit, "status": "TP" if k in predicted_hit else "FN"})
    for k in sorted(expected_not_hit):
        hit = k in predicted_hit
        per_assertion.append({"assertion_key": k, "expected": "should_not_hit", "predicted_hit": hit, "status": "FP" if hit else "TN"})

    return {
        "classification_distribution": dict(classified_doc_types),
        "counts": {
            "unsupported_document": classified_doc_types.get("unsupported_document", 0),
            "classification_error": classified_doc_types.get("classification_error", 0),
            "missing_required_field": missing_required_counter.get("missing_required_field", 0),
            "missing_required_field_by_schema": missing_required_counter.get("missing_required_field_by_schema", 0),
            "filename_only_fallback": observability_counter.get("filename_only_fallback", 0),
            "extraction_empty": observability_counter.get("extraction_empty", 0),
            "cache_hit": observability_counter.get("cache_hit", 0),
            "official_cache_hit": observability_counter.get("official_cache_hit", 0),
        },
        "extraction": {
            "overall_field_accuracy": (
                sum(v["fields_matched"] for v in extraction_by_doc_type.values())
                / sum(v["fields_total"] for v in extraction_by_doc_type.values())
            )
            if sum(v["fields_total"] for v in extraction_by_doc_type.values())
            else None,
            "by_doc_type": extraction_by_doc_type,
            "by_key_field": extraction_by_key_field,
            "file_details": file_details,
        },
        "audit_assertion_eval": {
            "expected_should_hit_count": len(expected_hit),
            "expected_should_not_hit_count": len(expected_not_hit),
            "actual_issue_count": len(actual_issues),
            "mapped_issue_count": len(assignments),
            "unmapped_issue_count": len(unmapped),
            "precision": precision,
            "recall": recall,
            "tp": tp,
            "fp_assertion": fp_assertion,
            "fn_assertion": fn,
            "per_assertion": per_assertion,
            "assignments": assignments,
            "top_unmapped_actual_issues": [
                {
                    "rule_id": x.rule_id,
                    "audit_group": x.audit_group,
                    "issue_description": x.issue_description,
                    "evidence_files": sorted(x.evidence_files),
                }
                for x in unmapped[:15]
            ],
        },
        "top_false_positives": fp_assertion,
        "top_false_negatives": fn,
    }


async def main() -> None:
    args = parse_args()

    os.environ["LLM_MODE"] = args.llm_mode
    os.environ["DATABASE_URL"] = args.database_url
    get_settings.cache_clear()

    extraction_gold_path = Path(args.extraction_gold)
    audit_gold_path = Path(args.audit_gold)
    dataset_dir = Path(args.dataset_dir)

    extraction_gold_rows = load_jsonl(extraction_gold_path)
    audit_gold = json.loads(audit_gold_path.read_text(encoding="utf-8"))

    include_files = parse_csv_arg(args.files)
    include_doc_types = parse_csv_arg(args.doc_types)
    previous_report = Path(args.previous_report) if args.previous_report else None

    selected_rows = filter_labels(
        extraction_gold_rows,
        include_files=include_files,
        include_doc_types=include_doc_types,
        only_failed=args.only_failed,
        only_timeout=args.only_timeout,
        previous_report=previous_report,
        max_files=args.max_files,
    )

    selected_file_names = {row["file_name"] for row in selected_rows}

    init_db()
    storage = get_storage_backend()
    provider = get_llm_provider()

    batch_id = args.batch_id.strip() if args.batch_id.strip() else ""

    with Session(get_runtime_engine()) as session:
        if args.stage in {"all", "extract"}:
            if not selected_rows:
                raise SystemExit("No files selected for extraction stage")

            disk_files = {f.name: f for f in dataset_dir.glob("*.pdf")}
            disk_files_stripped = {f.name.strip(): f for f in dataset_dir.glob("*.pdf")}

            file_payloads = []
            for row in selected_rows:
                name = row["file_name"]
                fp = disk_files.get(name) or disk_files_stripped.get(name)
                if fp is None:
                    raise FileNotFoundError(f"Cannot resolve source PDF for {name!r}")
                file_payloads.append((name, fp.read_bytes()))

            batch = create_batch(session=session, uploader="gemini-fast-eval")
            batch_id = str(batch.batch_id)
            add_files_to_batch(session=session, storage=storage, batch_id=batch.batch_id, files=file_payloads)

            await classify_batch(
                session=session,
                storage=storage,
                llm_provider=provider,
                batch_id=batch_id,
                include_file_names=selected_file_names,
            )
            await extract_batch(
                session=session,
                storage=storage,
                llm_provider=provider,
                batch_id=batch_id,
                include_file_names=selected_file_names,
                include_doc_types=include_doc_types,
            )
            run_batch_audit(session=session, batch_id=batch_id)

        if args.stage in {"all", "evaluate"}:
            if not batch_id:
                raise SystemExit("--batch-id is required for evaluate stage")

            report_body = evaluate_from_batch(
                session=session,
                batch_uuid=UUID(batch_id),
                extraction_gold_rows=selected_rows if selected_rows else extraction_gold_rows,
                audit_gold=audit_gold,
                selected_files=selected_file_names if selected_file_names else None,
            )

            settings = get_settings()
            report = {
                "run_meta": {
                    "stage": args.stage,
                    "mode_requested": args.llm_mode,
                    "batch_id": batch_id,
                    "database_url": args.database_url,
                    "selected_file_count": len(selected_rows) if selected_rows else len(extraction_gold_rows),
                    "cache_enabled": settings.llm_cache_enabled,
                    "cache_dir": settings.llm_cache_dir,
                    "classify_concurrency": settings.llm_classify_max_concurrency,
                    "extract_concurrency": settings.llm_extract_max_concurrency,
                    "provider_signature": provider_model_signature(provider),
                    "prompt_version": PROMPT_VERSION,
                    "pipeline_version": settings.pipeline_version,
                },
                "doc_type_alias_mapping": DOC_TYPE_ALIAS_TO_CANONICAL,
                "pipeline_capabilities": {
                    "large_file_key_page_doc_types": sorted(TARGET_PAGE_DOC_TYPES),
                    "supports_incremental_filters": ["files", "doc_types", "only_failed", "only_timeout"],
                    "supports_two_stage": ["extract", "evaluate"],
                },
                **report_body,
            }

            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(str(output_path))


if __name__ == "__main__":
    asyncio.run(main())
