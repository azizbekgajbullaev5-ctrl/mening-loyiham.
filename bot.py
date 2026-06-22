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
from aiohttp import web

import config
import payments
import store
from article_generator import ArticleRequest, generate_article
from docx_builder import build_docx
from pdf_builder import build_pdf
from fulfillment import deliver_order
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
    pages = State()
    kind = State()
    method = State()
    payment = State()


def fmt_sum(value: int) -> str:
    """1000000 -> '1 000 000' ko'rinishida formatlash."""
    return f"{value:,}".replace(",", " ")


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
    await message.answer(
        t(
            lang,
            "help",
            price=fmt_sum(config.PRICE_PER_PAGE),
            price_premium=fmt_sum(config.PRICE_PER_PAGE_PREMIUM),
        )
    )


@dp.message(Command("id"))
async def cmd_id(message: Message) -> None:
    """Foydalanuvchining Telegram ID sini ko'rsatadi (admin sozlash uchun)."""
    lang = get_lang(message.from_user.id)
    await message.answer(t(lang, "your_id", id=message.from_user.id))


@dp.message(Command("status"))
async def cmd_status(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    orders = await store.orders_by_user(message.from_user.id, limit=5)
    if not orders:
        await message.answer(t(lang, "status_empty"))
        return
    lines = [t(lang, "status_header")]
    for o in orders:
        lines.append(
            t(
                lang,
                "status_line",
                topic=html.escape((o["topic"] or "")[:40]),
                pages=o["pages"],
                total=fmt_sum(o["amount"]),
                status=t(lang, f"st_{o['status']}"),
            )
        )
    await message.answer("\n\n".join(lines))


@dp.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    lang = get_lang(message.from_user.id)
    if not config.ADMIN_CHAT_ID or message.from_user.id != config.ADMIN_CHAT_ID:
        await message.answer(t(lang, "stats_denied"))
        return
    s = await store.stats()
    await message.answer(
        t(
            lang,
            "stats_body",
            total=s["total_orders"],
            paid=s["paid"],
            delivered=s["delivered"],
            revenue=fmt_sum(s["revenue"]),
        )
    )


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
    await state.set_state(Form.pages)
    await message.answer(
        t(lang, "ask_pages", min=config.MIN_PAGES, max=config.MAX_PAGES)
    )


@dp.message(Form.pages)
async def step_pages(message: Message, state: FSMContext) -> None:
    lang = get_lang(message.from_user.id)
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (config.MIN_PAGES <= int(raw) <= config.MAX_PAGES):
        await message.answer(
            t(lang, "invalid_pages", min=config.MIN_PAGES, max=config.MAX_PAGES)
        )
        return

    pages = int(raw)
    await state.update_data(pages=pages)

    # Maqola turini tanlash: Oddiy yoki Premium (jadval + diagramma)
    await state.set_state(Form.kind)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_kind_standard"), callback_data="kind:standard"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_kind_premium"), callback_data="kind:premium"
                )
            ],
        ]
    )
    await message.answer(
        t(
            lang,
            "choose_kind",
            pages=pages,
            std=fmt_sum(pages * config.PRICE_PER_PAGE),
            prem=fmt_sum(pages * config.PRICE_PER_PAGE_PREMIUM),
        ),
        reply_markup=kb,
    )


@dp.callback_query(Form.kind, F.data.startswith("kind:"))
async def on_kind(callback: CallbackQuery, state: FSMContext) -> None:
    premium = callback.data.split(":", 1)[1] == "premium"
    lang = get_lang(callback.from_user.id)
    data = await state.get_data()
    pages = int(data.get("pages", 1))
    total = pages * config.price_per_page(premium)
    await state.update_data(premium=premium, total=total)
    await callback.answer()
    if callback.message:
        await _offer_payment(callback.message, state, lang, callback.from_user.id)


