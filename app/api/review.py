from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.api.utils import parse_uuid
from app.models import AuditIssue
from app.schemas.api import IssueReviewRequest

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/issues/{issue_id}")
def review_issue(
    issue_id: str,
    payload: IssueReviewRequest,
    session: Session = Depends(get_db_session),
) -> dict:
    issue_uuid = parse_uuid(issue_id, "issue_id")
    issue = session.exec(select(AuditIssue).where(AuditIssue.issue_id == issue_uuid)).first()
    if not issue:
        raise HTTPException(status_code=404, detail="issue not found")

    issue.review_status = payload.action.upper()
    issue.review_comment = payload.comment
    if "severity" in payload.updated_fields:
        issue.severity = payload.updated_fields["severity"]
    if "issue_description" in payload.updated_fields:
        issue.issue_description = payload.updated_fields["issue_description"]
    issue.updated_at = datetime.utcnow()

    session.add(issue)
    session.commit()
    session.refresh(issue)

    return {
        "issue_id": str(issue.issue_id),
        "review_status": issue.review_status,
        "review_comment": issue.review_comment,
    }
