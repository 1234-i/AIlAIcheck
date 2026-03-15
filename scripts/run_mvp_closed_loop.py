from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_runtime_engine, init_db
from app.llm.provider_factory import get_llm_provider
from app.services.batch_service import add_files_to_batch, create_batch
from app.services.workflow_service import run_full_pipeline
from app.storage.factory import get_storage_backend


async def run() -> dict:
    os.environ.setdefault("LLM_MODE", "mock")
    init_db()

    sample_dir = Path("examples/sample_batch")
    if not sample_dir.exists():
        raise RuntimeError("Sample dataset not found: examples/sample_batch")

    storage = get_storage_backend()
    provider = get_llm_provider()

    files = sorted(sample_dir.glob("*.pdf"))
    file_payloads = [(path.name, path.read_bytes()) for path in files]

    with Session(get_runtime_engine()) as session:
        batch = create_batch(session=session, uploader="mvp-demo")
        add_files_to_batch(session=session, storage=storage, batch_id=batch.batch_id, files=file_payloads)
        result = await run_full_pipeline(
            session=session,
            storage=storage,
            provider=provider,
            batch_id=str(batch.batch_id),
        )

    output_dir = Path("examples/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"report_{result['batch_id']}.json"
    json_path.write_text(json.dumps(result["report"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return {
        "batch_id": result["batch_id"],
        "json_report": str(json_path),
        "excel_report": result["report"].get("export_links", {}).get("excel"),
    }


if __name__ == "__main__":
    summary = asyncio.run(run())
    print(json.dumps(summary, ensure_ascii=False, indent=2))
