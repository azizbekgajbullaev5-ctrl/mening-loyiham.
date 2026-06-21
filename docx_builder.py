"""Maqola dict'idan OAK uslubidagi Word (.docx) hujjat tuzish."""
from __future__ import annotations

import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

_LABELS = {
    "annotation": {"uz": "Annotatsiya", "ru": "Аннотация", "en": "Abstract"},
    "keywords": {
        "uz": "Kalit so'zlar",
        "ru": "Ключевые слова",
        "en": "Keywords",
    },
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


def _add_body(doc: Document, text: str) -> None:
    """Ko'p paragrafli matnni qo'shadi (bo'sh qatorlar bo'yicha bo'linadi)."""
    for chunk in (text or "").split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        p = doc.add_paragraph(chunk)
        p.paragraph_format.first_line_indent = Pt(18)
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def build_docx(article: dict, author: str, lang: str) -> io.BytesIO:
    """Maqoladan .docx tuzib, BytesIO oqimini qaytaradi."""
    lang = lang if lang in _SECTION_TITLES else "uz"
    doc = Document()

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(14)

    # UDK
    udk = doc.add_paragraph()
    udk.add_run(f"UDK: {article.get('udk', '')}").bold = True

    # Sarlavha (interfeys tilida)
    title = article.get("title", {})
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h.add_run(title.get(lang) or title.get("uz", ""))
    run.bold = True
    run.font.size = Pt(15)

    # Muallif
    if author and author.strip() not in {"—", "-"}:
        a = doc.add_paragraph()
        a.alignment = WD_ALIGN_PARAGRAPH.CENTER
        a.add_run(author).italic = True

    doc.add_paragraph()

    # Annotatsiya va kalit so'zlar — uchta tilda
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
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph()

    # Asosiy bo'limlar
    titles = _SECTION_TITLES[lang]
    for key in ("introduction", "main_part", "results", "conclusion"):
        heading = doc.add_paragraph()
        heading.add_run(titles[key]).bold = True
        _add_body(doc, article.get(key, ""))

    # Adabiyotlar
    refs = article.get("references") or []
    if refs:
        heading = doc.add_paragraph()
        heading.add_run(titles["references"]).bold = True
        for i, ref in enumerate(refs, 1):
            doc.add_paragraph(f"{i}. {ref}")

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
