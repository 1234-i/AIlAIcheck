from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _configure_test_env(tmp_dir: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_dir / 'mvp.db'}"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["LOCAL_STORAGE_PATH"] = str(tmp_dir / "storage")
    os.environ["LLM_MODE"] = "mock"
    get_settings.cache_clear()


def test_mvp_closed_loop_with_sample_batch(tmp_path: Path) -> None:
    _configure_test_env(tmp_path)

    from app.main import app

    sample_dir = Path("examples/sample_batch")
    files = []
    for path in sorted(sample_dir.glob("*.pdf")):
        files.append(("files", (path.name, path.read_bytes(), "application/pdf")))

    with TestClient(app) as client:
        upload = client.post("/api/v1/batches/uploads", files=files)
        assert upload.status_code == 200
        batch_id = upload.json()["batch_id"]

        assert client.post(f"/api/v1/batches/{batch_id}/classify").status_code == 200
        assert client.post(f"/api/v1/batches/{batch_id}/extract").status_code == 200
        assert client.post(f"/api/v1/batches/{batch_id}/audit").status_code == 200
        assert client.post(f"/api/v1/batches/{batch_id}/report").status_code == 200

        report = client.get(f"/api/v1/batches/{batch_id}/report")
        assert report.status_code == 200
        report_data = report.json()
        assert len(report_data["issue_list"]) >= 1

        issues = client.get(f"/api/v1/batches/{batch_id}/issues")
        assert issues.status_code == 200
        issue_items = issues.json()["items"]
        assert len(issue_items) >= 1

        evidence = issue_items[0]["evidence_chain"][0]
        assert "source_file_id" in evidence
        assert "source_file_name" in evidence
        assert "extracted_field_source" in evidence
        assert "rule_id" in evidence
        assert "clause_id" in evidence

        excel = client.get(f"/api/v1/batches/{batch_id}/report.xlsx")
        assert excel.status_code == 200
