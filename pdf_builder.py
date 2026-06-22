"""Maqola dict'idan OAK uslubidagi PDF hujjat tuzish (fpdf2 + DejaVu shrifti)."""
from __future__ import annotations

import io
import os

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

from chart_builder import render_chart

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
    "table": {"uz": "jadval", "ru": "таблица"},
    "figure": {"uz": "rasm", "ru": "рисунок"},
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


def _add_tables(pdf: _PDF, tables: list, lang: str) -> None:
    """Premium jadvallarni chizadi."""
    for idx, tbl in enumerate(tables, 1):
        headers = [str(h) for h in (tbl.get("headers") or [])]
        rows = tbl.get("rows") or []
        if not headers and not rows:
            continue
        label = _LABELS["table"].get(lang, _LABELS["table"]["uz"])
        _cell(pdf, f"{idx}-{label}. {tbl.get('title', '')}".strip(), 12, bold=True)

        ncols = max(len(headers), max((len(r) for r in rows), default=0))
        if ncols == 0:
            continue
        data = []
        if headers:
            data.append([headers[i] if i < len(headers) else "" for i in range(ncols)])
        for r in rows:
            data.append([str(r[i]) if i < len(r) else "" for i in range(ncols)])

        pdf.set_font("DejaVu", "", 10)
        with pdf.table(
            first_row_as_headings=bool(headers),
            headings_style=FontFace(emphasis="BOLD"),
        ) as table:
            for data_row in data:
                row = table.row()
                for datum in data_row:
                    row.cell(datum)
        pdf.ln(3)


def _add_charts(pdf: _PDF, charts: list, lang: str) -> None:
    """Premium diagrammalarni (matplotlib rasm) chizadi."""
    for idx, chart in enumerate(charts, 1):
        png = render_chart(chart)
        if png is None:
            continue
        # Sahifa kengligiga moslab markazga joylashtiramiz
        epw = pdf.epw  # samarali sahifa kengligi (mm)
        width = min(150, epw)
        x = pdf.l_margin + (epw - width) / 2
        pdf.image(png, x=x, w=width)
        label = _LABELS["figure"].get(lang, _LABELS["figure"]["uz"])
        _cell(pdf, f"{idx}-{label}. {chart.get('title', '')}".strip(), 11, align="C")
        pdf.ln(3)


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
        # Jadval/diagrammalar natijalardan keyin (premium)
        if key == "results":
            _add_tables(pdf, article.get("tables") or [], lang)
            _add_charts(pdf, article.get("charts") or [], lang)

    # Adabiyotlar
    refs = article.get("references") or []
    if refs:
        _cell(pdf, titles["references"], 13, bold=True)
        for i, ref in enumerate(refs, 1):
            _cell(pdf, f"{i}. {ref}", 12)

    out = pdf.output()
    return io.BytesIO(bytes(out))
