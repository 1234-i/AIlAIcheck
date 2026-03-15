from __future__ import annotations

import asyncio
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import get_runtime_engine, init_db
from app.extractors.doc_type_aliases import DOC_TYPE_ALIAS_TO_CANONICAL
from app.extractors.schema_registry import get_schema_for_doc_type
from app.models import AuditIssue, ExtractionRecord, FileRecord
from app.services.batch_service import add_files_to_batch, create_batch
from app.services.workflow_service import run_full_pipeline
from app.storage.factory import get_storage_backend
from app.llm.provider_factory import get_llm_provider

BASE = Path('/Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real')
EXTRACTION_GOLD = BASE / 'extraction_gold_labels.fixed.v1.jsonl'
AUDIT_GOLD = BASE / 'audit_gold_labels.fixed.v1.json'
OUT_JSON = BASE / 'eval_output.gemini.v1_real.round2.assertion.json'


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def norm(v: Any) -> Any:
    if isinstance(v, str):
        return ''.join(v.split()).lower()
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, dict):
        return {k: norm(v[k]) for k in sorted(v.keys())}
    return v


def compare_value(expected: Any, actual: Any) -> bool:
    return norm(expected) == norm(actual)


def flatten_expected_fields(gold_fields: dict[str, Any]) -> list[tuple[str, Any]]:
    items = []
    for k, v in (gold_fields or {}).items():
        if v is None:
            continue
        if isinstance(v, list) and not v:
            continue
        items.append((k, v))
    return items


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def desc_tokens(text: str) -> set[str]:
    toks = set()
    for kw in [
        '应急', '演练', '预案', '培训', '教育', '关键岗位', '签字', '发电机', '进场',
        '报审', '准入', '风险', '分析', 'jsa', '承诺书', '物资', '合同', '许可证',
    ]:
        if kw.lower() in text.lower():
            toks.add(kw.lower())
    toks.update(t.lower() for t in re.findall(r'[A-Za-z]{3,}', text))
    return toks


CATEGORY_TO_AUDIT_GROUP: dict[str, set[str]] = {
    '人员链路闭环': {'PERSONNEL_CONSISTENCY_QUALIFICATION', 'TRAINING_PERMIT_CLOSURE'},
    '人员一致性': {'PERSONNEL_CONSISTENCY_QUALIFICATION'},
    '关键岗位资格': {'PERSONNEL_CONSISTENCY_QUALIFICATION'},
    '培训/考试/发证闭环': {'TRAINING_PERMIT_CLOSURE'},
    '项目名称/单位名称一致性': {'PROJECT_ADMISSION_LEGAL', 'CROSS_DOCUMENT_CONFLICT_SCAN'},
    '合同/准入/承诺类资料完整性': {'PROJECT_ADMISSION_LEGAL', 'TRAINING_PERMIT_CLOSURE'},
    '设备/机具/材料一致性': {'EQUIPMENT_TOOLS_MATERIALS'},
    '风险识别与控制措施一致性': {'HSE_RISK_DOCUMENTS'},
    '应急预案/演练闭环': {'HSE_RISK_DOCUMENTS'},
    '时间逻辑异常': {'CROSS_DOCUMENT_CONFLICT_SCAN', 'PROJECT_ADMISSION_LEGAL'},
}


@dataclass
class ActualIssue:
    rule_id: str
    audit_group: str
    issue_description: str
    evidence_files: set[str]


def score_actual_to_assertion(ai: ActualIssue, gold_issue: dict[str, Any]) -> float:
    g_files = set(gold_issue.get('related_files', []))
    file_score = jaccard(ai.evidence_files, g_files)

    a_desc = ai.issue_description or ''
    g_desc = gold_issue.get('description', '') or ''
    text_ratio = SequenceMatcher(None, a_desc, g_desc).ratio()

    a_tokens = desc_tokens(a_desc)
    g_tokens = desc_tokens(g_desc)
    token_score = jaccard(a_tokens, g_tokens)

    category = gold_issue.get('rule_category', '')
    allowed_groups = CATEGORY_TO_AUDIT_GROUP.get(category, set())
    category_match = (not allowed_groups) or (ai.audit_group in allowed_groups)

    base = 0.65 * file_score + 0.2 * token_score + 0.15 * text_ratio

    # Tightening constraints for stability.
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
                'assertion_key': gi['assertion_key'],
                'issue_id': gi.get('issue_id'),
                'actual_rule_id': ai.rule_id,
                'actual_audit_group': ai.audit_group,
                'gold_rule_category': gi.get('rule_category'),
                'score': round(score, 4),
                'actual_issue_description': ai.issue_description,
                'evidence_files': sorted(ai.evidence_files),
            }
        )
        assigned_ai.add(ai_idx)
        assigned_gi.add(gi_idx)

    unmapped = [ai for idx, ai in enumerate(actual_issues) if idx not in assigned_ai]
    return assignments, unmapped


