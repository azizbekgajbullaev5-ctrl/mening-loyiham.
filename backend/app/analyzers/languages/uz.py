"""Uzbek (Latin script) profile.

Calibration caveat: there is no public, validated corpus of human vs.
AI-generated Uzbek academic prose. Baselines below are heuristic, and the
local detector therefore never reports HIGH confidence for Uzbek.
Some phrases that are formulaic in English translations ("bugungi kunda") are
extremely common in genuine Uzbek academic writing and are deliberately NOT
treated as AI-like markers.
"""
from app.analyzers.languages.base import DEFAULT_BASELINES, FeatureBaseline, LanguageProfile

_STOP = """
va bilan uchun bu u ham esa lekin ammo biroq yoki bo'lib bo'ladi bo'lgan hisoblanadi kabi deb edi emas har bir
shu ushbu mazkur o'z bo'yicha orqali sababli tomonidan qilib qilish keyin oldin hamda ya'ni agar chunki ko'ra yana
juda eng barcha ular biz men siz nima qanday qaysi hech hamma o'sha shunday bunday endi faqat balki ekan ekanligi
bor yo'q kerak lozim mumkin etib etadi etilgan qiladi qilingan uning ularning bizning bunda unda shuning ichida
ning ga da dan ni dir hali doim yil yilda
"""

UZBEK = LanguageProfile(
    code="uz",
    name="O'zbek (lotin)",
    script="latin",
    max_confidence="medium",
    reliability_note=(
        "O'zbek tili uchun tasdiqlangan AI-matn korpusi mavjud emas; lokal baholash evristik "
        "va ishonchlilik darajasi 'O'rta'dan oshmaydi."
    ),
    stopwords=frozenset(_STOP.split()),
    transitions=frozenset(
        {
            "shuningdek", "bundan tashqari", "shu bilan birga", "biroq", "ammo", "lekin", "demak",
            "xulosa qilib aytganda", "natijada", "birinchidan", "ikkinchidan", "uchinchidan", "avvalo",
            "jumladan", "aksincha", "shunday qilib", "qolaversa", "ta'kidlash joizki", "shu sababli",
            "shuning uchun", "umuman olganda", "binobarin", "yakuniy", "yakunda", "eng muhimi",
            "shu nuqtai nazardan", "boshqacha aytganda", "o'z navbatida", "qo'shimcha ravishda",
        }
    ),
    generic_phrases=(
        "muhim ahamiyat kasb etadi", "muhim ahamiyatga ega", "alohida ahamiyatga ega", "katta ahamiyatga ega",
        "muhim rol o'ynaydi", "hal qiluvchi rol o'ynaydi", "muhim o'rin tutadi", "alohida o'rin tutadi",
        "shuni ta'kidlash kerakki", "shuni ta'kidlash joizki", "ta'kidlash lozimki", "ta'kidlash joizki",
        "zamonaviy dunyoda", "globallashuv sharoitida", "keng qamrovli", "kompleks yondashuv",
        "yangi imkoniyatlar ochib beradi", "yangi imkoniyatlar yaratadi", "samaradorligini oshirishga xizmat qiladi",
        "dolzarb masalalardan biri hisoblanadi", "muhim omil hisoblanadi", "yangi bosqichga ko'taradi",
        "barqaror rivojlanishini ta'minlaydi", "xulosa qilib aytganda", "salmoqli hissa qo'shadi",
        "keng ko'lamli", "ajralmas qismi hisoblanadi", "innovatsion yondashuv", "muhim vazifalardan biri",
        "tizimli yondashuv", "chuqur tahlil qilish", "muhim ahamiyatga ega ekanligini", "yaxlit yondashuv",
        "ko'p qirrali", "samarali vosita hisoblanadi", "asosiy omillardan biri",
    ),
    qualifiers=(
        "samarali", "innovatsion", "keng qamrov", "muhim", "dolzarb", "zamonaviy", "turli", "xilma-xil",
        "kompleks", "tizimli", "yaxlit", "chuqur", "salmoqli", "strategik",
    ),
    conjunction_and="va",
    formal_suffix_regex=r"(?:lik|lash|lashtirish|ish|uv|iya|siya|tsiya|chilik|garlik)(?:lar)?(?:i|si|ning|ni|ga|da|dan|ini|ining|iga|ida|idan|imiz)?$",
    abbreviations=("h.k.", "va b.", "b.", "y.", "yy.", "prof.", "akad.", "t.", "s.", "sh.", "m.", "rasm.", "jadv.", "bet.", "no."),
    chapter_patterns=(
        r"^\s*([IVXLC]+|\d+)\s*[-–.]?\s*bob\b",
        r"^\s*bob\s+([IVXLC]+|\d+)\b",
        r"^\s*(birinchi|ikkinchi|uchinchi|to'rtinchi|beshinchi|oltinchi)\s+bob\b",
    ),
    section_keywords={
        "toc": ("mundarija",),
        "abstract": ("annotatsiya", "referat", "abstrakt", "dissertatsiya annotatsiyasi"),
        "keywords": ("kalit so'zlar", "tayanch so'zlar", "tayanch iboralar"),
        "introduction": ("kirish",),
        "literature_review": ("adabiyotlar tahlili", "adabiyotlar sharhi", "mavzuga oid adabiyotlar tahlili"),
        "methodology": (
            "tadqiqot metodologiyasi", "metodologiya", "tadqiqot metodlari", "tadqiqot usullari",
            "material va metodlar", "tadqiqot materiallari va usullari",
        ),
        "results": ("natijalar", "tadqiqot natijalari", "tahlil va natijalar"),
        "discussion": ("muhokama", "natijalar muhokamasi"),
        "conclusion": ("xulosa", "xulosalar", "umumiy xulosalar", "xulosa va takliflar", "xulosa va tavsiyalar"),
        "references": (
            "foydalanilgan adabiyotlar ro'yxati", "foydalanilgan adabiyotlar", "adabiyotlar ro'yxati",
            "adabiyotlar", "foydalanilgan manbalar",
        ),
        "appendix": ("ilova", "ilovalar"),
    },
    academic_words=frozenset(
        "tahlil tadqiqot usul metod nazariya gipoteza natija xulosa omil jarayon tizim tuzilma samaradorlik "
        "ko'rsatkich ma'lumot empirik konsepsiya yondashuv model baholash mezon tamoyil tajriba statistik "
        "o'zgaruvchi korrelyatsiya dalil manba ilmiy".split()
    ),
    baselines={
        **DEFAULT_BASELINES,
        # Uzbek is agglutinative: nominalising suffixes and "muhim" are very frequent in human text.
        "formalization_density": FeatureBaseline(15.0, 4.0, +1),
        "qualifier_density": FeatureBaseline(3.0, 1.2, +1),
        "generic_phrase_density": FeatureBaseline(1.0, 0.5, +1),
        "transition_start_ratio": FeatureBaseline(0.20, 0.08, +1),
    },
    long_sentence_words=35,
)
