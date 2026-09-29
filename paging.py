"""Word (.docx) hujjatidagi sahifalar sonini aniq o'lchash.

LibreOffice (soffice) orqali docx -> pdf ga aylantiriladi va pdf sahifalari
sanaladi. soffice yoki pypdf bo'lmasa — None qaytaradi (moslashuv o'tkazilmaydi).
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile

logger = logging.getLogger(__name__)


def soffice_bin() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def _count_pdf(path: str) -> int | None:
    try:
        from pypdf import PdfReader

        return len(PdfReader(path).pages)
    except Exception:  # noqa: BLE001
        logger.warning("PDF sahifalarini sanashда xatolik", exc_info=True)
        return None


async def docx_page_count(docx_bytes: bytes) -> int | None:
    """docx -> pdf (LibreOffice) -> sahifalar soni. Aniqlab bo'lmasa None."""
    binary = soffice_bin()
    if not binary:
        return None
    tmp = tempfile.mkdtemp(prefix="pg_")
    try:
        docx_path = os.path.join(tmp, "doc.docx")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        profile = os.path.join(tmp, "profile")
        proc = await asyncio.create_subprocess_exec(
            binary,
            "--headless",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to",
            "pdf",
            "--outdir",
            tmp,
            docx_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
            logger.warning("LibreOffice aylantirish vaqti tugadi")
            return None
        pdf_path = os.path.join(tmp, "doc.pdf")
        if not os.path.exists(pdf_path):
            return None
        return _count_pdf(pdf_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
