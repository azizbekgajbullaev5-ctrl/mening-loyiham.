"""Claude API orqali OAK talablariga mos ilmiy maqola / tezis generatsiyasi."""
from __future__ import annotations

import copy
import json
import logging
import re
from dataclasses import dataclass

from anthropic import AsyncAnthropic

import config
import sources

logger = logging.getLogger(__name__)

_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

_CIT_RE = re.compile(r"\[(\d[\d\s,;]*)\]")

# Maqola/tezis tana qismi qaysi tilda yoziladi
BODY_LANGUAGE = {
    "uz": "o'zbek tilida (lotin yozuvida)",
    "ru": "на русском языке",
    "en": "in academic English",
}

# --- Premium (jadval + diagramma) sxema qismlari ---
_TABLE_SCHEMA = {
    "type": "array",
    "description": "Natijalarni ko'rsatadigan jadvallar (asosiy tilda).",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Jadval sarlavhasi"},
            "headers": {"type": "array", "items": {"type": "string"}},
            "rows": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
            },
            "source": {"type": "string", "description": "Manba (yoki bo'sh)"},
        },
        "required": ["title", "headers", "rows", "source"],
        "additionalProperties": False,
    },
}

_CHART_SCHEMA = {
    "type": "array",
    "description": "Diagrammalar (bar/pie/line) — asosiy tilda.",
    "items": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["bar", "pie", "line"]},
            "title": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
            "values": {"type": "array", "items": {"type": "number"}},
            "x_label": {"type": "string"},
            "y_label": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["type", "title", "labels", "values", "x_label", "y_label", "source"],
        "additionalProperties": False,
    },
}

_TRILANG = {
    "type": "object",
    "properties": {
        "uz": {"type": "string"},
        "ru": {"type": "string"},
        "en": {"type": "string"},
    },
    "required": ["uz", "ru", "en"],
    "additionalProperties": False,
}

_TRILANG_LIST = {
    "type": "object",
    "properties": {
        "uz": {"type": "array", "items": {"type": "string"}},
        "ru": {"type": "array", "items": {"type": "string"}},
        "en": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["uz", "ru", "en"],
    "additionalProperties": False,
}

# --- Maqola sxemasi (IMRAD) ---
ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "udk": {"type": "string", "description": "UDK/UO'K indeksi"},
        "title": _TRILANG,
        "annotation": _TRILANG,
        "keywords": _TRILANG_LIST,
        "introduction": {"type": "string", "description": "Kirish"},
        "methods": {"type": "string", "description": "Materiallar va metodlar"},
        "results": {"type": "string", "description": "Natijalar"},
        "discussion": {"type": "string", "description": "Muhokama"},
        "conclusion": {"type": "string", "description": "Xulosa"},
        "references": {"type": "array", "items": {"type": "string"}},
        "tables": _TABLE_SCHEMA,
        "charts": _CHART_SCHEMA,
    },
    "required": [
        "udk", "title", "annotation", "keywords",
        "introduction", "methods", "results", "discussion", "conclusion",
        "references", "tables", "charts",
    ],
    "additionalProperties": False,
}

