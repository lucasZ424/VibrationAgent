"""Unit tests for deterministic bibliography extraction (Phase-2 Obj3).

Each test pins a contract the citation layer depends on: how author strings are
split, where the year comes from, that prose never invents authors, and that
metadata wins over text on merge. The Chinese-marker cases guard bilingual
support, which is the reason this project exists.
"""
from vibration_agent.ingestion import bibliography as B
from vibration_agent.schemas import DocumentBibliography


def test_metadata_author_field_splits_into_multiple_authors():
    # A single metadata "author" string packs several names; per-author citation
    # needs them split, not kept as one blob.
    result = B.from_pdf_metadata({"author": "Jane Roe; John Doe"})

    assert result["authors"] == ["Jane Roe", "John Doe"]


def test_metadata_inverted_single_author_keeps_ascii_comma():
    # Metadata often stores "Lastname, First"; that comma is part of one author,
    # not a multi-author separator.
    result = B.from_pdf_metadata({"author": "Bently, Donald E."})

    assert result["authors"] == ["Bently, Donald E"]


def test_metadata_comma_still_splits_multiple_full_names():
    result = B.from_pdf_metadata({"author": "Jane Roe, John Doe"})

    assert result["authors"] == ["Jane Roe", "John Doe"]


def test_metadata_year_comes_from_creation_date():
    result = B.from_pdf_metadata({"creationDate": "D:20210615000000"})

    assert result["year"] == 2021


def test_metadata_year_falls_back_to_mod_date():
    # When creationDate carries no year, modDate is the next-best source.
    result = B.from_pdf_metadata({"modDate": "D:20190101000000"})

    assert result["year"] == 2019


def test_metadata_absent_yields_empty_bibliography():
    # Documents without metadata must degrade to empty defaults, preserving the
    # Phase-1 citation behaviour rather than raising.
    assert B.from_pdf_metadata(None) == {"year": None, "authors": [], "publisher": None}
    assert B.from_pdf_metadata({}) == {"year": None, "authors": [], "publisher": None}


def test_text_english_byline_yields_authors_year_and_publisher():
    text = "By John Doe and Jane Roe\n2021\nSpringer Press\n"

    result = B.infer_from_text(text)

    assert result["authors"] == ["John Doe", "Jane Roe"]
    assert result["year"] == 2021
    assert result["publisher"] == "Springer Press"


def test_text_author_label_marker_is_honoured():
    result = B.infer_from_text("Author: Alice Smith\n")

    assert result["authors"] == ["Alice Smith"]


def test_text_prose_does_not_invent_authors():
    # Author inference must fire only on explicit markers; pulling names out of
    # ordinary prose would corrupt citations across the corpus.
    result = B.infer_from_text("This book studies rotor vibration measured in 1998 on many rigs.")

    assert result["authors"] == []
    assert result["year"] == 1998


def test_text_chinese_markers_extract_author_and_publisher():
    text = "作者：张三、李四\n机械工业出版社\n"

    result = B.infer_from_text(text)

    assert result["authors"] == ["张三", "李四"]
    assert result["publisher"] == "机械工业出版社"


def test_text_chinese_year_suffix_is_recognized():
    # "YYYY年" is the dominant Chinese year form. Regression guard for the
    # word-boundary/CJK interaction in the year regex.
    result = B.infer_from_text("出版年份：2019年\n")

    assert result["year"] == 2019


def test_text_chinese_year_can_be_prefixed_by_cjk_text():
    result = B.infer_from_text("鍏厓2019骞碶n")

    assert result["year"] == 2019


def test_english_publisher_label_is_honoured_without_press_false_positive():
    labelled = B.infer_from_text("Publisher: Rotor Dynamics Press\n")
    prose = B.infer_from_text("The bearing press fit was measured in 2018.\n")

    assert labelled["publisher"] == "Rotor Dynamics Press"
    assert prose["publisher"] is None


def test_merge_prefers_metadata_then_fills_gaps_from_text():
    meta = {"year": 2021, "authors": ["Meta Author"], "publisher": None}
    text = {"year": 1999, "authors": ["Text Author"], "publisher": "Text Press"}

    merged = B.merge(meta, text)

    assert merged.year == 2021  # metadata wins when present
    assert merged.authors == ["Meta Author"]  # metadata wins when non-empty
    assert merged.publisher == "Text Press"  # text fills the gap metadata left


def test_has_author_year_requires_both_author_and_year():
    # citation_anchor's "Author (Year)" form gates on this predicate, so it must
    # be true only when BOTH are present.
    assert DocumentBibliography(year=2020, authors=["A"]).has_author_year() is True
    assert DocumentBibliography(year=2020, authors=[]).has_author_year() is False
    assert DocumentBibliography(year=None, authors=["A"]).has_author_year() is False
