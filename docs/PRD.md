# PRD — Contractor HSE Document Audit System

## Product Goals
- Provide automated, evidence-grounded contractor HSE document audit for project admission and ongoing compliance checks.
- Reduce manual review time while increasing detection of cross-document contradictions and closure breaks.
- Produce auditor-style findings suitable for operational remediation workflows.

## Target Users
- HSE auditors (primary)
- Project owner supervision teams
- Contractor compliance managers
- Internal quality and legal reviewers

## End-to-End Workflow
1. User uploads a full batch of project PDFs.
2. System creates `batch_record` and persists files.
3. Filename-based first-pass classification is executed.
4. Ambiguous files trigger Gemini content classification.
5. Known `doc_type` files trigger template-based structured extraction.
6. Extraction outputs are schema-validated and normalized into fact layer.
7. Rule engine executes completeness/validity/consistency/closure/anomaly checks.
8. Issues are generated only with evidence chain.
9. Human-like audit report is generated and exported in JSON/Excel.
10. Reviewer can accept/reject/edit issues and re-run selective audits.

## Input / Output
### Input
- Multipart batch upload of PDFs.
- Optional batch metadata (project hint, contractor hint, language).
- Optional policy files for AI-assisted rule drafting.

### Output
- Classification records (`doc_type`, `primary_group`, `related_groups`, confidence, evidence).
- Structured extraction records per file and schema.
- Rule execution results with hit status and evidence.
- Audit issues and final report artifacts (JSON, Excel).

## Audit Scenarios
- Project admission package completeness verification.
- Personnel qualification/medical/insurance consistency validation.
- Entry permit and training closure checks.
- Equipment and inspection consistency checks.
- Risk analysis and control measure matching checks.
- Cross-document contradiction scan (project name, contractor, timeline, key roles).

## MVP Scope
Included:
- Six audit groups.
- Native Gemini PDF direct-read integration via provider adapter.
- Deterministic mock mode without API key.
- Rule engine categories required by architecture.
- Evidence-chain-enforced issue generation.
- JSON and Excel report export.

Excluded from MVP:
- OCR fallback implementation.
- Full interactive web frontend.
- Advanced policy lifecycle governance UI.

## Future Iterations
- OCR fallback execution path with confidence arbitration.
- Active learning loop from reviewer decisions.
- Multi-project benchmarking dashboards.
- Automated regulation updates and clause impact analysis.
- Multi-language report rendering templates.

## Success Metrics
- >= 95% extraction schema validity rate on supported templates.
- >= 90% precision for high-severity findings in golden dataset.
- >= 99% issue-to-evidence traceability completeness.
- >= 50% median reduction in audit turnaround time vs manual baseline.
