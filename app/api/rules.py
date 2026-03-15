from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.deps import get_provider
from app.llm.adapters.base import LLMProvider
from app.schemas.api import RuleApproveRequest

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("/draft-from-policy")
async def draft_rules_from_policy(
    policy_text: str | None = Form(default=None),
    policy_file: UploadFile | None = File(default=None),
    provider: LLMProvider = Depends(get_provider),
) -> dict:
    text = policy_text
    if policy_file:
        raw = await policy_file.read()
        text = raw.decode("utf-8", errors="ignore")[:8000]

    if not text:
        raise HTTPException(status_code=400, detail="policy text or file is required")

    draft = await provider.extract_rules_from_policy(policy_text=text)
    return {"rules": draft.rules}


@router.post("/approve")
def approve_rules(payload: RuleApproveRequest) -> dict:
    target = Path("examples/approved_rules.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload.rules, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"approved_count": len(payload.rules), "path": str(target)}
