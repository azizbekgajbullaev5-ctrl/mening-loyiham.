#!/usr/bin/env bash
# Botni yangilash: git pull + kutubxonalar + qayta ishga tushirish.
# Ishlatish:  bash update.sh
cd "$(dirname "$0")" || exit 1
echo "==> Yangi kod tortilmoqda..."
git pull || exit 1
echo "==> Kutubxonalar tekshirilmoqda..."
.venv/bin/pip install -q -r requirements.txt
echo "==> Bot qayta ishga tushirilmoqda..."
systemctl restart maqola-bot
sleep 2
if systemctl is-active --quiet maqola-bot; then
  echo "✅ TAYYOR — bot ishlayapti (active)."
else
  echo "⚠️ Bot ishga tushmadi. Log: journalctl -u maqola-bot -n 30 --no-pager"
fi
