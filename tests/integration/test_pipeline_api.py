from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _configure_test_env(tmp_dir: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_dir / 'test.db'}"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["LOCAL_STORAGE_PATH"] = str(tmp_dir / "storage")
    os.environ["LLM_MODE"] = "mock"
    get_settings.cache_clear()


def test_upload_to_report_flow(tmp_path: Path) -> None:
    _configure_test_env(tmp_path)

    from app.main import app

    with TestClient(app) as client:
        upload_response = client.post(
            "/api/v1/batches/uploads",
            files=[("files", ("sample_contract.pdf", b"%PDF-1.4 test", "application/pdf"))],
        )
        assert upload_response.status_code == 200
        payload = upload_response.json()
        batch_id = payload["batch_id"]
        file_id = payload["file_ids"][0]

        classify_response = client.post(f"/api/v1/batches/{batch_id}/classify")
        assert classify_response.status_code == 200

        extraction_response = client.post(f"/api/v1/batches/{batch_id}/extract")
        assert extraction_response.status_code == 200

        audit_response = client.post(f"/api/v1/batches/{batch_id}/audit")
        assert audit_response.status_code == 200

        report_response = client.post(f"/api/v1/batches/{batch_id}/report")
        assert report_response.status_code == 200

        classification = client.get(f"/api/v1/files/{file_id}/classification")
        assert classification.status_code == 200
        assert classification.json()["doc_type"] is not None

        report_get = client.get(f"/api/v1/batches/{batch_id}/report")
        assert report_get.status_code == 200
        assert "issue_list" in report_get.json()

        issues_get = client.get(f"/api/v1/batches/{batch_id}/issues")
        assert issues_get.status_code == 200
        assert "items" in issues_get.json()
