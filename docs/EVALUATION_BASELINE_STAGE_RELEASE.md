# Evaluation Baseline (Stage Release, v1_real)

## Frozen gold baseline
- Extraction gold:
  - `/Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/extraction_gold_labels.fixed.v1.jsonl`
- Audit gold:
  - `/Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/audit_gold_labels.fixed.v1.json`

## Passing full-run report (stage release)
- Report file:
  - `/Users/wei.lb/Documents/vibecoding/AllAICheck/examples/golden_dataset/v1_real/eval_output.gemini.v1_real.full.relay50.round7.json`

## Passed metrics snapshot
- Assertion:
  - `TP=9`
  - `FP=0`
  - `FN=0`
  - `TN=8`
  - `recall=1.0`
  - `precision=0.5625`
- Extraction:
  - `overall_field_accuracy=0.205607476635514`
- Provider/cache:
  - provider usage: relay=30, official=1, local_weak=6
  - cache hit: 37/37 (hot-cache run)

## Release gate targets and current status
- FP must be 0: `PASS`
- Provider transport failure rate <1%: `PASS` (no transport/parse failure in stage pass run)
- Official usage share <10%: `PASS` (1/37)
- Hot-cache full-run runtime <10s: `PASS` (~3s)
- Cache hit rate >=95% on hot reruns: `PASS` (100%)

## Migration validation recommendations
- For new projects/domains, run:
  - 1 cold-cache full run
  - 1 hot-cache full run
  - targeted subset replay on manual-authoritative assertions
- Keep the same gate thresholds initially; tune only after collecting at least 2 full reruns.
- If manual-authoritative assertions drift, adjust only narrow bridge conditions first; avoid broad rule/prompt rewrites.
