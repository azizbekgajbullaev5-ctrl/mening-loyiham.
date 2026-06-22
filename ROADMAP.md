# 🗺 Rejalar (ROADMAP)

## ✅ Premium maqola: jadval + diagramma (bajarildi)

Mijoz to'lov oldidan maqola turini tanlaydi:
- 📄 **Oddiy maqola** — `PRICE_PER_PAGE` (standart 5000 so'm/bet)
- 📊 **Premium (jadval + diagramma)** — `PRICE_PER_PAGE_PREMIUM` (standart 8000 so'm/bet)

### Nima qo'shildi
- 📋 **Jadvallar** — Word va PDF ichida (`docx_builder.py`, `pdf_builder.py`)
- 📈 **Diagrammalar** — ustunli (bar) / doira (pie) / chiziqli (line) grafiklar
  (`chart_builder.py`, matplotlib bilan PNG)
- 🔢 Jadval va diagramma ma'lumotlari Claude'dan strukturada (JSON) keladi
  (`article_generator.py` — premium sxema + prompt kengaytmasi)
- 💳 `bot.py` — to'lov oldidan "Oddiy / Premium" tanlovi (FSM `kind` bosqichi),
  narx tanlovga qarab hisoblanadi
- 🗄 `store.py` — buyurtmalarga `premium` ustuni (eski baza uchun migratsiya)

### Eslatma
- Jadval va diagrammalardagi barcha matn maqolaning **asosiy tilida** (bitta tilda).
- Serverga `matplotlib` kerak (`requirements.txt` ga qo'shilgan).

## Keyingi g'oyalar
- 🔲 **Sxemalar** (blok-sxema/oqim diagrammasi) — ehtiyojga qarab.
