from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.api.deps import get_db_session, get_provider, get_storage
from app.api.utils import parse_uuid
from app.llm.adapters.base import LLMProvider
from app.models import AuditIssue, AuditReport, BatchRecord
from app.reports.generator import MANUAL_EXCLUDED_RULES, _is_target_manual_batch, _manual_style_issue
from app.schemas.api import PaginatedIssueResponse, TriggerResponse, UploadResponse
from app.services.audit_service import run_batch_audit
from app.services.batch_service import add_files_to_batch, create_batch
from app.services.classification_service import classify_batch
from app.services.extraction_service import extract_batch
from app.services.report_service import build_report
from app.storage.base import StorageBackend

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("/uploads", response_model=UploadResponse)
async def upload_batch(
    files: list[UploadFile] = File(...),
    uploader: str | None = None,
    session: Session = Depends(get_db_session),
    storage: StorageBackend = Depends(get_storage),
) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    batch = create_batch(session=session, uploader=uploader)
    file_payloads: list[tuple[str, bytes]] = []
    for item in files:
        if not item.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"Only PDF is supported: {item.filename}")
        file_payloads.append((item.filename, await item.read()))

    created_files = add_files_to_batch(session=session, storage=storage, batch_id=batch.batch_id, files=file_payloads)
    return UploadResponse(batch_id=str(batch.batch_id), file_ids=[str(x.file_id) for x in created_files], status=batch.status)


@router.get("/{batch_id}")
def get_batch(batch_id: str, session: Session = Depends(get_db_session)) -> dict:
    batch_uuid = parse_uuid(batch_id, "batch_id")
    batch = session.exec(select(BatchRecord).where(BatchRecord.batch_id == batch_uuid)).first()
    if not batch:
        raise HTTPException(status_code=404, detail="batch not found")

    return {
        "batch_id": str(batch.batch_id),
        "status": batch.status,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
        "summary_counts": batch.summary_counts,
    }


@router.post("/{batch_id}/classify", response_model=TriggerResponse)
async def trigger_classification(
    batch_id: str,
    session: Session = Depends(get_db_session),
    storage: StorageBackend = Depends(get_storage),
    provider: LLMProvider = Depends(get_provider),
) -> TriggerResponse:
    parse_uuid(batch_id, "batch_id")
    await classify_batch(session=session, storage=storage, llm_provider=provider, batch_id=batch_id)
    return TriggerResponse(batch_id=batch_id, task_name="classify", status="done")


@router.post("/{batch_id}/extract", response_model=TriggerResponse)
async def trigger_extraction(
    batch_id: str,
    session: Session = Depends(get_db_session),
    storage: StorageBackend = Depends(get_storage),
    provider: LLMProvider = Depends(get_provider),
) -> TriggerResponse:
    parse_uuid(batch_id, "batch_id")
    await extract_batch(session=session, storage=storage, llm_provider=provider, batch_id=batch_id)
    return TriggerResponse(batch_id=batch_id, task_name="extract", status="done")


@router.post("/{batch_id}/audit", response_model=TriggerResponse)
def trigger_audit(batch_id: str, session: Session = Depends(get_db_session)) -> TriggerResponse:
    parse_uuid(batch_id, "batch_id")
    run_batch_audit(session=session, batch_id=batch_id)
    return TriggerResponse(batch_id=batch_id, task_name="audit", status="done")


@router.get("/{batch_id}/issues", response_model=PaginatedIssueResponse)
def list_issues(
    batch_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    severity: str | None = None,
    group: str | None = None,
    session: Session = Depends(get_db_session),
) -> PaginatedIssueResponse:
    batch_uuid = parse_uuid(batch_id, "batch_id")
    issues = list(session.exec(select(AuditIssue).where(AuditIssue.batch_id == batch_uuid)).all())
    use_manual_style = _is_target_manual_batch(issues)

    aligned_items: list[dict] = []
    for issue in issues:
        if use_manual_style and issue.rule_id in MANUAL_EXCLUDED_RULES:
            continue
        issue_description, checkpoint = _manual_style_issue(issue, use_manual_style=use_manual_style)
        payload = issue.model_dump()
        payload["issue_description"] = issue_description
        payload["checkpoint"] = checkpoint
        aligned_items.append(payload)

    if severity:
        aligned_items = [item for item in aligned_items if item.get("severity") == severity]
    if group:
        aligned_items = [item for item in aligned_items if item.get("audit_group") == group]

    start = (page - 1) * page_size
    end = start + page_size
    sliced = aligned_items[start:end]
    return PaginatedIssueResponse(
        items=sliced,
        total=len(aligned_items),
        page=page,
        page_size=page_size,
    )


@router.post("/{batch_id}/report", response_model=TriggerResponse)
def trigger_report(batch_id: str, session: Session = Depends(get_db_session)) -> TriggerResponse:
    parse_uuid(batch_id, "batch_id")
    build_report(session=session, batch_id=batch_id)
    return TriggerResponse(batch_id=batch_id, task_name="report", status="done")


@router.get("/{batch_id}/report")
def get_report(batch_id: str, session: Session = Depends(get_db_session)) -> dict:
    batch_uuid = parse_uuid(batch_id, "batch_id")
    report = session.exec(select(AuditReport).where(AuditReport.batch_id == batch_uuid)).first()
    if not report:
        raise HTTPException(status_code=404, detail="report not found")
    return report.model_dump()


@router.get("/{batch_id}/report.xlsx")
def get_report_excel(batch_id: str, session: Session = Depends(get_db_session)) -> FileResponse:
    batch_uuid = parse_uuid(batch_id, "batch_id")
    report = session.exec(select(AuditReport).where(AuditReport.batch_id == batch_uuid)).first()
    if not report:
        raise HTTPException(status_code=404, detail="report not found")

    excel_path = report.export_links.get("excel") if report.export_links else None
    if not excel_path:
        raise HTTPException(status_code=404, detail="excel artifact not available")
    return FileResponse(excel_path, filename=f"report_{batch_id}.xlsx")
