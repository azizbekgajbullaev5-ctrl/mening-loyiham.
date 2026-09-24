"""Collects everything a report needs from stored results (format-independent)."""
from __future__ import annotations

from datetime import UTC, datetime

from app.api.serializers import analysis_detail, match_out, passage_out, section_out
from app.core.i18n import DISCLAIMER, t
from app.models import Analysis

LABELS = {
    "uz": {
        "title": "Akademik AI va o'xshashlik tahlili — hisobot",
        "s_doc": "1. Hujjat ma'lumotlari", "file": "Fayl", "doc_type": "Hujjat turi", "size": "Hajmi",
        "language": "Til", "words": "So'zlar soni", "pages": "Sahifalar soni", "pages_est": "(taxminiy)", "chars": "Belgilar soni",
        "analysis_date": "Tahlil sanasi va vaqti", "report_date": "Hisobot yaratilgan", "depth": "Tahlil chuqurligi",
        "s_ai": "2. AI-ehtimollik (baho, isbot emas)", "ai_overall": "Umumiy baho", "confidence": "Ishonchlilik",
        "flagged": "Shubhali parchalar", "of": "dan", "basis": "Asos",
        "s_providers": "Tahlil usullari va provayderlar",
        "s_sim": "3. O'xshashlik (AI tahlilidan alohida o'lchov)", "sim_overall": "Umumiy lokal o'xshashlik",
        "sim_internal": "Hujjat ichidagi takror", "sim_corpus": "Sizning boshqa hujjatlaringiz bilan", "sim_external": "Tashqi manbalar",
        "not_configured": "Tashqi provayder sozlanmagan", "not_run": "Bajarilmagan",
        "s_chapters": "4. Boblar va bo'limlar bo'yicha tahlil", "section": "Bo'lim", "ai": "AI-ehtimollik", "sim": "O'xshashlik",
        "s_passages": "5. Shubhali parchalar", "page": "Sahifa", "paragraph": "Paragraf", "characteristics": "Kuzatilgan xususiyatlar",
        "no_passages": "Chegara qiymatidan yuqori parchalar topilmadi.",
        "s_matches": "6. O'xshash parchalar", "no_matches": "Mosliklar topilmadi.",
        "s_academic": "7. Akademik yozuv ko'rsatkichlari", "no_issues": "Muammolar aniqlanmadi.",
        "s_method": "8. Metodologiya", "s_limits": "9. Cheklovlar", "s_disclaimer": "Muhim ogohlantirish",
        "excluded": "baholanmaydi", "chart_ai": "AI-ehtimollik boblar bo'yicha (0–100, baho)",
        "repeated": "Takrorlanuvchi iboralar",
    },
    "en": {
        "title": "Academic AI & Similarity Analysis — Report",
        "s_doc": "1. Document information", "file": "File", "doc_type": "Document type", "size": "Size",
        "language": "Language", "words": "Word count", "pages": "Page count", "pages_est": "(estimated)", "chars": "Characters",
        "analysis_date": "Analysis date/time", "report_date": "Report generated", "depth": "Analysis depth",
        "s_ai": "2. AI-likelihood (estimate, not proof)", "ai_overall": "Overall estimate", "confidence": "Confidence",
        "flagged": "Suspicious passages", "of": "of", "basis": "Basis",
        "s_providers": "Methods and providers",
        "s_sim": "3. Similarity (measured separately from AI-likelihood)", "sim_overall": "Overall local similarity",
        "sim_internal": "Internal repetition", "sim_corpus": "Against your other documents", "sim_external": "External sources",
        "not_configured": "External provider not configured", "not_run": "Not run",
        "s_chapters": "4. Chapter and section analysis", "section": "Section", "ai": "AI-likelihood", "sim": "Similarity",
        "s_passages": "5. Suspicious passages", "page": "Page", "paragraph": "Paragraph", "characteristics": "Observed characteristics",
        "no_passages": "No passages above the threshold.",
        "s_matches": "6. Similar passages", "no_matches": "No matches found.",
        "s_academic": "7. Academic writing indicators", "no_issues": "No issues detected.",
        "s_method": "8. Methodology", "s_limits": "9. Limitations", "s_disclaimer": "Important notice",
        "excluded": "not scored", "chart_ai": "AI-likelihood by chapter (0–100, estimate)",
        "repeated": "Repeated phrases",
    },
}

