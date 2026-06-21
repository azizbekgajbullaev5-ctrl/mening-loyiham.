"""OAK talablari asosida ilmiy maqola yozadigan Telegram bot."""
from __future__ import annotations

import asyncio
import html
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import config
from article_generator import ArticleRequest, generate_article
from docx_builder import build_docx
from locales import LANGUAGES, t

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Foydalanuvchi tilini saqlash (oddiy xotira; konteyner qayta ishga tushsa tiklanadi)
_user_lang: dict[int, str] = {}


def get_lang(user_id: int) -> str:
    return _user_lang.get(user_id, "uz")


class Form(StatesGroup):
    topic = State()
    field = State()
    author = State()
    keywords = State()


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"lang:{code}")]
            for code, label in LANGUAGES.items()
        ]
    )


dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("uz", "choose_language"), reply_markup=language_keyboard())


@dp.message(Command("lang"))
async def cmd_lang(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("uz", "choose_language"), reply_markup=language_keyboard())


@dp.callback_query(F.data.startswith("lang:"))
async def on_language(callback: CallbackQuery, state: FSMContext) -> None:
    lang = callback.data.split(":", 1)[1]
    _user_lang[callback.from_user.id] = lang
    await callback.answer()
    if callback.message:
        await callback.message.answer(t(lang, "lang_set"))
        await callback.message.answer(t(lang, "welcome"))


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    await message.answer(t(lang, "help"))


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    await state.clear()
    await message.answer(t(lang, "cancelled"))


@dp.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    await state.clear()
    await state.set_state(Form.topic)
    await message.answer(t(lang, "ask_topic"))


@dp.message(Form.topic)
async def step_topic(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    await state.update_data(topic=message.text or "")
    await state.set_state(Form.field)
    await message.answer(t(lang, "ask_field"))


@dp.message(Form.field)
async def step_field(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    await state.update_data(field=message.text or "")
    await state.set_state(Form.author)
    await message.answer(t(lang, "ask_author"))


@dp.message(Form.author)
async def step_author(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    await state.update_data(author=message.text or "")
    await state.set_state(Form.keywords)
    await message.answer(t(lang, "ask_keywords"))


@dp.message(Form.keywords)
async def step_keywords(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    await state.update_data(keywords=message.text or "")
    data = await state.get_data()
    await state.clear()

    status = await message.answer(t(lang, "generating"))

    req = ArticleRequest(
        topic=data.get("topic", ""),
        field=data.get("field", ""),
        author=data.get("author", ""),
        keywords=data.get("keywords", ""),
        lang=lang,
    )

    try:
        article = await generate_article(req)
        docx_stream = build_docx(article, req.author, lang)
    except Exception as err:  # noqa: BLE001
        logger.exception("Maqola generatsiyasida xatolik")
        await status.edit_text(t(lang, "error", err=html.escape(str(err)[:300])))
        return

    await status.edit_text(t(lang, "done_text"))
    await message.answer(_preview(article, lang))

    title = article.get("title", {}).get(lang) or article.get("title", {}).get("uz", "maqola")
    filename = _safe_filename(title) + ".docx"
    await message.answer_document(
        BufferedInputFile(docx_stream.read(), filename=filename),
        caption=t(lang, "docx_caption"),
    )


def _preview(article: dict, lang: str) -> str:
    """Telegram uchun qisqa HTML ko'rinish (4096 belgidan kam)."""
    title = article.get("title", {})
    annotation = article.get("annotation", {})
    keywords = article.get("keywords", {}).get(lang) or []

    parts = []
    udk = article.get("udk")
    if udk:
        parts.append(f"<b>UDK:</b> {html.escape(str(udk))}")
    head = title.get(lang) or title.get("uz", "")
    if head:
        parts.append(f"<b>{html.escape(head)}</b>")
    ann = annotation.get(lang) or annotation.get("uz", "")
    if ann:
        parts.append(html.escape(ann[:600]))
    if keywords:
        parts.append("<i>" + html.escape(", ".join(keywords)) + "</i>")

    text = "\n\n".join(parts)
    return text[:4000] if text else "—"


def _safe_filename(title: str) -> str:
    keep = [c if (c.isalnum() or c in " -_") else "_" for c in title]
    name = "".join(keep).strip().replace(" ", "_")
    return (name[:60] or "maqola")


async def main() -> None:
    bot = Bot(
        token=config.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    logger.info("Bot ishga tushdi.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
