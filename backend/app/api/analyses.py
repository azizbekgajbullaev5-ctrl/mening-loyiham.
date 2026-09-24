from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user, owned_analysis
from app.api.serializers import analysis_detail, analysis_summary, match_out, passage_out, plagiarism_out, section_out
from app.core.database import get_db
from app.models import Analysis, Report, User
from app.reporting.builder import build_report_data
from app.reporting.docx_report import render_docx
from app.reporting.pdf_report import render_pdf
from app.services.audit import audit
from app.services.pipeline import reset_for_resume
from app.tasks.queue import enqueue_analysis

router = APIRouter(prefix="/analyses", tags=["analyses"])
Lang = Literal["uz", "en"]


@router.get("")
def list_analyses(limit: int = Query(50, ge=1, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Analysis).where(Analysis.owner_id == user.id).order_by(Analysis.created_at.desc()).limit(limit)).all()
    return [analysis_summary(a) for a in rows]


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, lang: Lang = "uz", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analysis_detail(owned_analysis(db, user, analysis_id), lang)


class ConfirmIn(BaseModel):
    web_check: bool = True


@router.post("/{analysis_id}/confirm")
def confirm_analysis(analysis_id: str, body: ConfirmIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Start an analysis that waits for confirmation of the internet-check cost (or run it without the web check)."""
    a = owned_analysis(db, user, analysis_id)
    if a.status != "awaiting_confirmation":
        raise HTTPException(409, "not_awaiting_confirmation")
    a.web_check = body.web_check
    a.status, a.stage = "queued", "queued"
    audit(db, "analysis_confirmed", user.id, "analysis", a.id, client_ip(request), web_check=body.web_check,
          estimate=(a.web_estimate or {}).get("cost_usd"))
    db.commit()
    enqueue_analysis(a.id)
    db.refresh(a)
    return analysis_summary(a)


@router.get("/{analysis_id}/plagiarism")
def get_plagiarism(analysis_id: str, lang: Lang = "uz", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_analysis(db, user, analysis_id)
    if a.plagiarism is None:
        raise HTTPException(404, "no_plagiarism_result")
    return plagiarism_out(a.plagiarism, lang)


@router.post("/{analysis_id}/resume")
def resume_analysis(analysis_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Continue a failed analysis. Saved extraction/OCR checkpoints are reused."""
    a = owned_analysis(db, user, analysis_id)
    if a.status not in ("failed",):
        raise HTTPException(409, "analysis_not_failed")
    if not a.document.storage_key:
        raise HTTPException(410, "file_deleted")
    reset_for_resume(db, a)
    audit(db, "analysis_resumed", user.id, "analysis", a.id, client_ip(request))
    db.commit()
    enqueue_analysis(a.id)
    db.refresh(a)
    return analysis_summary(a)


@router.get("/{analysis_id}/sections")
def get_sections(analysis_id: str, lang: Lang = "uz", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_analysis(db, user, analysis_id)
    return [section_out(s, lang) for s in a.sections]


@router.get("/{analysis_id}/passages")
def get_passages(
    analysis_id: str,
    lang: Lang = "uz",
    chapter: int | None = None,
    section: int | None = None,
    min_score: float = Query(0, ge=0, le=100),
    confidence: Literal["low", "medium", "high"] | None = None,
    q: str | None = Query(None, max_length=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = owned_analysis(db, user, analysis_id)
    secs = {s.order: s for s in a.sections}
    items = []
    for p in a.passages:
        if chapter is not None and p.chapter_order != chapter:
            continue
        if section is not None and p.section_order != section and not _is_descendant(secs, p.section_order, section):
            continue
        if p.ai_likelihood < min_score:
            continue
        if confidence and p.confidence != confidence:
            continue
        if q and not re.search(re.escape(q), p.text, re.IGNORECASE):
            continue
        items.append(passage_out(p, secs, lang))
    return items


def _is_descendant(secs, order, ancestor) -> bool:
    cur = secs.get(order)
    while cur is not None and cur.parent_order is not None:
        if cur.parent_order == ancestor:
            return True
        cur = secs.get(cur.parent_order)
    return False


@router.get("/{analysis_id}/similarity")
def get_similarity(analysis_id: str, lang: Lang = "uz", match_type: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = owned_analysis(db, user, analysis_id)
    secs = {s.order: s for s in a.sections}
    matches = [m for m in a.similarity_matches if match_type is None or m.match_type == match_type]
    matches.sort(key=lambda m: -m.similarity)
    return {"matches": [match_out(m, secs, lang) for m in matches], "repeated_phrases": a.result.repeated_phrases if a.result else []}


@router.get("/{analysis_id}/report")
def download_report(
    analysis_id: str,
    request: Request,
    format: Literal["pdf", "docx"] = "pdf",
    lang: Lang = "uz",
    kind: Literal["full", "plagiarism"] = "full",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    a = owned_analysis(db, user, analysis_id)
    if a.status != "completed" or a.result is None:
        raise HTTPException(409, "analysis_not_completed")
    if kind == "plagiarism":
        if a.plagiarism is None:
            raise HTTPException(404, "no_plagiarism_result")
        from app.reporting.plagiarism_report import render_plagiarism_pdf

        content = render_plagiarism_pdf(a, user, lang)
        format = "pdf"
    else:
        data = build_report_data(a, lang)
        content = render_pdf(data) if format == "pdf" else render_docx(data)
    db.add(Report(analysis_id=a.id, owner_id=user.id, format=format, size_bytes=len(content)))
    audit(db, "report_downloaded", user.id, "analysis", a.id, client_ip(request), format=format)
    db.commit()
    base = re.sub(r"[^\w.-]+", "_", a.document.original_filename.rsplit(".", 1)[0])[:60] or "report"
    media = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(
        content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{base}_{"antiplagiat" if kind == "plagiarism" else "report"}.{format}"', "Cache-Control": "no-store"},
    )
