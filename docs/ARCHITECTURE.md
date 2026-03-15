# System Architecture

## Overview
The system is a modular backend that processes contractor PDF batches asynchronously and produces evidence-grounded audit reports.

## Module Boundaries
- `api`: external contract surface (upload, query, audit, review, export).
- `services`: orchestration logic coordinating storage, LLM calls, normalization, rule execution.
- `llm`: provider-agnostic interfaces and Gemini/mock adapters.
- `extractors`: doc-type schema selection and extraction orchestration.
- `rule_engine`: deterministic rule evaluation, evidence linking, issue composition.
- `reports`: report assembly and Excel export.
- `storage`: S3/local abstraction.
- `db/models`: persisted domain and execution records.
- `tasks`: asynchronous workflow orchestration with Celery.

## Data Flow
1. Upload API receives PDFs, writes source files to storage, creates `BatchRecord` + `FileRecord`.
2. Task queue runs classification pipeline.
3. Classification assigns `doc_type`, `primary_group`, `related_groups`, confidence, evidence.
4. Extraction pipeline calls LLM with selected schema.
5. Validated extraction is normalized into master facts.
6. Rule engine executes rules over normalized facts and links evidence.
7. Report pipeline composes issue list and exports JSON/Excel.

## Async Task Flow
- `batch_upload_received` -> `classify_files` -> `extract_files` -> `normalize_facts` -> `run_rules` -> `generate_report`.
- Task retry policy: exponential backoff, max retries configurable per step.
- Dead-letter handling: failed tasks marked with reason for manual intervention.

## Evidence Chain Mechanism
Each issue references one or more `EvidenceItem` objects containing:
- `file_id`, `file_name`
- `page`
- `snippet`
- `field_path`
- optional `locator` (bounding location, if provided)
- `rule_id`, `clause_id`

Issue creation guard: no issue persisted unless evidence chain meets minimum required evidence count for triggering rule.

## Model Invocation Flow
- Service invokes `LLMProvider` interface only.
- Provider selected by `LLM_MODE` (`mock`, `gemini`, `auto`).
- Gemini adapter reads PDFs via `inline_data` base64 and returns structured JSON.
- Response is validated against strict schemas before downstream use.

## Audit Engine Flow
1. Load active rules by version and group.
2. Build rule context from normalized facts.
3. Evaluate rules deterministically by logic type.
4. Generate issue draft from templates.
5. Attach evidence chain.
6. Persist rule results and issue records.

## Report Generation Flow
- Aggregate batch metadata, issue summary, and detailed findings.
- Apply wording templates for human-style report language.
- Optional LLM phrasing refinement (non-authoritative; rule results remain source of truth).
- Export JSON and Excel workbook.

## Human Review and Fallback Strategy
- Reviewers can accept/reject/edit issue text and severity.
- Reviewer actions are stored with actor/time/reason.
- Re-run supports selective scopes (single file, single group, all).
- OCR fallback reserved as architecture hook only; not active in MVP.

## Deployment Topology (MVP)
- API service (FastAPI)
- Worker service (Celery workers)
- PostgreSQL
- Redis
- S3-compatible storage
- Optional reverse proxy/API gateway
