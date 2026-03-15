from __future__ import annotations

import json
import re

from app.llm.errors import LLMParseError


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def parse_json_object_strict(text: str) -> dict:
    candidate = _strip_fences(text)
    if not candidate:
        raise LLMParseError("empty model response")

    try:
        payload = json.loads(candidate)
        if isinstance(payload, dict):
            return payload
        raise LLMParseError("model response is not a JSON object")
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
        if not match:
            raise LLMParseError("failed to parse strict JSON object") from None
        try:
            payload = json.loads(match.group(0))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError as exc:
            raise LLMParseError(f"JSON parsing failed: {exc}") from exc

    raise LLMParseError("failed to parse strict JSON object")
