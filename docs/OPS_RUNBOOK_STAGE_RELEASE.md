# Ops Runbook (Stage Release, v1_real)

## Scope
- This runbook is for the stage-released evaluation flow on `examples/golden_dataset/v1_real`.
- Gold files are frozen in this stage and must not be edited during routine reruns.

## Key `.env` configuration
- `LLM_MODE=gemini`
- `RELAY_GEMINI_BASE_URL=https://oneapi.gemiaude.com`
- `RELAY_GEMINI_API_KEY=...`
- `RELAY_GEMINI_MODEL=gemini-3.1-flash-lite-preview`
- `PDF_PROVIDER_SIZE_THRESHOLD_MB=50`
- `ENABLE_PROVIDER_ESCALATION=true`
- `OFFICIAL_GEMINI_API_KEY=...` (or `ORG_GEMINI_API_KEY=...`)
- `OFFICIAL_GEMINI_PARSE_MODEL=gemini-3.1-flash-lite-preview`
- `OFFICIAL_GEMINI_COMPLEX_MODEL=gemini-3.1-pro-preview`
- `ENABLE_OFFICIAL_COMPLEX_ESCALATION=false`
- `LLM_CACHE_ENABLED=true`
- `LLM_CACHE_DIR=./.cache/llm_results`

## Cold-cache full run
1. Optional: point to a new cache directory for strict cold-run benchmarking.
2. Run:
   - `env PYTHONPATH=. LLM_MODE=gemini RELAY_GEMINI_BASE_URL=https://oneapi.gemiaude.com RELAY_GEMINI_MODEL=gemini-3.1-flash-lite-preview PDF_PROVIDER_SIZE_THRESHOLD_MB=50 LLM_CACHE_DIR=./.cache/llm_results_cold_<tag> python3 scripts/eval_v1_real_fast.py --stage all --llm-mode gemini --database-url sqlite:///./hse_audit_eval_stage_release_cold_<tag>.db --output /Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/eval_output.stage_release.cold_<tag>.json`

## Hot-cache full run
1. Reuse the same cache directory as previous extraction run.
2. Run:
   - `env PYTHONPATH=. LLM_MODE=gemini RELAY_GEMINI_BASE_URL=https://oneapi.gemiaude.com RELAY_GEMINI_MODEL=gemini-3.1-flash-lite-preview PDF_PROVIDER_SIZE_THRESHOLD_MB=50 python3 scripts/eval_v1_real_fast.py --stage all --llm-mode gemini --database-url sqlite:///./hse_audit_eval_stage_release_hot_<tag>.db --output /Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/eval_output.stage_release.hot_<tag>.json`

## Evaluate-only (no re-extraction)
1. Keep database and `batch_id` from an existing extraction run.
2. Run:
   - `env PYTHONPATH=. LLM_MODE=gemini python3 scripts/eval_v1_real_fast.py --stage evaluate --llm-mode gemini --database-url sqlite:///./<existing_db>.db --batch-id <existing_batch_id> --output /Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/eval_output.stage_release.evaluate_only_<tag>.json`

## How to inspect provider/cache hits
- In output JSON:
  - `counts.cache_hit`
  - `counts.official_cache_hit`
  - `extraction.file_details[].observability.provider_selected`
  - `extraction.file_details[].observability.cache_source_provider`
  - `extraction.file_details[].observability.model_selected`

## Safe full-run rerun checklist
- Do not overwrite previous output file.
- Use a new `--database-url` file for each rerun.
- Keep frozen gold files unchanged:
  - `examples/golden_dataset/v1_real/extraction_gold_labels.fixed.v1.jsonl`
  - `examples/golden_dataset/v1_real/audit_gold_labels.fixed.v1.json`
- Keep default route config unchanged unless explicitly doing a controlled experiment.
