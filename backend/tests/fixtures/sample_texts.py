"""Synthetic sample texts (uz / ru / en) used by tests and sample documents.

IMPORTANT: every text here is synthetic and written for testing. Names,
numbers, and references are invented and illustrative only. "human_style"
passages imitate typical human academic prose (varied rhythm, concrete
details, citations); "ai_style" passages imitate typical generic LLM prose
(uniform rhythm, formulaic phrasing, many discourse markers). They are NOT a
validated corpus and must not be used to claim detector accuracy.
"""

UZ = {
    "title": "RAQAMLI TA'LIM MUHITIDA TALABALARNING MUSTAQIL ISHINI TASHKIL ETISH (namuna, sintetik matn)",
    "abstract": (
        "Ushbu namunaviy ishda Toshkent shahridagi uchta oliy ta'lim muassasasida 2021–2023 yillarda o'tkazilgan "
        "so'rovnoma natijalari asosida talabalarning mustaqil ishini raqamli platformalar yordamida tashkil etish "
        "masalasi ko'rib chiqiladi. So'rovnomada 412 nafar talaba ishtirok etdi."
    ),
    "keywords": "Kalit so'zlar: mustaqil ta'lim, raqamli platforma, Moodle, baholash, talaba faolligi.",
    "human": [
        (
            "Mustaqil ish soatlari o'quv rejasida umumiy yuklamaning qariyb 40 foizini tashkil qiladi, lekin amalda bu "
            "soatlar ko'pincha nazoratsiz qoladi. 2022 yil kuzgi semestrda biz kuzatgan 18 ta guruhdan faqat 7 tasida "
            "topshiriqlar muddatida tekshirilgan. Qolgan guruhlarda o'qituvchilar topshiriqlarni semestr oxirida, "
            "yakuniy nazorat oldidan bir yo'la qabul qilishgan. Bu holat A. Karimovning [3, 45-b.] ta'kidlaganidek, "
            "mustaqil ishni rasmiyatchilikka aylantiradi. Nega shunday? Birinchi sabab – o'qituvchi yuklamasi: bitta "
            "dotsentga o'rtacha 96 nafar talaba to'g'ri keladi. Ikkinchi sabab texnik edi, chunki Moodle tizimi 2021 "
            "yilgacha faqat ikki fakultetda ishlagan."
        ),
        (
            "So'rovnoma savollari R. Laykert shkalasi (1–5) asosida tuzildi va dastlab 36 nafar talabada sinovdan "
            "o'tkazildi. Sinovdan keyin uchta savol olib tashlandi: talabalar ularni bir xil tushunmagan edi. Masalan, "
            "\"platformadan foydalanish qulayligi\" iborasini ba'zilar internet tezligi deb, boshqalar esa interfeys "
            "deb talqin qilgan. Yakuniy anketa 24 savoldan iborat bo'ldi. Kronbax alfa koeffitsienti 0,81 ga teng "
            "chiqdi, bu ichki muvofiqlikni qoniqarli deb hisoblashga imkon beradi [7]. Ma'lumotlar SPSS 26 dasturida "
            "qayta ishlandi; guruhlar orasidagi farqlar Manna–Uitni mezoni bilan tekshirildi."
        ),
        (
            "Natijalar kutilganidan biroz boshqacha chiqdi. Raqamli platformada ishlagan talabalarning o'rtacha bahosi "
            "3,9 ball, an'anaviy guruhlarda esa 3,7 ball bo'ldi – farq statistik jihatdan ahamiyatli emas (p = 0,12). "
            "Ammo topshiriqni muddatida topshirish ko'rsatkichi keskin farq qildi: 78 foizga qarshi 41 foiz. Demak, "
            "platforma bilimni emas, balki intizomni o'zgartirgan. Suhbatlarda talabalar eslatma xabarlari va "
            "muddatlarni ko'rinib turishini eng foydali deb aytishdi. Bir talaba shunday dedi: \"Muddatni ko'rib "
            "turganimda, kechiktirishga uyalaman\"."
        ),
        (
            "Tadqiqotning cheklovlari ham bor. Tanlanma faqat Toshkentdagi muassasalarni qamrab oladi, viloyat "
            "oliygohlarida internet sifati boshqacha bo'lishi mumkin. Bundan tashqari, guruhlar tasodifiy tanlanmagan: "
            "platformani qo'llagan o'qituvchilar, ehtimol, dastlabdan faolroq bo'lgan. Shu sababli natijalarni "
            "umumlashtirishda ehtiyot bo'lish kerak. Keyingi bosqichda Samarqand va Nukusdagi ikki universitetni qo'shib, "
            "kvazi-eksperimental dizaynni qo'llash rejalashtirilgan."
        ),
    ],
    "ai": [
        (
            "Bugungi globallashuv sharoitida raqamli ta'lim texnologiyalari ta'lim tizimining ajralmas qismi hisoblanadi. "
            "Shuni ta'kidlash kerakki, raqamli platformalar talabalarning mustaqil ishini tashkil etishda muhim rol "
            "o'ynaydi. Shu bilan birga, ular ta'lim jarayonining samaradorligini oshirishga xizmat qiladi. Bundan "
            "tashqari, raqamli vositalar o'qituvchi va talaba o'rtasidagi hamkorlikni yangi bosqichga ko'taradi. "
            "Shuningdek, bu yondashuv ta'lim sifatini oshirishda muhim ahamiyat kasb etadi. Natijada, zamonaviy ta'lim "
            "muhiti yanada samarali va innovatsion tus oladi."
        ),
        (
            "Raqamli ta'lim muhitida mustaqil ishni tashkil etish kompleks yondashuvni talab qiladi. Birinchidan, "
            "o'quv materiallari tizimli va keng qamrovli bo'lishi lozim. Ikkinchidan, baholash mezonlari aniq va "
            "shaffof bo'lishi muhim ahamiyatga ega. Uchinchidan, talabalarning faolligini oshirish uchun innovatsion "
            "usullardan foydalanish zarur. Shu bilan birga, o'qituvchilarning raqamli kompetensiyasi ham muhim o'rin "
            "tutadi. Xulosa qilib aytganda, kompleks yondashuv ta'lim sifatini yangi bosqichga ko'taradi."
        ),
        (
            "Shuni ta'kidlash joizki, raqamli platformalar talabalarga yangi imkoniyatlar ochib beradi. Ular o'quv "
            "materiallariga istalgan vaqtda murojaat qilish imkonini yaratadi. Shu bilan birga, ular mustaqil fikrlash "
            "ko'nikmalarini rivojlantirishga xizmat qiladi. Bundan tashqari, raqamli vositalar ta'lim jarayonini "
            "shaxsiylashtirishda muhim rol o'ynaydi. Shuningdek, ular talabalarning motivatsiyasini oshirishda alohida "
            "ahamiyatga ega. Natijada, ta'lim jarayoni yanada samarali, innovatsion va zamonaviy tus oladi."
        ),
        (
            "Xulosa qilib aytganda, raqamli ta'lim muhitida mustaqil ishni tashkil etish dolzarb masalalardan biri "
            "hisoblanadi. Shuni ta'kidlash kerakki, bu jarayon kompleks yondashuvni talab qiladi. Shu bilan birga, "
            "raqamli platformalar ta'lim sifatini oshirishda hal qiluvchi rol o'ynaydi. Bundan tashqari, ular "
            "talabalarning mustaqil faoliyatini samarali tashkil etishga xizmat qiladi. Shuningdek, bu yondashuv "
            "ta'lim tizimining barqaror rivojlanishini ta'minlaydi. Natijada, zamonaviy ta'lim yangi bosqichga ko'tariladi."
        ),
    ],
    "references": [
        "1. Abdullayeva N. Oliy ta'limda mustaqil ish. – Toshkent: Fan, 2019. – 184 b. (namuna)",
        "2. Bekmurodov S. Raqamli pedagogika asoslari. – Toshkent, 2020. – 212 b. (namuna)",
        "3. Karimov A. Talabalar mustaqil ishini nazorat qilish // Ta'lim va innovatsiya. – 2021. – №4. – B. 40–47. (namuna)",
        "4. Rashidova D. Masofaviy ta'lim platformalari. – Samarqand, 2022. – 150 b. (namuna)",
        "5. Tursunov B. Baholash mezonlari. – Toshkent, 2018. (namuna)",
        "6. Yusupov O. Moodle tizimida kurs yaratish. – Toshkent, 2021. – 96 b. (namuna)",
        "7. Cronbach L. Coefficient alpha and the internal structure of tests // Psychometrika. – 1951. – Vol. 16. – P. 297–334.",
    ],
    "headings": {
        "abstract": "ANNOTATSIYA",
        "intro": "KIRISH",
        "ch1": "I BOB. MUSTAQIL TA'LIMNI TASHKIL ETISHNING NAZARIY ASOSLARI",
        "s11": "1.1. Mustaqil ish tushunchasi va uning o'quv rejadagi o'rni",
        "s12": "1.2. Raqamli platformalarning imkoniyatlari",
        "ch2": "II BOB. TAJRIBA-SINOV ISHLARI VA NATIJALAR",
        "s21": "2.1. Tadqiqot metodikasi",
        "s22": "2.2. Natijalar tahlili",
        "conclusion": "XULOSA",
        "references": "FOYDALANILGAN ADABIYOTLAR RO'YXATI",
    },
}

