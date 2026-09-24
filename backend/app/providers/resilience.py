"""Retry with backoff, simple per-provider rate limiting, and result caching."""
from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models import ProviderCache
from app.providers.base import ProviderError

T = TypeVar("T")


class RateLimiter:
    """Token-bucket limiter shared by all calls to one provider in this process."""

    def __init__(self, per_minute: int):
        self.interval = 60.0 / max(1, per_minute)
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self, sleep: Callable[[float], None] = time.sleep) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if delay:
            sleep(delay)


def with_retries(
    fn: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    attempt = 0
    while True:
        try:
            return fn()
        except ProviderError as exc:
            if not exc.retryable or attempt >= max_retries:
                raise
            delay = exc.retry_after if exc.retry_after is not None else base_delay * (2**attempt) + random.uniform(0, 0.3)
            sleep(min(delay, 60.0))
            attempt += 1


def cache_get(provider: str, text_hash: str) -> dict | None:
    with SessionLocal() as db:
        row = db.query(ProviderCache).filter_by(provider=provider, text_hash=text_hash).one_or_none()
        return dict(row.result) if row else None


def cache_put(provider: str, text_hash: str, result: dict) -> None:
    with SessionLocal() as db:
        try:
            db.add(ProviderCache(provider=provider, text_hash=text_hash, result=result))
            db.commit()
        except IntegrityError:
            db.rollback()
