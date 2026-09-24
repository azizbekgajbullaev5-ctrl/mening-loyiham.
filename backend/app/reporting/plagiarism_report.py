"""Plagiarism report in the familiar Antiplagiat layout (uz / en)."""
from __future__ import annotations

import io
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.api.serializers import plagiarism_out
from app.reporting.pdf_report import _fonts

# light source colours (text background); the source number is always printed too
SOURCE_COLORS = ["#fde68a", "#bfdbfe", "#fecaca", "#bbf7d0", "#e9d5ff", "#fed7aa", "#a5f3fc", "#fbcfe8", "#d9f99d", "#c7d2fe", "#fef08a", "#99f6e4"]
CITATION_COLOR = "#e5e7eb"
C_ORIG, C_BORROW, C_CITE = colors.HexColor("#1f9d55"), colors.HexColor("#e8590c"), colors.HexColor("#2a78d6")

L = {
    "uz": {
        "title": "O'ZLASHTIRISHLARNI TEKSHIRISH HISOBOTI", "author": "Tekshiruvchi", "doc": "Hujjat", "type": "Hujjat turi",
        "started": "Tekshiruv sanasi", "size": "Hajmi", "pages": "bet", "words": "so'z", "modules": "Tekshirish modullari",
        "results": "TEKSHIRUV NATIJALARI", "orig": "ORIGINALLIK", "borrow": "O'ZLASHTIRISH", "cite": "IQTIBOSLAR",
        "def_borrow": "O'zlashtirish — matnning manbalarda topilgan, iqtibos sifatida rasmiylashtirilmagan qismi (so'zma-so'z va parafraz).",
        "def_cite": "Iqtibos — qo'shtirnoqqa olingan va manbaga havola berilgan (yoki qo'shtirnoqdagi manbada topilgan) matn.",
        "def_orig": "Originallik — hech bir tekshirilgan manbada topilmagan matn ulushi.",
        "scope": "Foizlar faqat ulangan manbalarga nisbatan hisoblangan: ma'lumotnoma bazasi, sizning hujjatlaringiz{web}. Adabiyotlar ro'yxati, mundarija, jadvallar va formulalar hisobga olinmagan ({excl} so'z).",
        "web_yes": ", internet (Brave, {q} so'rov, ≈${c})", "sources": "MANBALAR", "no_sources": "Manbalarda moslik topilmadi.",
        "h_n": "№", "h_rep": "Hisobotdagi ulush", "h_text": "Matndagi ulush", "h_src": "Manba", "h_mod": "Modul",
        "tricks": "TEXNIK HIYLALAR (OGOHLANTIRISH)", "no_tricks": "Texnik hiylalar aniqlanmadi.",
        "text": "TEKSHIRILGAN MATN", "legend": "Rangli fon — manbadagi moslik ([n] — manba raqami); kursiv — parafraz; kulrang — iqtibos.",
        "no_text": "Asl fayl o'chirilgan — matn ko'rinishi mavjud emas.", "para": "parafraz",
        "disclaimer": "Hisobot avtomatik yaratilgan va ekspert xulosasi o'rnini bosmaydi. Yakuniy qaror matnni ko'rib chiqqan mutaxassis tomonidan qabul qilinadi.",
        "corpus": "Ma'lumotnoma bazasi ({n} hujjat)", "own": "Sizning hujjatlaringiz", "web": "Internet (Brave)", "paraphrase": "Semantik o'xshashlik ({b})",
        "dup": "Bu hujjat avval yuklangan. Quyidagi nusxa(lar) solishtiruvdan chiqarildi: {items}.",
        "dup_reasons": {"same_file": "aynan shu fayl", "same_name": "bir xil nom", "same_text": "bir xil matn"},
        "web_pages": "TEKSHIRILGAN INTERNET SAHIFALARI",
        "web_line": "{q} so'rov, {r} natija; {ok} sahifa yuklandi, {c} keshdan, {f} yuklanmadi.",
        "h_page": "Sahifa", "h_status": "Holat", "h_found": "Natija", "found": "manba [{n}]", "not_found": "moslik yo'q",
        "more_pages": "… va yana {n} ta sahifa.",
    },
    "en": {
        "title": "PLAGIARISM CHECK REPORT", "author": "Checked by", "doc": "Document", "type": "Document type", "started": "Checked on",
        "size": "Size", "pages": "pages", "words": "words", "modules": "Search modules", "results": "RESULTS", "orig": "ORIGINALITY",
        "borrow": "BORROWINGS", "cite": "CITATIONS",
        "def_borrow": "Borrowings — text found in sources and not formatted as a citation (verbatim and paraphrase).",
        "def_cite": "Citations — quoted text with a reference marker (or quoted text found in a source).",
        "def_orig": "Originality — share of text not found in any checked source.",
        "scope": "Percentages refer to the connected sources only: reference corpus, your documents{web}. Reference list, TOC, tables and formulas are excluded ({excl} words).",
        "web_yes": ", internet (Brave, {q} queries, ≈${c})", "sources": "SOURCES", "no_sources": "No matches found in the sources.",
        "h_n": "No.", "h_rep": "Share in report", "h_text": "Share in text", "h_src": "Source", "h_mod": "Module",
        "tricks": "TECHNICAL TRICKS (WARNING)", "no_tricks": "No technical tricks detected.", "text": "CHECKED TEXT",
        "legend": "Coloured background — match in a source ([n] = source number); italic — paraphrase; grey — citation.",
        "no_text": "Original file deleted — text view unavailable.", "para": "paraphrase",
        "disclaimer": "This report is generated automatically and does not replace an expert opinion. The final decision is made by a person who has read the text.",
        "corpus": "Reference corpus ({n} documents)", "own": "Your documents", "web": "Internet (Brave)", "paraphrase": "Semantic similarity ({b})",
        "dup": "This document was uploaded before. These copies were left out of the comparison: {items}.",
        "dup_reasons": {"same_file": "same file", "same_name": "same name", "same_text": "same text"},
        "web_pages": "CHECKED WEB PAGES",
        "web_line": "{q} queries, {r} results; {ok} pages downloaded, {c} from cache, {f} failed.",
        "h_page": "Page", "h_status": "Status", "h_found": "Result", "found": "source [{n}]", "not_found": "no match",
        "more_pages": "… and {n} more pages.",
    },
}


