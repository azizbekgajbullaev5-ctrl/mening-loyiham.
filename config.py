"""Konfiguratsiya — muhit o'zgaruvchilaridan o'qiladi."""
import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN o'rnatilmagan. .env faylini to'ldiring.")
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY o'rnatilmagan. .env faylini to'ldiring.")
