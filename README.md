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