async def _offer_payment(
    target: Message, state: FSMContext, lang: str, user_id: int
) -> None:
    """To'lov usulini taklif qiladi (yoki bitta usul bo'lsa to'g'ridan boshlaydi)."""
    data = await state.get_data()
    pages = int(data.get("pages", 1))
    total = int(data.get("total", pages * config.PRICE_PER_PAGE))

    methods = []
    if config.method_payme_enabled():
        methods.append("payme")
    if config.method_click_enabled():
        methods.append("click")
    if config.method_card_enabled():
        methods.append("card")

    # Bitta usul bo'lsa — to'g'ridan-to'g'ri shu usulni boshlaymiz
    if len(methods) == 1:
        await _start_method(target, state, lang, methods[0], user_id)
        return

    btn_key = {"payme": "btn_payme", "click": "btn_click", "card": "btn_card"}
    keyboard = [
        [InlineKeyboardButton(text=t(lang, btn_key[m]), callback_data=f"pay:{m}")]
        for m in methods
    ]
    await state.set_state(Form.method)
    await target.answer(
        t(lang, "choose_method", pages=pages, total=fmt_sum(total)),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@dp.callback_query(Form.method, F.data.startswith("pay:"))
async def on_method(callback: CallbackQuery, state: FSMContext) -> None:
    method = callback.data.split(":", 1)[1]
    lang = get_lang(callback.from_user.id)
    await callback.answer()
    if callback.message:
        await _start_method(callback.message, state, lang, method, callback.from_user.id)


async def _start_method(
    target: Message, state: FSMContext, lang: str, method: str, user_id: int
) -> None:
    data = await state.get_data()
    pages = int(data.get("pages", 1))
    total = int(data.get("total", pages * config.PRICE_PER_PAGE))

    # Karta + chek usuli — eski oqim
    if method == "card":
        await state.set_state(Form.payment)
        await target.answer(
            t(
                lang,
                "payment_info",
                pages=pages,
                total=fmt_sum(total),
                card=config.PAYMENT_CARD_NUMBER,
                holder=config.PAYMENT_CARD_HOLDER or "—",
            )
        )
        return

    # Online to'lov (Payme / Click) — buyurtma yaratiladi, havola yuboriladi
    order_id = await store.create_order(
        {
            "user_id": user_id,
            "chat_id": target.chat.id,
            "lang": lang,
            "topic": data.get("topic", ""),
            "field": data.get("field", ""),
            "author": data.get("author", ""),
            "keywords": data.get("keywords", ""),
            "pages": pages,
            "amount": total,
            "premium": bool(data.get("premium")),
        }
    )
    if method == "payme":
        url = payments.payme_link(order_id, total)
    else:
        url = payments.click_link(order_id, total)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_pay"), url=url)]]
    )
    await target.answer(t(lang, "online_pay_msg"), reply_markup=kb)
    await state.clear()


@dp.message(Form.payment, F.photo)
async def on_receipt(message: Message, state: FSMContext) -> None:
    """To'lov cheki (rasm) kelganda buyurtmani ro'yxatga oladi.

    ADMIN_CHAT_ID sozlangan bo'lsa — chek admin (egasi) ga tasdiqlash uchun
    yuboriladi va maqola faqat admin tasdiqlagandan keyin tayyorlanadi.
    Aks holda (admin sozlanmagan) — eski avtomatik oqim ishlaydi.
    """
    lang = get_lang(message.from_user.id)
    data = await state.get_data()
    await state.clear()

    pages = int(data.get("pages", 5))
    total = int(data.get("total", pages * config.PRICE_PER_PAGE))
    order_id = await store.create_order(
        {
            "user_id": message.from_user.id,
            "chat_id": message.chat.id,
            "lang": lang,
            "topic": data.get("topic", ""),
            "field": data.get("field", ""),
            "author": data.get("author", ""),
            "keywords": data.get("keywords", ""),
            "pages": pages,
            "amount": total,
            "premium": bool(data.get("premium")),
        }
    )

    if config.ADMIN_CHAT_ID:
        user = message.from_user
        uname = f"@{user.username}" if user.username else user.full_name
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t("uz", "btn_approve"),
                        callback_data=f"approve:{order_id}",
                    ),
                    InlineKeyboardButton(
                        text=t("uz", "btn_reject"),
                        callback_data=f"reject:{order_id}",
                    ),
                ]
            ]
        )
        try:
            await message.bot.send_photo(
                config.ADMIN_CHAT_ID,
                message.photo[-1].file_id,
                caption=t(
                    "uz",
                    "receipt_forwarded",
                    user=html.escape(uname),
                    topic=html.escape(data.get("topic", "")[:120]),
                    pages=pages,
                    total=fmt_sum(total),
                ),
                reply_markup=kb,
            )
            await message.answer(t(lang, "receipt_pending"))
            return
        except Exception:  # noqa: BLE001
            logger.warning("Chekni adminga yuborib bo'lmadi", exc_info=True)
            # Admin'ga yuborilmasa — mijoz kutib qolmasligi uchun avtomatik davom

    # Admin sozlanmagan (yoki yuborib bo'lmadi) — avtomatik tayyorlanadi
    await store.set_status(order_id, store.PAID, paid=True)
    await message.answer(t(lang, "receipt_ok"))
    await deliver_order(message.bot, order_id)


