from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings


def log_raw_response(request_tag: str, response_obj: dict | str) -> None:
    settings = get_settings()
    if not settings.llm_raw_response_log_enabled:
        return

    target_dir = Path(settings.llm_raw_response_log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = target_dir / f"{stamp}_{request_tag}.json"

    if isinstance(response_obj, dict):
        content = json.dumps(response_obj, ensure_ascii=False)
    else:
        content = str(response_obj)

    truncated = content[: settings.llm_raw_response_max_chars]
    payload = {
        "ts_utc": stamp,
        "request_tag": request_tag,
        "raw_response": truncated,
        "truncated": len(content) > len(truncated),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