# --- Tezis sxemasi (yaxlit matn, bir tilda) ---
THESIS_SCHEMA = {
    "type": "object",
    "properties": {
        "udk": {"type": "string", "description": "UDK/UO'K indeksi"},
        "title": {"type": "string", "description": "Sarlavha (tanlangan tilda)"},
        "annotation": {"type": "string", "description": "Annotatsiya 40–60 so'z"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "body": {"type": "string", "description": "Yaxlit matn (ichki sarlavhasiz)"},
        "references": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["udk", "title", "annotation", "keywords", "body", "references"],
    "additionalProperties": False,
}


@dataclass
class ArticleRequest:
    topic: str
    field: str
    author: str
    keywords: str
    lang: str  # tana/kontent tili: "uz" | "ru" | "en"
    pages: int = 5
    work_type: str = config.WORK_ARTICLE  # "article" | "thesis"
    extra: str = ""  # qo'shimcha istaklar


# Bir A4 bet taxminan shuncha so'z (TNR 14, interval 1,5)
WORDS_PER_PAGE = 270


def _note(value: str, default: str) -> str:
    v = (value or "").strip()
    return v if v and v not in {"—", "-"} else default


def _common_head(req: ArticleRequest, body_lang: str) -> str:
    author_note = _note(req.author, "Muallif ko'rsatilmagan.")
    kw_note = (
        f"Foydalanuvchi taklif qilgan kalit so'zlar: {req.keywords}."
        if _note(req.keywords, "") else "Kalit so'zlarni mavzuga qarab tanlang."
    )
    extra_note = _note(req.extra, "")
    extra_line = f"\nQO'SHIMCHA ISTAKLAR: {extra_note}\n" if extra_note else ""
    return (
        f"MAVZU: {req.topic}\n"
        f"ILMIY SOHA: {req.field}\n"
        f"MUALLIF: {author_note}\n"
        f"{kw_note}\n"
        f"{extra_line}"
        f"Asosiy matn {body_lang} yozilsin.\n"
    )


def _queries(req: ArticleRequest) -> list[str]:
    qs = [req.topic.strip()]
    if req.field and req.field.strip() not in {"—", "-"}:
        qs.append(f"{req.topic} {req.field}".strip())
    kw = (req.keywords or "").strip()
    if kw and kw not in {"—", "-"}:
        qs.append(kw.replace(",", " "))
    return [q for q in qs if q][:3]


def _cite_block(evidence: str, low: int, high: int) -> str:
    if not evidence:
        return (
            "\n- Foydalanilgan adabiyotlar: real, mavzuga mos manbalar; "
            "har biri muallif, sarlavha, nashr, yil, DOI/URL bilan."
        )
    return (
        "\n\nMANBALAR RO'YXATI (faqat SHULARDAN foydalaning):\n" + evidence +
        "\n\nIQTIBOS QOIDALARI (majburiy):\n"
        "- Matnda faqat yuqoridagi ro'yxatdagi manbalarga [raqam] shaklida havola "
        "bering (masalan [1], [3; 7]). Ro'yxatda YO'Q raqamga havola bermang.\n"
        "- O'ylab topilgan manba, muallif, DOI yoki statistika QAT'IYAN taqiqlanadi. "
        "Har bir da'vo va raqam mos manba bilan asoslansin.\n"
        f"- Iloji boricha ko'proq, taxminan {low}–{high} xil manbadan foydalaning.\n"
        "- Jadval/diagrammadagi raqamlar ham shu manbalardan olinsin va 'source' "
        "maydonida manba ko'rsatilsin.\n"
        "- 'references' maydonini bo'sh massiv [] qoldiring — u avtomatik tuziladi."
    )


def _article_prompt(req: ArticleRequest, evidence: str = "") -> str:
    body_lang = BODY_LANGUAGE.get(req.lang, BODY_LANGUAGE["uz"])
    target_words = max(1, req.pages) * WORDS_PER_PAGE
    return (
        "Siz O'zbekiston OAK (VAK) talablariga to'liq mos ilmiy maqola yozadigan "
        "tajribali ilmiy muharrirsiz. Maqola IMRAD tuzilmasida bo'lsin.\n\n"
        f"{_common_head(req, body_lang)}"
        f"HAJM: taxminan {req.pages} A4 bet, ya'ni asosiy matn jami ~{target_words} "
        "so'z. Bo'limlarni shu hajmga mutanosib taqsimlang.\n\n"
        "TALABLAR:\n"
        "- UDK indeksini to'g'ri tanlang.\n"
        "- Sarlavha, annotatsiya va kalit so'zlar UCHTA tilda (uz, ru, en). "
        "Annotatsiya har birida 150–250 so'z, kalit so'zlar 5–8 ta.\n"
        "- Kirish: mavzuning dolzarbligi (umumiy fikr bilan boshlanadi), muammo, "
        "adabiyotlar tahlili, maqsad va vazifalar.\n"
        "- Materiallar va metodlar: tadqiqot obyekti, manbalar, metodlar.\n"
        "- Natijalar: aniq natijalar; kamida 1–2 jadval va 1 diagramma "
        "('tables' va 'charts' da), har biri matnda tilga olinsin.\n"
        "- Muhokama: natijalar boshqa tadqiqotlar bilan qiyoslanadi.\n"
        "- Xulosa: aniq xulosa va amaliy takliflar.\n"
        "- Ilmiy-akademik uslub, sun'iy intellekt izlarisiz, shablon iboralarsiz, "
        "markdown belgilarisiz. Yaxlit abzaslar.\n"
        "- Jadval/diagrammadagi barcha matn asosiy tilda bo'lsin."
        + _cite_block(evidence, 15, 25)
    )


def _thesis_prompt(req: ArticleRequest, evidence: str = "") -> str:
    body_lang = BODY_LANGUAGE.get(req.lang, BODY_LANGUAGE["uz"])
    target_words = max(1, req.pages) * WORDS_PER_PAGE
    return (
        "Siz ilmiy konferensiya to'plami uchun tezis yozadigan tajribali ilmiy "
        "muharrirsiz. Tezis — qisqa ilmiy matn, ICHKI SARLAVHALARSIZ (Kirish, "
        "Natijalar kabi sarlavhalar qo'yilmaydi), yaxlit abzaslardan iborat.\n\n"
        f"{_common_head(req, body_lang)}"
        f"HAJM: taxminan {req.pages} A4 bet, ya'ni ~{target_words} so'z.\n\n"
        "MATN MANTIQIY TARTIBI (sarlavhasiz): 1) mavzuning dolzarbligi (umumiy "
        "fikr bilan boshlanadi); 2) muammo va maqsad; 3) metodlar (1–2 jumla); "
        "4) asosiy natijalar/ilmiy g'oyalar (eng katta qism); 5) xulosa va taklif.\n\n"
        "TALABLAR:\n"
        "- UDK indeksini to'g'ri tanlang.\n"
        "- Sarlavha, annotatsiya va kalit so'zlar FAQAT tanlangan tilda.\n"
        "- Annotatsiya 40–60 so'z, kalit so'zlar 4–6 ta.\n"
        "- Ilmiy-akademik uslub, sun'iy intellekt izlarisiz, markdown belgilarisiz.\n"
        "- 'body' — yaxlit matn, ichki sarlavhalarsiz."
        + _cite_block(evidence, 6, 10)
    )


def normalize_uz(text: str) -> str:
    """O'zbek lotin imlosi: o' -> oʻ, g' -> gʻ, qolgan ' -> ʼ (tutuq belgisi)."""
    if not text:
        return text
    for a, b in (("o'", "oʻ"), ("O'", "Oʻ"), ("g'", "gʻ"), ("G'", "Gʻ")):
        text = text.replace(a, b)
    return text.replace("'", "ʼ").replace("’", "ʼ")


def _normalize_tree(obj):
    if isinstance(obj, str):
        return normalize_uz(obj)
    if isinstance(obj, list):
        return [_normalize_tree(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _normalize_tree(v) for k, v in obj.items()}
    return obj


def _apply_citations(article: dict, srcs: list, is_thesis: bool) -> None:
    """Matndagi [n] iqtiboslarni real manbalar bo'yicha qayta raqamlab,
    'references' ro'yxatini haqiqiy manbalardan tuzadi (kod darajasida tekshiruv)."""
    n = len(srcs)
    assign: dict[int, int] = {}
    order: list[int] = []

    def repl(m: re.Match) -> str:
        nums = [int(x) for x in re.split(r"[;,]", m.group(1)) if x.strip().isdigit()]
        new = []
        for old in nums:
            if 1 <= old <= n:
                if old not in assign:
                    order.append(old)
                    assign[old] = len(order)
                new.append(assign[old])
        if not new:
            return ""
        return "[" + "; ".join(str(x) for x in sorted(set(new))) + "]"

    fields = ["body"] if is_thesis else [
        "introduction", "methods", "results", "discussion", "conclusion"
    ]
    for f in fields:
        if article.get(f):
            txt = _CIT_RE.sub(repl, article[f])
            txt = re.sub(r"\s+([.,;:])", r"\1", txt)  # bo'sh iqtibos izlari
            txt = re.sub(r"[ \t]{2,}", " ", txt)
            article[f] = txt

    if order:
        article["references"] = [srcs[old - 1].gost() for old in order]
    else:
        # Model iqtibos bermagan bo'lsa ham — ro'yxat real manbalardan bo'lsin
        limit = 10 if is_thesis else 15
        article["references"] = [s.gost() for s in srcs[:limit]]


async def generate_article(req: ArticleRequest) -> dict:
    """Maqola yoki tezisni real manbalar asosida generatsiya qiladi."""
    is_thesis = req.work_type == config.WORK_THESIS

    # 1) Real manbalarni topish (best-effort — tarmoq ishlamasa, modelга tayanamiz)
    want = 12 if is_thesis else 24
    srcs: list = []
    try:
        srcs = await sources.find_sources(req.topic, req.field, _queries(req), want=want)
        logger.info("Topilgan manbalar: %d (%s)", len(srcs), req.topic[:40])
    except Exception:  # noqa: BLE001
        logger.warning("Manba qidirishда xatolik", exc_info=True)
    evidence = sources.build_evidence(srcs) if srcs else ""

    # 2) Generatsiya
    prompt = (_thesis_prompt(req, evidence) if is_thesis
              else _article_prompt(req, evidence))
    schema = THESIS_SCHEMA if is_thesis else ARTICLE_SCHEMA
    max_tokens = min(48000, 6000 + max(1, req.pages) * WORDS_PER_PAGE * 4)

    async with _client.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": schema},
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = await stream.get_final_message()

    text = next((b.text for b in message.content if b.type == "text"), "")
    article = json.loads(text)
    article["work_type"] = req.work_type

    # 3) Iqtiboslarni real manbalarga bog'lash
    if srcs:
        _apply_citations(article, srcs, is_thesis)

    if req.lang == "uz":
        article = _normalize_tree(article)
    return article
