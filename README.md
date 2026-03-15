# Contractor HSE Document Audit System

## Project Background
Contractor project onboarding and HSE compliance audits are often manual, slow, and inconsistent. This project provides a production-oriented backend that audits full batches of contractor PDF documents using native multimodal LLM PDF reading, deterministic rule execution, and evidence-grounded reporting.

## Goals
- Audit uploaded project document batches for HSE compliance.
- Classify document types with filename-first and content-correction strategy.
- Extract structured facts from common HSE document templates.
- Normalize extracted facts into cross-document domain records.
- Detect completeness, validity, consistency, closure, and anomaly issues.
- Produce auditor-style report outputs in JSON and Excel.

## Core Capabilities
- Batch PDF upload and asynchronous processing.
- Native Gemini PDF direct-read via `inline_data(base64)`.
- Template-based structured extraction per document type.
- Configurable and versioned rule engine.
- Evidence chain for every issue (file/page/snippet/rule/clause).
- Human review API for issue acceptance/rejection/edit.
- Mock LLM mode for local development without real API key.

## Technical Route
- Backend: FastAPI
- Schemas: Pydantic
- Persistence: SQLModel + PostgreSQL (primary)
- Async: Celery + Redis
- Storage: S3-compatible object storage (local fallback)
- LLM calls: `httpx` via provider adapter pattern
- Excel export: `openpyxl`
- Testing: `pytest`

## Scope Boundaries (MVP)
Included:
- End-to-end backend pipeline from upload to report export.
- Gemini provider adapter and deterministic mock mode.
- Rule engine core and evidence chain enforcement.
- Phase-2 hardened MVP scope:
  - 4 supported doc types (`construction_contract`, `personnel_qualification_review_form`, `entry_permit`, `safety_education_training_record`)
  - 13 core rules
  - 3 cross-document checks (`person_role_consistency`, `person_training_closure`, `project_name_consistency`)

Deferred:
- OCR fallback implementation (architectural hook only).
- Full frontend UI.
- Advanced workflow orchestration dashboards.

## Quick Start
### 1) Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
make install-dev
cp .env.example .env
```

### 2) Start dependencies (example)
```bash
# postgres + redis + minio/s3 are expected for production-like local runs
```

### 3) Run API
```bash
make run
```

### 4) Run worker
```bash
make worker
```

### 5) Run tests
```bash
make test
```

### 6) Run mock demo pipeline
```bash
make demo
```

### 7) Run migrations
```bash
make upgrade
```

## Environment Variables
- `GEMINI_BASE_URL` (default: `https://reelxai.com/v1beta`)
- `GEMINI_API_KEY` (required for real Gemini calls)
- `GEMINI_AUDIT_MODEL` (default: `gemini-3.1-pro-preview`)
- `LLM_MODE` (`auto|gemini|mock`)
- `DATABASE_URL`
- `REDIS_URL`
- `S3_ENDPOINT_URL`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`

## Folder Structure Overview
```text
app/
  api/            # FastAPI routers
  core/           # settings, logging, constants
  db/             # engine/session setup
  models/         # SQLModel entities
  schemas/        # Pydantic schemas
  services/       # orchestration services
  llm/            # provider abstraction + Gemini + mock
  rule_engine/    # rule schema, loader, executor
  extractors/     # doc-type extraction schema registry
  reports/        # report composition and export
  tasks/          # Celery tasks
  storage/        # object storage abstraction

docs/             # product and engineering docs
tests/            # unit/integration/e2e tests
scripts/          # tooling scripts
examples/         # sample payloads/reports/rules
```

## Documentation Index
- [PRD](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Domain Model](docs/DOMAIN_MODEL.md)
- [Rule Engine](docs/RULE_ENGINE.md)
- [Multimodal PDF Strategy](docs/MULTIMODAL_PDF.md)
- [API Spec](docs/API_SPEC.md)
- [JSON Schema](docs/JSON_SCHEMA.md)
- [Development Plan](docs/DEVELOPMENT_PLAN.md)
- [Task Board](docs/TASK_BOARD.md)
- [Test Plan](docs/TEST_PLAN.md)
- [Security](docs/SECURITY.md)
- [Migrations](docs/MIGRATIONS.md)
- [Phase Status](docs/PHASE_STATUS.md)
