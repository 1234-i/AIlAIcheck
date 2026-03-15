from __future__ import annotations

import base64
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.llm.errors import LLMTimeoutError, LLMTransportError
from app.llm.raw_logger import log_raw_response

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        provider_name: str,
    ) -> None:
        self.settings = get_settings()
        self.base_url = self._normalize_base_url(base_url)
        self.api_key = api_key
        self.model = model
        self.provider_name = provider_name

    @property
    def signature(self) -> str:
        return f"{self.provider_name}:{self.base_url}:{self.model}"

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        raw = (base_url or "").strip().rstrip("/")
        if not raw:
            return raw
        parsed = urlparse(raw)
        # New relay endpoint may be provided as host-only; default to /v1beta path.
        if parsed.path in ("", "/"):
            raw = f"{raw}/v1beta"
        return raw.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMTransportError(f"{self.provider_name} API key is not configured")
        if self.provider_name == "official":
            return {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            }
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def generate_content_with_meta(
        self,
        *,
        contents: list[dict[str, Any]],
        request_tag: str,
        response_schema: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = self._headers()
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        }
        if response_schema:
            payload["generationConfig"]["response_schema"] = response_schema

        timeout_retry_count = 0
        timeout = httpx.Timeout(self.settings.gemini_timeout_seconds)
        max_retries = max(1, int(self.settings.gemini_max_retries))

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    body = response.json()
                    if self.settings.llm_raw_response_log_success:
                        log_raw_response(
                            request_tag=f"{request_tag}_{self.provider_name}",
                            response_obj=body,
                        )
                    meta = {
                        "raw_response_status": f"http_{response.status_code}",
                        "timeout_retry_count": timeout_retry_count,
                        "provider_name": self.provider_name,
                        "model_name": self.model,
                    }
                    return body, meta
            except httpx.TimeoutException as exc:
                timeout_retry_count += 1
                if attempt >= max_retries:
                    raise LLMTimeoutError(f"{self.provider_name} timed out for {request_tag}") from exc
                continue
            except httpx.HTTPStatusError as exc:
                body = exc.response.text if exc.response is not None else ""
                log_raw_response(
                    request_tag=f"{request_tag}_{self.provider_name}_http_error",
                    response_obj=body,
                )
                raise LLMTransportError(
                    f"{self.provider_name} HTTP error {exc.response.status_code}: {body[:500]}"
                ) from exc
            except httpx.HTTPError as exc:
                if attempt >= max_retries:
                    raise LLMTransportError(f"{self.provider_name} transport failure: {exc}") from exc
                continue
            except ImportError as exc:
                raise LLMTransportError(f"{self.provider_name} client initialization failed: {exc}") from exc

        raise LLMTransportError(f"{self.provider_name} transport failure: exhausted retries")

    async def generate_content(
        self,
        *,
        contents: list[dict[str, Any]],
        request_tag: str,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body, _ = await self.generate_content_with_meta(
            contents=contents,
            request_tag=request_tag,
            response_schema=response_schema,
        )
        return body

    @staticmethod
    def build_pdf_part(pdf_bytes: bytes) -> dict[str, Any]:
        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        return {
            "inline_data": {
                "mime_type": "application/pdf",
                "data": encoded,
            }
        }

    @staticmethod
    def extract_text(response: dict[str, Any]) -> str:
        candidates = response.get("candidates", [])
        for candidate in candidates:
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part:
                    return part["text"]
        logger.warning("Gemini response did not include text parts")
        return ""
