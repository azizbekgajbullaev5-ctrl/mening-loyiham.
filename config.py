"""Konfiguratsiya — muhit o'zgaruvchilaridan o'qiladi."""
import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

# --- Narx sozlamalari ---
PRICE_PER_PAGE = int(os.getenv("PRICE_PER_PAGE", "5000"))  # oddiy maqola — bir bet (so'm)
# Premium (jadval + diagrammali) maqola — bir bet narxi (so'm)
PRICE_PER_PAGE_PREMIUM = int(os.getenv("PRICE_PER_PAGE_PREMIUM", "8000"))
MIN_PAGES = int(os.getenv("MIN_PAGES", "1"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "15"))


def price_per_page(premium: bool) -> int:
    return PRICE_PER_PAGE_PREMIUM if premium else PRICE_PER_PAGE

# --- Karta + chek (qo'lbola) usuli ---
PAYMENT_CARD_NUMBER = os.getenv("PAYMENT_CARD_NUMBER", "")
PAYMENT_CARD_HOLDER = os.getenv("PAYMENT_CARD_HOLDER", "")
_admin = os.getenv("ADMIN_CHAT_ID", "").strip()
ADMIN_CHAT_ID = int(_admin) if _admin.lstrip("-").isdigit() else None

# Egasi (admin) Telegram username — shikoyat/taklif tugmasi shunga bog'lanadi
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").lstrip("@").strip()


def feedback_url() -> str:
    """Shikoyat/taklif uchun egasi bilan bog'lanish havolasi (yoki bo'sh)."""
    return f"https://t.me/{ADMIN_USERNAME}" if ADMIN_USERNAME else ""

# --- Veb-server (Click/Payme webhook'lari uchun) ---
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
# Tashqi ochiq HTTPS manzil (mas. https://bot.example.uz) — to'lov havolalari uchun
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").rstrip("/")

# --- Payme (Paycom) Merchant API ---
PAYME_MERCHANT_ID = os.getenv("PAYME_MERCHANT_ID", "")
PAYME_KEY = os.getenv("PAYME_KEY", "")
PAYME_ACCOUNT_FIELD = os.getenv("PAYME_ACCOUNT_FIELD", "order_id")
PAYME_CHECKOUT_URL = os.getenv("PAYME_CHECKOUT_URL", "https://checkout.paycom.uz")

# --- Click Merchant API ---
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")
CLICK_BASE_URL = os.getenv("CLICK_BASE_URL", "https://my.click.uz/services/pay")


# --- Yoqilgan to'lov usullari (kredensiallarga qarab) ---
def method_card_enabled() -> bool:
    return bool(PAYMENT_CARD_NUMBER)


def method_payme_enabled() -> bool:
    return bool(PAYME_MERCHANT_ID and PAYME_KEY)


def method_click_enabled() -> bool:
    return bool(CLICK_MERCHANT_ID and CLICK_SERVICE_ID and CLICK_SECRET_KEY)


if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN o'rnatilmagan. .env faylini to'ldiring.")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY o'rnatilmagan. .env faylini to'ldiring.")
if not (method_card_enabled() or method_payme_enabled() or method_click_enabled()):
    raise RuntimeError(
        "Hech qaysi to'lov usuli sozlanmagan. Kamida karta yoki Payme yoki "
        "Click kredensiallarini .env ga kiriting."
    )