@dp.callback_query(F.data.startswith("approve:"))
async def on_approve(callback: CallbackQuery) -> None:
    """Admin chekni tasdiqlaydi — maqola tayyorlanib mijozga yuboriladi."""
    if not config.ADMIN_CHAT_ID or callback.from_user.id != config.ADMIN_CHAT_ID:
        await callback.answer(t("uz", "stats_denied"), show_alert=True)
        return
    order_id = callback.data.split(":", 1)[1]
    order = await store.get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    if order["status"] != store.CREATED:
        await callback.answer(t("uz", "already_handled"), show_alert=True)
        return
    await callback.answer(t("uz", "admin_approved"))
    if callback.message:
        try:
            await callback.message.edit_caption(
                (callback.message.caption or "") + "\n\n" + t("uz", "admin_approved")
            )
        except Exception:  # noqa: BLE001
            pass
    await store.set_status(order_id, store.PAID, paid=True)
    await deliver_order(callback.bot, order_id)


@dp.callback_query(F.data.startswith("reject:"))
async def on_reject(callback: CallbackQuery) -> None:
    """Admin chekni rad etadi — mijozga xabar beriladi."""
    if not config.ADMIN_CHAT_ID or callback.from_user.id != config.ADMIN_CHAT_ID:
        await callback.answer(t("uz", "stats_denied"), show_alert=True)
        return
    order_id = callback.data.split(":", 1)[1]
    order = await store.get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    if order["status"] != store.CREATED:
        await callback.answer(t("uz", "already_handled"), show_alert=True)
        return
    await store.set_status(order_id, store.CANCELLED)
    await callback.answer(t("uz", "admin_rejected"))
    if callback.message:
        try:
            await callback.message.edit_caption(
                (callback.message.caption or "") + "\n\n" + t("uz", "admin_rejected")
            )
        except Exception:  # noqa: BLE001
            pass
    try:
        await callback.bot.send_message(
            order["chat_id"], t(order["lang"], "payment_rejected")
        )
    except Exception:  # noqa: BLE001
        pass


@dp.message(Form.payment)
async def payment_need_receipt(message: Message) -> None:
    """To'lov bosqichida rasmdan boshqa narsa kelsa — chek so'rash."""
    lang = get_lang(message.from_user.id)
    await message.answer(t(lang, "need_receipt"))


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
    store.init_db()
    bot = Bot(
        token=config.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Click/Payme webhook'lari uchun veb-server (bot bilan bir loopda)
    runner = web.AppRunner(payments.create_web_app(bot))
    await runner.setup()
    site = web.TCPSite(runner, config.WEB_HOST, config.WEB_PORT)
    await site.start()
    logger.info("Webhook server: %s:%s", config.WEB_HOST, config.WEB_PORT)

    logger.info("Bot ishga tushdi.")
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
