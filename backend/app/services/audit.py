from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import AuditLog

log = logging.getLogger("audit")


def audit(db: Session, action: str, user_id: str | None, target_type: str | None = None, target_id: str | None = None,
          ip: str | None = None, **details) -> None:
    """Record a security-relevant event. Never include document content or secrets in ``details``."""
    db.add(AuditLog(user_id=user_id, action=action, target_type=target_type, target_id=target_id, ip=ip, details=details))
    log.info("audit action=%s user=%s target=%s:%s", action, user_id, target_type, target_id)
