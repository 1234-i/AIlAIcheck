from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.db.session import get_runtime_engine, init_db
from app.evaluation.metrics import aggregate_extraction, compare_extraction, compare_rule_hits
from app.extractors.schema_registry import get_schema_for_doc_type
from app.llm.prompts.version import PROMPT_VERSION
from app.llm.provider_factory import get_llm_provider
from app.models import AuditIssue
from app.services.batch_service import add_files_to_batch, create_batch
from app.services.workflow_service import run_full_pipeline
from app.storage.factory import get_storage_backend


def load_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    return rows


async def run_extraction_evaluation(dataset_dir: str, extraction_labels_path: str) -> dict[str, Any]:
    labels = load_jsonl(extraction_labels_path)
    provider = get_llm_provider()

    results: list[dict[str, Any]] = []
    for label in labels:
        doc_type = label["doc_type"]
        schema = get_schema_for_doc_type(doc_type)
        if not schema:
            continue

        file_path = Path(dataset_dir) / label["file_name"]
        pdf_bytes = file_path.read_bytes()

        output = await provider.extract_structured(
            file_name=file_path.name,
            pdf_bytes=pdf_bytes,
            schema_name=schema["schema_name"],
            schema_definition=schema,
        )

        fields = label["fields_to_eval"]
        eval_result = compare_extraction(expected=label["gold_data"], actual=output.data, fields=fields)
        results.append(
            {
                "file_name": file_path.name,
                "doc_type": doc_type,
                "accuracy": eval_result["accuracy"],
                "mismatches": eval_result["mismatches"],
                "prompt_version": output.prompt_version or PROMPT_VERSION,
            }
        )

    summary = aggregate_extraction(results)
    return {
        "prompt_version": PROMPT_VERSION,
        "summary": summary,
        "details": results,
    }


async def run_rule_evaluation(dataset_dir: str, audit_labels_path: str) -> dict[str, Any]:
    labels = json.loads(Path(audit_labels_path).read_text(encoding="utf-8"))
    provider = get_llm_provider()
    storage = get_storage_backend()
    init_db()

    batch_results: list[dict[str, Any]] = []

    with Session(get_runtime_engine()) as session:
        for batch_label in labels["batches"]:
            files = []
            for file_name in batch_label["file_names"]:
                path = Path(dataset_dir) / file_name
                files.append((file_name, path.read_bytes()))

            batch = create_batch(session=session, uploader="golden-eval")
            add_files_to_batch(session=session, storage=storage, batch_id=batch.batch_id, files=files)
            await run_full_pipeline(
                session=session,
                storage=storage,
                provider=provider,
                batch_id=str(batch.batch_id),
            )

            issues = list(session.exec(select(AuditIssue).where(AuditIssue.batch_id == batch.batch_id)).all())
            actual_rules = {issue.rule_id for issue in issues}
            expected_rules = set(batch_label["expected_hit_rules"])
            rule_metrics = compare_rule_hits(expected_rules=expected_rules, actual_rules=actual_rules)
            batch_results.append(
                {
                    "batch_name": batch_label["batch_name"],
                    "expected_hit_rules": sorted(expected_rules),
                    "actual_hit_rules": sorted(actual_rules),
                    **rule_metrics,
                }
            )

    overall_tp = sum(item["tp"] for item in batch_results)
    overall_fp = sum(item["fp"] for item in batch_results)
    overall_fn = sum(item["fn"] for item in batch_results)
    precision = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) else 0.0
    recall = overall_tp / (overall_tp + overall_fn) if (overall_tp + overall_fn) else 0.0

    return {
        "prompt_version": PROMPT_VERSION,
        "summary": {
            "tp": overall_tp,
            "fp": overall_fp,
            "fn": overall_fn,
            "precision": precision,
            "recall": recall,
        },
        "batches": batch_results,
    }
