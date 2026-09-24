import io
import shutil
import zipfile

import pytest

from app.analyzers.languages.registry import detect_distribution, detect_language
from app.document_processing.extractors import decode_text, extract
from app.document_processing.segmentation import MAX_PASSAGE_WORDS, segment
from app.document_processing.structure import build_sections, detect_headings
from app.document_processing.types import Block, ExtractionError
from app.document_processing.validation import ValidationError, sanitize_filename, validate_upload


# ---------------------------------------------------------------- parsing
@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_docx_parsing_preserves_structure_pages_and_tables(samples, lang):
    doc = extract("docx", samples[f"{lang}.docx"])
    kinds = {b.kind for b in doc.blocks}
    assert {"heading", "paragraph", "table"} <= kinds
    assert doc.pages_estimated is False  # real page breaks are present
    assert doc.page_count >= 6
    pages = [b.page for b in doc.blocks]
    assert pages == sorted(pages) and pages[0] == 1 and pages[-1] > 1
    table = next(b for b in doc.blocks if b.kind == "table")
    assert "|" in table.text and "78" in table.text


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_pdf_parsing_keeps_page_numbers_and_strips_page_footer(samples, lang):
    doc = extract("pdf", samples[f"{lang}.pdf"])
    assert doc.page_count >= 6 and not doc.is_scanned
    assert all(b.page is not None for b in doc.blocks)
    assert not any(b.text.strip().isdigit() for b in doc.blocks), "page-number footers must be removed"
    assert any(b.kind == "heading" for b in doc.blocks)


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_txt_parsing(samples, lang):
    doc = extract("txt", samples[f"{lang}.txt"])
    assert len(doc.blocks) > 20
    assert doc.pages_estimated


def test_txt_legacy_cp1251_encoding():
    text = "Введение\n\nНаучный текст на русском языке для проверки кодировки."
    assert decode_text(text.encode("cp1251")) == text


def test_txt_form_feed_pages():
    doc = extract("txt", "Page one text here.\fPage two text here.".encode())
    assert doc.page_count == 2 and not doc.pages_estimated
    assert [b.page for b in doc.blocks] == [1, 2]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_scanned_pdf_is_detected_and_ocrd(samples):
    doc = extract("pdf", samples["en_scanned.pdf"])
    assert doc.is_scanned and doc.ocr_used
    text = " ".join(b.text for b in doc.blocks).lower()
    assert "abstract" in text and "students" in text
    assert all(b.is_ocr for b in doc.blocks)


def test_scanned_pdf_without_ocr_reports_clearly(samples, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "OCR_ENABLED", False)
    with pytest.raises(ExtractionError) as e:
        extract("pdf", samples["en_scanned.pdf"])
    assert e.value.code == "scanned_no_ocr"


def test_empty_text_document_rejected():
    with pytest.raises(ExtractionError):
        extract("txt", b"   \n\n  ")


# ---------------------------------------------------------------- validation
def test_validation_accepts_valid_files(samples):
    assert validate_upload("a.docx", samples["uz.docx"]).file_type == "docx"
    assert validate_upload("a.PDF", samples["uz.pdf"]).file_type == "pdf"
    assert validate_upload("a.txt", samples["uz.txt"]).file_type == "txt"


@pytest.mark.parametrize(
    "name,data,code",
    [
        ("x.exe", b"MZ....", "unsupported_type"),
        ("x.pdf", b"PK\x03\x04 not a pdf", "bad_signature"),
        ("x.docx", b"%PDF-1.4 fake", "bad_signature"),
        ("x.txt", b"\x00\x01\x02binary", "bad_signature"),
        ("x.txt", b"", "empty_file"),
    ],
)
def test_validation_rejects_bad_files(name, data, code):
    with pytest.raises(ValidationError) as e:
        validate_upload(name, data)
    assert e.value.code == code


def test_validation_rejects_macro_docx(samples):
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(samples["en.docx"])) as src, zipfile.ZipFile(buf, "w") as dst:
        for item in src.infolist():
            dst.writestr(item, src.read(item.filename))
        dst.writestr("word/vbaProject.bin", b"macro")
    with pytest.raises(ValidationError) as e:
        validate_upload("m.docx", buf.getvalue())
    assert e.value.code == "macro_content"


def test_validation_rejects_zip_bomb(samples, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "MAX_DOCX_UNCOMPRESSED_MB", 0)
    with pytest.raises(ValidationError) as e:
        validate_upload("b.docx", samples["en.docx"])
    assert e.value.code == "zip_bomb"


