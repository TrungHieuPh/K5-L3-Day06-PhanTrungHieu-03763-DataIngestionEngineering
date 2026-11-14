"""Read and normalize source data."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from .models import DocumentPage


# Known repeating headers in the Labor Code PDF — stripped before normalize.
# Pattern allows an optional page number prefix: "4 CÔNG BÁO/Số 993 + 994/Ngày..."
_HEADER_PATTERNS = [
    re.compile(
        r"^\s*\d*\s*CÔNG\s*BÁO\s*/\s*Số\s*\d+\s*\+\s*\d+\s*/\s*Ngày[^\n]*$",
        re.MULTILINE,
    ),
]

# Soft hyphen (U+00AD) and the ASCII hyphen-at-line-end pattern.
_SOFT_HYPHEN_RE = re.compile(r"­")
_HYPHEN_LINEBREAK_RE = re.compile(r"-\n(?=\w)")

# Collapse runs of spaces/tabs but preserve newlines (paragraphs).
_INLINE_WS_RE = re.compile(r"[ \t\f\v]+")
# Normalize 3+ newlines down to 2 (keeps paragraph breaks).
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")

# Fix pypdf's intra-syllable spacing in Vietnamese text.
# Pattern: 1-2 lowercase consonant letters + space + a Vietnamese vowel
# (plain or diacritic). Deliberately conservative — won't merge "lao động"
# or "của người" because right side there starts with a consonant.
_VIET_VOWEL = (
    "aăâeêioôơuưy"
    "àáảãạằắẳẵặầấẩẫậ"
    "èéẻẽẹềếểễệ"
    "ìíỉĩị"
    "òóỏõọồốổỗộờớởỡợ"
    "ùúủũụừứửữự"
    "ỳýỷỹỵ"
)
_SYLLABLE_MERGE_RE = re.compile(
    rf"\b(gi|qu|ngh|nh|ng|ch|gh|kh|ph|th|tr|[bcdghklmnpqrstvxyđ])\s+([{_VIET_VOWEL}])",
    re.IGNORECASE,
)

# Second pass: left is 2-4 chars ending in a plain vowel (incomplete rime),
# right is a diacritic vowel (continuation of the rime).
# Catches "thu ận", "vi ệc", "kho ản", "nghi ệp", "ho ặc", "ti ền", "su ất".
_DIACRITIC_VOWEL = (
    "ăâêôơư"
    "àáảãạằắẳẵặầấẩẫậ"
    "èéẻẽẹềếểễệ"
    "ìíỉĩị"
    "òóỏõọồốổỗộờớởỡợ"
    "ùúủũụừứửữự"
    "ỳýỷỹỵ"
)
_SYLLABLE_MERGE_2_RE = re.compile(
    rf"\b([a-zđ]{{1,3}}[iouy])\s+([{_DIACRITIC_VOWEL}])",
    re.IGNORECASE,
)


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract each physical page as a DocumentPage.

    Empty pages are kept with text='' so downstream code has a 1:1 map between
    physical pages and DocumentPage entries. The chunker will skip empty text.
    """
    path = Path(path)
    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    for idx, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        pages.append(
            DocumentPage(
                document_id=document_id,
                source=source,
                page=idx,
                text=raw,
                metadata={"char_count_raw": len(raw)},
            )
        )
    return pages


def normalize_text(text: str) -> str:
    """Normalize Unicode + whitespace while preserving paragraph structure."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)

    for pat in _HEADER_PATTERNS:
        text = pat.sub("", text)

    text = _SOFT_HYPHEN_RE.sub("", text)
    text = _HYPHEN_LINEBREAK_RE.sub("", text)

    # Run syllable-merge twice: one pass can leave a chain like "s ử d ụng"
    # with the second gap still unmerged until the first is fixed.
    for _ in range(2):
        text = _SYLLABLE_MERGE_RE.sub(r"\1\2", text)
    for _ in range(2):
        text = _SYLLABLE_MERGE_2_RE.sub(r"\1\2", text)

    # Trim inline whitespace per line but keep newline separators.
    lines = [_INLINE_WS_RE.sub(" ", line).strip() for line in text.split("\n")]
    text = "\n".join(lines)

    text = _MULTI_NEWLINE_RE.sub("\n\n", text).strip()
    return text
