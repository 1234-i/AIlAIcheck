from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_runtime_engine, init_db
from app.models import RuleDefinition


def seed_rules(path: str = "examples/rules_v2_high_value.json") -> int:
    init_db()
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    count = 0
    with Session(get_runtime_engine()) as session:
        for item in raw:
            rule = RuleDefinition(**item)
            session.add(rule)
            count += 1
        session.commit()
    return count


if __name__ == "__main__":
    inserted = seed_rules()
    print(f"Seeded {inserted} rules")
