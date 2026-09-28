"""Claude API orqali OAK talablariga mos ilmiy maqola / tezis generatsiyasi."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from anthropic import AsyncAnthropic

import config

_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

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


def _article_prompt(req: ArticleRequest) -> str:
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
        "- Adabiyotlar: 15–25 ta manba, GOST R 7.0.5 uslubida, DOI/URL bilan.\n"
        "- Ilmiy-akademik uslub, sun'iy intellekt izlarisiz, shablon iboralarsiz, "
        "markdown belgilarisiz. Yaxlit abzaslar.\n"
        "- Jadval/diagrammadagi barcha matn asosiy tilda bo'lsin."
    )


def _thesis_prompt(req: ArticleRequest) -> str:
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
        "- Adabiyotlar: 6–10 ta real, GOST R 7.0.5 uslubida, DOI/URL bilan.\n"
        "- Ilmiy-akademik uslub, sun'iy intellekt izlarisiz, markdown belgilarisiz.\n"
        "- 'body' — yaxlit matn, ichki sarlavhalarsiz."
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


async def generate_article(req: ArticleRequest) -> dict:
    """Maqola yoki tezisni generatsiya qiladi va bo'limlar dict'ini qaytaradi."""
    is_thesis = req.work_type == config.WORK_THESIS
    prompt = _thesis_prompt(req) if is_thesis else _article_prompt(req)
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
    if req.lang == "uz":
        article = _normalize_tree(article)
    return article
