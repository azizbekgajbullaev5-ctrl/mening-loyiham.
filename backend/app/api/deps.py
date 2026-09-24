from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Analysis, Document, User

COOKIE_NAME = "aasa_session"


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    user_id = decode_access_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return user


def owned_document(db: Session, user: User, document_id: str) -> Document:
    doc = db.get(Document, document_id)
    # 404 (not 403) so other users' document ids cannot be probed
    if doc is None or doc.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document_not_found")
    return doc


def owned_analysis(db: Session, user: User, analysis_id: str) -> Analysis:
    a = db.get(Analysis, analysis_id)
    if a is None or a.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "analysis_not_found")
    return a
