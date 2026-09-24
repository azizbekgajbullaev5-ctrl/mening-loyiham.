# Windows'da Docker'siz ishga tushirish — qadamma-qadam yo'riqnoma

Bu usulda **faqat Python** kerak bo'ladi. Docker, PostgreSQL, Redis yoki Node.js kerak emas.
Ma'lumotlar bazasi — SQLite (bitta fayl), veb-interfeys esa dastur ichida tayyor holda keladi.

Minimal talablar: Windows 10/11 (64-bit), 8 GB RAM, ~1,5 GB bo'sh joy, birinchi ishga tushirishda internet.

---

## 1-qadam. Python 3.12 ni o'rnating

1. Brauzerda oching: **https://www.python.org/downloads/windows/**
2. **"Python 3.12.x"** bo'limidan **"Windows installer (64-bit)"** ni yuklab oling.
   (3.11 yoki 3.13 ham ishlaydi; 3.12 tavsiya etiladi.)
3. Yuklangan faylni ishga tushiring.
4. **MUHIM:** birinchi oynaning pastidagi **"Add python.exe to PATH"** belgisiga ✅ qo'ying.
5. **"Install Now"** ni bosing va tugashini kuting → **"Close"**.

Tekshirish (ixtiyoriy): **Win + R** → `cmd` → Enter → quyidagini yozing:
```
python --version
```
`Python 3.12.x` chiqsa — tayyor.

## 2-qadam. Dasturni yuklab oling

