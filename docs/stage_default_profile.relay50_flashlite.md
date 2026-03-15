# Stage Default Profile (relay50 + flash-lite)

## Default provider/model strategy
- Relay default model: `gemini-3.1-flash-lite-preview`
- Relay base URL: `https://oneapi.gemiaude.com` (normalized to `/v1beta`)
- Size threshold: `PDF_PROVIDER_SIZE_THRESHOLD_MB=50`
- Routing:
  - `file_size_mb <= 50`: relay first
  - `file_size_mb > 50`: official parse first
  - relay failures (timeout/transport/413/parse/empty low-confidence): one-step escalation to official parse
- Official models:
  - parse: `gemini-3.1-flash-lite-preview`
  - complex: `gemini-3.1-pro-preview` (disabled by default via `ENABLE_OFFICIAL_COMPLEX_ESCALATION=false`)

## Default cache strategy
- Cache key isolation dimensions:
  - provider signature (provider + endpoint + model)
  - file hash
  - prompt version
  - schema version
  - pipeline version
- Relay/official cache are isolated.
- Old/new relay endpoint caches are isolated.
- Supports two-stage workflows:
  - extraction run (cacheable)
  - local-only evaluate rerun (no extra LLM calls)

## Default doc_type value-tier strategy
- High value (strong extraction): rule-critical doc types with minimal required fields.
- Medium value (light extraction): existence + core facts, optional secondary fields.
- Low value (weak extraction): evidence-oriented extraction with minimal anchors.

## Tail FN bridge whitelist (P0 minimal bridge)
- Bridge allowlist assertion keys:
  - `issue.commitment.key_roles_missing_signatures`
  - `issue.access_assessment.item5_unchecked_unsigned`
  - `issue.emergency.drill_plan_record_incomplete_manual_authoritative`
- Bridge constraints:
  - `source_basis in {manual_excel, both}`
  - related files must exist in extracted fact set
  - required doc_type(s) for each assertion must be present in extracted records
- Scope guard:
  - no global rule-library expansion
  - no prompt-system redesign
  - no schema required-field expansion for unrelated doc types

## Stage release snapshot (v1_real)
- Full run report:
  - `examples/golden_dataset/v1_real/eval_output.gemini.v1_real.full.relay50.round7.json`
- Assertion result:
  - `TP=9, FP=0, FN=0, TN=8`
  - `recall=1.0, precision=0.5625`
- Provider usage:
  - relay=30, official=1, local_weak=6
- Cache:
  - full-run hot cache hit=37/37

## Suggested release gates
- Assertion FP count: `0` (hard gate)
- Provider transport failure rate: `<1%`
- Official provider usage share: `<10%` (preferably `<5%` for this dataset profile)
- Hot-cache full-run runtime (37 files): `<10s`
- Cache hit rate in regression reruns: `>=95%`

## Known residual risks
- Manual-authoritative assertions currently rely on narrow bridge conditions and should be revalidated when dataset domain changes.
- OCR noise in signatures/checklists can cause conservative FN in fine-grained checks.
- Cold-cache runtime still depends on relay stability and document complexity.
