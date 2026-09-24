"""Upload validation: extension, magic bytes, size limits, zip-bomb and macro checks.

Uploaded files are never executed or served back as-is; they are parsed by
python-docx / PyMuPDF inside the worker only.
"""
from __future__ import annotations

import io
import re
import socket
import struct
import zipfile
from dataclasses import dataclass

from app.core.config import get_settings

ALLOWED_EXTENSIONS = {"docx", "pdf", "txt"}


class ValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class ValidatedFile:
    file_type: str
    safe_name: str


def sanitize_filename(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name).strip(" .")
    return (name or "document")[:200]


def validate_upload(filename: str, data: bytes) -> ValidatedFile:
    s = get_settings()
    safe = sanitize_filename(filename)
    ext = safe.rsplit(".", 1)[-1].lower() if "." in safe else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError("unsupported_type", f"Unsupported file type: .{ext or '?'} (allowed: DOCX, PDF, TXT)")
    if not data:
        raise ValidationError("empty_file", "File is empty")
    if len(data) > s.max_upload_bytes:
        raise ValidationError("too_large", f"File exceeds {s.MAX_UPLOAD_MB} MB limit")

    if ext == "pdf":
        if not data[:1024].lstrip().startswith(b"%PDF-"):
            raise ValidationError("bad_signature", "File content is not a valid PDF")
    elif ext == "docx":
        _validate_docx(data, s.MAX_DOCX_UNCOMPRESSED_MB * 1024 * 1024)
    else:
        _validate_txt(data)

    _scan_malware(data)
    return ValidatedFile(file_type=ext, safe_name=safe)


def _validate_docx(data: bytes, max_uncompressed: int) -> None:
    if not data.startswith(b"PK\x03\x04"):
        raise ValidationError("bad_signature", "File content is not a valid DOCX (zip) archive")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise ValidationError("bad_signature", "Archive is not a Word document")
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                raise ValidationError("macro_content", "Macro-enabled documents are not accepted")
            total = 0
            for info in zf.infolist():
                total += info.file_size
                if info.compress_size and info.file_size / info.compress_size > 200 and info.file_size > 10_000_000:
                    raise ValidationError("zip_bomb", "Suspicious compression ratio")
            if total > max_uncompressed:
                raise ValidationError("zip_bomb", "Uncompressed document is too large")
            ct = zf.read("[Content_Types].xml")
            if b"macroEnabled" in ct:
                raise ValidationError("macro_content", "Macro-enabled documents are not accepted")
    except zipfile.BadZipFile as exc:
        raise ValidationError("bad_signature", "Corrupted DOCX archive") from exc


def _validate_txt(data: bytes) -> None:
    sample = data[:65536]
    if b"\x00" in sample and not (sample.startswith(b"\xff\xfe") or sample.startswith(b"\xfe\xff")):
        raise ValidationError("bad_signature", "Binary content in a .txt file")


def _scan_malware(data: bytes) -> None:
    """Optional ClamAV (clamd INSTREAM) scan when CLAMAV_HOST is configured."""
    s = get_settings()
    if not s.CLAMAV_HOST:
        return
    try:
        with socket.create_connection((s.CLAMAV_HOST, s.CLAMAV_PORT), timeout=30) as sock:
            sock.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 65536):
                chunk = data[i : i + 65536]
                sock.sendall(struct.pack("!L", len(chunk)) + chunk)
            sock.sendall(struct.pack("!L", 0))
            reply = sock.recv(4096).decode(errors="replace")
    except OSError as exc:
        raise ValidationError("scan_unavailable", "Malware scanner unavailable; upload rejected") from exc
    if "FOUND" in reply:
        raise ValidationError("malware", "The file was rejected by the malware scanner")
