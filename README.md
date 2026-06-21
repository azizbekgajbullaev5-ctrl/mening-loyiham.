# 📚 OAK ilmiy maqola boti / Бот научных статей по ВАК

OAK (Oliy Attestatsiya Komissiyasi) talablari asosida **ilmiy maqola** yozib
beradigan Telegram bot. Matnni [Claude AI](https://www.anthropic.com) yordamida
generatsiya qiladi va tayyor maqolani **Word (.docx)** faylda yuboradi.

Interfeys ikki tilda: 🇺🇿 o'zbekcha va 🇷🇺 ruscha.

## ✨ Imkoniyatlar

- ОАК tuzilmasiga mos maqola: UDK, sarlavha, annotatsiya va kalit so'zlar
  (uz/ru/en), kirish, asosiy qism, natijalar, xulosa, foydalanilgan adabiyotlar.
- Universal — har qanday ilmiy soha uchun.
- Tayyor maqola Word (.docx) hujjatida (Times New Roman, 14pt, OAK uslubi).
- Til tanlash (o'zbekcha / ruscha).
- 💳 **To'lov tizimi**: mijoz maqola hajmini (1–15 bet) tanlaydi, har bet
  uchun belgilangan narx (standart **5 000 so'm**) hisoblanadi. Mijoz plastik
  kartaga to'lov qilib, **chekni (rasm)** botga yuboradi — shundan keyin maqola
  avtomatik tayyorlanadi. Chek nusxasi (ixtiyoriy) bot egasiga ham yuboriladi.

## 💳 To'lov jarayoni

1. Mijoz mavzu, soha, muallif, kalit so'zlar va **bet sonini (1–15)** kiritadi.
2. Bot jami summani hisoblaydi (`bet × narx`) va sizning **karta raqamingizni**
   ko'rsatadi.
3. Mijoz kartangizga pul o'tkazadi va **to'lov chekini rasm ko'rinishida** yuboradi.
4. Chek kelishi bilan maqola yoziladi va Word faylda qaytariladi.

> Narx, bet chegaralari va karta ma'lumotlari `.env` orqali sozlanadi
> (`PRICE_PER_PAGE`, `MIN_PAGES`, `MAX_PAGES`, `PAYMENT_CARD_NUMBER`,
> `PAYMENT_CARD_HOLDER`, `ADMIN_CHAT_ID`).

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
   - `PRICE_PER_PAGE` — bir bet narxi (standart `5000`).
   - `MIN_PAGES`, `MAX_PAGES` — bet chegaralari (standart `1`–`15`).
   - `ADMIN_CHAT_ID` — cheklar yuboriladigan Telegram ID ingiz (ixtiyoriy,
     [@userinfobot](https://t.me/userinfobot) orqali bilib oling).

3. Botni ishga tushiring:

   ```bash
   python bot.py
   ```

## 💬 Buyruqlar

| Buyruq    | Vazifasi                          |
| --------- | --------------------------------- |
| `/start`  | Boshlash va til tanlash           |
| `/new`    | Yangi ilmiy maqola yozish         |
| `/lang`   | Interfeys tilini o'zgartirish     |
| `/cancel` | Joriy jarayonni bekor qilish      |
| `/help`   | Yordam                            |

## 🧩 Loyiha tuzilishi

```
bot.py                # Telegram bot (aiogram 3.x), FSM
article_generator.py  # Claude API orqali maqola generatsiyasi
docx_builder.py       # Maqoladan Word (.docx) hujjat tuzish
locales.py            # O'zbekcha / ruscha matnlar
config.py             # Muhit o'zgaruvchilari
```

## ⚠️ Eslatma

Bot AI yordamida matn tayyorlaydi. Yakuniy maqolani nashr etishdan oldin
**ilmiy jihatdan tekshirib chiqing**: faktlar, adabiyotlar ro'yxati va
ma'lumotlarning to'g'riligiga ishonch hosil qiling.
