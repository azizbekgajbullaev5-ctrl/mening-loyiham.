# OAK Xalqaro Jurnallar — Maqola portali

OAK (Oliy Attestatsiya Komissiyasi) ro'yxatiga kirgan xalqaro jurnallarga
maqola tayyorlash va yuborish uchun veb-ilova.

## Imkoniyatlar

- 📚 **Jurnallar ro'yxati va qidiruv** — soha, til va davlat bo'yicha filtrlash
- 📖 **Jurnal tafsilotlari** — ISSN, indekslanish (Scopus/Web of Science), kvartil, talablar
- 📝 **Maqola talablari va shabloni** — IMRAD tuzilishi va yuklab olinadigan shablon
- ✉️ **Maqola yuborish formasi** — ma'lumotlar brauzerda (localStorage) saqlanadi

## Ishga tushirish

Ilova oddiy statik veb-sayt. Hech qanday o'rnatish talab qilinmaydi:

```bash
# 1-usul: index.html faylini brauzerda oching
# 2-usul: lokal server orqali
python3 -m http.server 8000
# so'ng brauzerda http://localhost:8000 ni oching
```

## Tuzilish

```
index.html          — asosiy sahifa
assets/styles.css   — dizayn
assets/app.js       — ilova mantig'i
assets/journals.js  — jurnallar ma'lumotlar bazasi (namuna)
```

## Jurnallar ma'lumotlari

Ilovadagi 48 ta jurnal — **Scopus / Web of Science** bazalarida indekslangan
haqiqiy xalqaro jurnallar (turli sohalar bo'yicha, to'g'ri ISSN bilan).

OAK xorijiy jurnallarning yopiq ro'yxatini yuritmaydi: Nizomga ko'ra, xorijiy
nashr **Scopus**, **Web of Science**, Springer, PubMed, Index Copernicus kabi
bazalarda indekslangan bo'lsa, dissertatsiya talabiga javob beradi. Shu sababli
ushbu jurnallar OAK tomonidan qabul qilinadi.

To'liq rasmiy ro'yxat (milliy va MDH jurnallari bilan birga) uchun
[oak.uz](https://oak.uz) saytiga murojaat qiling. Yangi jurnal qo'shish uchun
`assets/journals.js` faylidagi `JOURNALS` massiviga yozuv qo'shing.
