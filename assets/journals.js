// OAK (Oliy Attestatsiya Komissiyasi) ro'yxatiga tavsiya etilgan
// xalqaro jurnallar namuna ma'lumotlar bazasi.
// Eslatma: Bu namuna ro'yxat. Rasmiy va to'liq ro'yxat uchun
// OAK rasmiy saytiga (https://oak.uz) murojaat qiling.

const JOURNALS = [
  {
    id: 1,
    nomi: "Nature",
    nashriyot: "Springer Nature",
    soha: "Tabiiy fanlar",
    til: "Ingliz",
    davlat: "Buyuk Britaniya",
    issn: "0028-0836",
    indeks: ["Scopus", "Web of Science"],
    kvartil: "Q1",
    davriylik: "Haftalik",
    web: "https://www.nature.com",
    tavsif:
      "Dunyodagi eng nufuzli ko'p sohali ilmiy jurnallardan biri. Fizika, biologiya, kimyo va boshqa tabiiy fanlar bo'yicha yuqori ta'sir ko'rsatuvchi tadqiqotlarni nashr etadi.",
    talablar:
      "Maqola ingliz tilida, original tadqiqot natijalarini o'z ichiga olishi shart. Hajmi odatda 3000–5000 so'z. Tuzilishi: Abstract, Introduction, Methods, Results, Discussion.",
  },
  {
    id: 2,
    nomi: "The Lancet",
    nashriyot: "Elsevier",
    soha: "Tibbiyot",
    til: "Ingliz",
    davlat: "Buyuk Britaniya",
    issn: "0140-6736",
    indeks: ["Scopus", "Web of Science", "PubMed"],
    kvartil: "Q1",
    davriylik: "Haftalik",
    web: "https://www.thelancet.com",
    tavsif:
      "Tibbiyot sohasidagi eng obro'li jurnallardan biri. Klinik tadqiqotlar, sog'liqni saqlash siyosati va global tibbiyot masalalarini yoritadi.",
    talablar:
      "Klinik tadqiqotlar uchun ro'yxatdan o'tish (registration) talab qilinadi. IMRAD tuzilishi, etik komissiya tasdig'i shart.",
  },
  {
    id: 3,
    nomi: "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    nashriyot: "IEEE",
    soha: "Axborot texnologiyalari",
    til: "Ingliz",
    davlat: "AQSH",
    issn: "0162-8828",
    indeks: ["Scopus", "Web of Science", "IEEE Xplore"],
    kvartil: "Q1",
    davriylik: "Oylik",
    web: "https://www.computer.org/csdl/journal/tp",
    tavsif:
      "Sun'iy intellekt, kompyuter ko'rishi va mashinali o'qitish bo'yicha yetakchi xalqaro jurnal.",
    talablar:
      "Maqola IEEE shabloni (LaTeX/Word) bo'yicha tayyorlanadi. Yangi algoritm yoki yondashuv, eksperimental natijalar va taqqoslash talab qilinadi.",
  },
  {
    id: 4,
    nomi: "Journal of Cleaner Production",
    nashriyot: "Elsevier",
    soha: "Ekologiya va energetika",
    til: "Ingliz",
    davlat: "Niderlandiya",
    issn: "0959-6526",
    indeks: ["Scopus", "Web of Science"],
    kvartil: "Q1",
    davriylik: "Oylik",
    web: "https://www.sciencedirect.com/journal/journal-of-cleaner-production",
    tavsif:
      "Barqaror ishlab chiqarish, toza energiya va atrof-muhitni muhofaza qilish bo'yicha xalqaro tadqiqotlar jurnali.",
    talablar:
      "Maqola amaliy ahamiyatga ega bo'lishi, barqarorlik tamoyillariga mos kelishi kerak. Hajmi 6000–8000 so'z.",
  },
  {
    id: 5,
    nomi: "Applied Economics",
    nashriyot: "Taylor & Francis",
    soha: "Iqtisodiyot",
    til: "Ingliz",
    davlat: "Buyuk Britaniya",
    issn: "0003-6846",
    indeks: ["Scopus", "Web of Science"],
    kvartil: "Q2",
    davriylik: "Oylik",
    web: "https://www.tandfonline.com/journals/raec20",
    tavsif:
      "Amaliy iqtisodiyot, ekonometrika va moliyaviy tahlil sohasidagi tadqiqotlarni nashr etadi.",
    talablar:
      "Empirik tahlil, ma'lumotlar bazasi va ekonometrik modellashtirish talab qilinadi. APA/Harvard iqtibos uslubi.",
  },
  {
    id: 6,
    nomi: "Educational Researcher",
    nashriyot: "SAGE / AERA",
    soha: "Pedagogika",
    til: "Ingliz",
    davlat: "AQSH",
    issn: "0013-189X",
    indeks: ["Scopus", "Web of Science"],
    kvartil: "Q1",
    davriylik: "9 marta yiliga",
    web: "https://journals.sagepub.com/home/edr",
    tavsif:
      "Ta'lim sohasidagi tadqiqotlar, ta'lim siyosati va pedagogik innovatsiyalar bo'yicha xalqaro jurnal.",
    talablar:
      "Maqola ta'lim amaliyoti uchun ahamiyatli bo'lishi kerak. Tadqiqot metodologiyasi aniq bayon qilinadi.",
  },
  {
    id: 7,
    nomi: "Voprosy Filosofii (Вопросы философии)",
    nashriyot: "RAS",
    soha: "Falsafa va gumanitar fanlar",
    til: "Rus",
    davlat: "Rossiya",
    issn: "0042-8744",
    indeks: ["Scopus", "RSCI"],
    kvartil: "Q3",
    davriylik: "Oylik",
    web: "https://pq.iphras.ru",
    tavsif:
      "Falsafa, ijtimoiy fanlar va gumanitar yo'nalishdagi tadqiqotlar uchun nufuzli rus tilidagi jurnal.",
    talablar:
      "Maqola rus tilida, falsafiy tahlil va nazariy asoslarga ega bo'lishi kerak. Hajmi 0.5–1 bosma taboq.",
  },
  {
    id: 8,
    nomi: "Materials Science and Engineering: A",
    nashriyot: "Elsevier",
    soha: "Materialshunoslik",
    til: "Ingliz",
    davlat: "Shveytsariya",
    issn: "0921-5093",
    indeks: ["Scopus", "Web of Science"],
    kvartil: "Q1",
    davriylik: "Haftalik",
    web: "https://www.sciencedirect.com/journal/materials-science-and-engineering-a",
    tavsif:
      "Metallar, qotishmalar va konstruksion materiallarning xossalari bo'yicha xalqaro tadqiqot jurnali.",
    talablar:
      "Eksperimental natijalar, mikrostruktura tahlili va mexanik xossalar talab qilinadi.",
  },
  {
    id: 9,
    nomi: "Agricultural Water Management",
    nashriyot: "Elsevier",
    soha: "Qishloq xo'jaligi",
    til: "Ingliz",
    davlat: "Niderlandiya",
    issn: "0378-3774",
    indeks: ["Scopus", "Web of Science"],
    kvartil: "Q1",
    davriylik: "Oylik",
    web: "https://www.sciencedirect.com/journal/agricultural-water-management",
    tavsif:
      "Suv resurslarini boshqarish, sug'orish va qishloq xo'jaligi melioratsiyasi bo'yicha jurnal. O'zbekiston olimlari uchun dolzarb.",
    talablar:
      "Dala tajribalari, suvdan foydalanish samaradorligi tahlili va amaliy tavsiyalar talab qilinadi.",
  },
  {
    id: 10,
    nomi: "International Journal of Law and Management",
    nashriyot: "Emerald",
    soha: "Huquqshunoslik",
    til: "Ingliz",
    davlat: "Buyuk Britaniya",
    issn: "1754-243X",
    indeks: ["Scopus"],
    kvartil: "Q2",
    davriylik: "6 marta yiliga",
    web: "https://www.emerald.com/insight/publication/issn/1754-243X",
    tavsif:
      "Huquq, korporativ boshqaruv va huquqiy tartibga solish masalalari bo'yicha xalqaro jurnal.",
    talablar:
      "Huquqiy tahlil, qiyosiy huquqshunoslik va amaliy xulosalar talab qilinadi.",
  },
];

const SOHALAR = [...new Set(JOURNALS.map((j) => j.soha))].sort();
const TILLAR = [...new Set(JOURNALS.map((j) => j.til))].sort();
