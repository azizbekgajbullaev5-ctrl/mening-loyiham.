"""Password hashing, JWT tokens and at-rest file encryption."""
from __future__ import annotations

import base64
import hashlib
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import get_settings

_hasher = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(user_id: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=s.ACCESS_TOKEN_MINUTES)}
    return jwt.encode(payload, s.SECRET_KEY.get_secret_value(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, get_settings().SECRET_KEY.get_secret_value(), algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def get_fernet() -> Fernet:
    s = get_settings()
    key = s.FILE_ENCRYPTION_KEY.get_secret_value()
    if not key:
        # Development fallback: derive a key from SECRET_KEY. Production refuses to
        # start without an explicit FILE_ENCRYPTION_KEY (see config.get_settings).
        digest = hashlib.sha256(("file-key:" + s.SECRET_KEY.get_secret_value()).encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


class RateLimiter:
    """Small in-process sliding-window limiter (used for login attempts)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter()
