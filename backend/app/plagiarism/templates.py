"""Standard academic phrases ("shablon iboralar") that are not counted as borrowing.

Such phrases appear in almost every thesis ("dolzarbligi shundaki", "ushbu ishda", "актуальность
темы", "the aim of this study") and say nothing about plagiarism. When the *templates* module is on,
their words are removed from matched (borrowed) text; they stay visible as ordinary text.
Extra phrases: TEMPLATE_PHRASES setting, separated by "|".
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.core.config import get_settings
from app.plagiarism.textnorm import canonical_words

UZ = [
    "mavzuning dolzarbligi", "dolzarbligi shundaki", "tadqiqotning dolzarbligi", "ushbu ishda", "ushbu maqolada",
    "ushbu tadqiqotda", "ushbu bitiruv malakaviy ishida", "tadqiqotning maqsadi", "tadqiqot maqsadi", "tadqiqotning vazifalari",
    "tadqiqot vazifalari", "tadqiqot obyekti", "tadqiqot ob'ekti", "tadqiqot predmeti", "tadqiqotning ilmiy yangiligi",
    "ilmiy yangiligi quyidagilardan iborat", "tadqiqot natijalarining amaliy ahamiyati", "natijalarning amaliy ahamiyati",
    "tadqiqot natijalarining ilmiy ahamiyati", "tadqiqot metodlari", "tadqiqot usullari", "ishning tuzilishi va hajmi",
    "dissertatsiyaning tuzilishi va hajmi", "dissertatsiya kirish", "xulosa va takliflar", "foydalanilgan adabiyotlar ro'yxati",
    "shuni ta'kidlash kerakki", "shuni ta'kidlash joizki", "shuni aytish mumkinki", "yuqoridagilardan kelib chiqib",
    "yuqoridagilardan xulosa qilib aytganda", "xulosa qilib aytganda", "xulosa o'rnida shuni aytish mumkinki",
    "bugungi kunda", "hozirgi kunda", "so'nggi yillarda", "shu bilan birga", "bundan tashqari", "birinchi navbatda",
    "muhim ahamiyat kasb etadi", "katta ahamiyatga ega", "alohida e'tibor qaratilmoqda", "tadqiqot natijalari shuni ko'rsatdiki",
    "olingan natijalar shuni ko'rsatadiki", "mazkur tadqiqotda", "mazkur ishda", "quyidagi xulosalarga kelindi",
]
RU = [
    "актуальность темы", "актуальность темы исследования", "актуальность исследования", "в данной работе", "в настоящей работе",
    "в данной статье", "в настоящей статье", "цель исследования", "целью исследования является", "задачи исследования",
    "объект исследования", "предмет исследования", "научная новизна", "научная новизна исследования", "практическая значимость",
    "теоретическая значимость", "методы исследования", "структура и объем работы", "структура работы", "список использованной литературы",
    "следует отметить что", "необходимо отметить что", "таким образом можно сделать вывод", "таким образом", "в заключение",
    "в настоящее время", "в последние годы", "на сегодняшний день", "кроме того", "вместе с тем", "в первую очередь",
    "имеет большое значение", "играет важную роль", "результаты исследования показали", "полученные результаты показывают",
    "можно сделать следующие выводы",
]
EN = [
    "the aim of this study", "the purpose of this study", "the aim of the research", "in this paper", "in this article",
    "in this study", "in this work", "the relevance of the topic", "research objectives", "the objectives of the study",
    "object of the research", "subject of the research", "scientific novelty", "practical significance", "theoretical significance",
    "research methods", "structure of the thesis", "list of references", "it should be noted that", "it is worth noting that",
    "in conclusion", "to sum up", "nowadays", "in recent years", "at the same time", "first of all", "plays an important role",
    "is of great importance", "the results of the study showed", "the results show that", "the following conclusions",
]


@lru_cache(maxsize=4)
def _phrases(extra: str) -> tuple[dict[str, list[tuple[str, ...]]], int]:
    by_first: dict[str, list[tuple[str, ...]]] = {}
    longest = 0
    for p in [*UZ, *RU, *EN, *[x for x in extra.split("|") if x.strip()]]:
        toks = tuple(canonical_words(p))
        if len(toks) < 2:
            continue
        by_first.setdefault(toks[0], []).append(toks)
        longest = max(longest, len(toks))
    for lst in by_first.values():
        lst.sort(key=len, reverse=True)  # longest match first
    return by_first, longest


def mask(canon: list[str]) -> tuple[np.ndarray, int]:
    """Bool mask of tokens inside standard phrases, and the number of phrase occurrences."""
    by_first, _ = _phrases(get_settings().TEMPLATE_PHRASES)
    out = np.zeros(len(canon), dtype=bool)
    count = 0
    for i, word in enumerate(canon):  # overlapping phrases ("mavzuning dolzarbligi" + "dolzarbligi shundaki") all count
        hit = next((p for p in by_first.get(word, ()) if tuple(canon[i : i + len(p)]) == p), None)
        if hit:
            out[i : i + len(hit)] = True
            count += 1
    return out, count
