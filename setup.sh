#!/usr/bin/env bash
#
# Bot'ни серверга bir buyruq bilan o'rnatuvchi skript.
# Ishlatish:  bash setup.sh
#
set -e

cd "$(dirname "$0")"
APP_DIR="$(pwd)"

echo "==================================================="
echo "  📚 OAK maqola bot — o'rnatish"
echo "==================================================="
echo

# --- 1. Python muhiti va kutubxonalar ---
echo "⏳ Python muhiti tayyorlanmoqda..."
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
echo "⏳ Kutubxonalar o'rnatilmoqda (bir-ikki daqiqa)..."
.venv/bin/pip install --quiet -r requirements.txt
echo "✅ Kutubxonalar o'rnatildi."
echo

# --- 2. Sozlamalar (.env) ---
if [ -f .env ]; then
  echo "ℹ️  .env fayli allaqachon mavjud."
  read -rp "Uni qaytadan to'ldirasizmi? (ha/yo'q): " redo
  case "$redo" in
    ha|HA|Ha|h|y|yes) ;;
    *) echo "➡️  Eski .env saqlandi."; SKIP_ENV=1 ;;
  esac
fi

if [ -z "$SKIP_ENV" ]; then
  # Agar qiymatlar muhit o'zgaruvchilari orqali berilgan bo'lsa —
  # savol bermasdan to'g'ridan-to'g'ri ishlatamiz (telefon uchun qulay).
  if [ -n "$BOT_TOKEN" ] && [ -n "$API_KEY" ] && [ -n "$CARD_NUM" ]; then
    echo "➡️  Sozlamalar buyruq ichidan olindi (savolsiz)."
  else
    echo
    echo "--- Sozlamalarni kiriting (har birini yozib Enter bosing) ---"
    echo
    read -rp "1) Telegram bot tokeni (@BotFather'dan): " BOT_TOKEN
    read -rp "2) Anthropic API kaliti (console.anthropic.com): " API_KEY
    read -rp "3) Karta raqami (mijoz pul o'tkazadi, mas. 8600 1234 5678 9012): " CARD_NUM
    read -rp "4) Karta egasi ismi (mas. AZIZBEK G.): " CARD_HOLDER
    read -rp "5) Bir bet narxi so'mda (Enter = 5000): " PRICE
    read -rp "6) Admin Telegram ID (ixtiyoriy, bilmasangiz Enter): " ADMIN_ID
  fi
  PRICE="${PRICE:-5000}"

  cat > .env <<EOF
TELEGRAM_BOT_TOKEN=$BOT_TOKEN
ANTHROPIC_API_KEY=$API_KEY
CLAUDE_MODEL=claude-opus-4-8

PAYMENT_CARD_NUMBER=$CARD_NUM
PAYMENT_CARD_HOLDER=$CARD_HOLDER
PRICE_PER_PAGE=$PRICE
MIN_PAGES=1
MAX_PAGES=15
ADMIN_CHAT_ID=$ADMIN_ID

WEB_HOST=127.0.0.1
WEB_PORT=8080
WEBHOOK_BASE_URL=

PAYME_MERCHANT_ID=
PAYME_KEY=
PAYME_ACCOUNT_FIELD=order_id
PAYME_CHECKOUT_URL=https://checkout.paycom.uz

CLICK_MERCHANT_ID=
CLICK_SERVICE_ID=
CLICK_SECRET_KEY=
CLICK_BASE_URL=https://my.click.uz/services/pay
EOF
  echo "✅ Sozlamalar saqlandi (.env)."
fi
echo

# --- 3. Doimiy ishlash (systemd) ---
echo "⏳ Bot doimiy ishlaydigan qilinmoqda..."
cat > /etc/systemd/system/maqola-bot.service <<EOF
[Unit]
Description=OAK maqola Telegram bot
After=network.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now maqola-bot >/dev/null 2>&1 || systemctl restart maqola-bot
sleep 2

echo
echo "==================================================="
if systemctl is-active --quiet maqola-bot; then
  echo "  ✅ TAYYOR! Bot ishlayapti va 24/7 ishlaydi."
  echo "  Endi Telegram'da botingizga /start yozib sinab ko'ring."
else
  echo "  ⚠️  Bot ishga tushmadi. Loglarni ko'rish uchun:"
  echo "      journalctl -u maqola-bot -n 30 --no-pager"
fi
echo "==================================================="
