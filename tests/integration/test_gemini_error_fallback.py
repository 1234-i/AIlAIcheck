from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _configure_test_env(tmp_dir: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_dir / 'gemini_fallback.db'}"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["LOCAL_STORAGE_PATH"] = str(tmp_dir / "storage")
    os.environ["LLM_MODE"] = "gemini"
    os.environ.pop("GEMINI_API_KEY", None)
    get_settings.cache_clear()


def test_gemini_without_key_sets_classification_error(tmp_path: Path) -> None:
    _configure_test_env(tmp_path)

    from app.main import app

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/v1/batches/uploads",
            files=[("files", ("ambiguous.pdf", b"%PDF-1.4 test", "application/pdf"))],
        )
        assert upload_response.status_code == 200
        payload = upload_response.json()
        batch_id = payload["batch_id"]
        file_id = payload["file_ids"][0]

        classify_response = client.post(f"/api/v1/batches/{batch_id}/classify")
        assert classify_response.status_code == 200

        classification = client.get(f"/api/v1/files/{file_id}/classification")
        assert classification.status_code == 200
        body = classification.json()
        assert body["doc_type"] == "classification_error"
        assert body["confidence"] == 0.0
        assert body["classification_evidence"]
