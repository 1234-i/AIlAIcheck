from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "Contractor HSE Document Audit System"
    app_env: str = "dev"
    app_debug: bool = False
    log_level: str = "INFO"

    database_url: str = "sqlite:///./hse_audit.db"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: str = Field(default="local", pattern="^(local|s3)$")
    local_storage_path: str = "./.local_storage"
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    llm_mode: str = Field(default="auto", pattern="^(auto|gemini|mock)$")
    relay_gemini_base_url: str = "https://oneapi.gemiaude.com"
    relay_gemini_api_key: str | None = None
    relay_gemini_model: str = "gemini-3.1-flash-lite-preview"
    official_gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    official_gemini_api_key: str | None = None
    org_gemini_api_key: str | None = None
    official_gemini_parse_model: str = "gemini-3.1-flash-lite-preview"
    official_gemini_complex_model: str = "gemini-3.1-pro-preview"
    enable_official_complex_escalation: bool = False
    official_complex_escalation_min_confidence: float = 0.45
    official_complex_escalation_doc_types: str = ""
    official_gemini_model: str = "gemini-3.1-pro-preview"
    pdf_provider_size_threshold_mb: float = 50.0
    enable_provider_escalation: bool = True

    # Backward-compatible legacy settings
    gemini_base_url: str = "https://reelxai.com/v1beta"
    gemini_api_key: str | None = None
    gemini_audit_model: str = "gemini-3.1-pro-preview"
    gemini_timeout_seconds: float = 90.0
    gemini_max_retries: int = 3
    llm_raw_response_log_enabled: bool = True
    llm_raw_response_log_success: bool = False
    llm_raw_response_log_dir: str = "./logs/llm_raw"
    llm_raw_response_max_chars: int = 12000
    llm_cache_enabled: bool = True
    llm_cache_dir: str = "./.cache/llm_results"
    llm_classify_max_concurrency: int = 4
    llm_extract_max_concurrency: int = 3
    large_pdf_keypage_threshold_bytes: int = 6291456
    pipeline_version: str = "pipeline-v2.3.0"

    celery_task_always_eager: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
