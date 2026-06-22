"""Claude API orqali OAK talablariga mos ilmiy maqola generatsiyasi."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from anthropic import AsyncAnthropic

import config

_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

# Maqola tana qismi qaysi tilda yoziladi (interfeys tiliga bog'liq)
BODY_LANGUAGE = {
    "uz": "o'zbek tilida (kirill yoki lotin — mavzuga mos)",
    "ru": "на русском языке",
}

# Maqola bo'limlari uchun JSON sxema — structured outputs valid JSON kafolatlaydi.
ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "udk": {"type": "string", "description": "UDK indeksi, masalan '330.34'"},
        "title": {
            "type": "object",
            "properties": {
                "uz": {"type": "string"},
                "ru": {"type": "string"},
                "en": {"type": "string"},
            },
            "required": ["uz", "ru", "en"],
            "additionalProperties": False,
        },
        "annotation": {
            "type": "object",
            "properties": {
                "uz": {"type": "string"},
                "ru": {"type": "string"},
                "en": {"type": "string"},
            },
            "required": ["uz", "ru", "en"],
            "additionalProperties": False,
        },
        "keywords": {
            "type": "object",
            "properties": {
                "uz": {"type": "array", "items": {"type": "string"}},
                "ru": {"type": "array", "items": {"type": "string"}},
                "en": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["uz", "ru", "en"],
            "additionalProperties": False,
        },
        "introduction": {"type": "string", "description": "Kirish — to'liq paragraflar"},
        "main_part": {
            "type": "string",
            "description": "Asosiy qism: tahlil, usullar, muhokama. Bir necha paragraf.",
        },
        "results": {
            "type": "string",
            "description": "Natijalar va ularning tahlili.",
        },
        "conclusion": {"type": "string", "description": "Xulosa va takliflar."},
        "references": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Foydalanilgan adabiyotlar ro'yxati, GOST uslubida.",
        },
    },
    "required": [
        "udk",
        "title",
        "annotation",
        "keywords",
        "introduction",
        "main_part",
        "results",
        "conclusion",
        "references",
    ],
    "additionalProperties": False,
}

# --- Premium (jadval + diagramma) qo'shimcha sxemasi ---
# Jadval va diagrammalar maqolaning asosiy tilida (bitta til) bo'ladi.
_TABLE_SCHEMA = {
    "type": "array",
    "description": "Maqola natijalarini ko'rsatadigan jadvallar (asosiy tilda).",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Jadval sarlavhasi"},
            "headers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ustun nomlari",
            },
            "rows": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
                "description": "Qatorlar; har biri ustunlar soniga teng",
            },
        },
        "required": ["title", "headers", "rows"],
        "additionalProperties": False,
    },
}

_CHART_SCHEMA = {
    "type": "array",
    "description": "Diagrammalar (ustunli/doira/chiziqli) — asosiy tilda.",
    "items": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["bar", "pie", "line"]},
            "title": {"type": "string", "description": "Diagramma sarlavhasi"},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Kategoriya nomlari",
            },
            "values": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Son qiymatlar; labels bilan teng uzunlikda",
            },
            "x_label": {"type": "string", "description": "X o'qi nomi (bar/line)"},
            "y_label": {"type": "string", "description": "Y o'qi nomi (bar/line)"},
        },
        "required": ["type", "title", "labels", "values", "x_label", "y_label"],
        "additionalProperties": False,
    },
}


def _premium_schema() -> dict:
    schema = copy.deepcopy(ARTICLE_SCHEMA)
    schema["properties"]["tables"] = _TABLE_SCHEMA
    schema["properties"]["charts"] = _CHART_SCHEMA
    schema["required"] = schema["required"] + ["tables", "charts"]
    return schema


@dataclass
class ArticleRequest:
    topic: str
    field: str
    author: str
    keywords: str
    lang: str  # interfeys/tana tili: "uz" yoki "ru"
    pages: int = 5  # maqola hajmi (bet soni)
    premium: bool = False  # jadval + diagrammali (premium) variant


# Bir A4 bet taxminan shuncha so'z (Times New Roman 14pt) — hajmni shunga moslaymiz
WORDS_PER_PAGE = 450


def _build_prompt(req: ArticleRequest) -> str:
    body_lang = BODY_LANGUAGE.get(req.lang, BODY_LANGUAGE["uz"])
    keywords_note = (
        f"Foydalanuvchi taklif qilgan kalit so'zlar: {req.keywords}."
        if req.keywords and req.keywords.strip() not in {"—", "-"}
        else "Kalit so'zlarni mavzuga qarab o'zingiz tanlang."
    )
    author_note = (
        f"Muallif: {req.author}."
        if req.author and req.author.strip() not in {"—", "-"}
        else "Muallif ko'rsatilmagan."
    )
    target_words = max(1, req.pages) * WORDS_PER_PAGE
    premium_note = ""
    if req.premium:
        premium_note = (
            "\n\nPREMIUM TALABLARI (jadval + diagramma):\n"
            "- 'tables': 1–2 ta mazmunli jadval bering (natijalarni aks ettiruvchi). "
            "Har bir jadvalda sarlavha, ustun nomlari (headers) va qatorlar (rows) "
            "bo'lsin; har bir qatorda ustunlar soniga teng katak bo'lsin.\n"
            "- 'charts': 1–2 ta diagramma bering (type: 'bar', 'pie' yoki 'line'). "
            "labels va values teng uzunlikda, values — faqat sonlar. bar/line uchun "
            "x_label va y_label ni to'ldiring (pie uchun bo'sh qatordan foydalaning).\n"
            "- Jadval va diagrammalardagi BARCHA matn (sarlavha, ustun nomlari, "
            f"belgilar, o'q nomlari) FAQAT {body_lang} bo'lsin (bitta tilda).\n"
            "- Jadval/diagramma ma'lumotlari maqola matni (ayniqsa Natijalar) bilan "
            "mos va mantiqan asoslangan bo'lsin."
        )
    return (
        "Siz O'zbekiston Oliy attestatsiya komissiyasi (OAK/ВАК) talablariga "
        "to'liq mos ilmiy maqola yozadigan tajribali ilmiy muharrirsiz.\n\n"
        f"MAVZU: {req.topic}\n"
        f"ILMIY SOHA: {req.field}\n"
        f"{author_note}\n"
        f"{keywords_note}\n"
        f"HAJM: maqola taxminan {req.pages} ta A4 bet bo'lsin, ya'ni asosiy matn "
        f"(kirish + asosiy qism + natijalar + xulosa) jami taxminan {target_words} "
        "so'zdan iborat bo'lsin. Bo'limlarni shu hajmga mutanosib taqsimlang.\n\n"
        f"Maqolaning asosiy matnini {body_lang} yozing. "
        "Annotatsiya va kalit so'zlarni esa UCHTA tilda bering: "
        "o'zbek (uz), rus (ru) va ingliz (en).\n\n"
        "TALABLAR:\n"
        "- UDK indeksini mavzuga mos to'g'ri tanlang.\n"
        "- Annotatsiya har bir tilda 4–6 jumladan iborat bo'lsin.\n"
        "- Har bir tilda 6–10 ta kalit so'z bering.\n"
        "- Kirish: muammoning dolzarbligi, maqsad va vazifalar.\n"
        "- Asosiy qism: ilmiy tahlil, usullar, mavjud yondashuvlar muhokamasi "
        "(bir necha to'liq paragraf, akademik uslub).\n"
        "- Natijalar: aniq, asoslangan natijalar va ularning tahlili.\n"
        "- Xulosa: asosiy xulosalar va amaliy takliflar.\n"
        "- Foydalanilgan adabiyotlar: 8–15 ta manba, GOST bibliografik uslubida, "
        "ishonchli va mavzuga mos (mualliflar, sarlavha, nashr, yil, sahifa).\n"
        "- Matn ilmiy, ravon va plagiatsiz, mantiqiy izchil bo'lsin.\n"
        "- Paragraflar orasida bo'sh qatordan foydalaning."
        f"{premium_note}"
    )


async def generate_article(req: ArticleRequest) -> dict:
    """Maqolani generatsiya qiladi va bo'limlar dict'ini qaytaradi."""
    prompt = _build_prompt(req)
    schema = _premium_schema() if req.premium else ARTICLE_SCHEMA

    # Hajmga qarab max_tokens ni moslaymiz (kirill matn so'ziga ~2.5 token).
    max_tokens = min(48000, 6000 + max(1, req.pages) * WORDS_PER_PAGE * 3)

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
    return json.loads(text)