async def main() -> None:
    os.environ['LLM_MODE'] = 'gemini'
    os.environ['DATABASE_URL'] = 'sqlite:///./hse_audit_eval_v1_real_round2_real.db'
    get_settings.cache_clear()

    extraction_gold = load_jsonl(EXTRACTION_GOLD)
    audit_gold = json.loads(AUDIT_GOLD.read_text(encoding='utf-8'))

    init_db()
    storage = get_storage_backend()
    provider = get_llm_provider()

    disk_files = {f.name: f for f in BASE.glob('*.pdf')}
    disk_files_stripped = {f.name.strip(): f for f in BASE.glob('*.pdf')}

    file_payloads = []
    for row in extraction_gold:
        name = row['file_name']
        fp = disk_files.get(name) or disk_files_stripped.get(name)
        if fp is None:
            raise FileNotFoundError(f'Cannot resolve source PDF for {name!r}')
        file_payloads.append((name, fp.read_bytes()))

    run_error = None
    batch_uuid = None

    with Session(get_runtime_engine()) as session:
        try:
            batch = create_batch(session=session, uploader='gemini-round2-v1-real-assertion')
            batch_uuid = batch.batch_id
            add_files_to_batch(session=session, storage=storage, batch_id=batch.batch_id, files=file_payloads)
            await run_full_pipeline(session=session, storage=storage, provider=provider, batch_id=str(batch.batch_id))
        except Exception as exc:
            run_error = f"{type(exc).__name__}: {exc}"

        files = list(session.exec(select(FileRecord).where(FileRecord.batch_id == batch_uuid)).all()) if batch_uuid else []
        file_by_name = {f.file_name: f for f in files}

        ext_records = []
        if files:
            file_ids = [f.file_id for f in files]
            ext_records = list(session.exec(select(ExtractionRecord).where(ExtractionRecord.file_id.in_(file_ids))).all())
        ext_by_fileid = {r.file_id: r for r in ext_records}

        issues = list(session.exec(select(AuditIssue).where(AuditIssue.batch_id == batch_uuid)).all()) if batch_uuid else []

    classified_doc_types = Counter(f.doc_type or 'unknown' for f in files)

    by_doc_type = defaultdict(lambda: {'file_count': 0, 'fields_total': 0, 'fields_matched': 0})
    by_key_field = defaultdict(lambda: {'total': 0, 'matched': 0})
    file_details = []

    missing_required_counter = Counter()

    for row in extraction_gold:
        name = row['file_name']
        gold_dt = row['doc_type']
        eval_fields = flatten_expected_fields(row.get('extracted_fields') or {})

        f = file_by_name.get(name)
        actual_dt = None
        actual_payload = {}
        errors = []
        if f:
            actual_dt = f.doc_type
            er = ext_by_fileid.get(f.file_id)
            if er:
                actual_payload = er.validated_json or {}
                errors = er.errors or []
                for e in errors:
                    if e.startswith('missing required field'):
                        missing_required_counter['missing_required_field'] += 1
                    if e.startswith('missing required field by schema'):
                        missing_required_counter['missing_required_field_by_schema'] += 1

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
                mismatches.append({'field': k, 'expected': exp, 'actual': act})
            by_key_field[k]['total'] += 1
            if ok:
                by_key_field[k]['matched'] += 1

        by_doc_type[gold_dt]['file_count'] += 1
        by_doc_type[gold_dt]['fields_total'] += t
        by_doc_type[gold_dt]['fields_matched'] += m

        file_details.append({
            'file_name': name,
            'gold_doc_type': gold_dt,
            'actual_doc_type': actual_dt,
            'field_accuracy': (m / t) if t else None,
            'fields_total': t,
            'fields_matched': m,
            'mismatches': mismatches[:12],
            'extraction_errors': errors,
        })

    extraction_by_doc_type = {}
    for dt, st in by_doc_type.items():
        acc = st['fields_matched'] / st['fields_total'] if st['fields_total'] else None
        extraction_by_doc_type[dt] = {**st, 'field_accuracy': acc}

    extraction_by_key_field = {}
    for k, st in sorted(by_key_field.items()):
        extraction_by_key_field[k] = {
            'total': st['total'],
            'matched': st['matched'],
            'accuracy': (st['matched'] / st['total']) if st['total'] else None,
        }

    gold_issues = audit_gold.get('expected_issues', [])
    gold_non = audit_gold.get('expected_non_issues', [])
    expected_hit = {g['assertion_key'] for g in gold_issues}
    expected_not_hit = {g['assertion_key'] for g in gold_non}

    actual_issues = []
    for i in issues:
        fileset = set()
        for ev in i.evidence_chain or []:
            fn = ev.get('source_file_name')
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
    predicted_hit = {a['assertion_key'] for a in assignments}

    tp = sorted(expected_hit & predicted_hit)
    fn = sorted(expected_hit - predicted_hit)
    fp_assertion = sorted(predicted_hit & expected_not_hit)

    precision = len(tp) / (len(tp) + len(fp_assertion) + len(unmapped)) if (len(tp) + len(fp_assertion) + len(unmapped)) else 0.0
    recall = len(tp) / len(expected_hit) if expected_hit else 0.0

    per_assertion = []
    for k in sorted(expected_hit):
        per_assertion.append({'assertion_key': k, 'expected': 'should_hit', 'predicted_hit': k in predicted_hit, 'status': 'TP' if k in predicted_hit else 'FN'})
    for k in sorted(expected_not_hit):
        hit = k in predicted_hit
        per_assertion.append({'assertion_key': k, 'expected': 'should_not_hit', 'predicted_hit': hit, 'status': 'FP' if hit else 'TN'})

    unstable = []
    for dt, st in extraction_by_doc_type.items():
        if st['file_count'] >= 2 and st['field_accuracy'] is not None:
            unstable.append((st['field_accuracy'], dt, st['file_count']))
    unstable.sort()

    root_causes = []
    ce = classified_doc_types.get('classification_error', 0)
    us = classified_doc_types.get('unsupported_document', 0)
    if ce:
        root_causes.append(f'classification_error remains: {ce}')
    if us:
        root_causes.append(f'unsupported_document remains: {us}')

    err_counter = Counter()
    for d in file_details:
        for e in d.get('extraction_errors', []):
            err_counter[e.split(':', 1)[0]] += 1
    if err_counter:
        root_causes.append('top extraction error categories: ' + ', '.join(f'{k}={v}' for k, v in err_counter.most_common(5)))
    if recall < 0.4:
        root_causes.append('audit assertion recall still low; rule output granularity differs from gold assertions')

    focus_doc_types = [
        'hse_guidance',
        'hse_plan',
        'medical_exam',
        'insurance',
        'equipment_inspection',
        'material_inspection',
        'emergency_plan',
        'emergency_drill_plan',
        'emergency_drill_record',
    ]
    field_alignment_mappings = {}
    for dt in focus_doc_types:
        schema = get_schema_for_doc_type(dt)
        if not schema:
            continue
        aliases = schema.get('field_aliases', {})
        mapping_items = []
        for actual_field, canonical_field in sorted(aliases.items()):
            mapping_items.append(
                {
                    'prompt_expected_field': canonical_field,
                    'gemini_actual_field': actual_field,
                    'schema_canonical_field': canonical_field,
                }
            )
        field_alignment_mappings[dt] = mapping_items

    report = {
        'run_meta': {
            'mode_requested': 'gemini',
            'batch_id': str(batch_uuid) if batch_uuid else None,
            'run_error': run_error,
            'source_file_count': len(extraction_gold),
            'database_url': os.environ.get('DATABASE_URL'),
        },
        'doc_type_alias_mapping': DOC_TYPE_ALIAS_TO_CANONICAL,
        'classification_distribution': dict(classified_doc_types),
        'counts': {
            'unsupported_document': us,
            'classification_error': ce,
            'missing_required_field': missing_required_counter.get('missing_required_field', 0),
            'missing_required_field_by_schema': missing_required_counter.get('missing_required_field_by_schema', 0),
        },
        'extraction': {
            'overall_field_accuracy': (sum(v['fields_matched'] for v in extraction_by_doc_type.values()) / sum(v['fields_total'] for v in extraction_by_doc_type.values())) if sum(v['fields_total'] for v in extraction_by_doc_type.values()) else None,
            'by_doc_type': extraction_by_doc_type,
            'by_key_field': extraction_by_key_field,
            'file_details': file_details,
        },
        'field_alignment_mappings': field_alignment_mappings,
        'audit_assertion_eval': {
            'expected_should_hit_count': len(expected_hit),
            'expected_should_not_hit_count': len(expected_not_hit),
            'actual_issue_count': len(actual_issues),
            'mapped_issue_count': len(assignments),
            'unmapped_issue_count': len(unmapped),
            'precision': precision,
            'recall': recall,
            'tp': tp,
            'fp_assertion': fp_assertion,
            'fn_assertion': fn,
            'per_assertion': per_assertion,
            'assignments': assignments,
            'top_unmapped_actual_issues': [
                {
                    'rule_id': x.rule_id,
                    'audit_group': x.audit_group,
                    'issue_description': x.issue_description,
                    'evidence_files': sorted(x.evidence_files),
                }
                for x in unmapped[:15]
            ],
        },
        'top_false_positives': fp_assertion,
        'top_false_negatives': fn,
        'top_unstable_doc_types': [
            {'doc_type': dt, 'field_accuracy': acc, 'file_count': cnt}
            for acc, dt, cnt in unstable[:10]
        ],
        'likely_root_causes': root_causes,
    }

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(OUT_JSON))


if __name__ == '__main__':
    asyncio.run(main())
