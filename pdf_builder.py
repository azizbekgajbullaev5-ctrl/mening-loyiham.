"""Maqola/tezis dict'idan OAK uslubidagi PDF (fpdf2 + DejaVu shrifti)."""
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
    "keywords": {"uz": "Kalit soʻzlar", "ru": "Ключевые слова", "en": "Keywords"},
}

_SECTION_TITLES = {
    "uz": {
        "introduction": "KIRISH",
        "methods": "MATERIALLAR VA METODLAR",
        "results": "NATIJALAR",
        "discussion": "MUHOKAMA",
        "conclusion": "XULOSA",
        "references": "FOYDALANILGAN ADABIYOTLAR RO'YXATI",
    },
    "ru": {
        "introduction": "ВВЕДЕНИЕ",
        "methods": "МАТЕРИАЛЫ И МЕТОДЫ",
        "results": "РЕЗУЛЬТАТЫ",
        "discussion": "ОБСУЖДЕНИЕ",
        "conclusion": "ЗАКЛЮЧЕНИЕ",
        "references": "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
    },
    "en": {
        "introduction": "INTRODUCTION",
        "methods": "MATERIALS AND METHODS",
        "results": "RESULTS",
        "discussion": "DISCUSSION",
        "conclusion": "CONCLUSION",
        "references": "REFERENCES",
    },
}

_ARTICLE_SECTIONS = ("introduction", "methods", "results", "discussion", "conclusion")


def _table_caption(lang, idx, title):
    if lang == "ru":
        return f"Таблица {idx} – {title}".strip()
    if lang == "en":
        return f"Table {idx}. {title}".strip()
    return f"{idx}-jadval. {title}".strip()


def _figure_caption(lang, idx, title):
    if lang == "ru":
        return f"Рисунок {idx} – {title}".strip()
    if lang == "en":
        return f"Figure {idx}. {title}".strip()
    return f"{idx}-rasm. {title}".strip()


def _source_label(lang):
    return {"ru": "Источник", "en": "Source"}.get(lang, "Manba")


class _PDF(FPDF):
    pass


def _new_pdf() -> _PDF:
    pdf = _PDF()
    pdf.add_font("DejaVu", "", _FONT_REGULAR)
    pdf.add_font("DejaVu", "B", _FONT_BOLD)
    pdf.set_margins(left=28, top=20, right=15)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    return pdf


def _cell(pdf, text, size, *, bold=False, align="L"):
    pdf.set_font("DejaVu", "B" if bold else "", size)
    pdf.multi_cell(0, 7, text, align=align, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _body(pdf, text):
    for chunk in (text or "").split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        _cell(pdf, chunk, 14, align="J")
        pdf.ln(1)


def _add_tables(pdf, tables, lang):
    for idx, tbl in enumerate(tables or [], 1):
        headers = [str(h) for h in (tbl.get("headers") or [])]
        rows = tbl.get("rows") or []
        if not headers and not rows:
            continue
        _cell(pdf, _table_caption(lang, idx, tbl.get("title", "")), 12, bold=True)
        ncols = max(len(headers), max((len(r) for r in rows), default=0))
        if ncols == 0:
            continue
        data = []
        if headers:
            data.append([headers[i] if i < len(headers) else "" for i in range(ncols)])
        for r in rows:
            data.append([str(r[i]) if i < len(r) else "" for i in range(ncols)])
        pdf.set_font("DejaVu", "", 11)
        with pdf.table(
            first_row_as_headings=bool(headers),
            headings_style=FontFace(emphasis="BOLD"),
        ) as table:
            for data_row in data:
                row = table.row()
                for datum in data_row:
                    row.cell(datum)
        src = (tbl.get("source") or "").strip()
        if src:
            _cell(pdf, f"{_source_label(lang)}: {src}", 11)
        pdf.ln(2)


def _add_charts(pdf, charts, lang):
    for idx, chart in enumerate(charts or [], 1):
        png = render_chart(chart)
        if png is None:
            continue
        epw = pdf.epw
        width = min(150, epw)
        x = pdf.l_margin + (epw - width) / 2
        pdf.image(png, x=x, w=width)
        _cell(pdf, _figure_caption(lang, idx, chart.get("title", "")), 11, align="C")
        src = (chart.get("source") or "").strip()
        if src:
            _cell(pdf, f"{_source_label(lang)}: {src}", 11, align="C")
        pdf.ln(2)


def _header(pdf, udk, title, author):
    if udk:
        _cell(pdf, f"UDK: {udk}", 13, bold=True)
    _cell(pdf, (title or "").upper(), 15, bold=True, align="C")
    if author and author.strip() not in {"—", "-"}:
        _cell(pdf, author, 12, align="C")
    pdf.ln(3)


def _build_article(pdf, article, author, lang):
    title = article.get("title", {})
    _header(pdf, article.get("udk", ""), title.get(lang) or title.get("uz", ""), author)
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
    titles = _SECTION_TITLES[lang]
    for key in _ARTICLE_SECTIONS:
        _cell(pdf, titles[key], 14, bold=True)
        _body(pdf, article.get(key, ""))
        if key == "results":
            _add_tables(pdf, article.get("tables"), lang)
            _add_charts(pdf, article.get("charts"), lang)
    refs = article.get("references") or []
    if refs:
        _cell(pdf, titles["references"], 14, bold=True)
        for i, ref in enumerate(refs, 1):
            _cell(pdf, f"{i}. {ref}", 12)


def _build_thesis(pdf, article, author, lang):
    _header(pdf, article.get("udk", ""), article.get("title", ""), author)
    ann = article.get("annotation")
    if ann:
        _cell(pdf, f"{_LABELS['annotation'].get(lang, 'Annotatsiya')}:", 12, bold=True)
        _cell(pdf, ann, 12, align="J")
    kw = article.get("keywords") or []
    if kw:
        _cell(pdf, f"{_LABELS['keywords'].get(lang, 'Kalit soʻzlar')}: {', '.join(kw)}", 12)
    pdf.ln(2)
    _body(pdf, article.get("body", ""))
    refs = article.get("references") or []
    if refs:
        pdf.ln(1)
        _cell(pdf, _SECTION_TITLES[lang]["references"], 14, bold=True)
        for i, ref in enumerate(refs, 1):
            _cell(pdf, f"{i}. {ref}", 12)


def build_pdf(article: dict, author: str, lang: str) -> io.BytesIO:
    """Maqola/tezisdan .pdf tuzib, BytesIO oqimini qaytaradi."""
    lang = lang if lang in _SECTION_TITLES else "uz"
    pdf = _new_pdf()
    if article.get("work_type") == "thesis":
        _build_thesis(pdf, article, author, lang)
    else:
        _build_article(pdf, article, author, lang)
    out = pdf.output()
    return io.BytesIO(bytes(out))
