"""Maqola/tezis dict'idan OAK uslubidagi Word (.docx) hujjat tuzish."""
from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Inches, Pt

from chart_builder import render_chart

_LABELS = {
    "annotation": {"uz": "Annotatsiya", "ru": "Аннотация", "en": "Abstract"},
    "keywords": {"uz": "Kalit so'zlar", "ru": "Ключевые слова", "en": "Keywords"},
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


def _table_caption(lang: str, idx: int, title: str) -> str:
    if lang == "ru":
        return f"Таблица {idx} – {title}".strip()
    if lang == "en":
        return f"Table {idx}. {title}".strip()
    return f"{idx}-jadval. {title}".strip()


def _figure_caption(lang: str, idx: int, title: str) -> str:
    if lang == "ru":
        return f"Рисунок {idx} – {title}".strip()
    if lang == "en":
        return f"Figure {idx}. {title}".strip()
    return f"{idx}-rasm. {title}".strip()


def _source_label(lang: str) -> str:
    return {"ru": "Источник", "en": "Source"}.get(lang, "Manba")


def _new_doc() -> Document:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(14)
    pf = style.paragraph_format
    pf.line_spacing = 1.5
    pf.space_after = Pt(0)
    pf.space_before = Pt(0)
    sec = doc.sections[0]
    sec.left_margin = Cm(3)
    sec.right_margin = Cm(1.5)
    sec.top_margin = Cm(2)
    sec.bottom_margin = Cm(2)
    return doc


def _add_body(doc: Document, text: str) -> None:
    for chunk in (text or "").split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        p = doc.add_paragraph(chunk)
        p.paragraph_format.first_line_indent = Cm(1.25)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def _heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = True


def _add_tables(doc: Document, tables: list, lang: str) -> None:
    for idx, tbl in enumerate(tables or [], 1):
        headers = [str(h) for h in (tbl.get("headers") or [])]
        rows = tbl.get("rows") or []
        if not headers and not rows:
            continue
        cap = doc.add_paragraph()
        cap.add_run(_table_caption(lang, idx, tbl.get("title", ""))).bold = True

        ncols = max(len(headers), max((len(r) for r in rows), default=0))
        if ncols == 0:
            continue
        table = doc.add_table(rows=0, cols=ncols)
        table.style = "Table Grid"
        if headers:
            hc = table.add_row().cells
            for i in range(ncols):
                hc[i].text = headers[i] if i < len(headers) else ""
                for p in hc[i].paragraphs:
                    for run in p.runs:
                        run.bold = True
                        run.font.size = Pt(12)
        for r in rows:
            cells = table.add_row().cells
            for i in range(ncols):
                cells[i].text = str(r[i]) if i < len(r) else ""
                for p in cells[i].paragraphs:
                    for run in p.runs:
                        run.font.size = Pt(12)
        src = (tbl.get("source") or "").strip()
        if src:
            s = doc.add_paragraph()
            r = s.add_run(f"{_source_label(lang)}: {src}")
            r.italic = True
            r.font.size = Pt(12)
        doc.add_paragraph()


def _add_charts(doc: Document, charts: list, lang: str) -> None:
    for idx, chart in enumerate(charts or [], 1):
        png = render_chart(chart)
        if png is None:
            continue
        doc.add_picture(png, width=Inches(5.5))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cap.add_run(_figure_caption(lang, idx, chart.get("title", "")))
        r.italic = True
        r.font.size = Pt(12)
        src = (chart.get("source") or "").strip()
        if src:
            s = doc.add_paragraph()
            s.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sr = s.add_run(f"{_source_label(lang)}: {src}")
            sr.italic = True
            sr.font.size = Pt(12)
        doc.add_paragraph()


def _add_header(doc: Document, udk: str, title: str, author: str) -> None:
    if udk:
        doc.add_paragraph().add_run(f"UDK: {udk}").bold = True
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h.add_run((title or "").upper())
    run.bold = True
    run.font.size = Pt(15)
    if author and author.strip() not in {"—", "-"}:
        a = doc.add_paragraph()
        a.alignment = WD_ALIGN_PARAGRAPH.CENTER
        a.add_run(author).italic = True
    doc.add_paragraph()


def _build_article(doc: Document, article: dict, author: str, lang: str) -> None:
    title = article.get("title", {})
    _add_header(doc, article.get("udk", ""),
                title.get(lang) or title.get("uz", ""), author)

    annotation = article.get("annotation", {})
    keywords = article.get("keywords", {})
    for code in ("uz", "ru", "en"):
        ann = annotation.get(code)
        if ann:
            p = doc.add_paragraph()
            p.add_run(f"{_LABELS['annotation'][code]}. ").bold = True
            p.add_run(ann)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        kw = keywords.get(code) or []
        if kw:
            p = doc.add_paragraph()
            p.add_run(f"{_LABELS['keywords'][code]}: ").bold = True
            p.add_run(", ".join(kw))
    doc.add_paragraph()

    titles = _SECTION_TITLES[lang]
    for key in _ARTICLE_SECTIONS:
        _heading(doc, titles[key])
        _add_body(doc, article.get(key, ""))
        if key == "results":
            _add_tables(doc, article.get("tables"), lang)
            _add_charts(doc, article.get("charts"), lang)

    refs = article.get("references") or []
    if refs:
        _heading(doc, titles["references"])
        for i, ref in enumerate(refs, 1):
            doc.add_paragraph(f"{i}. {ref}")


def _build_thesis(doc: Document, article: dict, author: str, lang: str) -> None:
    _add_header(doc, article.get("udk", ""), article.get("title", ""), author)

    ann = article.get("annotation")
    if ann:
        p = doc.add_paragraph()
        p.add_run(f"{_LABELS['annotation'].get(lang, 'Annotatsiya')}. ").bold = True
        p.add_run(ann)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    kw = article.get("keywords") or []
    if kw:
        p = doc.add_paragraph()
        p.add_run(f"{_LABELS['keywords'].get(lang, 'Kalit soʻzlar')}: ").bold = True
        p.add_run(", ".join(kw))
    doc.add_paragraph()

    _add_body(doc, article.get("body", ""))

    refs = article.get("references") or []
    if refs:
        doc.add_paragraph()
        _heading(doc, _SECTION_TITLES[lang]["references"])
        for i, ref in enumerate(refs, 1):
            doc.add_paragraph(f"{i}. {ref}")


def build_docx(article: dict, author: str, lang: str) -> io.BytesIO:
    """Maqola/tezisdan .docx tuzib, BytesIO oqimini qaytaradi."""
    lang = lang if lang in _SECTION_TITLES else "uz"
    doc = _new_doc()
    if article.get("work_type") == "thesis":
        _build_thesis(doc, article, author, lang)
    else:
        _build_article(doc, article, author, lang)
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
