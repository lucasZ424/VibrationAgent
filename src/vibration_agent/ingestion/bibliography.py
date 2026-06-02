"""Bibliographic metadata extraction from PDF metadata and first-page text.

Phase-2 Obj3. Deterministic only: regex/keyword heuristics, no model calls. Every
field falls back to empty/None when nothing is found, so the Phase-1 citation
behaviour is preserved when a document carries no recoverable bibliography.

Author parsing splits on strong multi-author separators such as ``;`` ``&`` CJK
enumeration/full-width commas and the word "and". ASCII comma is handled
separately so "Lastname, First" can remain a single author while
"Jane Roe, John Doe" still splits. Text-based author inference only fires on an
explicit marker (the CJK author labels, or English "By"/"Author:") to avoid
pulling names out of prose.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from vibration_agent.schemas import DocumentBibliography

_MIN_YEAR = 1500
_MAX_YEAR = 2100

# CJK regex pieces use \u escapes (ingestion-package style) to keep this source
# ASCII and byte-stable. These are normal strings holding the real characters at
# runtime, interpolated into the raw patterns below. Decoded values:
#   _ZH_AUTHOR_MARKERS = author/editor labels  zuozhe|zhuzhe|bianzhu|bianzhe
#   _PUBLISHER_ZH      = the "Press"/publisher suffix
#   _COLON             = ascii + full-width colon
#   _AUTHOR_SEPARATORS = ; , & + CJK enumeration/full-width comma + the word "and"
_ZH_AUTHOR_MARKERS = "作者|著者|编著|编者"
_PUBLISHER_ZH = "出版社"
_COLON = "[:：]"
_CJK_RANGE = "[一-鿿]"
_AUTHOR_SEPARATORS = ";|,|&|、|，|\\band\\b"

# Trailing (?!\d) instead of \b: Python's \w (and thus \b) treats CJK as word
# chars, so a trailing \b never fires before "年" -> the common Chinese year form
# "2019年" would be missed. The negative lookahead still rejects 5+ digit runs.
_YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_METADATA_YEAR_RE = re.compile(r"(?:19|20)\d{2}")
_AUTHOR_SEPARATOR_RE = re.compile(r"\s*(?:;|&|\u3001|\uff0c|\band\b)\s*", re.IGNORECASE)
_ASCII_COMMA_RE = re.compile(r"\s*,\s*")
_INVERTED_AUTHOR_RE = re.compile(
    r"^[A-Za-z][A-Za-z'`\.-]+,\s*[A-Za-z][A-Za-z'`\.-]*(?:\s+[A-Za-z][A-Za-z'`\.-]*){0,2}$"
)
_ZH_AUTHOR_RE = re.compile(rf"(?:{_ZH_AUTHOR_MARKERS})\s*{_COLON}\s*(?P<names>.+)")
_EN_AUTHOR_RE = re.compile(rf"^\s*(?:by|authors?\s*{_COLON})\s*(?P<names>.+)$", re.IGNORECASE)
_ZH_PUBLISHER_RE = re.compile(rf"{_CJK_RANGE}{{2,15}}{_PUBLISHER_ZH}")
_EN_PUBLISHER_LABEL_RE = re.compile(r"^\s*publisher\s*[:：]\s*(?P<name>.+)$", re.IGNORECASE)
_EN_PUBLISHER_LINE_RE = re.compile(
    r"^(?:[A-Z][A-Za-z&.\-]*(?:\s+[A-Z][A-Za-z&.\-]*){0,5}\s+"
    r"(?:Press|Publishing|Publishers)|Springer|Elsevier|Wiley|McGraw-Hill)\b",
)
_EN_PUBLISHER_KEYWORDS = (
    "springer",
    "elsevier",
    "wiley",
    "mcgraw-hill",
)


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _plausible_year(year: int | None) -> int | None:
    if year is None:
        return None
    return year if _MIN_YEAR <= year <= _MAX_YEAR else None


def _split_authors(raw: str) -> list[str]:
    authors: list[str] = []
    for segment in _AUTHOR_SEPARATOR_RE.split(raw):
        cleaned = segment.strip(" \t\r\n.")
        if not cleaned:
            continue
        if _INVERTED_AUTHOR_RE.match(cleaned):
            authors.append(cleaned)
            continue
        authors.extend(part.strip(" \t\r\n.") for part in _ASCII_COMMA_RE.split(cleaned) if part.strip(" \t\r\n."))
    return authors


def _infer_authors_from_text(text: str) -> list[str]:
    for line in text.splitlines():
        match = _ZH_AUTHOR_RE.search(line) or _EN_AUTHOR_RE.search(line)
        if match:
            authors = _split_authors(match.group("names"))
            if authors:
                return authors
    return []


def _infer_publisher_from_text(text: str) -> str | None:
    zh = _ZH_PUBLISHER_RE.search(text)
    if zh:
        return zh.group(0)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or len(line) > 80:
            continue
        if label := _EN_PUBLISHER_LABEL_RE.match(line):
            value = label.group("name").strip()
            return value or None
        if _EN_PUBLISHER_LINE_RE.search(line):
            return line
        lowered = line.lower()
        if any(keyword in lowered for keyword in _EN_PUBLISHER_KEYWORDS):
            return line
    return None


def from_pdf_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract author/year from a PyMuPDF ``doc.metadata`` mapping."""
    meta = metadata or {}
    authors = _split_authors(_clean(meta.get("author")))
    year: int | None = None
    for key in ("creationDate", "modDate"):
        match = _METADATA_YEAR_RE.search(_clean(meta.get(key)))
        if match:
            year = _plausible_year(int(match.group(0)))
            if year is not None:
                break
    return {"year": year, "authors": authors, "publisher": None}


def infer_from_text(text: str | None) -> dict[str, Any]:
    """Infer year/authors/publisher from first-page text via markers/keywords."""
    text = text or ""
    year_match = _YEAR_RE.search(text)
    return {
        "year": _plausible_year(int(year_match.group(0))) if year_match else None,
        "authors": _infer_authors_from_text(text),
        "publisher": _infer_publisher_from_text(text),
    }


def merge(meta: Mapping[str, Any], text: Mapping[str, Any]) -> DocumentBibliography:
    """Merge metadata-derived and text-derived fields; metadata wins, text fills gaps."""
    return DocumentBibliography(
        year=meta["year"] if meta.get("year") is not None else text.get("year"),
        authors=list(meta.get("authors") or text.get("authors") or []),
        publisher=meta.get("publisher") or text.get("publisher"),
    )


def extract_bibliography(
    pdf_path: str | Path,
    *,
    first_page_text: str | None = None,
) -> DocumentBibliography:
    """Open a PDF and merge its metadata with first-page-text inference.

    ``first_page_text`` lets the caller reuse already-parsed text; when omitted the
    first page's raw text is read from the PDF directly.
    """
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on env
        raise RuntimeError("PyMuPDF is required for bibliography extraction.") from exc

    source = Path(pdf_path).resolve()
    with fitz.open(source) as doc:
        meta = from_pdf_metadata(doc.metadata)
        page_text = first_page_text
        if page_text is None and doc.page_count:
            page_text = doc[0].get_text("text")
    return merge(meta, infer_from_text(page_text))