RU = {
    "title": "ОРГАНИЗАЦИЯ САМОСТОЯТЕЛЬНОЙ РАБОТЫ СТУДЕНТОВ В ЦИФРОВОЙ СРЕДЕ (образец, синтетический текст)",
    "abstract": (
        "В образце рассматриваются результаты анкетирования 412 студентов трёх вузов Ташкента, проведённого в "
        "2021–2023 гг., и влияние цифровых платформ на выполнение самостоятельной работы."
    ),
    "keywords": "Ключевые слова: самостоятельная работа, цифровая платформа, Moodle, оценивание.",
    "human": [
        (
            "На самостоятельную работу по учебному плану отводится почти 40% общей нагрузки, однако на практике эти "
            "часы часто остаются без контроля. Осенью 2022 г. из 18 наблюдаемых групп лишь в 7 задания проверялись в "
            "срок. В остальных преподаватели принимали работы разом, накануне итогового контроля. Как отмечает "
            "А. Каримов [3, с. 45], это превращает самостоятельную работу в формальность. Почему так происходит? "
            "Первая причина – нагрузка: на одного доцента приходится в среднем 96 студентов. Вторая – техническая: "
            "до 2021 г. система Moodle работала только на двух факультетах."
        ),
        (
            "Анкета строилась на шкале Лайкерта (1–5) и сначала была опробована на 36 студентах. После пилотажа три "
            "вопроса пришлось убрать: студенты понимали их по-разному. Например, выражение «удобство платформы» одни "
            "связывали со скоростью интернета, другие – с интерфейсом. В итоговой анкете осталось 24 вопроса. "
            "Коэффициент альфа Кронбаха составил 0,81, что позволяет считать внутреннюю согласованность приемлемой [7]. "
            "Данные обрабатывались в SPSS 26; различия между группами проверялись критерием Манна–Уитни."
        ),
        (
            "Результаты оказались несколько неожиданными. Средний балл студентов, работавших на платформе, составил "
            "3,9, в традиционных группах – 3,7; разница статистически незначима (p = 0,12). Зато доля работ, сданных в "
            "срок, различалась резко: 78% против 41%. Иначе говоря, платформа изменила не знания, а дисциплину. В "
            "интервью студенты чаще всего называли полезными напоминания и видимые сроки. Одна студентка сказала: "
            "«Когда я вижу дедлайн, мне стыдно откладывать»."
        ),
        (
            "У исследования есть ограничения. Выборка охватывает только ташкентские вузы, а в регионах качество "
            "интернета может быть иным. Кроме того, группы формировались не случайно: преподаватели, внедрившие "
            "платформу, вероятно, изначально были активнее. Поэтому обобщать выводы следует осторожно. На следующем "
            "этапе планируется добавить два университета в Самарканде и Нукусе и применить квазиэкспериментальный дизайн."
        ),
    ],
    "ai": [
        (
            "В современном мире цифровые образовательные технологии являются неотъемлемой частью системы образования. "
            "Важно отметить, что цифровые платформы играют ключевую роль в организации самостоятельной работы "
            "студентов. Кроме того, они способствуют повышению эффективности образовательного процесса. Более того, "
            "цифровые инструменты открывают новые возможности для взаимодействия преподавателя и студента. Таким "
            "образом, данный подход имеет важное значение для повышения качества образования. В результате "
            "современная образовательная среда становится более эффективной и инновационной."
        ),
        (
            "Организация самостоятельной работы в цифровой среде требует комплексного подхода. Во-первых, учебные "
            "материалы должны быть системными и всесторонними. Во-вторых, критерии оценивания должны быть чёткими и "
            "прозрачными. В-третьих, для повышения активности студентов необходимо использовать инновационные методы. "
            "Кроме того, цифровая компетентность преподавателей играет важную роль. Таким образом, комплексный подход "
            "открывает новые возможности для повышения качества образования."
        ),
        (
            "Следует отметить, что цифровые платформы открывают новые возможности для студентов. Они обеспечивают "
            "доступ к учебным материалам в любое время. Кроме того, они способствуют развитию навыков самостоятельного "
            "мышления. Более того, цифровые инструменты играют ключевую роль в персонализации обучения. Также они "
            "имеют важное значение для повышения мотивации студентов. Таким образом, образовательный процесс "
            "становится более эффективным, инновационным и современным."
        ),
        (
            "Подводя итог, можно сделать вывод, что организация самостоятельной работы в цифровой среде является "
            "одним из важнейших направлений развития образования. Важно отметить, что данный процесс требует "
            "комплексного подхода. Кроме того, цифровые платформы играют решающую роль в повышении качества "
            "образования. Более того, они способствуют эффективной организации самостоятельной деятельности. Таким "
            "образом, данный подход служит основой устойчивого развития системы образования."
        ),
    ],
    "references": [
        "1. Абдуллаева Н. Самостоятельная работа в вузе. – Ташкент: Фан, 2019. – 184 с. (образец)",
        "2. Бекмуродов С. Основы цифровой педагогики. – Ташкент, 2020. – 212 с. (образец)",
        "3. Каримов А. Контроль самостоятельной работы студентов // Образование и инновации. – 2021. – № 4. – С. 40–47. (образец)",
        "4. Рашидова Д. Платформы дистанционного обучения. – Самарканд, 2022. – 150 с. (образец)",
        "5. Турсунов Б. Критерии оценивания. – Ташкент, 2018. (образец)",
        "6. Юсупов О. Создание курса в Moodle. – Ташкент, 2021. – 96 с. (образец)",
        "7. Cronbach L. Coefficient alpha and the internal structure of tests // Psychometrika. – 1951. – Vol. 16. – P. 297–334.",
    ],
    "headings": {
        "abstract": "АННОТАЦИЯ",
        "intro": "ВВЕДЕНИЕ",
        "ch1": "ГЛАВА I. ТЕОРЕТИЧЕСКИЕ ОСНОВЫ САМОСТОЯТЕЛЬНОЙ РАБОТЫ",
        "s11": "1.1. Понятие самостоятельной работы и её место в учебном плане",
        "s12": "1.2. Возможности цифровых платформ",
        "ch2": "ГЛАВА II. ОПЫТНО-ЭКСПЕРИМЕНТАЛЬНАЯ РАБОТА",
        "s21": "2.1. Методика исследования",
        "s22": "2.2. Анализ результатов",
        "conclusion": "ЗАКЛЮЧЕНИЕ",
        "references": "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
    },
}

