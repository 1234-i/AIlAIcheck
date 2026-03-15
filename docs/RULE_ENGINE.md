# Rule Engine Design

## Objectives
- Deterministic, configurable, versioned rule execution.
- Evidence-grounded issue output.
- Support for both strict contradictions and soft anomaly signals.

## Rule Schema
Required fields:
- `rule_id`
- `clause_id`
- `rule_name`
- `audit_group`
- `audit_object`
- `checkpoint`
- `evidence_required`
- `logic_type`
- `severity`
- `issue_template`
- `rectification_template`
- `enabled`
- `version`

Optional fields:
- `preconditions`
- `threshold`
- `metadata`

## Rule Categories
1. Single-document presence rules
2. Single-document required-field completeness rules
3. Date validity rules
4. Person cross-document consistency rules
5. Equipment cross-document consistency rules
6. Training/permit/entry closure rules
7. Risk-to-control matching rules
8. Anomaly/soft contradiction rules

## Single-Document Rules
- Evaluate document presence and mandatory field completeness.
- Use extraction schemas to verify field existence and type validity.

## Cross-Document Rules
- Match entities by normalized keys (name hash, role, equipment serial).
- Compare values across contract, permit, plan, and inspection files.
- Detect mismatches in project identity, contractor identity, role assignment, and equipment coverage.

## Soft Contradiction Framework
- Produces `warn` or `risk` outcomes with confidence scores.
- Uses heuristic signals and optional model-assisted phrasing.
- Requires evidence snippets from at least two conflicting sources.

## Execution Pipeline
1. Load active rule set by version.
2. Build fact context for batch.
3. Evaluate rules by `logic_type`.
4. Build candidate findings.
5. Attach evidence and clause references.
6. Suppress findings lacking minimum evidence.
7. Persist execution results and issues.

## Rule Versioning
- Semantic version string (`major.minor.patch`).
- Activation window (`effective_from`, `effective_to`).
- Each audit run stores rule snapshot version set.

## AI Draft Rule + Human Review Flow
1. Upload policy text/PDF.
2. Gemini drafts structured rules.
3. Human reviewer validates clause mapping and logic.
4. Approved rules enter formal rule library.
5. Rejected drafts stored for traceability.

## Rule Execution Result Contract
Each result includes:
- `hit` / `not_hit`
- `evidence_items`
- `related_files`
- `related_pages`
- `generated_issue_text`
- `clause_id`
- `severity`
- `confidence`
