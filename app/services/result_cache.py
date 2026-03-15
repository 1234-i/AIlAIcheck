from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def provider_model_signature(llm_provider: Any) -> str:
    provider_name = type(llm_provider).__name__
    model_name = None
    if hasattr(llm_provider, "model_signature"):
        try:
            return str(llm_provider.model_signature())
        except Exception:
            pass
    model_name = getattr(getattr(llm_provider, "client", None), "model", None)
    if model_name:
        return f"{provider_name}:{model_name}"
    return provider_name


def provider_model_signatures_for_file(
    llm_provider: Any,
    *,
    file_size_bytes: int,
    stage: str,
) -> list[str]:
    if hasattr(llm_provider, "cache_model_signatures"):
        try:
            signatures = list(
                llm_provider.cache_model_signatures(
                    file_size_bytes=file_size_bytes,
                    stage=stage,
                )
            )
            if signatures:
                return signatures
        except Exception:
            pass
    return [provider_model_signature(llm_provider)]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_result_cache_key(
    *,
    stage: str,
    file_bytes: bytes,
    model_signature: str,
    prompt_version: str,
    pipeline_version: str,
    schema_version: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    descriptor: dict[str, Any] = {
        "stage": stage,
        "file_sha256": _sha256_bytes(file_bytes),
        "model_signature": model_signature,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "pipeline_version": pipeline_version,
        "extra": extra or {},
    }
    raw = json.dumps(descriptor, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ResultCache:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.llm_cache_enabled
        self.base_dir = Path(settings.llm_cache_dir)

    def _path(self, stage: str, cache_key: str) -> Path:
        return self.base_dir / stage / f"{cache_key}.json"

    def load(self, *, stage: str, cache_key: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        path = self._path(stage, cache_key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def save(self, *, stage: str, cache_key: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._path(stage, cache_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