EN = {
    "title": "ORGANISING STUDENTS' INDEPENDENT WORK IN A DIGITAL LEARNING ENVIRONMENT (sample, synthetic text)",
    "abstract": (
        "This sample discusses a 2021–2023 survey of 412 students at three universities in Tashkent and how digital "
        "platforms affected the completion of independent coursework."
    ),
    "keywords": "Keywords: independent study, digital platform, Moodle, assessment.",
    "human": [
        (
            "Independent study accounts for almost 40% of the credit load in the curriculum, yet in practice these "
            "hours often go unsupervised. In autumn 2022, only 7 of the 18 groups we observed had assignments marked "
            "on time. Elsewhere, lecturers collected everything at once, the week before the final exam. As Karimov "
            "[3, p. 45] points out, this turns independent study into a formality. Why does it happen? The first reason "
            "is workload: one associate professor supervises 96 students on average. The second was technical, since "
            "until 2021 Moodle ran in only two faculties."
        ),
        (
            "The questionnaire used a five-point Likert scale and was piloted with 36 students. After the pilot we "
            "dropped three items because students read them differently. For instance, \"ease of using the platform\" "
            "meant internet speed to some respondents and the interface to others. The final instrument had 24 items. "
            "Cronbach's alpha was 0.81, which we took as acceptable internal consistency [7]. Data were processed in "
            "SPSS 26, and group differences were tested with the Mann–Whitney U test."
        ),
        (
            "The results were not quite what we expected. Students who worked on the platform averaged 3.9 points, "
            "against 3.7 in traditional groups; the gap is not significant (p = 0.12). On-time submission, however, "
            "differed sharply: 78% versus 41%. In other words, the platform changed discipline rather than knowledge. "
            "In interviews, students singled out reminders and visible deadlines as the most useful features. One "
            "student put it bluntly: \"When I can see the deadline, I'm embarrassed to put it off.\""
        ),
        (
            "The study has limitations. The sample covers only universities in Tashkent, and internet quality in the "
            "regions may differ. Groups were also not randomised: lecturers who adopted the platform were probably "
            "more active to begin with. Our findings should therefore be generalised with care. The next stage will "
            "add two universities in Samarkand and Nukus and use a quasi-experimental design."
        ),
    ],
    "ai": [
        (
            "In today's rapidly evolving world, digital learning technologies have become an integral part of the "
            "education system. It is important to note that digital platforms play a crucial role in organising "
            "students' independent work. Moreover, they contribute to enhancing the effectiveness of the learning "
            "process. Furthermore, digital tools unlock new opportunities for collaboration between teachers and "
            "students. Additionally, this approach plays a pivotal role in improving the quality of education. As a "
            "result, the modern learning environment becomes more effective, innovative, and dynamic."
        ),
        (
            "Organising independent work in a digital environment requires a holistic approach. Firstly, learning "
            "materials should be systematic and comprehensive. Secondly, assessment criteria should be clear and "
            "transparent. Thirdly, innovative methods are essential to foster student engagement. Moreover, teachers' "
            "digital competence plays a vital role in this process. Ultimately, a comprehensive approach paves the way "
            "for a significant improvement in the quality of education."
        ),
        (
            "It is worth noting that digital platforms offer students a wide range of new opportunities. They provide "
            "access to learning materials at any time. Furthermore, they foster the development of independent "
            "thinking skills. Moreover, digital tools play a key role in personalising the learning experience. "
            "Additionally, they are essential for enhancing students' motivation. As a result, the learning process "
            "becomes more effective, innovative, and engaging."
        ),
        (
            "In conclusion, organising independent work in a digital environment is a multifaceted and crucial "
            "challenge. It is important to note that this process requires a comprehensive approach. Furthermore, "
            "digital platforms play a pivotal role in enhancing the quality of education. Moreover, they help to "
            "organise students' independent activities seamlessly. Ultimately, this approach paves the way for the "
            "sustainable development of the education system."
        ),
    ],
    "references": [
        "1. Abdullayeva N. Independent Study in Higher Education. Tashkent: Fan, 2019. 184 p. (sample)",
        "2. Bekmurodov S. Foundations of Digital Pedagogy. Tashkent, 2020. 212 p. (sample)",
        "3. Karimov A. Monitoring students' independent work. Education and Innovation, 2021, no. 4, pp. 40–47. (sample)",
        "4. Rashidova D. Distance Learning Platforms. Samarkand, 2022. 150 p. (sample)",
        "5. Tursunov B. Assessment Criteria. Tashkent, 2018. (sample)",
        "6. Yusupov O. Building a Course in Moodle. Tashkent, 2021. 96 p. (sample)",
        "7. Cronbach L. Coefficient alpha and the internal structure of tests. Psychometrika, 1951, 16, 297–334.",
    ],
    "headings": {
        "abstract": "ABSTRACT",
        "intro": "INTRODUCTION",
        "ch1": "CHAPTER I. THEORETICAL FOUNDATIONS OF INDEPENDENT STUDY",
        "s11": "1.1. The concept of independent work and its place in the curriculum",
        "s12": "1.2. Capabilities of digital platforms",
        "ch2": "CHAPTER II. EXPERIMENTAL WORK AND RESULTS",
        "s21": "2.1. Research methodology",
        "s22": "2.2. Analysis of results",
        "conclusion": "CONCLUSION",
        "references": "REFERENCES",
    },
}

