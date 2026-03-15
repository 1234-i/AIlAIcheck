from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.evaluation.runner import run_extraction_evaluation, run_rule_evaluation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate golden dataset for extraction and rule accuracy")
    parser.add_argument(
        "--dataset-dir",
        default="examples/golden_dataset/v1/pdfs",
        help="Path to golden dataset PDF folder",
    )
    parser.add_argument(
        "--extraction-labels",
        default="examples/golden_dataset/v1/extraction_gold_labels.jsonl",
        help="Path to extraction label jsonl",
    )
    parser.add_argument(
        "--audit-labels",
        default="examples/golden_dataset/v1/audit_gold_labels.json",
        help="Path to audit/rule label json",
    )
    parser.add_argument(
        "--output",
        default="examples/golden_dataset/v1/eval_output.json",
        help="Path to evaluation output json",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    extraction_eval = await run_extraction_evaluation(
        dataset_dir=args.dataset_dir,
        extraction_labels_path=args.extraction_labels,
    )
    rule_eval = await run_rule_evaluation(
        dataset_dir=args.dataset_dir,
        audit_labels_path=args.audit_labels,
    )

    result = {
        "extraction_evaluation": extraction_eval,
        "rule_evaluation": rule_eval,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["rule_evaluation"]["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