DOC_TYPE_LABELS = {
    "uz": {"phd_dissertation": "PhD dissertatsiya", "masters_dissertation": "Magistrlik dissertatsiyasi", "textbook": "Darslik",
           "study_guide": "O'quv qo'llanma", "article": "Ilmiy maqola", "conference_paper": "Konferensiya materiali", "report": "Ilmiy hisobot"},
    "en": {"phd_dissertation": "PhD dissertation", "masters_dissertation": "Master's dissertation", "textbook": "Textbook",
           "study_guide": "Study guide", "article": "Research article", "conference_paper": "Conference paper", "report": "Academic report"},
}
LANG_NAMES = {"uz": {"uz": "O'zbek", "ru": "Rus", "en": "Ingliz", "unknown": "Aniqlanmadi"}, "en": {"uz": "Uzbek", "ru": "Russian", "en": "English", "unknown": "Unknown"}}

METHODOLOGY = {
    "uz": [
        "Hujjat matni ajratib olinadi (DOCX, PDF, TXT; skanerlangan PDF uchun OCR), tili avtomatik aniqlanadi va akademik tuzilma "
        "(boblar, bo'limlar, kirish, xulosa, adabiyotlar) aniqlanadi. Tahlil butun hujjat bo'yicha emas, bo'limma-bo'lim, 120–380 so'zli parchalarda bajariladi.",
        "AI-ehtimollik lokal stilometrik usul bilan baholanadi: gap uzunligi o'zgaruvchanligi (burstiness), qolip iboralar zichligi, bog'lovchi "
        "iboralar bilan boshlanuvchi gaplar ulushi, gap boshlanishlari va sintaktik qoliplar takrori, aniq tafsilotlar zichligi, leksik bir xillik, "
        "nominalizatsiya, noaniq kuchaytiruvchilar, paragraf bir xilligi va hujjat ichidagi keskin uslub o'zgarishi. Har bir signal til profili bo'yicha "
        "(o'zbek, rus, ingliz alohida) me'yorlashtiriladi va vaznli o'rtacha sifatida birlashtiriladi. Hech bir signal yakka o'zi hal qiluvchi emas.",
        "Adabiyotlar ro'yxati, mundarija, kalit so'zlar va ilovalar AI-ehtimollik bahosiga kiritilmaydi.",
        "O'xshashlik alohida modulda hisoblanadi: hujjat ichidagi takrorlar (6 so'zli shingllar), foydalanuvchining oldingi hujjatlari bilan "
        "moslik (faqat xeshlangan barmoq izlari), takrorlanuvchi iboralar va parafraz ko'rsatkichlari (TF-IDF belgi n-grammalari).",
        "Tashqi provayderlar (AI detektor API, o'xshashlik API, LLM tahlil) faqat sozlangan bo'lsa va CHUQUR tahlilda ishlatiladi; ularning natijalari "
        "lokal baho bilan yonma-yon ko'rsatiladi va birlashtirilmaydi.",
    ],
    "en": [
        "Text is extracted (DOCX, PDF, TXT; OCR for scanned PDFs), the language is detected automatically, and the academic structure "
        "(chapters, sections, introduction, conclusion, references) is detected. Analysis is performed section by section on 120–380 word passages.",
        "AI-likelihood is estimated with a local stylometric method combining: sentence-length variability (burstiness), formulaic phrase density, "
        "share of sentences opening with transitions, repeated sentence openings and syntactic templates, density of concrete details, lexical uniformity, "
        "nominalisation, vague intensifiers, paragraph uniformity and sudden style shifts within the document. Each signal is normalised against a "
        "language-specific profile (Uzbek, Russian, English separately) and combined as a weighted average. No single signal is decisive.",
        "References, table of contents, keywords and appendices are excluded from AI-likelihood scoring.",
        "Similarity is computed by a separate module: internal repetition (6-word shingles), overlap with the user's earlier documents (hashed "
        "fingerprints only), repeated phrases, and paraphrase indicators (TF-IDF character n-grams).",
        "External providers (AI detector API, similarity API, LLM review) are used only when configured and only in DEEP analysis; their results are "
        "shown side by side with the local estimate and are not merged into it.",
    ],
}