SAMPLES = {"uz": UZ, "ru": RU, "en": EN}


def dissertation_outline(lang: str) -> list[tuple[str, str]]:
    """Return [(kind, text)] where kind is 'title'|'heading'|'para'.

    Layout: human-style intro/1.1/2.1, AI-style 1.2/2.2/conclusion, and one
    paragraph deliberately repeated (2.2 re-uses a 1.1 paragraph) so the
    similarity module has something real to find.
    """
    s = SAMPLES[lang]
    h = s["headings"]
    out: list[tuple[str, str]] = [("title", s["title"])]
    out += [("heading", h["abstract"]), ("para", s["abstract"]), ("para", s["keywords"])]
    out += [("heading", h["intro"]), ("para", s["human"][0]), ("para", s["human"][3])]
    out += [("heading", h["ch1"]), ("heading", h["s11"]), ("para", s["human"][0]), ("para", s["human"][1])]
    out += [("heading", h["s12"]), ("para", s["ai"][0]), ("para", s["ai"][1])]
    out += [("heading", h["ch2"]), ("heading", h["s21"]), ("para", s["human"][1]), ("para", s["human"][2])]
    out += [("heading", h["s22"]), ("para", s["ai"][2]), ("para", s["human"][0])]
    out += [("heading", h["conclusion"]), ("para", s["ai"][3])]
    out += [("heading", h["references"])] + [("para", r) for r in s["references"]]
    return out