1. Repozitoriy sahifasini oching: https://github.com/azizbekgajbullaev5-ctrl/mening-loyiham.
2. Yashil **"Code"** tugmasi → **"Download ZIP"**.
   (Papkada `start.bat` fayli bo'lishi kerak. Bo'lmasa — Windows rejimi hali asosiy branch'ga qo'shilmagan:
   ochiq Pull Request'ni merge qiling yoki PR sahifasidagi branch'ning ZIP'ini yuklab oling.)
3. ZIP faylni o'ng tugma bilan bosing → **"Extract All…"** (Hammasini chiqarish).
4. Chiqarilgan papkani qisqa manzilga ko'chiring, masalan: **`C:\AkademikTahlil`**
   (Desktop yoki OneDrive ichiga qo'ymaslik tavsiya etiladi).

## 3-qadam. `start.bat` ni ikki marta bosing

1. `C:\AkademikTahlil` papkasini oching va **`start.bat`** faylini ikki marta bosing.
2. Agar **"Windows protected your PC"** (SmartScreen) oynasi chiqsa: **"More info"** → **"Run anyway"**.
3. Birinchi marta dastur o'zi quyidagilarni bajaradi (internet kerak, **3–10 daqiqa**):
   - kerakli kutubxonalarni o'rnatadi (~100 MB);
   - maxfiy kalitlarni yaratadi (**`FILE_ENCRYPTION_KEY`** ham — qo'lda hech narsa kiritish shart emas);
   - SQLite ma'lumotlar bazasini yaratadi.
4. Oxirida oynada shunday yozuv chiqadi va brauzer o'zi ochiladi:
   ```
   Akademik AI va o'xshashlik tahlilchisi ishga tushdi
   Brauzerda oching:  http://127.0.0.1:8000
   ```
   Brauzer ochilmasa, shu manzilni o'zingiz brauzerga kiriting.

**Qora oynani yopmang** — u dasturning o'zi. Dasturni to'xtatish uchun shu oynani yopasiz.
Keyingi safar `start.bat` bir necha soniyada ishga tushadi.

## 4-qadam. Hujjat tekshirish

1. **"Ro'yxatdan o'tish"** — email va parol (kamida 10 belgi, harf va raqam).
2. **"Hujjat yuklash"** maydoniga DOCX/PDF faylni tashlang (60 MB gacha).
3. **Hujjat turi** (dissertatsiya, darslik, o'quv qo'llanma, …) va **tahlil chuqurligi**ni tanlang
   (**"Standart"** tavsiya etiladi) → **"Tahlilni boshlash"**.
4. Jarayon foizi va bosqichi (matn ajratish → OCR → AI tahlili boblar bo'yicha → o'xshashlik → …)
   ekranda ko'rinib turadi.
5. Tayyor bo'lgach, hujjat nomini bosing → natijalar, grafiklar, shubhali parchalar.
6. **"PDF hisobot"** yoki **"DOCX hisobot"** tugmasi bilan hisobotni yuklab oling.

### Katta hujjatlar (150–500 bet) haqida

* Hujjat bo'limlarga va 120–380 so'zli bo'laklarga bo'linib tahlil qilinadi.
* **Bir vaqtda faqat bitta hujjat** tahlil qilinadi; qolganlari navbatda turadi ("Navbatdagi o'rni: 2").
* Sinovda (500 bet, 27 MB PDF) tahlil ~1,5 daqiqa davom etdi va ~500 MB xotira ishlatdi; 500 betlik DOCX ~40 soniya.
  Sizning kompyuteringizda tezlik boshqacha bo'lishi mumkin.
* **Skanerlangan PDF** (rasm ko'rinishidagi sahifalar) OCR talab qiladi — bu sekin: sahifasiga bir necha soniya,
  ya'ni 300 betlik skaner kitob 30–60+ daqiqa olishi mumkin.
* **Xato yoki uzilish bo'lsa:**
  - dastur avtomatik 2 marta qayta urinadi;
  - oynani yopsangiz yoki kompyuter o'chib qolsa, keyingi `start.bat` da tahlil **to'xtagan joyidan davom etadi**
    (matn ajratish va OCR qilingan sahifalar saqlanadi — qaytadan qilinmaydi);
  - natija sahifasida **"To'xtagan joyidan davom ettirish"** tugmasi ham bor.

## 5-qadam (ixtiyoriy). Skanerlangan PDF uchun OCR — Tesseract

Faqat skaner qilingan (matni belgilanmaydigan) PDF'lar uchun kerak. Oddiy DOCX/PDF uchun shart emas.

1. Oching: **https://github.com/UB-Mannheim/tesseract/wiki**
2. **"tesseract-ocr-w64-setup-….exe"** (64-bit) ni yuklab, ishga tushiring.
3. O'rnatish jarayonida **"Additional language data (download)"** bo'limini oching va
   ✅ **Russian**, ✅ **Uzbek** (xohlasangiz ✅ **Uzbek (Cyrillic)**) ni belgilang.
4. O'rnatish manzilini o'zgartirmang (`C:\Program Files\Tesseract-OCR`) — dastur uni o'zi topadi.
5. `start.bat` ni qayta ishga tushiring. Oynada **`OCR: bor`** chiqishi kerak.
   Boshqa papkaga o'rnatgan bo'lsangiz, `backend\.env` faylida yozing:
   `TESSERACT_CMD=D:\boshqa\papka\tesseract.exe`

## FILE_ENCRYPTION_KEY haqida

* Kalit **birinchi ishga tushirishda avtomatik** yaratiladi va `C:\AkademikTahlil\backend\.env` fayliga yoziladi.
  Yuklangan hujjatlar shu kalit bilan shifrlanadi.
* **`backend\.env` faylining zaxira nusxasini oling** (masalan, fleshkaga). Kalit yo'qolsa, saqlangan
  hujjatlarni ochib bo'lmaydi (tahlil natijalari saqlanib qoladi).
* Yangi kalitni qo'lda olish kerak bo'lsa (Docker'siz), ikki usul:
  - `C:\AkademikTahlil` papkasida adres satriga `cmd` yozib Enter bosing, keyin:
    ```
    backend\.venv\Scripts\python.exe run_local.py --genkey
    ```
  - yoki **PowerShell**da (Python'siz):
    ```powershell
    $b = New-Object byte[] 32; (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($b); [Convert]::ToBase64String($b).Replace('+','-').Replace('/','_')
    ```
  Chiqqan qatorni `backend\.env` dagi `FILE_ENCRYPTION_KEY=` dan keyin qo'ying.
  ⚠️ Mavjud kalitni almashtirsangiz, avval yuklangan hujjatlarning asl fayllari ochilmay qoladi.

## Ixtiyoriy: tashqi AI API (Claude Haiku 4.5 — eng yengil model)

Standart holatda **hech qanday AI model yuklanmaydi va internetga matn yuborilmaydi**: AI-ehtimollik lokal
lingvistik (stilometrik) usul bilan hisoblanadi — 8 GB RAM uchun eng yengil variant.

Qo'shimcha tashqi baho kerak bo'lsa:
1. https://console.anthropic.com dan API kalit oling (pullik xizmat).
2. `backend\.env` faylini Blocknot bilan oching va o'zgartiring:
   ```
   LLM_REVIEW_ENABLED=true
   ANTHROPIC_API_KEY=sk-ant-...
   ANTHROPIC_MODEL=claude-haiku-4-5
   ```
3. `start.bat` ni qayta ishga tushiring va tahlilda **"Chuqur"** ni tanlang.
   Har bir hujjatdan faqat eng shubhali 40 ta parcha yuboriladi (butun hujjat emas); natijalar keshlanadi.
   Tashqi baho lokal baho bilan **yonma-yon** ko'rsatiladi, ular birlashtirilmaydi.

## Ma'lumotlar qayerda?

`C:\AkademikTahlil\backend\data\` — ma'lumotlar bazasi (`app.db`), shifrlangan hujjatlar va checkpoint'lar.
Hujjatni ilovada **"O'chirish"** tugmasi bilan o'chirsangiz, fayl va barcha natijalar butunlay o'chadi.

## Yangilash

1. Yangi versiyani ZIP qilib yuklab oling va boshqa papkaga chiqaring.
2. Eski papkadan **`backend\.env`** faylini va **`backend\data`** papkasini yangi papkaning `backend\` ichiga ko'chiring.
3. Yangi papkadagi `start.bat` ni ishga tushiring (kutubxonalar kerak bo'lsa o'zi yangilanadi).

## Muammolar va yechimlar

| Belgi | Yechim |
|---|---|
| `[XATO] Python 3.11 yoki undan yangi versiya topilmadi` | 1-qadamni takrorlang, **"Add python.exe to PATH"** ni belgilang. Kompyuterni qayta yoqing. |
| `Kutubxonalar o'rnatilmadi` | Internetni tekshiring; antivirus/proksi bloklamayotganini tekshiring; `start.bat` ni qayta ishga tushiring. |
| Brauzer ochilmadi | Qora oynadagi manzilni (`http://127.0.0.1:8000`) brauzerga qo'lda kiriting. Port band bo'lsa dastur 8001, 8002, … ni o'zi tanlaydi. |
| "Skanerlangan PDF: OCR (Tesseract) o'rnatilmagan" | 5-qadam (Tesseract) ni bajaring. |
| "PDF parol bilan himoyalangan" | Parolni olib tashlab qayta yuklang. |
| Tahlil xato bilan to'xtadi | Natija sahifasida **"To'xtagan joyidan davom ettirish"** ni bosing. Takrorlansa, qora oynadagi xabarni nusxalab yuboring. |
| Butunlay qaytadan o'rnatish kerak | `backend\.venv` papkasini o'chirib, `start.bat` ni qayta ishga tushiring (`backend\.env` va `backend\data` ga tegmang). |

---

**Eslatma:** AI-ehtimollik natijalari ehtimoliy ko'rsatkichlardir va AI mualliflikning qat'iy isboti emas.
O'xshashlik tahlili va AI-ehtimollik tahlili alohida o'lchovlardir. Tashqi o'xshashlik xizmati ulanmagan bo'lsa,
internet bo'yicha plagiat tekshiruvi o'tkazilmaydi.