LIMITATIONS = {
    "uz": [
        "AI-ehtimollik — ehtimoliy baho. U muallif AI'dan foydalanganini isbotlamaydi va yagona asos sifatida qaror qabul qilishda ishlatilmasligi kerak.",
        "Qat'iy, qolipga solingan rasmiy akademik uslub (ayniqsa o'zbek va rus tillarida) AI-ga xos signallarni oshirishi mumkin; aksincha, tahrirlangan AI matni past baho olishi mumkin.",
        "O'zbek tili uchun tasdiqlangan korpus mavjud emas, shuning uchun o'zbekcha matnlarda ishonchlilik 'O'rta'dan oshmaydi.",
        "Tashqi provayder ulanmagan bo'lsa, internet yoki ma'lumotlar bazalari bo'yicha plagiat tekshiruvi o'tkazilmaydi.",
        "Tahlil ilmiy natijalarning to'g'riligi yoki ilmiy qiymatini baholamaydi.",
        "Sahifa raqamlari DOCX/TXT fayllarda ba'zan taxminiy bo'lishi mumkin; OCR natijalarida xatolar bo'lishi mumkin.",
    ],
    "en": [
        "AI-likelihood is a probabilistic estimate. It does not prove that the author used AI and must not be the sole basis for any decision.",
        "Rigid, formulaic formal academic style (especially in Uzbek and Russian) can raise AI-like signals; conversely, edited AI text may score low.",
        "No validated Uzbek corpus exists, so confidence for Uzbek text never exceeds 'Medium'.",
        "Without a connected external provider, no internet-wide or database plagiarism check is performed.",
        "The analysis does not assess the correctness or scientific value of the research.",
        "Page numbers for DOCX/TXT may be estimated; OCR output may contain errors.",
    ],
}


def build_report_data(a: Analysis, lang: str = "uz", max_passages: int = 60, max_matches: int = 30) -> dict:
    lang = lang if lang in LABELS else "uz"
    detail = analysis_detail(a, lang)
    sections = {s.order: s for s in a.sections}
    passages = sorted(a.passages, key=lambda p: -p.ai_likelihood)[:max_passages]
    matches = sorted(a.similarity_matches, key=lambda m: -m.similarity)[:max_matches]
    v = a.version
    return {
        "lang": lang,
        "L": LABELS[lang],
        "detail": detail,
        "doc": {
            "file": a.document.original_filename, "file_type": a.document.file_type.upper(),
            "doc_type": DOC_TYPE_LABELS[lang].get(a.document.doc_type, a.document.doc_type),
            "size_kb": round(a.document.size_bytes / 1024, 1),
            "language": LANG_NAMES[lang].get(v.language if v else "unknown", v.language if v else "—"),
            "words": v.word_count if v else 0, "chars": v.char_count if v else 0,
            "pages": v.page_count if v else 0, "pages_estimated": v.pages_estimated if v else False,
            "ocr": v.ocr_used if v else False,
        },
        "depth": t(f"depth.{a.depth}", lang),
        "analysis_date": (a.finished_at or a.created_at),
        "report_date": datetime.now(UTC),
        "sections": [section_out(s, lang) for s in a.sections if s.kind != "front_matter" or s.word_count > 0],
        "passages": [passage_out(p, sections, lang) for p in sorted(passages, key=lambda p: p.paragraph_index)],
        "matches": [match_out(m, sections, lang) for m in matches],
        "methodology": METHODOLOGY[lang],
        "limitations": LIMITATIONS[lang],
        "disclaimer": DISCLAIMER[lang],
    }


def fmt_pct(v) -> str:
    return "—" if v is None else f"{v:.1f}%"


def fmt_dt(d) -> str:
    return d.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC") if d else "—"
