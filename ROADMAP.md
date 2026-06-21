# 🗺 Keyingi rejalar (ROADMAP)

## Premium maqola: jadval + diagramma (5 kundan keyin)

Mijozlar ko'paygach qo'shiladigan funksiya.

### Nima qo'shiladi
- 📋 **Jadvallar** — Word va PDF ichida (oson, ishonchli)
- 📈 **Diagrammalar** — ustunli/doira/chiziqli grafiklar (matplotlib bilan rasm)
- 🔲 **Sxemalar** — keyinroq, ehtiyojga qarab (murakkabroq)

### Narx modeli: PREMIUM VARIANT
Mijoz to'lov oldidan tanlaydi:
- 📄 **Oddiy maqola** — hozirgi narx (mas. 5000 so'm/bet)
- 📊 **Jadval/diagrammali (Premium)** — qimmatroq (mas. 8000–10000 so'm/bet)

### Texnik eslatma (ishlab chiqishda)
- `article_generator.py` — Claude'dan jadval/grafik ma'lumotlarini ham
  strukturada qaytaradigan qilish (prompt + JSON sxema kengaytiriladi)
- `docx_builder.py` — python-docx jadval + rasm qo'shish
- `pdf_builder.py` — fpdf2 jadval + rasm qo'shish
- Yangi: `chart_builder.py` — matplotlib bilan grafik rasm chizadi
- Serverga `matplotlib` o'rnatiladi (requirements.txt ga qo'shiladi)
- `bot.py` — to'lov oldidan "Oddiy / Premium" tanlovi (FSM bosqichi),
  narx tanlovga qarab hisoblanadi
- `config.py` — `PRICE_PER_PAGE_PREMIUM` qo'shiladi

> Holat: rejalashtirilgan. Boshlash uchun "premium funksiyani qilamiz" deng.
