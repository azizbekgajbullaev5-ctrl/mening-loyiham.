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

## Eslatma

Jurnallar ro'yxati — **namuna** ma'lumotlar. Rasmiy va to'liq ro'yxat uchun
[oak.uz](https://oak.uz) saytiga murojaat qiling. Yangi jurnal qo'shish uchun
`assets/journals.js` faylidagi `JOURNALS` massiviga yangi yozuv qo'shing.