def color_for(idx: int) -> str:
    return SOURCE_COLORS[idx % len(SOURCE_COLORS)] if idx >= 0 else "#fde68a"


def _result_bar(orig: float, borrow: float, cite: float) -> Drawing:
    w, h = 170 * mm, 7 * mm
    d = Drawing(w, h + 2)
    x = 0.0
    for val, col in ((orig, C_ORIG), (borrow, C_BORROW), (cite, C_CITE)):
        width = w * max(0.0, val) / 100.0
        if width > 0:
            d.add(Rect(x, 0, width, h, fillColor=col, strokeColor=None))
        x += width
    return d


def render_plagiarism_pdf(a, user, lang: str = "uz") -> bytes:
    from app.document_processing.types import ExtractionError
    from app.services import storage
    from app.services.pipeline import prepare

    lang = lang if lang in L else "uz"
    t = L[lang]
    font, bold = _fonts()
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName=font, fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, leading=10.5, textColor=colors.HexColor("#52514e"))
    h1 = ParagraphStyle("h1", parent=body, fontName=bold, fontSize=15, leading=19, textColor=colors.HexColor("#1e3a8a"))
    h2 = ParagraphStyle("h2", parent=body, fontName=bold, fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor("#1e3a8a"))
    big = lambda c: ParagraphStyle("big", parent=body, fontName=bold, fontSize=22, leading=26, textColor=c)  # noqa: E731
    P = lambda txt, st=body: Paragraph(escape(str(txt)), st)  # noqa: E731

    p = plagiarism_out(a.plagiarism, lang)
    doc = a.document
    v = a.version
    mods = p["modules"] or {}
    story = [P(t["title"], h1), Spacer(1, 6)]
    mod_names = []
    if mods.get("corpus"):
        mod_names.append(t["corpus"].format(n=mods.get("corpus_documents", 0)))
    if mods.get("own"):
        mod_names.append(t["own"])
    if mods.get("web"):
        mod_names.append(t["web"])
    if isinstance(mods.get("paraphrase"), dict):
        mod_names.append(t["paraphrase"].format(b=mods["paraphrase"].get("backend", "")))
    info = [
        [t["author"], user.full_name or user.email], [t["doc"], doc.original_filename],
        [t["started"], (a.finished_at or a.created_at).astimezone(UTC).strftime("%d.%m.%Y %H:%M UTC")],
        [t["size"], f"{v.page_count if v else '—'} {t['pages']}, {v.word_count if v else '—'} {t['words']}"],
        [t["modules"], "; ".join(mod_names) or "—"],
    ]
    tbl = Table([[P(k, small), P(val)] for k, val in info], colWidths=[45 * mm, 125 * mm])
    tbl.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#e1e0d9")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [tbl, Spacer(1, 8), P(t["results"], h2)]
    res = Table([[P(t["orig"], small), P(t["borrow"], small), P(t["cite"], small)],
                 [P(f"{p['originality']:.2f}%", big(C_ORIG)), P(f"{p['borrowing']:.2f}%", big(C_BORROW)), P(f"{p['citation']:.2f}%", big(C_CITE))]],
                colWidths=[57 * mm, 57 * mm, 56 * mm])
    story += [res, Spacer(1, 3), _result_bar(p["originality"], p["borrowing"], p["citation"]), Spacer(1, 5)]
    story += [P(t["def_borrow"], small), P(t["def_cite"], small), P(t["def_orig"], small)]
    ws = mods.get("web_stats") or {}
    web_txt = t["web_yes"].format(q=ws.get("queries_used", 0), c=ws.get("cost_usd", 0)) if mods.get("web") else ""
    story += [Spacer(1, 4), P(t["scope"].format(web=web_txt, excl=p["excluded_words"]), small)]
    dups = [d for d in mods.get("duplicates") or [] if d.get("excluded")]
    if dups:
        items = "; ".join(f"{d['filename']} ({', '.join(t['dup_reasons'].get(r, r) for r in d['reasons'])})" for d in dups)
        story += [Spacer(1, 4), Paragraph(f'<font color="#b45309">⚠</font> {escape(t["dup"].format(items=items))}', body)]

    story.append(P(t["sources"], h2))
    if p["sources"]:
        rows = [[P(t["h_n"], small), P(t["h_rep"], small), P(t["h_text"], small), P(t["h_src"], small), P(t["h_mod"], small)]]
        styles = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        for i, src in enumerate(p["sources"], start=1):
            label = src["title"]
            if src.get("authors"):
                label = f"{src['authors']}. {label}"
            if src.get("year"):
                label += f" ({src['year']})"
            if src.get("url"):
                label += f"\n{src['url']}"
            if src.get("paraphrase_words"):
                label += f"\n[{t['para']}: {src['paraphrase_words']} {t['words']}]"
            rows.append([P(f"[{i}]"), P(f"{src['share_report']:.2f}%"), P(f"{src['share_text']:.2f}%"), Paragraph(escape(label).replace("\n", "<br/>"), small), P(src["module_label"], small)])
            styles.append(("BACKGROUND", (0, i), (0, i), colors.HexColor(color_for(src["index"]))))
        st = Table(rows, colWidths=[12 * mm, 24 * mm, 22 * mm, 82 * mm, 30 * mm], repeatRows=1)
        st.setStyle(TableStyle(styles))
        story.append(st)
    else:
        story.append(P(t["no_sources"]))

    if mods.get("web") and ws:
        src_num = {src["index"]: i for i, src in enumerate(p["sources"], start=1)}
        story += [P(t["web_pages"], h2), P(t["web_line"].format(q=ws.get("queries_used", 0), r=ws.get("results_total", "—"),
                                                                ok=ws.get("fetched_pages", 0), c=ws.get("cached_pages", 0), f=ws.get("failed_pages", 0)), small)]
        pages = sorted(ws.get("pages") or [], key=lambda pg: (pg.get("source_index") is None, pg.get("status") != "ok"))
        if pages:
            rows = [[P(t["h_page"], small), P(t["h_status"], small), P(t["h_found"], small)]]
            for pg in pages[:60]:
                n = src_num.get(pg.get("source_index"))
                found = t["found"].format(n=n) if n else (t["not_found"] if pg.get("status") == "ok" else "—")
                label = (pg.get("title") or "") + "\n" + pg["url"]
                rows.append([Paragraph(escape(label).replace("\n", "<br/>"), small), P(pg.get("status", ""), small), P(found, small)])
            wt = Table(rows, colWidths=[120 * mm, 28 * mm, 22 * mm], repeatRows=1)
            wt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(wt)
            if len(pages) > 60:
                story.append(P(t["more_pages"].format(n=len(pages) - 60), small))

    story.append(P(t["tricks"], h2))
    items = (p["integrity"] or {}).get("items", [])
    if items:
        for it in items:
            ex = f" — {', '.join(map(str, it.get('examples', [])[:5]))}" if it.get("examples") else ""
            pages = f" (bet: {', '.join(map(str, it['pages'][:15]))})" if it.get("pages") else ""
            story.append(Paragraph(f'<font color="#b91c1c">⚠</font> {escape(it["label"])}: {it["count"]}{escape(ex)}{escape(pages)}', body))
    else:
        story.append(P(t["no_tricks"]))

    # ---- full text with highlights
    story += [PageBreak(), P(t["text"], h2), P(t["legend"], small), Spacer(1, 4)]
    prep = None
    if doc.storage_key:
        try:
            ver = doc.versions[-1] if doc.versions else None
            manual = ver.structure if ver and ver.structure_source == "manual" else None
            prep = prepare(doc.file_type, storage.load(doc.storage_key), manual, checkpoint=(doc.id, doc.sha256))
        except (ExtractionError, OSError, ValueError):
            prep = None
    if prep is None:
        story.append(P(t["no_text"]))
    else:
        from app.plagiarism.textnorm import display_text

        spans_by_block: dict[int, list] = {}
        for sp in p["spans"]:
            spans_by_block.setdefault(sp[0], []).append(sp)
        src_num = {s["index"]: n for n, s in enumerate(p["sources"], start=1)}
        last_page = None
        for b in prep.doc.blocks:
            if b.kind == "table":
                continue
            if b.page and b.page != last_page:
                story.append(Paragraph(f'<font color="#9ca3af" size="7">— {b.page} —</font>', small))
                last_page = b.page
            text = display_text(b.text)
            story.append(Paragraph(_highlight(text, spans_by_block.get(b.index, []), src_num), body))
    story += [Spacer(1, 10), P(t["disclaimer"], small)]

    buf = io.BytesIO()

    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(15 * mm, 10 * mm, f"{t['title']} · {doc.original_filename[:60]} · {datetime.now(UTC).strftime('%d.%m.%Y')}")
        canvas.drawRightString(195 * mm, 10 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=18 * mm,
                      title=t["title"]).build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _highlight(text: str, spans: list, src_num: dict[int, int]) -> str:
    out, pos = [], 0
    for _, start, end, src, cls in sorted(spans, key=lambda s: s[1]):
        if start < pos:
            continue
        out.append(escape(text[pos:start]))
        frag = escape(text[start:end])
        if cls == "c":
            out.append(f'<font backColor="{CITATION_COLOR}">{frag}</font>')
        else:
            n = src_num.get(src)
            mark = f'<super><font size="6">[{n}]</font></super>' if n else ""
            inner = f"<i>{frag}</i>" if cls == "p" else frag
            out.append(f'{mark}<font backColor="{color_for(src)}">{inner}</font>')
        pos = end
    out.append(escape(text[pos:]))
    return "".join(out)
