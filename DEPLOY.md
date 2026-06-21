# 🚀 Serverга joylashtirish (deploy) — noldan to'liq yo'riqnoma

Bu qo'llanma botni **24/7 ishlaydigan serverda** ishga tushirish va Click/Payme
webhook'larini ulash uchun. Hech narsangiz yo'q bo'lsa ham — noldan boshlaymiz.

> **Nega kerak?** Bot doim onlayn bo'lishi, Click/Payme esa to'lov tasdig'ini
> sizning **ochiq HTTPS manzilingizga** yuborishi kerak. Buning uchun:
> **VPS (server) + domen + SSL** zarur.

Yakuniy ko'rinish:

```
Mijoz → Telegram → Bot (VPS'da, polling)
Click/Payme → https://sizning-domen.uz/click/... → Nginx (443, SSL) → Bot (8080)
```

---

## 1-qadam. VPS (server) ijaraga olish

Ubuntu 22.04 yoki 24.04 o'rnatilgan, ochiq IP manzilli istalgan VPS bo'ladi.
Eng arzon variant (~4–6 $/oy) yetarli (1 vCPU, 1–2 GB RAM).

Tavsiya etiladigan provayderlar:

- **Xalqaro (arzon):** Hetzner, Contabo, DigitalOcean, Vultr
- **O'zbekistonda:** ahost.uz, cloud.uz va sh.k.

Server ochilgach sizga **IP manzil**, **root parol** (yoki SSH kalit) beriladi.

Serverга ulanish (o'z kompyuteringiz terminalidan):

```bash
ssh root@SERVER_IP
```

---

## 2-qadam. Domen olish va serverга yo'naltirish

1. Domen sotib oling:
   - **.uz** — [ZONE.UZ](https://zone.uz), ahost.uz
   - **.com** — Namecheap, Cloudflare
2. Domen boshqaruvida **A-record** qo'shing:

   | Turi | Nomi | Qiymati |
   | ---- | ---- | ------- |
   | A | `@` (yoki `bot`) | `SERVER_IP` |

   Masalan `bot.example.uz` → server IP manziliga ishora qilsin.
   (DNS yangilanishi 5 daqiqadan bir necha soatgacha vaqt olishi mumkin.)

---

## 3-qadam. Serverни tayyorlash

Serverга SSH bilan ulangach:

```bash
# Tizimni yangilash
apt update && apt upgrade -y

# Kerakli paketlar
apt install -y python3 python3-venv python3-pip git nginx

# (PDF/cryptography uchun) tizim kutubxonalari
apt install -y build-essential libffi-dev
```

---

## 4-qadam. Botни o'rnatish

```bash
# Loyihani klonlash (o'z repozitoriyangiz manzili bilan)
cd /opt
git clone https://github.com/azizbekgajbullaev5-ctrl/mening-loyiham..git bot
cd bot

# Virtual muhit va kutubxonalar
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Sozlamalar fayli
cp .env.example .env
nano .env   # to'ldiring (pastga qarang)
```

`.env` da kamida quyidagilarni to'ldiring:

```env
TELEGRAM_BOT_TOKEN=...        # @BotFather
ANTHROPIC_API_KEY=...         # console.anthropic.com
PAYMENT_CARD_NUMBER=8600...   # karta+chek usuli uchun
WEB_HOST=127.0.0.1
WEB_PORT=8080
WEBHOOK_BASE_URL=https://bot.example.uz

# Click kelganda (shartnomadan keyin):
CLICK_MERCHANT_ID=
CLICK_SERVICE_ID=
CLICK_SECRET_KEY=
```

> Click kalitlari hali yo'q bo'lsa — bo'sh qoldiring. Bot **karta+chek** usuli
> bilan darrov ishlaydi. Kalitlar kelgach qo'shasiz.

Tez tekshiruv (ixtiyoriy): `.venv/bin/python bot.py` — ishga tushsa, `Ctrl+C`.

---

## 5-qadam. Botни doimiy ishlatish (systemd)

`/etc/systemd/system/maqola-bot.service` faylini yarating:

```bash
nano /etc/systemd/system/maqola-bot.service
```

Ichiga:

```ini
[Unit]
Description=OAK maqola Telegram bot
After=network.target

[Service]
WorkingDirectory=/opt/bot
ExecStart=/opt/bot/.venv/bin/python bot.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/bot/.env

[Install]
WantedBy=multi-user.target
```

Ishga tushirish:

```bash
systemctl daemon-reload
systemctl enable --now maqola-bot
systemctl status maqola-bot      # ishlayotganini ko'rish
journalctl -u maqola-bot -f      # loglarni kuzatish
```

Endi bot 24/7 ishlaydi va server qayta yuklansa ham o'zi qaytadan ishga tushadi.

---

## 6-qadam. Nginx + SSL (HTTPS webhook)

Bot ichki `127.0.0.1:8080` da ishlaydi. Nginx uni tashqi HTTPS (443) ga chiqaradi.

`/etc/nginx/sites-available/maqola-bot` yarating:

```bash
nano /etc/nginx/sites-available/maqola-bot
```

Ichiga (domeningizni yozing):

```nginx
server {
    listen 80;
    server_name bot.example.uz;

    location /payme {
        proxy_pass http://127.0.0.1:8080/payme;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /click/ {
        proxy_pass http://127.0.0.1:8080/click/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /health {
        proxy_pass http://127.0.0.1:8080/health;
    }
}
```

Yoqish:

```bash
ln -s /etc/nginx/sites-available/maqola-bot /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

SSL (bepul, Let's Encrypt):

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d bot.example.uz
```

Certbot avtomatik HTTPS sozlaydi va sertifikatni o'zi yangilab turadi.

Tekshiruv:

```bash
curl https://bot.example.uz/health      # "ok" qaytishi kerak
```

---

## 7-qadam. Xavfsizlik devori (firewall)

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

> Bot porti (8080) tashqaridan **yopiq** qoladi — faqat Nginx orqali kiriladi.

---

## 8-qadam. Click/Payme webhook'larini ulash

Shartnoma tuzib, kalitlarni olgach:

1. `.env` ga `CLICK_MERCHANT_ID`, `CLICK_SERVICE_ID`, `CLICK_SECRET_KEY` ni
   yozing (Payme bo'lsa `PAYME_MERCHANT_ID`, `PAYME_KEY`).
2. Botни qayta ishga tushiring:

   ```bash
   systemctl restart maqola-bot
   ```

3. Click/Payme kabinetida webhook URL'larini ko'rsating:
   - **Click Prepare:** `https://bot.example.uz/click/prepare`
   - **Click Complete:** `https://bot.example.uz/click/complete`
   - **Payme:** `https://bot.example.uz/payme`

4. Test to'lov qilib tekshiring.

---

## 🔄 Yangilanish (kod o'zgarganda)

```bash
cd /opt/bot
git pull
.venv/bin/pip install -r requirements.txt
systemctl restart maqola-bot
```

---

## ✅ Tartib (qisqacha)

1. VPS ijaraga ol (~5 $/oy)
2. Domen ol va A-record bilan serverга yo'naltir
3. Server tayyorla → botни o'rnat → `.env` to'ldir
4. systemd bilan 24/7 ishlat → **karta+chek darrov ishlaydi**
5. Nginx + SSL (HTTPS)
6. Parallel: Click shartnomasi → kalitlar
7. Kalitlarni `.env` ga yoz → webhook ula → **Click yoqiladi**
