from __future__ import annotations

import json
from pathlib import Path

from app.rule_engine.contracts import RuleDefinitionSchema


def load_rules(path: str = "examples/rules_v2_high_value.json") -> list[RuleDefinitionSchema]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [RuleDefinitionSchema.model_validate(item) for item in raw if item.get("enabled", True)]
