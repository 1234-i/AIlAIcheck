from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sqlmodel import Session

from app.db.session import get_runtime_engine, init_db
from app.llm.provider_factory import get_llm_provider
from app.services.batch_service import add_files_to_batch, create_batch
from app.services.workflow_service import run_full_pipeline
from app.storage.factory import get_storage_backend


def ensure_demo_file(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Minimal placeholder bytes for demo-only pipeline checks.
    path.write_bytes(b"%PDF-1.4\n% Mock PDF for demo\n")


async def main() -> None:
    os.environ.setdefault("LLM_MODE", "mock")
    init_db()

    demo_pdf = Path("examples/demo/sample_contract.pdf")
    ensure_demo_file(demo_pdf)

    storage = get_storage_backend()
    provider = get_llm_provider()

    with Session(get_runtime_engine()) as session:
        batch = create_batch(session, uploader="demo")
        add_files_to_batch(
            session,
            storage,
            batch.batch_id,
            files=[(demo_pdf.name, demo_pdf.read_bytes())],
        )
        result = await run_full_pipeline(
            session=session,
            storage=storage,
            provider=provider,
            batch_id=str(batch.batch_id),
        )
        print(result["status"], result["batch_id"])


if __name__ == "__main__":
    asyncio.run(main())
