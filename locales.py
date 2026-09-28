"""Bot interfeysi matnlari — hammasi o'zbek (lotin) tilida.

Interfeys doim o'zbek lotin tilida. Mijoz tanlaydigan til faqat tayyorlanadigan
maqola/tezis MATNIGA taalluqli (buyurtmaning oxirida so'raladi).
"""

# Maqola/tezis qaysi tillarda yozilishi mumkin (til kodi -> ko'rinadigan nom)
LANGUAGES = {
    "uz": "🇺🇿 O'zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
}

TEXTS = {
    "uz": {
        "welcome": (
            "👋 Assalomu alaykum!\n\n"
            "Men <b>OAK talablari asosida ilmiy maqola va tezis</b> yozib "
            "beradigan botman.\n\n"
            "Ish quyidagi tuzilishda tayyorlanadi:\n"
            "• UDK, sarlavha, annotatsiya va kalit so'zlar\n"
            "• Kirish · Materiallar va metodlar · Natijalar · Muhokama · Xulosa\n"
            "• Foydalanilgan adabiyotlar ro'yxati\n\n"
            "Boshlash uchun /new buyrug'ini yuboring."
        ),
        # --- Buyurtma dialogi ---
        "choose_worktype": "🧩 <b>Ish turini tanlang:</b>",
        "btn_article": "📄 Maqola",
        "btn_thesis": "📝 Tezis",
        "ask_topic": (
            "📌 <b>Mavzuni</b> kiriting.\n\n"
            "Masalan: <i>«Raqamli iqtisodiyot sharoitida kichik biznesni "
            "rivojlantirish»</i>"
        ),
        "ask_field": (
            "🔬 <b>Ilmiy sohani tanlang</b> (yoki «Boshqa»ni bosib o'zingiz yozing):"
        ),
        "btn_field_other": "✍️ Boshqa",
        "ask_field_other": "🔬 Ilmiy sohani (yo'nalishni) yozing:",
        "ask_author_full": (
            "✍️ <b>Muallif ma'lumotlari:</b>\n"
            "F.I.Sh., ish/o'qish joyi, lavozim yoki maqom (talaba, magistrant, "
            "doktorant, o'qituvchi…), e-mail.\n"
            "Ixtiyoriy: ORCID, ilmiy rahbar.\n\n"
            "Hammasini bir xabarda yozing. Kerak bo'lmasa <b>—</b> yuboring."
        ),
        "ask_keywords": (
            "🏷 <b>Kalit so'zlarni</b> kiriting (vergul bilan ajratib).\n\n"
            "Bot o'zi tanlasin desangiz <b>—</b> yuboring."
        ),
        "ask_pages": (
            "📄 Ish necha bet bo'lsin?\n\n"
            "{min} dan {max} gacha raqam kiriting."
        ),
        "invalid_pages": "⚠️ Iltimos, {min} dan {max} gacha butun raqam kiriting.",
        "ask_extra": (
            "📎 <b>Qo'shimcha istaklar</b> (ixtiyoriy):\n"
            "tadqiqot obyekti/hududi, jurnal/konferensiya nomi va h.k.\n"
            "Kerak bo'lmasa <b>—</b> yuboring."
        ),
        "ask_work_language": (
            "🌐 <b>Ish qaysi tilda yozilsin?</b>\n\n"
            "Tanlagan tilingizda maqola/tezis tayyorlanadi."
        ),
        "confirm_summary": (
            "📋 <b>Buyurtmani tekshiring:</b>\n\n"
            "🧩 Turi: <b>{work}</b>\n"
            "🌐 Til: <b>{wlang}</b>\n"
            "📌 Mavzu: {topic}\n"
            "🔬 Soha: {field}\n"
            "✍️ Muallif: {author}\n"
            "🏷 Kalit so'zlar: {keywords}\n"
            "📄 Hajm: <b>{pages} bet</b>\n"
            "📎 Qo'shimcha: {extra}\n\n"
            "💰 Jami: <b>{total} so'm</b>"
        ),
        "btn_confirm": "✅ Tasdiqlash",
        "btn_edit": "✏️ O'zgartirish",
        "wt_article": "Maqola",
        "wt_thesis": "Tezis",
        # --- To'lov ---
        "choose_method": (
            "💳 To'lov usulini tanlang.\n\n"
            "Ish hajmi: <b>{pages} bet</b>\n"
            "Jami to'lov: <b>{total} so'm</b>"
        ),
        "btn_payme": "💳 Payme",
        "btn_click": "💳 Click",
        "btn_card": "🧾 Karta + chek",
        "btn_pay": "💳 To'lash",
        "online_pay_msg": (
            "💳 Quyidagi tugma orqali to'lov qiling.\n"
            "To'lov muvaffaqiyatli bo'lgach, ish <b>avtomatik</b> yuboriladi."
        ),
        "payment_info": (
            "💳 <b>To'lov</b>\n\n"
            "Ish hajmi: <b>{pages} bet</b>\n"
            "Jami to'lov: <b>{total} so'm</b>\n\n"
            "Quyidagi plastik kartaga to'lov qiling:\n"
            "💳 <code>{card}</code>\n"
            "👤 {holder}\n\n"
            "To'lov qilgach, <b>to'lov chekini (skrinshot/rasm)</b> shu yerga "
            "yuboring — tasdiqlangach ish tayyorlanib yuboriladi."
        ),
        "need_receipt": (
            "📸 Iltimos, to'lov chekini <b>rasm (foto)</b> ko'rinishida yuboring."
        ),
        "receipt_ok": "✅ Chek qabul qilindi. Ish tayyorlanmoqda...",
        "receipt_pending": (
            "✅ Chekingiz qabul qilindi!\n\n"
            "⏳ To'lov tekshirilmoqda. Tasdiqlangach, ish avtomatik tayyorlanib "
            "yuboriladi. Iltimos, kutib turing."
        ),
        "receipt_forwarded": (
            "🧾 Yangi to'lov cheki!\n"
            "👤 Mijoz: {user}\n"
            "📄 Mavzu: {topic}\n"
            "📃 Hajm: {pages} bet\n"
            "💰 Summa: {total} so'm"
        ),
        "btn_approve": "✅ Tasdiqlash",
        "btn_reject": "❌ Rad etish",
        "admin_approved": "✅ Tasdiqlandi — ish tayyorlanmoqda.",
        "admin_rejected": "❌ Rad etildi.",
        "already_handled": "Bu buyurtma allaqachon ko'rib chiqilgan.",
        "payment_rejected": (
            "❌ Afsuski, to'lov tasdiqlanmadi.\n\n"
            "Iltimos, to'lovni tekshirib, chekni qaytadan yuboring yoki /new "
            "orqali yangi buyurtma bering."
        ),
        "your_id": "🆔 Sizning Telegram ID: <code>{id}</code>",
        # --- Yetkazish ---
        "payment_confirmed": "✅ To'lov qabul qilindi! Rahmat.",
        "generating": (
            "⏳ Ish tayyorlanmoqda... Bu 1–3 daqiqa davom etishi mumkin.\n"
            "Iltimos, kutib turing."
        ),
        "done_text": "✅ Ish tayyor! Quyida matn va Word (.docx) fayli:",
        "docx_caption": "📄 Word formatidagi ish",
        "pdf_caption": "📕 PDF formatidagi ish",
        "after_delivery": (
            "🎉 Ishingiz tayyor bo'ldi!\n\n"
            "🆕 Yangi ish buyurtma qilish uchun pastdagi tugmani bosing.\n"
            "✍️ Fikr, shikoyat yoki taklifingiz bo'lsa — biz bilan bog'laning."
        ),
        "btn_new_article": "🆕 Yangi ish",
        "btn_feedback": "✍️ Shikoyat / Taklif",
        "error": (
            "❌ Xatolik yuz berdi:\n<code>{err}</code>\n"
            "Qaytadan /new orqali urinib ko'ring."
        ),
        "cancelled": "Bekor qilindi. Yangi ish uchun /new yuboring.",
        # --- Buyruqlar ---
        "help": (
            "ℹ️ <b>Yordam</b>\n\n"
            "/new — yangi maqola yoki tezis\n"
            "/status — buyurtmalaringiz holati\n"
            "/cancel — joriy jarayonni bekor qilish\n"
            "/help — ushbu yordam\n\n"
            "Bot OAK talablari asosida maqola va tezis tayyorlaydi, Word hamda "
            "PDF faylda yuboradi.\n"
            "📄 Maqola — {article} so'm/bet\n"
            "📝 Tezis — {thesis} so'm/bet\n"
            "Ish qaysi tilda (o'zbek/rus/ingliz) yozilishini buyurtma oxirida "
            "tanlaysiz. To'lovdan keyin ish tayyorlanadi."
        ),
        "status_empty": "Sizda hali buyurtmalar yo'q. /new orqali boshlang.",
        "status_header": "📋 <b>So'nggi buyurtmalaringiz:</b>",
        "status_line": (
            "📄 {topic}\n📃 {pages} bet · 💰 {total} so'm\n📌 Holat: {status}"
        ),
        "st_created": "⏳ To'lov kutilmoqda",
        "st_paid": "✅ To'langan",
        "st_delivering": "✍️ Tayyorlanmoqda",
        "st_delivered": "📨 Yuborilgan",
        "st_cancelled": "❌ Bekor qilingan",
        "stats_denied": "⛔ Bu buyruq faqat admin uchun.",
        "stats_body": (
            "📊 <b>Statistika</b>\n\n"
            "Jami buyurtmalar: <b>{total}</b>\n"
            "To'langan: <b>{paid}</b>\n"
            "Yuborilgan: <b>{delivered}</b>\n"
            "Jami daromad: <b>{revenue} so'm</b>"
        ),
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """Interfeys matnini olish. Interfeys doim o'zbek (lotin) tilida."""
    text = TEXTS["uz"].get(key, key)
    return text.format(**kwargs) if kwargs else text