def test_validation_size_limit(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "MAX_UPLOAD_MB", 0)
    with pytest.raises(ValidationError) as e:
        validate_upload("a.txt", b"hello world")
    assert e.value.code == "too_large"


def test_filename_sanitized():
    assert sanitize_filename("../../etc/passwd.txt") == "passwd.txt"
    assert "<" not in sanitize_filename("a<script>.pdf")


# ---------------------------------------------------------------- language
@pytest.mark.parametrize(
    "text,code",
    [
        ("Ushbu tadqiqotda o'zbek tilidagi ilmiy matnlarning tuzilishi tahlil qilindi va natijalar keltirildi.", "uz"),
        ("Tadqiqot natijalari shuni ko'rsatdiki, talabalarning mustaqil ishi samaradorligi oshgan.", "uz"),
        ("В данной работе рассматриваются особенности научного стиля и методы анализа текста.", "ru"),
        ("This study examines the structure of academic texts and the methods used to analyse them.", "en"),
    ],
)
def test_language_detection(text, code):
    assert detect_language(text).code == code


def test_language_detection_unsupported_uzbek_cyrillic():
    assert detect_language("Бу тадқиқотда ўзбек тилидаги илмий матнлар таҳлил қилинди.").code == "unknown"


def test_language_distribution_mixed_document():
    paras = ["This study examines academic texts and the methods used to analyse them in detail."] * 3 + [
        "В данной работе рассматриваются особенности научного стиля и методы анализа."
    ]
    dom, conf, dist = detect_distribution(paras)
    assert dom == "en" and set(dist) == {"en", "ru"} and 0 < conf <= 1


# ---------------------------------------------------------------- structure
@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
@pytest.mark.parametrize("fmt", ["docx", "pdf", "txt"])
def test_section_detection(samples, lang, fmt):
    doc = extract(fmt, samples[f"{lang}.{fmt}"])
    heads = detect_headings(doc.blocks, lang)
    kinds = [h.kind for h in heads]
    assert kinds.count("chapter") == 2
    assert kinds.count("section") == 4
    for k in ("abstract", "keywords", "introduction", "conclusion", "references"):
        assert k in kinds, (k, kinds)
    sections = build_sections(heads, len(doc.blocks))
    ch1 = next(s for s in sections if s.kind == "chapter")
    children = [s for s in sections if s.parent_order == ch1.order]
    assert [s.kind for s in children] == ["section", "section"]
    assert ch1.end > children[-1].start


def test_table_of_contents_entries_are_not_headings():
    lines = [
        "MUNDARIJA", "KIRISH ........................ 3", "I BOB. NAZARIY ASOSLAR ........ 7", "1.1. Tushuncha ........ 7",
        "KIRISH", "Matn " * 30, "I BOB. NAZARIY ASOSLAR", "1.1. Tushuncha", "Matn " * 30,
    ]
    blocks = [Block(i, t) for i, t in enumerate(lines)]
    heads = detect_headings(blocks, "uz")
    assert [(h.paragraph_index, h.kind) for h in heads] == [(0, "toc"), (4, "introduction"), (6, "chapter"), (7, "section")]


def test_numbered_sentence_is_not_a_heading():
    blocks = [Block(0, "KIRISH"), Block(1, "2.5 million students were enrolled in 2021, which is a sizeable share of the cohort and more.")]
    assert [h.kind for h in detect_headings(blocks, "en")] == ["introduction"]


# ---------------------------------------------------------------- chunking
def test_segmentation_sizes_and_provenance(samples):
    doc = extract("docx", samples["en.docx"])
    sections = build_sections(detect_headings(doc.blocks, "en"), len(doc.blocks))
    passages = segment(doc.blocks, sections)
    assert passages
    assert all(p.word_count <= MAX_PASSAGE_WORDS for p in passages)
    heading_idx = {s.start for s in sections}
    for p in passages:
        assert p.paragraph_start not in heading_idx
        assert p.page is not None and len(p.hash) == 64
    refs = [p for p in passages if p.excluded_from_ai]
    assert refs, "reference list passages must be excluded from AI scoring"


def test_long_paragraph_is_split_by_sentences():
    long = " ".join(f"Sentence number {i} talks about a specific finding with value {i}." for i in range(120))
    blocks = [Block(0, "INTRODUCTION"), Block(1, long)]
    sections = build_sections(detect_headings(blocks, "en"), len(blocks))
    ps = segment(blocks, sections)
    assert len(ps) >= 3 and all(p.word_count <= MAX_PASSAGE_WORDS for p in ps)
    assert all(p.paragraph_start == 1 for p in ps)
