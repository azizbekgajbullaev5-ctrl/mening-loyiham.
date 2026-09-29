#!/usr/bin/env bash
# Aniq sahifa soni uchun LibreOffice + 1GB server uchun swap o'rnatadi.
# Ishlatish:  bash install-extras.sh
set -e

echo "==> LibreOffice (Writer) o'rnatilmoqda... (bir necha daqiqa)"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libreoffice-writer

echo "==> Swap (qo'shimcha xotira) tekshirilmoqda..."
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  echo "   Swap yoqildi (2GB)."
else
  echo "   Swap allaqachon mavjud."
fi

echo
echo "✅ TAYYOR. Tekshirish:"
soffice --version 2>/dev/null | head -1 || libreoffice --version 2>/dev/null | head -1
free -h | head -3
