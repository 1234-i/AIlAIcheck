# Multi-Agent Task Board

This board splits work into agent-friendly packages for parallel delivery.

## Package A — Platform Foundation
- Objective: bootstrap app/runtime, config, logging, DB session, storage abstraction, Celery wiring.
- Inputs: `ARCHITECTURE.md`, `SECURITY.md`.
- Outputs: runnable API and worker skeleton.
- Dependencies: none.
- Definition of Done: app boots, worker starts, health endpoint passes.
- Test Points: config load test, DB init test, storage adapter unit tests.

## Package B — API Contracts
- Objective: implement API routes/schemas from `API_SPEC.md`.
- Inputs: `API_SPEC.md`, `JSON_SCHEMA.md`.
- Outputs: route stubs, request/response models, error envelope.
- Dependencies: Package A.
- Definition of Done: documented endpoints callable and schema-valid.
- Test Points: request validation tests, route smoke tests.

## Package C — LLM Provider Layer
- Objective: implement provider interface + Gemini + mock adapters.
- Inputs: `MULTIMODAL_PDF.md`, `SECURITY.md`.
- Outputs: `LLMProvider`, Gemini client, deterministic mock outputs.
- Dependencies: Package A.
- Definition of Done: all interface methods available and test-covered.
- Test Points: payload assembly tests, mock determinism tests, timeout/retry tests.

## Package D — Classification & Template Extraction
- Objective: filename classifier + content correction + extraction orchestration.
- Inputs: `DOMAIN_MODEL.md`, `JSON_SCHEMA.md`.
- Outputs: classification and extraction service modules.
- Dependencies: Packages B, C.
- Definition of Done: supported doc types extract to schema-valid JSON.
- Test Points: ambiguous filename cases, per-template extraction validation tests.

## Package E — Normalization & Fact Layer
- Objective: map extraction outputs into project/person/equipment/file masters.
- Inputs: `DOMAIN_MODEL.md`.
- Outputs: normalization services and relation persistence.
- Dependencies: Package D.
- Definition of Done: deterministic normalized records with provenance.
- Test Points: entity merge tests, cross-source provenance tests.

## Package F — Rule Engine Core
- Objective: implement rule schema/loader/executor/evidence linker.
- Inputs: `RULE_ENGINE.md`, seed rule files.
- Outputs: rule execution results and issue generation.
- Dependencies: Package E.
- Definition of Done: required rule categories runnable with evidence guard.
- Test Points: positive/negative rule hits, no-evidence suppression, version snapshot tests.

## Package G — Report & Export
- Objective: compose auditor-style report and export JSON/Excel.
- Inputs: rule execution results + evidence + templates.
- Outputs: report generator and exporter modules.
- Dependencies: Package F.
- Definition of Done: JSON and Excel exports consistent with report schema.
- Test Points: workbook structure tests, report item field completeness.

## Package H — Human Review Workflow
- Objective: issue review APIs and rerun hooks.
- Inputs: issue schema, report model.
- Outputs: review endpoints and status transitions.
- Dependencies: Packages B, F, G.
- Definition of Done: review actions persisted and auditable.
- Test Points: accept/reject/edit path tests, audit trail integrity tests.

## Package I — Test Harness & Demo
- Objective: build fixture packs, integration/e2e suites, demo scripts.
- Inputs: all package outputs.
- Outputs: CI-oriented tests and local demo runnable path.
- Dependencies: cross-cutting.
- Definition of Done: deterministic local run with mock mode and passing test suite.
- Test Points: full pipeline e2e, regression snapshots, failure-path retries.
