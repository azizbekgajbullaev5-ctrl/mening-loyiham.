from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import COOKIE_NAME, client_ip, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, login_limiter, verify_password
from app.models import User
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(default="", max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


def _user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "created_at": u.created_at}


def _set_cookie(resp: Response, token: str) -> None:
    s = get_settings()
    resp.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=s.COOKIE_SECURE, samesite="lax",
        max_age=s.ACCESS_TOKEN_MINUTES * 60, path="/",
    )


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    if not any(c.isdigit() for c in body.password) or not any(c.isalpha() for c in body.password):
        raise HTTPException(422, "weak_password")
    if db.scalar(select(func.count()).select_from(User).where(User.email == email)):
        raise HTTPException(409, "email_taken")
    user = User(email=email, full_name=body.full_name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    audit(db, "register", user.id, "user", user.id, client_ip(request))
    db.commit()
    token = create_access_token(user.id)
    _set_cookie(response, token)
    return {"user": _user_out(user), "access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    email = body.email.lower()
    key = f"{client_ip(request)}:{email}"
    if not login_limiter.allow(key, get_settings().LOGIN_RATE_LIMIT_PER_MINUTE):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash) or not user.is_active:
        audit(db, "login_failed", user.id if user else None, "user", None, client_ip(request))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    audit(db, "login", user.id, "user", user.id, client_ip(request))
    db.commit()
    token = create_access_token(user.id)
    _set_cookie(response, token)
    return {"user": _user_out(user), "access_token": token, "token_type": "bearer"}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _user_out(user)
