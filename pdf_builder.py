"""Maqola dict'idan OAK uslubidagi PDF hujjat tuzish (fpdf2 + DejaVu shrifti)."""
from __future__ import annotations

import io
import os

from fpdf import FPDF
from fpdf.enums import XPos, YPos

_BASE = os.path.dirname(os.path.abspath(__file__))
_FONT_REGULAR = os.getenv(
    "FONT_PATH", os.path.join(_BASE, "assets", "fonts", "DejaVuSans.ttf")
)
_FONT_BOLD = os.getenv(
    "FONT_PATH_BOLD", os.path.join(_BASE, "assets", "fonts", "DejaVuSans-Bold.ttf")
)

_LABELS = {
    "annotation": {"uz": "Annotatsiya", "ru": "Аннотация", "en": "Abstract"},
    "keywords": {"uz": "Kalit so'zlar", "ru": "Ключевые слова", "en": "Keywords"},
}

_SECTION_TITLES = {
    "uz": {
        "introduction": "KIRISH",
        "main_part": "ASOSIY QISM",
        "results": "NATIJALAR VA ULARNING TAHLILI",
        "conclusion": "XULOSA",
        "references": "FOYDALANILGAN ADABIYOTLAR RO'YXATI",
    },
    "ru": {
        "introduction": "ВВЕДЕНИЕ",
        "main_part": "ОСНОВНАЯ ЧАСТЬ",
        "results": "РЕЗУЛЬТАТЫ И ИХ ОБСУЖДЕНИЕ",
        "conclusion": "ЗАКЛЮЧЕНИЕ",
        "references": "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
    },
}


class _PDF(FPDF):
    pass


def _new_pdf() -> _PDF:
    pdf = _PDF()
    pdf.add_font("DejaVu", "", _FONT_REGULAR)
    pdf.add_font("DejaVu", "B", _FONT_BOLD)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    return pdf


def _cell(pdf: _PDF, text: str, size: int, *, bold: bool = False,
          align: str = "L") -> None:
    """Bitta blok matnni chiqaradi va keyingi qatorga o'tadi."""
    pdf.set_font("DejaVu", "B" if bold else "", size)
    pdf.multi_cell(0, 7, text, align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _body(pdf: _PDF, text: str) -> None:
    for chunk in (text or "").split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        _cell(pdf, chunk, 13, align="J")
        pdf.ln(2)


def build_pdf(article: dict, author: str, lang: str) -> io.BytesIO:
    """Maqoladan .pdf tuzib, BytesIO oqimini qaytaradi."""
    lang = lang if lang in _SECTION_TITLES else "uz"
    pdf = _new_pdf()

    _cell(pdf, f"UDK: {article.get('udk', '')}", 13, bold=True)

    title = article.get("title", {})
    _cell(pdf, title.get(lang) or title.get("uz", ""), 15, bold=True, align="C")

    if author and author.strip() not in {"—", "-"}:
        _cell(pdf, author, 12, align="C")
    pdf.ln(3)

    # Annotatsiya va kalit so'zlar — uchta tilda
    annotation = article.get("annotation", {})
    keywords = article.get("keywords", {})
    for code in ("uz", "ru", "en"):
        ann = annotation.get(code)
        if ann:
            _cell(pdf, f"{_LABELS['annotation'][code]}:", 12, bold=True)
            _cell(pdf, ann, 12, align="J")
        kw = keywords.get(code) or []
        if kw:
            _cell(pdf, f"{_LABELS['keywords'][code]}: {', '.join(kw)}", 12)
        pdf.ln(1)
    pdf.ln(2)

    # Asosiy bo'limlar
    titles = _SECTION_TITLES[lang]
    for key in ("introduction", "main_part", "results", "conclusion"):
        _cell(pdf, titles[key], 13, bold=True)
        _body(pdf, article.get(key, ""))

    # Adabiyotlar
    refs = article.get("references") or []
    if refs:
        _cell(pdf, titles["references"], 13, bold=True)
        for i, ref in enumerate(refs, 1):
            _cell(pdf, f"{i}. {ref}", 12)

    out = pdf.output()
    return io.BytesIO(bytes(out))
