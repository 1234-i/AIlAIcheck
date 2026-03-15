# Development Plan

## Phase Sequence

## Phase 1 — Documentation and Contracts
Deliverables:
- `README.md`
- all docs under `docs/`
- JSON contract definitions
- API contract baseline
- task decomposition

Dependencies: none

## Phase 2 — Project Skeleton
Deliverables:
- FastAPI app bootstrap
- settings and logging
- DB session/models base
- Celery worker scaffold
- storage abstraction
- upload API stub

Dependencies: Phase 1

## Phase 3 — Gemini Adapter Layer
Deliverables:
- provider interface
- Gemini relay client with `inline_data(base64)`
- mock provider
- prompt templates and typed LLM response schemas

Dependencies: Phase 2

## Phase 4 — Classification and Extraction
Deliverables:
- filename classifier
- ambiguity content classifier
- doc-type extraction orchestrator
- schema validation and persistence

Dependencies: Phase 3

## Phase 5 — Rule Engine
Deliverables:
- rule schema and loader
- deterministic executor
- cross-doc consistency checks
- soft contradiction framework
- evidence guard

Dependencies: Phase 4

## Phase 6 — Report and Export
Deliverables:
- issue composition and report model
- JSON report API
- Excel export

Dependencies: Phase 5

## Phase 7 — Testing and Demo
Deliverables:
- unit/integration/e2e tests
- model mocks and fixtures
- sample input batch and expected outputs
- runnable demo script

Dependencies: all prior phases

## Main Risks
- LLM extraction variability across template variants.
- Ambiguous entity matching across documents.
- Evidence snippet quality for scanned/low-quality PDFs.
- Queue stability under large-batch processing.

## Risk Mitigations
- strict schema validation and retry prompts.
- normalized canonical keys and fuzzy-match thresholds.
- confidence gating with manual review fallback.
- task retry/backoff and idempotent workflows.

## Test Strategy Summary
- Unit: adapters, schema validation, rule evaluators.
- Integration: upload -> classify -> extract -> audit pipeline with mock provider.
- E2E: full batch run, report export, review update.
- Regression: golden datasets and expected issue snapshots.

## Parallelizable Modules
- API contracts and request schemas.
- LLM adapter layer and prompt packs.
- Storage abstraction.
- Rule loader and rule definitions.
- Report exporter.

## Serial-Only Modules
- Finalized domain model before normalization layer.
- Rule executor before report composition finalization.
- End-to-end workflow wiring after major components stabilize.
