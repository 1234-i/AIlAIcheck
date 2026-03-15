from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class BinaryMetrics:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0


def compare_extraction(expected: dict[str, Any], actual: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    matched = 0
    mismatches: list[dict[str, Any]] = []
    for field in fields:
        expected_val = expected.get(field)
        actual_val = actual.get(field)
        if str(expected_val).strip() == str(actual_val).strip():
            matched += 1
        else:
            mismatches.append({"field": field, "expected": expected_val, "actual": actual_val})

    total = len(fields)
    return {
        "matched": matched,
        "total": total,
        "accuracy": matched / total if total else 0.0,
        "mismatches": mismatches,
    }


def compare_rule_hits(expected_rules: set[str], actual_rules: set[str]) -> dict[str, Any]:
    metrics = BinaryMetrics(
        tp=len(expected_rules & actual_rules),
        fp=len(actual_rules - expected_rules),
        fn=len(expected_rules - actual_rules),
    )
    return {
        "tp": metrics.tp,
        "fp": metrics.fp,
        "fn": metrics.fn,
        "precision": metrics.precision,
        "recall": metrics.recall,
        "false_positives": sorted(actual_rules - expected_rules),
        "false_negatives": sorted(expected_rules - actual_rules),
    }


def aggregate_extraction(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_doc_type: dict[str, list[float]] = defaultdict(list)
    for item in results:
        by_doc_type[item["doc_type"]].append(item["accuracy"])

    summary = {
        doc_type: {
            "count": len(scores),
            "avg_accuracy": sum(scores) / len(scores) if scores else 0.0,
        }
        for doc_type, scores in by_doc_type.items()
    }
    overall_scores = [item["accuracy"] for item in results]
    return {
        "overall_avg_accuracy": sum(overall_scores) / len(overall_scores) if overall_scores else 0.0,
        "by_doc_type": summary,
    }
