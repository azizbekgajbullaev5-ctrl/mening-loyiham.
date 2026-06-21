"""Claude API orqali OAK talablariga mos ilmiy maqola generatsiyasi."""
from __future__ import annotations

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


@dataclass
class ArticleRequest:
    topic: str
    field: str
    author: str
    keywords: str
    lang: str  # interfeys/tana tili: "uz" yoki "ru"


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
    return (
        "Siz O'zbekiston Oliy attestatsiya komissiyasi (OAK/ВАК) talablariga "
        "to'liq mos ilmiy maqola yozadigan tajribali ilmiy muharrirsiz.\n\n"
        f"MAVZU: {req.topic}\n"
        f"ILMIY SOHA: {req.field}\n"
        f"{author_note}\n"
        f"{keywords_note}\n\n"
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
    )


async def generate_article(req: ArticleRequest) -> dict:
    """Maqolani generatsiya qiladi va bo'limlar dict'ini qaytaradi."""
    prompt = _build_prompt(req)

    async with _client.messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": ARTICLE_SCHEMA},
        },
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = await stream.get_final_message()

    text = next((b.text for b in message.content if b.type == "text"), "")
    return json.loads(text)
