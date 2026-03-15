# Productization Checklist (Stage Release)

## Ready now
- Stable default route:
  - relay50 + flash-lite default
  - official parse fallback with low usage
- Cache isolation and high hit-rate reruns
- Incremental/targeted evaluation pipeline
- Frozen gold baseline and passing full-run evidence
- Tail FN bridge coverage for stage dataset

## Remaining productization items
### P0
- Add CI job to replay stage full-run in evaluate-only mode and verify gate metrics.
- Add release artifact manifest:
  - config profile
  - runbook
  - baseline report pointer

### P1
- Add dashboard summary script for:
  - provider usage trend
  - cache hit trend
  - assertion TP/FP/FN deltas between runs
- Add migration validation template for new project onboarding.

### P2
- Introduce structured alerting thresholds for:
  - official usage spike
  - transport failure spike
  - sudden FN regression in manual-authoritative assertions

## Priority order
1. P0 CI replay and release manifest
2. P1 trend dashboard and migration template
3. P2 alerting automation
