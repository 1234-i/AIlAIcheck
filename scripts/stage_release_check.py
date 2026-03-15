from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate stage release gates from manifest + full-run report")
    parser.add_argument("--manifest", default="stage_release_manifest.json")
    parser.add_argument("--strict", action="store_true", help="fail if manifest metrics snapshot differs from report")
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _status_counts(report: dict[str, Any]) -> dict[str, int]:
    c = Counter(item.get("status") for item in report.get("audit_assertion_eval", {}).get("per_assertion", []))
    return {
        "TP": int(c.get("TP", 0)),
        "FP": int(c.get("FP", 0)),
        "FN": int(c.get("FN", 0)),
        "TN": int(c.get("TN", 0)),
    }


def _provider_stats(report: dict[str, Any]) -> dict[str, Any]:
    file_details = report.get("extraction", {}).get("file_details", [])
    selected_count = int(report.get("run_meta", {}).get("selected_file_count", 0)) or len(file_details)
    provider_counter: Counter[str] = Counter()

    transport_fail_files = 0
    for item in file_details:
        obs = item.get("observability") or {}
        provider = str(obs.get("provider_selected") or "").strip()
        if provider:
            provider_counter[provider] += 1

        raw_status = str(obs.get("raw_response_status") or "").lower()
        parse_error_category = str(obs.get("parse_error_category") or "").lower()
        err_text = " ".join(str(e) for e in (item.get("extraction_errors") or [])).lower()

        has_transport_fail = (
            raw_status.startswith("error")
            or "transport" in parse_error_category
            or "timeout" in parse_error_category
            or "llm_transport_error" in err_text
            or "llm_timeout" in err_text
            or "http error" in err_text
            or "payload too large" in err_text
        )
        if has_transport_fail:
            transport_fail_files += 1

    official_count = provider_counter.get("official", 0)
    official_share = (official_count / selected_count) if selected_count else 0.0
    transport_fail_rate = (transport_fail_files / selected_count) if selected_count else 0.0

    return {
        "selected_file_count": selected_count,
        "provider_distribution": dict(provider_counter),
        "official_count": official_count,
        "official_share": official_share,
        "transport_fail_files": transport_fail_files,
        "transport_fail_rate": transport_fail_rate,
    }


def _cache_stats(report: dict[str, Any]) -> dict[str, Any]:
    counts = report.get("counts", {}) or {}
    selected_count = int(report.get("run_meta", {}).get("selected_file_count", 0))
    cache_hit = int(counts.get("cache_hit", 0))
    cache_hit_rate = (cache_hit / selected_count) if selected_count else 0.0
    return {
        "cache_hit": cache_hit,
        "selected_file_count": selected_count,
        "cache_hit_rate": cache_hit_rate,
        "official_cache_hit": int(counts.get("official_cache_hit", 0)),
    }


def _print_check(ok: bool, name: str, detail: str) -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}: {detail}")


def main() -> int:
    args = parse_args()
    root = Path(".").resolve()
    manifest_path = (root / args.manifest).resolve()
    if not manifest_path.exists():
        print(f"[FAIL] manifest missing: {manifest_path}")
        return 2

    manifest = _load_json(manifest_path)
    report_path = (root / manifest["passed_full_run_report"]).resolve()
    if not report_path.exists():
        print(f"[FAIL] full-run report missing: {report_path}")
        return 2
    report = _load_json(report_path)

    ok_all = True

    print("Stage release check")
    print(f"manifest: {manifest_path}")
    print(f"baseline extraction: {manifest['gold_baselines']['extraction']}")
    print(f"baseline audit: {manifest['gold_baselines']['audit']}")
    print(f"full-run report: {manifest['passed_full_run_report']}")

    # Baseline and docs existence
    for key, rel in manifest.get("gold_baselines", {}).items():
        p = (root / rel).resolve()
        ok = p.exists()
        _print_check(ok, f"baseline.{key}", str(p))
        ok_all = ok_all and ok

    for doc in manifest.get("docs", []):
        p = (root / doc).resolve()
        ok = p.exists()
        _print_check(ok, "doc.exists", str(p))
        ok_all = ok_all and ok

    # Assertion gate checks
    status = _status_counts(report)
    gates = manifest.get("release_gates", {})

    fp_target = int(gates.get("fp_must_equal", 0))
    fn_target = int(gates.get("fn_must_equal", 0))
    fp_ok = status["FP"] == fp_target
    fn_ok = status["FN"] == fn_target
    _print_check(fp_ok, "gate.fp", f"actual={status['FP']} target={fp_target}")
    _print_check(fn_ok, "gate.fn", f"actual={status['FN']} target={fn_target}")
    ok_all = ok_all and fp_ok and fn_ok

    # Official usage and transport failure gates
    pstats = _provider_stats(report)
    official_share_max = float(gates.get("official_usage_share_max", 0.10))
    transport_fail_rate_max = float(gates.get("provider_transport_failure_rate_max", 0.01))
    official_ok = pstats["official_share"] <= official_share_max
    transport_ok = pstats["transport_fail_rate"] < transport_fail_rate_max
    _print_check(
        official_ok,
        "gate.official_usage_share",
        f"actual={pstats['official_share']:.4f} limit={official_share_max:.4f} ({pstats['official_count']}/{pstats['selected_file_count']})",
    )
    _print_check(
        transport_ok,
        "gate.provider_transport_failure_rate",
        f"actual={pstats['transport_fail_rate']:.4f} limit={transport_fail_rate_max:.4f} ({pstats['transport_fail_files']}/{pstats['selected_file_count']})",
    )
    ok_all = ok_all and official_ok and transport_ok

    # Hot-cache full-run gate
    cstats = _cache_stats(report)
    hot_cache_min_rate = float(gates.get("hot_cache_hit_rate_min", 0.95))
    hot_cache_ok = cstats["cache_hit_rate"] >= hot_cache_min_rate
    _print_check(
        hot_cache_ok,
        "gate.hot_cache_hit_rate",
        f"actual={cstats['cache_hit_rate']:.4f} limit={hot_cache_min_rate:.4f} ({cstats['cache_hit']}/{cstats['selected_file_count']})",
    )
    ok_all = ok_all and hot_cache_ok

    # Optional strict snapshot consistency
    if args.strict:
        snap = manifest.get("metrics_snapshot", {})
        strict_checks = {
            "precision": float(report.get("audit_assertion_eval", {}).get("precision", 0.0)),
            "recall": float(report.get("audit_assertion_eval", {}).get("recall", 0.0)),
            "tp": status["TP"],
            "fp": status["FP"],
            "fn": status["FN"],
            "tn": status["TN"],
        }
        strict_ok = True
        for key, actual in strict_checks.items():
            expected = snap.get(key)
            if expected is None:
                continue
            if isinstance(expected, float):
                same = abs(float(expected) - float(actual)) < 1e-9
            else:
                same = expected == actual
            _print_check(same, f"snapshot.{key}", f"actual={actual} expected={expected}")
            strict_ok = strict_ok and same
        ok_all = ok_all and strict_ok

    print("result:", "PASS" if ok_all else "FAIL")
    print("release_manifest:", manifest_path)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
