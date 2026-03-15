from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlmodel import Session

from app.core.enums import BatchStatus
from app.models import BatchRecord, FileRecord
from app.services.file_utils import checksum_sha256
from app.storage.base import StorageBackend


def create_batch(session: Session, uploader: str | None = None) -> BatchRecord:
    batch = BatchRecord(uploader=uploader, status=BatchStatus.UPLOADED, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def add_files_to_batch(
    session: Session,
    storage: StorageBackend,
    batch_id: UUID,
    files: Iterable[tuple[str, bytes]],
) -> list[FileRecord]:
    records: list[FileRecord] = []
    for file_name, content in files:
        key = f"batches/{batch_id}/{Path(file_name).name}"
        storage_uri = storage.save_bytes(key=key, data=content, content_type="application/pdf")
        record = FileRecord(
            batch_id=batch_id,
            file_name=Path(file_name).name,
            storage_uri=storage_uri,
            storage_key=key,
            checksum=checksum_sha256(content),
            confidence=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(record)
        records.append(record)

    session.commit()
    for item in records:
        session.refresh(item)
    return records
