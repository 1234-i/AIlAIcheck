# Parallel Development Packages — Real-Data Validation Phase

## Package A — Real Gemini Extraction
- Objective: harden Gemini direct PDF extraction/classification with strict JSON schema output, retry/timeout controls, and raw-response observability.
- Changed modules: `app/llm/*`, `app/services/classification_service.py`, `app/services/extraction_service.py`, `app/core/config.py`.
- Dependencies: none (base platform already available).
- Tests: LLM unit tests for parse/validation/error fallback and service-level error-state tests.
- Definition of done: real Gemini mode can process the 4 target doc types with schema-validated output and mock mode remains fully functional.

## Package B — Golden Dataset + Evaluation
- Objective: provide anonymized pilot dataset and reproducible extraction/rule evaluation with FP/FN reporting and prompt-version traceability.
- Changed modules: `examples/golden_dataset/v1/*`, `scripts/build_golden_dataset.py`, `scripts/evaluate_golden.py`, `app/evaluation/*`.
- Dependencies: Package A extraction interfaces and stable rule execution path.
- Tests: integration test for closed-loop sample batches and evaluation script smoke run.
- Definition of done: dataset/labels generated, evaluation outputs include extraction accuracy + rule TP/FP/FN + prompt version.

## Package C — Rule Engine V2
- Objective: expand to ~25-30 evidence-backed high-value rules focused on personnel chain closure, date logic, project identity, and light risk/control checks.
- Changed modules: `examples/rules_v2_high_value.json`, `app/rule_engine/*`, `app/services/normalization_service.py`.
- Dependencies: Package A extraction outputs and Package B labels for calibration.
- Tests: rule evaluator unit tests and batch-level integration assertions against gold labels.
- Definition of done: v2 rules execute deterministically, every hit issue is evidence-backed, and evaluation reports rule-level FP/FN.

## Package D — Report/Export Refinement
- Objective: ensure reports and Excel export preserve standardized evidence chain and remain auditor-readable.
- Changed modules: `app/reports/*`, `docs/JSON_SCHEMA.md`, `docs/DOMAIN_MODEL.md`.
- Dependencies: Package C stabilized issue schema.
- Tests: report generation integration tests validating issue/evidence fields and Excel evidence sheet completeness.
- Definition of done: JSON/Excel exports include standardized evidence fields for every issue and pass schema checks.
