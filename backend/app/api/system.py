from __future__ import annotations

from fastapi import APIRouter, Depends

from app.analyzers.languages.registry import PROFILES
from app.api.deps import get_current_user
from app.api.documents import DOC_TYPES
from app.core.config import get_settings
from app.models import User
from app.providers.registry import providers_status

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/system/providers")
def providers(_: User = Depends(get_current_user)):
    """Which analysis providers are active. Never includes keys or URLs."""
    return providers_status()


@router.get("/system/config")
def public_config():
    s = get_settings()
    return {
        "max_upload_mb": s.MAX_UPLOAD_MB,
        "max_files_per_upload": s.MAX_FILES_PER_UPLOAD,
        "allowed_types": ["docx", "pdf", "txt"],
        "doc_types": list(DOC_TYPES),
        "depths": ["quick", "standard", "deep"],
        "languages": [{"code": p.code, "name": p.name, "max_confidence": p.max_confidence} for p in PROFILES.values()],
        "suspicious_threshold": s.SUSPICIOUS_THRESHOLD,
    }
