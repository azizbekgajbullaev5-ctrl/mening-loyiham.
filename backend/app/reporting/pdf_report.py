"""PDF report (ReportLab) with Unicode fonts for Uzbek/Russian text."""
from __future__ import annotations

import io
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.reporting.builder import fmt_dt, fmt_pct

BLUE = colors.HexColor("#1d4ed8")
LIGHT = colors.HexColor("#eff6ff")
GREY = colors.HexColor("#64748b")
_FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", str(Path(__file__).parent / "fonts")]
_font_name = None


def _fonts() -> tuple[str, str]:
    global _font_name
    if _font_name:
        return _font_name, _font_name + "-Bold"
    for d in _FONT_DIRS:
        reg, bold = Path(d) / "DejaVuSans.ttf", Path(d) / "DejaVuSans-Bold.ttf"
        if reg.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("DejaVu", str(reg)))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold)))
            _font_name = "DejaVu"
            return "DejaVu", "DejaVu-Bold"
    return "Helvetica", "Helvetica-Bold"  # Latin-only fallback


def _p(text, style) -> Paragraph:
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def render_pdf(data: dict) -> bytes:
    font, bold = _fonts()
    L = data["L"]
    d = data["detail"]
    r = d["result"] or {}
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName=font, fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, leading=10.5, textColor=GREY)
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName=bold, fontSize=17, textColor=BLUE, leading=21)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=bold, fontSize=12.5, textColor=BLUE, spaceBefore=10, spaceAfter=5)
    note = ParagraphStyle("n", parent=body, backColor=LIGHT, borderColor=BLUE, borderWidth=0.6, borderPadding=6, spaceBefore=4, spaceAfter=8)
    big = ParagraphStyle("big", parent=body, fontName=bold, fontSize=20, leading=24, alignment=TA_CENTER, textColor=BLUE)

    cell = ParagraphStyle("c", parent=body, fontSize=8, leading=10)

    def table(rows, widths, header=True, compact=False):
        st = cell if compact else body
        t = Table([[c if isinstance(c, Paragraph) else _p(c, st) for c in row] for row in rows], colWidths=widths, repeatRows=1 if header else 0)
        style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), LIGHT)]
        t.setStyle(TableStyle(style))
        return t

    story = [_p(L["title"], h1), Spacer(1, 8), _p(data["disclaimer"], note)]

    doc = data["doc"]
    story += [_p(L["s_doc"], h2)]
    pages = f"{doc['pages']} {L['pages_est'] if doc['pages_estimated'] else ''}"
    story.append(table([
        [L["file"], doc["file"]], [L["doc_type"], doc["doc_type"]], [L["size"], f"{doc['size_kb']} KB ({doc['file_type']})"],
        [L["language"], doc["language"]], [L["words"], f"{doc['words']:,}".replace(",", " ")], [L["chars"], f"{doc['chars']:,}".replace(",", " ")],
        [L["pages"], pages], [L["depth"], data["depth"]], [L["analysis_date"], fmt_dt(data["analysis_date"])], [L["report_date"], fmt_dt(data["report_date"])],
    ], [55 * mm, 115 * mm], header=False))

    ai = r.get("ai", {})
    story += [_p(L["s_ai"], h2)]
    ai_val = "—" if ai.get("likelihood") is None else f"{ai['likelihood']:.0f}%"
    story.append(table([
        [_p(L["ai_overall"], body), _p(L["confidence"], body), _p(L["flagged"], body)],
        [_p(ai_val, big), _p(ai.get("confidence_label", "—"), big), _p(f"{ai.get('passages_flagged', 0)} / {ai.get('passages_analyzed', 0)}", big)],
    ], [57 * mm, 57 * mm, 56 * mm]))
    story += [Spacer(1, 8), _p(ai.get("note", ""), note)]
    story.append(_p(f"{L['basis']}: {ai.get('basis_text', '')}", small))
    if ai.get("language_note"):
        story.append(_p(ai["language_note"], small))
    comp = r.get("provider_comparison", {})
    prov_rows = [["Provider", "Status", L["ai"]]]
    for p in r.get("providers", []):
        mean = ai.get("likelihood") if p.get("kind") == "local" else next((c.get("mean_score") for c in comp.get("providers", []) if c["name"] == p["name"]), None)
        prov_rows.append([p["name"], p.get("status_label", p.get("status")), "—" if mean is None else f"{mean:.0f}%"])
    story += [_p(L["s_providers"], h2), table(prov_rows, [70 * mm, 60 * mm, 40 * mm]), Spacer(1, 3), _p(comp.get("summary_text", ""), small)]

    sim = r.get("similarity", {})
    story += [_p(L["s_sim"], h2)]
    ext = fmt_pct(sim.get("external")) if sim.get("external") is not None else (L["not_configured"] if sim.get("scope") == "local_only" else L["not_run"])
    story.append(table([
        [L["sim_overall"], fmt_pct(sim.get("overall"))], [L["sim_internal"], fmt_pct(sim.get("internal"))],
        [L["sim_corpus"], fmt_pct(sim.get("corpus")) if sim.get("corpus") is not None else L["not_run"]], [L["sim_external"], ext],
    ], [90 * mm, 80 * mm], header=False))
    story += [Spacer(1, 8), _p(sim.get("scope_text", ""), note)]

    # chapter chart + table
    story += [_p(L["s_chapters"], h2)]
    top = [s for s in data["sections"] if s["level"] == 1 and s["ai_likelihood"] is not None]
    if top:
        story.append(_bar_chart(top, font, L["chart_ai"]))
    rows = [[L["section"], L["pages"], L["words"], L["ai"], L["confidence"], L["sim"]]]
    for s in data["sections"]:
        indent = "    " * (s["level"] - 1)
        rows.append([
            indent + (s["title"] or s["kind_label"])[:90], f"{s['page_start'] or '—'}–{s['page_end'] or '—'}", str(s["word_count"]),
            L["excluded"] if s["excluded_from_ai"] else fmt_pct(s["ai_likelihood"]), s["ai_confidence_label"] or "—", fmt_pct(s["similarity"]),
        ])
    story.append(table(rows, [64 * mm, 18 * mm, 18 * mm, 26 * mm, 20 * mm, 24 * mm], compact=True))

    story += [PageBreak(), _p(L["s_passages"], h2)]
    if not data["passages"]:
        story.append(_p(L["no_passages"], body))
    for p in data["passages"]:
        head = f"{L['page']} {p['page'] or '—'} · {L['paragraph']} {p['paragraph_number']} · {p['section_title'] or ''}"
        chars = "; ".join(c["label"] for c in p["characteristics"]) or "—"
        block = [
            _p(head, small),
            _p(f"{L['ai']}: {p['ai_likelihood']:.0f}% · {L['confidence']}: {p['confidence_label']}", body),
            _p("“" + p["text"][:1800] + ("…" if len(p["text"]) > 1800 else "") + "”", body),
            _p(f"{L['characteristics']}: {chars}", small),
            _p(p["explanation"], small),
            Spacer(1, 7),
        ]
        story.append(KeepTogether(block[:3]))
        story.extend(block[3:])

    story += [_p(L["s_matches"], h2)]
    if not data["matches"]:
        story.append(_p(L["no_matches"], body))
    for m in data["matches"]:
        src = m["source_title"] or m["matched_document_name"] or (f"{L['page']} {m['matched_page']}, {L['paragraph']} {m['matched_paragraph_number']}" if m["matched_paragraph_number"] else "")
        story.append(_p(f"{m['match_type_label']} — {m['similarity']:.0f}% · {L['page']} {m['page'] or '—'}, {L['paragraph']} {m['paragraph_number'] or '—'} ↔ {src}", small))
        story.append(_p(m["text"][:500] + ("…" if len(m["text"]) > 500 else ""), body))
        if m["source_url"]:
            story.append(_p(m["source_url"], small))
        story.append(Spacer(1, 5))
    rp = r.get("repeated_phrases") or []
    if rp:
        story += [_p(L["repeated"], h2), table([["", "×"]] + [[x["phrase"], str(x["count"])] for x in rp[:15]], [150 * mm, 20 * mm])]

    ac = r.get("academic", {})
    story += [_p(L["s_academic"], h2)]
    m = ac.get("metrics", {})
    if m:
        story.append(_p(" · ".join(f"{k}: {v}" for k, v in m.items()), small))
    issues = ac.get("issues", [])
    if issues:
        story.append(table([["", ""]] + [[i["severity_label"], i["text"]] for i in issues], [30 * mm, 140 * mm]))
    else:
        story.append(_p(L["no_issues"], body))

    story += [_p(L["s_method"], h2)] + [_p(x, body) for x in data["methodology"]]
    story += [_p(L["s_limits"], h2)] + [_p("• " + x, body) for x in data["limitations"]]
    story += [_p(L["s_disclaimer"], h2), Spacer(1, 6), _p(data["disclaimer"], note)]

    buf = io.BytesIO()

    def footer(canvas, docx):
        canvas.saveState()
        canvas.setFont(font, 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(15 * mm, 10 * mm, f"{L['title']} · {doc['file'][:60]}")
        canvas.drawRightString(195 * mm, 10 * mm, str(canvas.getPageNumber()))
        canvas.restoreState()

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=18 * mm,
                      title=L["title"], author="Academic AI & Similarity Analyzer").build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


def _bar_chart(sections: list[dict], font: str, title: str) -> Drawing:
    dw = Drawing(170 * mm, 62 * mm)
    ch = VerticalBarChart()
    ch.x, ch.y, ch.width, ch.height = 12 * mm, 12 * mm, 150 * mm, 40 * mm
    ch.data = [[s["ai_likelihood"] for s in sections]]
    ch.valueAxis.valueMin, ch.valueAxis.valueMax, ch.valueAxis.valueStep = 0, 100, 25  # fixed 0–100 axis: no exaggeration
    ch.valueAxis.labels.fontName = font
    ch.categoryAxis.categoryNames = [(s["title"] or s["kind_label"])[:14] for s in sections]
    ch.categoryAxis.labels.fontName = font
    ch.categoryAxis.labels.fontSize = 6.5
    ch.categoryAxis.labels.angle = 20
    ch.categoryAxis.labels.dy = -6
    ch.bars[0].fillColor = BLUE
    ch.bars[0].strokeColor = None
    ch.barSpacing = 2
    ch.groupSpacing = 18
    dw.add(ch)
    dw.add(String(12 * mm, 57 * mm, title, fontName=font, fontSize=8.5, fillColor=GREY))
    return dw
