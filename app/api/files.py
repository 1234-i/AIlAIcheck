from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.api.utils import parse_uuid
from app.models import ExtractionRecord, FileRecord

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{file_id}/classification")
def get_file_classification(file_id: str, session: Session = Depends(get_db_session)) -> dict:
    file_uuid = parse_uuid(file_id, "file_id")
    file_record = session.exec(select(FileRecord).where(FileRecord.file_id == file_uuid)).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="file not found")
    return {
        "file_id": str(file_record.file_id),
        "doc_type": file_record.doc_type,
        "primary_group": file_record.primary_group,
        "related_groups": file_record.related_groups,
        "confidence": file_record.confidence,
        "classification_evidence": file_record.classification_evidence,
    }


@router.get("/{file_id}/extraction")
def get_file_extraction(file_id: str, session: Session = Depends(get_db_session)) -> dict:
    file_uuid = parse_uuid(file_id, "file_id")
    record = session.exec(select(ExtractionRecord).where(ExtractionRecord.file_id == file_uuid)).first()
    if not record:
        raise HTTPException(status_code=404, detail="extraction not found")

    return {
        "file_id": str(record.file_id),
        "schema_name": record.schema_name,
        "schema_version": record.schema_version,
        "validated_json": record.validated_json,
        "confidence": record.confidence,
        "validation_errors": record.errors,
    }
