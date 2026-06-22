# 📚 OAK ilmiy maqola boti / Бот научных статей по ВАК

OAK (Oliy Attestatsiya Komissiyasi) talablari asosida **ilmiy maqola** yozib
beradigan Telegram bot. Matnni [Claude AI](https://www.anthropic.com) yordamida
generatsiya qiladi va tayyor maqolani **Word (.docx)** faylda yuboradi.

Interfeys ikki tilda: 🇺🇿 o'zbekcha va 🇷🇺 ruscha.

## ✨ Imkoniyatlar

- ОАК tuzilmasiga mos maqola: UDK, sarlavha, annotatsiya va kalit so'zlar
  (uz/ru/en), kirish, asosiy qism, natijalar, xulosa, foydalanilgan adabiyotlar.
- Universal — har qanday ilmiy soha uchun.
- Tayyor maqola **Word (.docx)** va **PDF** hujjatlarida (OAK uslubi).
- 📊 **Premium maqola**: mijoz tanlasa, maqolaga **jadval va diagrammalar**
  (ustunli/doira/chiziqli) qo'shiladi (matn asosiy tilda). Narxi alohida —
  `PRICE_PER_PAGE_PREMIUM` (standart **8 000 so'm/bet**).
- Til tanlash (o'zbekcha / ruscha).
- 💳 **To'lov tizimi**: mijoz maqola hajmini (1–15 bet) va turini (oddiy/premium)
  tanlaydi, har bet uchun belgilangan narx (oddiy standart **5 000 so'm**)
  hisoblanadi. Uch xil to'lov:
  **Payme**, **Click** (rasmiy Merchant API, webhook orqali avtomatik) yoki
  **karta + chek**. To'lovdan keyin maqola avtomatik tayyorlanadi.

## 💳 To'lov usullari

Bot uchta to'lov usulini qo'llab-quvvatlaydi (mijoz tanlaydi). Har bir usul
`.env` da tegishli kredensiallar bo'lsagina ko'rsatiladi:

| Usul | Qanday ishlaydi |
| --- | --- |
| **Payme** | Rasmiy Paycom Merchant API (JSON-RPC webhook). To'lov muvaffaqiyatli bo'lgach maqola **avtomatik** yuboriladi. |
| **Click** | Rasmiy Click Merchant API (Prepare/Complete webhook). To'lovdan keyin maqola **avtomatik** yuboriladi. |
| **Karta + chek** | Mijoz kartaga pul o'tkazadi va chek rasmini yuboradi (qo'lbola usul). |

### Umumiy jarayon

1. Mijoz mavzu, soha, muallif, kalit so'zlar va **bet sonini (1–15)** kiritadi,
   so'ng maqola turini tanlaydi: **Oddiy** yoki **Premium (jadval+diagramma)**.
2. Bot summani hisoblaydi (`bet × narx`, tanlangan turga qarab) va **to'lov
   usulini** so'raydi.
3. Payme/Click — to'lov tugmasi yuboriladi; to'lovdan keyin webhook orqali
   maqola avtomatik tayyorlanadi. Karta — chek rasmini yuborgach tayyorlanadi.

### 🌐 Webhook sozlash (Payme/Click)

Payme va Click sizning serveringizga callback (webhook) yuboradi, shuning uchun
bot **ochiq HTTPS manzilda** ishlashi kerak (domен + SSL yoki reverse-proxy).

Veb-server `WEB_HOST:WEB_PORT` (standart `0.0.0.0:8080`) da ishlaydi. Provayder
kabinetida quyidagi URL larni ko'rsating:

- **Payme** endpoint: `https://<sizning-domen>/payme`
- **Click Prepare**: `https://<sizning-domen>/click/prepare`
- **Click Complete**: `https://<sizning-domen>/click/complete`

> ⚠️ Payme/Click kabinetida xizmat narxi va `account` maydoni (`order_id`)
> bot sozlamalariga mos bo'lishi kerak.

> Sozlamalar `.env` orqali: `PRICE_PER_PAGE`, `MIN_PAGES`, `MAX_PAGES`,
> `PAYMENT_CARD_NUMBER`, `PAYMENT_CARD_HOLDER`, `ADMIN_CHAT_ID`,
> `WEB_HOST`, `WEB_PORT`, `WEBHOOK_BASE_URL`,
> `PAYME_MERCHANT_ID`, `PAYME_KEY`, `CLICK_MERCHANT_ID`, `CLICK_SERVICE_ID`,
> `CLICK_SECRET_KEY`.

## 🚀 O'rnatish

1. Kutubxonalarni o'rnating:

   ```bash
   pip install -r requirements.txt
   ```

2. `.env` faylini yarating (`.env.example` dan nusxa oling):

   ```bash
   cp .env.example .env
   ```

   So'ngra to'ldiring:
   - `TELEGRAM_BOT_TOKEN` — [@BotFather](https://t.me/BotFather) dan oling.
   - `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com) dan oling.
   - `CLAUDE_MODEL` — ixtiyoriy (standart: `claude-opus-4-8`).
   - `PAYMENT_CARD_NUMBER`, `PAYMENT_CARD_HOLDER` — to'lov qabul qiladigan kartangiz.
   - `PRICE_PER_PAGE` — oddiy maqola bir bet narxi (standart `5000`).
   - `PRICE_PER_PAGE_PREMIUM` — premium (jadval+diagramma) bir bet narxi (standart `8000`).
   - `MIN_PAGES`, `MAX_PAGES` — bet chegaralari (standart `1`–`15`).
   - `ADMIN_CHAT_ID` — cheklar yuboriladigan Telegram ID ingiz (ixtiyoriy,
     [@userinfobot](https://t.me/userinfobot) orqali bilib oling).
   - `WEB_HOST`, `WEB_PORT`, `WEBHOOK_BASE_URL` — webhook veb-serveri (Payme/Click).
   - `PAYME_MERCHANT_ID`, `PAYME_KEY` — Payme Merchant API (bo'sh bo'lsa o'chiq).
   - `CLICK_MERCHANT_ID`, `CLICK_SERVICE_ID`, `CLICK_SECRET_KEY` — Click Merchant
     API (bo'sh bo'lsa o'chiq).

3. Botni ishga tushiring:

   ```bash
   python bot.py
   ```

> 🚀 **Serverга 24/7 joylashtirish** (VPS + domen + SSL + Click/Payme webhook):
> [DEPLOY.md](DEPLOY.md) — noldan to'liq yo'riqnoma.

## 💬 Buyruqlar

| Buyruq    | Vazifasi                          |
| --------- | --------------------------------- |
| `/start`  | Boshlash va til tanlash           |
| `/new`    | Yangi ilmiy maqola yozish         |
| `/status` | Buyurtmalaringiz holati           |
| `/stats`  | Statistika (faqat admin)          |
| `/lang`   | Interfeys tilini o'zgartirish     |
| `/cancel` | Joriy jarayonni bekor qilish      |
| `/help`   | Yordam                            |

## 🧩 Loyiha tuzilishi

```
bot.py                # Telegram bot (aiogram 3.x), FSM + webhook server
article_generator.py  # Claude API orqali maqola generatsiyasi
docx_builder.py       # Maqoladan Word (.docx) hujjat tuzish
pdf_builder.py        # Maqoladan PDF hujjat tuzish (fpdf2 + DejaVu)
payments.py           # Payme/Click to'lov havolalari va webhook'lari
store.py              # Buyurtmalar va tranzaksiyalar (SQLite)
fulfillment.py        # To'lovdan keyin maqolani yaratib yetkazish
locales.py            # O'zbekcha / ruscha matnlar
config.py             # Muhit o'zgaruvchilari
assets/fonts/         # PDF uchun DejaVu shriftlari (kirill/lotin)
```

## ⚠️ Eslatma

Bot AI yordamida matn tayyorlaydi. Yakuniy maqolani nashr etishdan oldin
**ilmiy jihatdan tekshirib chiqing**: faktlar, adabiyotlar ro'yxati va
ma'lumotlarning to'g'riligiga ishonch hosil qiling.
