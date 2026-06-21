"""To'lov tasdiqlangandan keyin maqolani yaratib, mijozga yetkazish."""
from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile

import store
from article_generator import ArticleRequest, generate_article
from docx_builder import build_docx
from pdf_builder import build_pdf
from locales import t

logger = logging.getLogger(__name__)


def _safe_filename(title: str) -> str:
    keep = [c if (c.isalnum() or c in " -_") else "_" for c in title]
    name = "".join(keep).strip().replace(" ", "_")
    return name[:60] or "maqola"


def _preview(article: dict, lang: str) -> str:
    title = article.get("title", {})
    annotation = article.get("annotation", {})
    keywords = article.get("keywords", {}).get(lang) or []
    parts = []
    if article.get("udk"):
        parts.append(f"<b>UDK:</b> {html.escape(str(article['udk']))}")
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


async def deliver_order(bot: Bot, order_id: str) -> None:
    """To'langan buyurtma bo'yicha maqolani yaratib yuboradi (idempotent)."""
    # Faqat bitta chaqiruv yetkazib berishni boshlasin
    if not await store.try_begin_delivery(order_id):
        logger.info("Buyurtma %s allaqachon yetkazilmoqda/yetkazilgan", order_id)
        return

    order = await store.get_order(order_id)
    if not order:
        logger.error("Buyurtma topilmadi: %s", order_id)
        return

    lang = order["lang"]
    chat_id = order["chat_id"]

    try:
        await bot.send_message(chat_id, t(lang, "payment_confirmed"))
        status = await bot.send_message(chat_id, t(lang, "generating"))

        req = ArticleRequest(
            topic=order["topic"],
            field=order["field"],
            author=order["author"],
            keywords=order["keywords"],
            lang=lang,
            pages=int(order["pages"]),
        )
        article = await generate_article(req)
        docx_stream = build_docx(article, req.author, lang)
        pdf_stream = build_pdf(article, req.author, lang)

        await status.edit_text(t(lang, "done_text"))
        await bot.send_message(chat_id, _preview(article, lang))

        title = article.get("title", {}).get(lang) or article.get("title", {}).get(
            "uz", "maqola"
        )
        fname = _safe_filename(title)
        await bot.send_document(
            chat_id,
            BufferedInputFile(docx_stream.read(), filename=fname + ".docx"),
            caption=t(lang, "docx_caption"),
        )
        await bot.send_document(
            chat_id,
            BufferedInputFile(pdf_stream.read(), filename=fname + ".pdf"),
            caption=t(lang, "pdf_caption"),
        )
        await store.set_status(order_id, store.DELIVERED, delivered=True)
    except Exception as err:  # noqa: BLE001
        logger.exception("Buyurtma %s yetkazishda xatolik", order_id)
        # Qayta urinish mumkin bo'lishi uchun 'paid' holatga qaytaramiz
        await store.set_status(order_id, store.PAID)
        try:
            await bot.send_message(
                chat_id, t(lang, "error", err=html.escape(str(err)[:300]))
            )
        except Exception:  # noqa: BLE001
            pass
