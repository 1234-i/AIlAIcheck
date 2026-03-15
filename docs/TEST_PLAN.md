# Test Plan

## Unit Test Strategy
Focus:
- schema validation and coercion boundaries.
- filename classifier logic.
- Gemini request payload creation.
- mock provider deterministic outputs.
- rule evaluator logic by category.
- evidence chain enforcement.
- report rendering and Excel sheet formatting.

## Integration Test Strategy
Flows:
- Upload -> classify -> extract -> audit -> report in mock mode.
- API endpoints with DB and local storage adapters.
- Task invocation behavior and idempotent triggers.

## End-to-End Strategy
- Use sample project batch containing mixed document types.
- Run full asynchronous workflow.
- Assert final issue count, critical findings, and evidence completeness.
- Validate JSON and Excel outputs against schema and expected structure.

## Evaluation Samples
- Curated sample sets:
  - complete compliant package
  - missing documents package
  - contradictory personnel package
  - equipment mismatch package
  - timeline anomaly package

## Regression Testing
- Golden snapshots for normalized facts and issue lists.
- Rule set version pinning per regression suite.
- CI gate for changed rule behavior with baseline diff output.

## Model Mocking Strategy
- Default local test mode uses `MockProvider` when key unavailable.
- Mock outputs are deterministic by input hash + fixed fixtures.
- Contract tests ensure mock response shape equals real provider schema contracts.

## Non-Functional Tests
- Large batch upload stress test.
- Worker retry behavior under transient provider failures.
- Storage read/write latency threshold checks.
- Security checks for secret redaction in logs.
