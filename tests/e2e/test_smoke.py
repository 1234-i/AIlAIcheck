from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _configure_test_env(tmp_dir: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_dir / 'test_smoke.db'}"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["LOCAL_STORAGE_PATH"] = str(tmp_dir / "storage")
    os.environ["LLM_MODE"] = "mock"
    get_settings.cache_clear()


def test_health_endpoint(tmp_path: Path) -> None:
    _configure_test_env(tmp_path)
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
