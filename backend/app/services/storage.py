"""Encrypted-at-rest file storage for uploaded documents.

Files are written under STORAGE_DIR with random names, encrypted with Fernet
(AES-128-CBC + HMAC). They are never served directly by the web server.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.security import get_fernet


def _root() -> Path:
    root = Path(get_settings().STORAGE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path(key: str) -> Path:
    if not key.isalnum():
        raise ValueError("invalid storage key")
    return _root() / f"{key}.bin"


def save(data: bytes) -> str:
    key = uuid.uuid4().hex
    path = _path(key)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(get_fernet().encrypt(data))
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    return key


def load(key: str) -> bytes:
    return get_fernet().decrypt(_path(key).read_bytes())


def exists(key: str | None) -> bool:
    return bool(key) and _path(key).exists()


def delete(key: str | None) -> None:
    if not key:
        return
    try:
        _path(key).unlink()
    except FileNotFoundError:
        pass
