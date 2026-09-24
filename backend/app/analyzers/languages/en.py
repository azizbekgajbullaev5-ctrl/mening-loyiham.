"""English profile."""
from app.analyzers.languages.base import DEFAULT_BASELINES, LanguageProfile

_STOP = """
a about above after again against all am an and any are as at be because been before being below between both but
by can could did do does doing down during each few for from further had has have having he her here hers herself
him himself his how i if in into is it its itself just me more most my myself no nor not now of off on once only or
other our ours ourselves out over own same she should so some such than that the their theirs them themselves then
there these they this those through to too under until up very was we were what when where which while who whom why
will with would you your yours yourself yourselves also may might must shall however thus
"""

ENGLISH = LanguageProfile(
    code="en",
    name="English",
    script="latin",
    max_confidence="high",
    reliability_note="Heuristic thresholds; calibrate on a labelled corpus before high-stakes use.",
    stopwords=frozenset(_STOP.split()),
    transitions=frozenset(
        {
            "moreover", "furthermore", "additionally", "in addition", "however", "therefore", "thus",
            "consequently", "overall", "in conclusion", "ultimately", "notably", "importantly", "firstly",
            "secondly", "thirdly", "finally", "as a result", "on the other hand", "in contrast", "similarly",
            "likewise", "nevertheless", "hence", "in summary", "to summarize", "to sum up", "in essence",
            "additionally", "equally important", "by contrast",
        }
    ),
    generic_phrases=(
        "it is important to note", "it is worth noting", "it should be noted", "plays a crucial role",
        "plays a vital role", "plays a pivotal role", "plays a key role", "plays an important role",
        "in today's rapidly", "in today's world", "rapidly evolving", "ever-evolving", "a wide range of",
        "delve into", "delves into", "shed light on", "sheds light on", "navigate the complexities",
        "the complexities of", "multifaceted", "a comprehensive understanding", "comprehensive analysis",
        "holistic approach", "paving the way", "pave the way", "a testament to", "in the realm of",
        "underscores the importance", "highlights the importance", "valuable insights", "in conclusion",
        "tapestry", "the landscape of", "seamlessly", "harness the power", "unlock the potential",
        "cutting-edge", "robust framework", "it is essential to", "a significant impact on", "various aspects",
        "a crucial aspect", "serves as a", "in the context of today's", "fostering", "ensuring that",
        "offers a nuanced", "nuanced understanding", "key takeaway", "stands as a",
    ),
    qualifiers=(
        "various", "numerous", "crucial", "vital", "essential", "pivotal", "comprehensive", "innovative",
        "robust", "seamless", "profound", "dynamic", "diverse", "significant", "key", "transformative",
        "invaluable", "holistic", "nuanced",
    ),
    conjunction_and="and",
    formal_suffix_regex=r"(?:tion|tions|ment|ments|ity|ities|ness|ance|ence|ization|isation)$",
    abbreviations=(
        "e.g.", "i.e.", "et al.", "fig.", "eq.", "vol.", "no.", "pp.", "p.", "dr.", "mr.", "mrs.", "ms.", "vs.",
        "etc.", "cf.", "ed.", "eds.", "approx.", "ch.", "sec.", "tab.",
    ),
    chapter_patterns=(r"^\s*chapter\s+([IVXLC]+|\d+|one|two|three|four|five|six|seven)\b",),
    section_keywords={
        "toc": ("table of contents", "contents"),
        "abstract": ("abstract", "summary"),
        "keywords": ("keywords", "key words"),
        "introduction": ("introduction",),
        "literature_review": ("literature review", "review of literature", "related work", "background"),
        "methodology": ("methodology", "methods", "materials and methods", "research methodology", "research design"),
        "results": ("results", "findings"),
        "discussion": ("discussion", "results and discussion"),
        "conclusion": ("conclusion", "conclusions", "concluding remarks"),
        "references": ("references", "bibliography", "works cited", "literature cited"),
        "appendix": ("appendix", "appendices"),
    },
    academic_words=frozenset(
        "analysis approach assess concept data method research significant theory hypothesis variable framework "
        "evidence empirical methodology context factor structure process indicate interpret establish derive "
        "estimate correlation sample statistical".split()
    ),
    baselines=dict(DEFAULT_BASELINES),
    long_sentence_words=40,
)
