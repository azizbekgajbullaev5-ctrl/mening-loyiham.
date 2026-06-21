"""Konfiguratsiya — muhit o'zgaruvchilaridan o'qiladi."""
import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

# --- To'lov sozlamalari ---
# Mijoz pul o'tkazadigan plastik karta raqami va egasi
PAYMENT_CARD_NUMBER = os.getenv("PAYMENT_CARD_NUMBER", "")
PAYMENT_CARD_HOLDER = os.getenv("PAYMENT_CARD_HOLDER", "")
# Har bir sahifa narxi (so'mda)
PRICE_PER_PAGE = int(os.getenv("PRICE_PER_PAGE", "5000"))
# Sahifa chegaralari
MIN_PAGES = int(os.getenv("MIN_PAGES", "1"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "15"))
# To'lov cheki yuboriladigan admin (egasi) Telegram chat ID si (ixtiyoriy)
_admin = os.getenv("ADMIN_CHAT_ID", "").strip()
ADMIN_CHAT_ID = int(_admin) if _admin.lstrip("-").isdigit() else None

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN o'rnatilmagan. .env faylini to'ldiring.")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY o'rnatilmagan. .env faylini to'ldiring.")
if not PAYMENT_CARD_NUMBER:
    raise RuntimeError("PAYMENT_CARD_NUMBER o'rnatilmagan. .env faylini to'ldiring.")
