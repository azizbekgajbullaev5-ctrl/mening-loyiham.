"""Server-side texts for explanations and reports (uz default, en available).

Analysis results store *codes*; human-readable text is produced here, so new
interface languages only need a new dictionary.
"""
from __future__ import annotations

DISCLAIMER = {
    "uz": (
        "AI aniqlash natijalari ehtimoliy ko'rsatkichlardir va AI mualliflikning qat'iy isboti sifatida "
        "talqin qilinmasligi kerak. O'xshashlik tahlili va AI-ehtimollik tahlili alohida o'lchovlardir."
    ),
    "en": (
        "AI-detection results are probabilistic indicators and should not be interpreted as definitive proof of AI "
        "authorship. Similarity analysis and AI-likelihood analysis are separate measurements."
    ),
}

ESTIMATE_NOTE = {
    "uz": "Bu analitik baho, AI mualliflikning qat'iy isboti emas.",
    "en": "This is an analytical estimate, not definitive proof of AI authorship.",
}

T: dict[str, dict[str, str]] = {
    "uz": {
        # confidence
        "conf.low": "Past", "conf.medium": "O'rta", "conf.high": "Yuqori",
        # characteristics (label)
        "char.sentence_length_cv": "Gap uzunliklari juda bir xil (past \"burstiness\")",
        "char.generic_phrase_density": "Umumiy, qolipga solingan akademik iboralar ko'p",
        "char.transition_start_ratio": "Gaplar ko'pincha bog'lovchi iboralar bilan boshlanadi",
        "char.opening_repetition": "Gap boshlanishlari takrorlanadi",
        "char.template_repetition": "Sintaktik qoliplar takrorlanadi",
        "char.specificity_density": "Aniq tafsilotlar (raqamlar, iqtiboslar, nomlar) kam",
        "char.lexical_uniformity": "Leksik xilma-xillik g'ayrioddiy darajada bir tekis",
        "char.triad_density": "\"A, B va C\" ko'rinishidagi sanashlar ko'p",
        "char.formalization_density": "Haddan tashqari rasmiylashtirilgan (nominalizatsiya ko'p)",
        "char.qualifier_density": "Noaniq kuchaytiruvchi sifatlar ko'p (samarali, muhim, innovatsion...)",
        "char.paragraph_uniformity": "Paragraf uzunliklari juda bir xil",
        "char.style_shift": "Hujjatning qolgan qismiga nisbatan uslubning keskin o'zgarishi",
        # characteristic explanation
        "exp.sentence_length_cv": "Inson yozgan akademik matnda gap uzunligi odatda ko'proq o'zgaradi; bu yerda o'zgaruvchanlik past (CV={value}).",
        "exp.generic_phrase_density": "Har 100 so'zga {value} ta qolip ibora to'g'ri keladi.",
        "exp.transition_start_ratio": "Gaplarning {pct}% i bog'lovchi ibora bilan boshlanadi.",
        "exp.opening_repetition": "Gaplarning {pct}% i bir xil so'z bilan boshlanadi.",
        "exp.template_repetition": "Funksional so'zlar qolipining {pct}% i takrorlanadi.",
        "exp.specificity_density": "Har 100 so'zga atigi {value} ta aniq tafsilot (raqam, iqtibos, nom) to'g'ri keladi.",
        "exp.lexical_uniformity": "Matn bo'ylab so'z xilma-xilligi deyarli o'zgarmaydi.",
        "exp.triad_density": "Uch elementli sanashlar har gapda o'rtacha {value} marta uchraydi.",
        "exp.formalization_density": "Har 100 so'zga {value} ta nominalizatsiya shakli.",
        "exp.qualifier_density": "Har 100 so'zga {value} ta noaniq kuchaytiruvchi so'z.",
        "exp.paragraph_uniformity": "Bo'limdagi paragraflar uzunligi deyarli bir xil.",
        "exp.style_shift": "Parcha uslubi hujjatning o'z me'yoridan sezilarli farq qiladi.",
        "exp.none": "Hech bir signal alohida kuchli emas; baho bir nechta kuchsiz signallar yig'indisidan iborat.",
        "exp.prefix": "Ushbu parchada yuqoridagi AI-ga xos xususiyatlar kuzatildi. Bu mualliflik haqida xulosa emas.",
        "exp.conf.low": "Ishonchlilik past: parcha qisqa yoki signallar bir-biriga to'liq mos kelmaydi.",
        "exp.conf.medium": "Ishonchlilik o'rta: bir nechta mustaqil signal bir yo'nalishni ko'rsatadi, ammo bu isbot emas.",
        "exp.conf.high": "Ishonchlilik yuqori: ko'plab signallar mos keladi, ammo bu ham mualliflikning isboti emas.",
        # section kinds
        "kind.title": "Sarlavha", "kind.toc": "Mundarija", "kind.abstract": "Annotatsiya", "kind.keywords": "Kalit so'zlar",
        "kind.introduction": "Kirish", "kind.literature_review": "Adabiyotlar tahlili", "kind.methodology": "Metodologiya",
        "kind.results": "Natijalar", "kind.discussion": "Muhokama", "kind.conclusion": "Xulosa",
        "kind.references": "Foydalanilgan adabiyotlar", "kind.appendix": "Ilovalar", "kind.chapter": "Bob",
        "kind.section": "Bo'lim", "kind.subsection": "Kichik bo'lim", "kind.heading": "Sarlavha", "kind.front_matter": "Boshlang'ich qism",
        # similarity scope
        "scope.local_only": "Faqat lokal/hujjat ichidagi o'xshashlik tahlili. Tashqi provayder ulanmagan — internet bo'yicha tekshiruv o'tkazilmagan.",
        "scope.local_and_external": "Lokal tahlil + tashqi o'xshashlik provayderi.",
        "scope.local_only_external_failed": "Faqat lokal tahlil: tashqi provayder xatolik qaytardi.",
        "scope.local_only_external_not_requested": "Faqat lokal tahlil: tashqi provayder faqat CHUQUR tahlilda ishlatiladi.",
        # match types
        "match.internal_duplicate": "Hujjat ichida takrorlangan matn",
        "match.cross_document": "Sizning boshqa hujjatingiz bilan moslik",
        "match.paraphrase": "Ehtimoliy parafraz (ma'no bo'yicha o'xshash)",
        "match.external": "Tashqi manba bilan moslik",
        # provider status
        "prov.used": "Ishlatildi", "prov.not_configured": "Tashqi provayder sozlanmagan", "prov.failed": "Xatolik",
        "prov.not_used_depth": "Faqat chuqur tahlilda", "prov.language_not_supported": "Til qo'llab-quvvatlanmaydi",
        "compare.single_method": "Natija lokal lingvistik tahlilga asoslangan.",
        "compare.methods_vary": "Natijalar tahlil usullari orasida farq qiladi. Hech bir alohida baho qat'iy deb hisoblanmasligi kerak.",
        "compare.methods_broadly_agree": "Usullar taxminan mos keladi, ammo bu ham qat'iy isbot emas.",
        # academic issues
        "issue.many_long_sentences": "Uzun gaplar ulushi yuqori ({share}% gap {limit} so'zdan uzun).",
        "issue.low_cohesion": "Qo'shni gaplar orasidagi leksik bog'liqlik past.",
        "issue.missing_component": "Kutilgan qism topilmadi: {kind_label}.",
        "issue.mixed_citation_style": "Raqamli va muallif-yil iqtibos uslublari aralash ishlatilgan.",
        "issue.citation_without_reference": "Ro'yxatda mavjud bo'lmagan manbaga havola: {numbers}.",
        "issue.uncited_references": "Matnda havola qilinmagan manbalar: {count} ta.",
        "issue.no_reference_list": "Foydalanilgan adabiyotlar ro'yxati topilmadi.",
        "issue.no_in_text_citations": "Matn ichida iqtiboslar topilmadi.",
        "issue.sections_without_citations": "Iqtibossiz uzun bo'limlar: {count} ta.",
        "issue.references_missing_year": "Yili ko'rsatilmagan manbalar: {count} ta.",
        "issue.duplicate_references": "Takrorlangan manbalar: {count} ta.",
        "issue.mixed_reference_formats": "Adabiyotlar ro'yxatida turli formatlar aralash (GOST-ga o'xshash: {gost}, APA-ga o'xshash: {apa}).",
        "issue.reference_numbering": "Adabiyotlar raqamlanishi ketma-ket emas.",
        "issue.heading_numbering_gap": "Sarlavhalar raqamlanishida uzilish bor.",
        "issue.heading_case_mixed": "Asosiy sarlavhalarda katta/kichik harf uslubi aralash.",
        "issue.heading_trailing_period_mixed": "Ba'zi sarlavhalar nuqta bilan tugaydi, ba'zilari yo'q.",
        "issue.mixed_apostrophes": "O'zbek tutuq belgisi turlicha yozilgan (masalan, o' / oʻ / o`).",
        "issue.term_variants": "Atamalarning turlicha yozilishi: {count} holat.",
        "issue.undefined_abbreviations": "Ta'rifi berilmagan qisqartmalar: {items}.",
        "issue.mixed_quotes": "Turli qo'shtirnoq uslublari aralash.",
        "issue.very_long_paragraphs": "Juda uzun paragraflar: {count} ta.",
        "issue.repeated_sentences": "Aynan takrorlangan gaplar: {count} ta.",
        "issue.overused_transitions": "Ayrim bog'lovchi iboralar haddan ko'p ishlatilgan: {markers}.",
        "sev.warning": "Ogohlantirish", "sev.info": "Ma'lumot",
        "depth.quick": "Tezkor", "depth.standard": "Standart", "depth.deep": "Chuqur",
    },
    "en": {
        "conf.low": "Low", "conf.medium": "Medium", "conf.high": "High",
        "char.sentence_length_cv": "Highly uniform sentence length (low burstiness)",
        "char.generic_phrase_density": "Many generic, formulaic academic phrases",
        "char.transition_start_ratio": "Sentences frequently open with transitional phrases",
        "char.opening_repetition": "Repeated sentence openings",
        "char.template_repetition": "Repeated syntactic templates",
        "char.specificity_density": "Few concrete details (numbers, citations, names)",
        "char.lexical_uniformity": "Unusually even lexical diversity",
        "char.triad_density": "Frequent 'A, B and C' enumerations",
        "char.formalization_density": "Excessive formalisation (heavy nominalisation)",
        "char.qualifier_density": "Many vague intensifiers (crucial, innovative, comprehensive...)",
        "char.paragraph_uniformity": "Very uniform paragraph lengths",
        "char.style_shift": "Sudden change of style relative to the rest of the document",
        "exp.sentence_length_cv": "Human academic prose usually varies sentence length more; variation here is low (CV={value}).",
        "exp.generic_phrase_density": "{value} formulaic phrases per 100 words.",
        "exp.transition_start_ratio": "{pct}% of sentences open with a transitional phrase.",
        "exp.opening_repetition": "{pct}% of sentences start with the same word as another sentence.",
        "exp.template_repetition": "{pct}% of function-word templates repeat.",
        "exp.specificity_density": "Only {value} concrete details (numbers, citations, names) per 100 words.",
        "exp.lexical_uniformity": "Vocabulary diversity barely varies across the passage.",
        "exp.triad_density": "Three-item enumerations appear {value} times per sentence.",
        "exp.formalization_density": "{value} nominalised forms per 100 words.",
        "exp.qualifier_density": "{value} vague intensifiers per 100 words.",
        "exp.paragraph_uniformity": "Paragraphs in this section have nearly identical lengths.",
        "exp.style_shift": "The passage's style departs markedly from the document's own norm.",
        "exp.none": "No single signal is strong; the estimate combines several weak signals.",
        "exp.prefix": "The AI-like characteristics listed above were observed. This is not a conclusion about authorship.",
        "exp.conf.low": "Low confidence: the passage is short or the signals do not fully agree.",
        "exp.conf.medium": "Medium confidence: several independent signals point the same way, but this is not proof.",
        "exp.conf.high": "High confidence: many signals agree, but this is still not proof of authorship.",
        "kind.title": "Title", "kind.toc": "Contents", "kind.abstract": "Abstract", "kind.keywords": "Keywords",
        "kind.introduction": "Introduction", "kind.literature_review": "Literature review", "kind.methodology": "Methodology",
        "kind.results": "Results", "kind.discussion": "Discussion", "kind.conclusion": "Conclusion",
        "kind.references": "References", "kind.appendix": "Appendices", "kind.chapter": "Chapter", "kind.section": "Section",
        "kind.subsection": "Subsection", "kind.heading": "Heading", "kind.front_matter": "Front matter",
        "scope.local_only": "Local/document similarity analysis only. No external provider connected — no internet-wide check was performed.",
        "scope.local_and_external": "Local analysis + external similarity provider.",
        "scope.local_only_external_failed": "Local analysis only: the external provider returned an error.",
        "scope.local_only_external_not_requested": "Local analysis only: external providers run only in DEEP analysis.",
        "match.internal_duplicate": "Text repeated within the document",
        "match.cross_document": "Overlap with another of your documents",
        "match.paraphrase": "Possible paraphrase (meaning-level similarity)",
        "match.external": "Match with an external source",
        "prov.used": "Used", "prov.not_configured": "External provider not configured", "prov.failed": "Error",
        "prov.not_used_depth": "Deep analysis only", "prov.language_not_supported": "Language not supported",
        "compare.single_method": "Result based on local linguistic analysis.",
        "compare.methods_vary": "Results vary between analysis methods. The system should not treat any individual score as definitive.",
        "compare.methods_broadly_agree": "Methods broadly agree, but this is still not definitive proof.",
        "issue.many_long_sentences": "High share of long sentences ({share}% exceed {limit} words).",
        "issue.low_cohesion": "Low lexical cohesion between adjacent sentences.",
        "issue.missing_component": "Expected part not found: {kind_label}.",
        "issue.mixed_citation_style": "Numeric and author–year citation styles are mixed.",
        "issue.citation_without_reference": "Citations to non-existent reference numbers: {numbers}.",
        "issue.uncited_references": "References never cited in the text: {count}.",
        "issue.no_reference_list": "No reference list found.",
        "issue.no_in_text_citations": "No in-text citations found.",
        "issue.sections_without_citations": "Long sections without citations: {count}.",
        "issue.references_missing_year": "References without a year: {count}.",
        "issue.duplicate_references": "Duplicate references: {count}.",
        "issue.mixed_reference_formats": "Mixed reference formats (GOST-like: {gost}, APA-like: {apa}).",
        "issue.reference_numbering": "Reference numbering is not sequential.",
        "issue.heading_numbering_gap": "Gaps in heading numbering.",
        "issue.heading_case_mixed": "Mixed capitalisation in top-level headings.",
        "issue.heading_trailing_period_mixed": "Some headings end with a period, others do not.",
        "issue.mixed_apostrophes": "Uzbek apostrophe written in several ways (o' / oʻ / o`).",
        "issue.term_variants": "Terms spelled in several ways: {count} cases.",
        "issue.undefined_abbreviations": "Abbreviations without definition: {items}.",
        "issue.mixed_quotes": "Mixed quotation mark styles.",
        "issue.very_long_paragraphs": "Very long paragraphs: {count}.",
        "issue.repeated_sentences": "Verbatim repeated sentences: {count}.",
        "issue.overused_transitions": "Some transitional phrases are overused: {markers}.",
        "sev.warning": "Warning", "sev.info": "Info",
        "depth.quick": "Quick", "depth.standard": "Standard", "depth.deep": "Deep",
    },
}


def t(key: str, lang: str = "uz", **params) -> str:
    table = T.get(lang, T["uz"])
    text = table.get(key) or T["en"].get(key) or key
    try:
        return text.format(**params)
    except (KeyError, IndexError, ValueError):
        return text


def explain_characteristics(chars: list[dict], lang: str = "uz", confidence: str | None = None) -> tuple[list[dict], str]:
    items = []
    for c in chars:
        code = c["code"]
        v = c.get("value", 0.0)
        items.append({"code": code, "label": t(f"char.{code}", lang), "detail": t(f"exp.{code}", lang, value=round(v, 2), pct=round(v * 100))})
    conf = (" " + t(f"exp.conf.{confidence}", lang)) if confidence else ""
    if not items:
        return [], t("exp.none", lang) + conf
    return items, t("exp.prefix", lang) + conf


def issue_text(issue: dict, lang: str = "uz") -> str:
    params = dict(issue.get("params", {}))
    if "kind" in params:
        params["kind_label"] = t(f"kind.{params['kind']}", lang)
    for k, v in list(params.items()):
        if isinstance(v, list):
            params[k] = ", ".join(str(x) for x in v)
    return t(f"issue.{issue['code']}", lang, **params)
