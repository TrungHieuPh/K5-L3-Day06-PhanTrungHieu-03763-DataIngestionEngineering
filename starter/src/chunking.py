"""Chunking strategies: fixed-size (A), by-article (B), by-clause (C).

All three strategies emit the SAME metadata schema so that A–B and B–C
comparisons change only the chunking rule, never the metadata available
to evaluation or filtering:

    strategy, article (primary Điều, int | None), articles (all Điều the
    chunk overlaps), article_title, chapter_roman, chapter_title,
    page_start, page_end, char_start, char_end  (+ strategy-specific keys)

`char_start` / `char_end` are offsets in the page-joined document text, so
any source position can be mapped back to the chunk(s) covering it.
"""
from __future__ import annotations

import bisect
import re
from collections import Counter

from .models import Chunk, DocumentPage


_ARTICLE_RE = re.compile(r"^Điều\s+(\d+)\.\s*(.*)$", re.MULTILINE)
_CHAPTER_RE = re.compile(r"^Chương\s+([IVXLCDM]+)\s*$", re.MULTILINE)
_CLAUSE_RE = re.compile(r"^(\d+)\.\s+", re.MULTILINE)


def concat_with_offsets(pages: list[DocumentPage]) -> tuple[str, list[int]]:
    """Join page texts with '\\n'. Return (joined_text, page_start_offsets)."""
    parts: list[str] = []
    offsets: list[int] = []
    cursor = 0
    for p in pages:
        offsets.append(cursor)
        parts.append(p.text)
        cursor += len(p.text) + 1  # +1 for the joining "\n"
    return "\n".join(parts), offsets


def _page_for_offset(offset: int, offsets: list[int]) -> int:
    """Return 1-indexed page number that contains character position `offset`."""
    idx = bisect.bisect_right(offsets, offset) - 1
    return max(1, idx + 1)


def _chapter_title_after(text: str, header_end: int) -> str:
    """Return the next non-empty line after a 'Chương X' header."""
    tail = text[header_end : header_end + 300]
    for line in tail.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def parse_articles(text: str) -> list[dict]:
    """Return list of article dicts with char offsets and chapter context.

    Each dict: {number, title, start, end, chapter_roman, chapter_title}.
    The chapter of an article is the nearest 'Chương' header before it.
    """
    chapter_positions: list[tuple[int, str, str]] = []
    for m in _CHAPTER_RE.finditer(text):
        chapter_positions.append((m.start(), m.group(1), _chapter_title_after(text, m.end())))

    article_matches = list(_ARTICLE_RE.finditer(text))
    articles: list[dict] = []
    for i, m in enumerate(article_matches):
        start = m.start()
        end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(text)
        # Trim at the next chapter header if it falls before the next article.
        for coff, _, _ in chapter_positions:
            if start < coff < end:
                end = coff
                break
        chapter_roman = ""
        chapter_title = ""
        for coff, croman, ctitle in chapter_positions:
            if coff <= start:
                chapter_roman = croman
                chapter_title = ctitle
            else:
                break
        articles.append(
            {
                "number": int(m.group(1)),
                "title": m.group(2).strip(),
                "start": start,
                "end": end,
                "chapter_roman": chapter_roman,
                "chapter_title": chapter_title,
            }
        )
    return articles


def _base_metadata(
    strategy: str,
    primary: dict | None,
    overlapped: list[dict],
    char_start: int,
    char_end: int,
    offsets: list[int],
) -> dict:
    """Metadata shared by every strategy (same keys, same semantics)."""
    return {
        "strategy": strategy,
        "article": primary["number"] if primary else None,
        "articles": [a["number"] for a in overlapped],
        "article_title": primary["title"] if primary else "",
        "chapter_roman": primary["chapter_roman"] if primary else "",
        "chapter_title": primary["chapter_title"] if primary else "",
        "page_start": _page_for_offset(char_start, offsets),
        "page_end": _page_for_offset(max(char_start, char_end - 1), offsets),
        "char_start": char_start,
        "char_end": char_end,
    }


def fixed_size(
    pages: list[DocumentPage], size: int = 500, overlap: int = 50
) -> list[Chunk]:
    """Strategy A — sliding character window over the full document text.

    Article/chapter metadata is derived from the window's char offsets:
    `articles` = every Điều the window overlaps, `article` = the Điều that
    contains the window start (or the first overlapped Điều if the window
    starts in a chapter heading / preamble).
    """
    if size <= overlap:
        raise ValueError("size must be greater than overlap")
    text, offsets = concat_with_offsets(pages)
    arts = parse_articles(text)
    art_starts = [a["start"] for a in arts]
    doc_id = pages[0].document_id
    source = pages[0].source
    chunks: list[Chunk] = []
    step = size - overlap
    pos = 0
    while pos < len(text):
        end = min(pos + size, len(text))
        piece = text[pos:end].strip()
        if piece:
            # Articles whose [start, end) intersects [pos, end).
            hi = bisect.bisect_left(art_starts, end)
            overlapped = [a for a in arts[:hi] if a["end"] > pos]
            containing = [a for a in overlapped if a["start"] <= pos < a["end"]]
            primary = containing[0] if containing else (overlapped[0] if overlapped else None)
            meta = _base_metadata("fixed_size", primary, overlapped, pos, end, offsets)
            meta.update({"size": size, "overlap": overlap})
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}#A#p{len(chunks):04d}",
                    document_id=doc_id,
                    source=source,
                    page=meta["page_start"],
                    text=piece,
                    metadata=meta,
                )
            )
        pos += step
    return chunks


def by_article(pages: list[DocumentPage]) -> list[Chunk]:
    """Strategy B — one chunk per Điều, no size limit."""
    text, offsets = concat_with_offsets(pages)
    doc_id = pages[0].document_id
    source = pages[0].source
    chunks: list[Chunk] = []
    for a in parse_articles(text):
        piece = text[a["start"] : a["end"]].strip()
        if not piece:
            continue
        meta = _base_metadata("by_article", a, [a], a["start"], a["end"], offsets)
        chunks.append(
            Chunk(
                chunk_id=f"{doc_id}#B#art{a['number']:03d}",
                document_id=doc_id,
                source=source,
                page=meta["page_start"],
                text=piece,
                metadata=meta,
            )
        )
    return chunks


# A segment is (clause_numbers, start, end) with offsets relative to the
# article text; clause_numbers=[] means the article heading / preamble.
Segment = tuple[list[int], int, int]


def _split_article_clauses(article_text: str) -> list[Segment]:
    """Split an article into contiguous segments: preamble + one per khoản."""
    clause_matches = list(_CLAUSE_RE.finditer(article_text))
    if not clause_matches:
        return [([], 0, len(article_text))] if article_text.strip() else []

    segments: list[Segment] = []
    if article_text[: clause_matches[0].start()].strip():
        segments.append(([], 0, clause_matches[0].start()))
    for i, cm in enumerate(clause_matches):
        seg_end = clause_matches[i + 1].start() if i + 1 < len(clause_matches) else len(article_text)
        segments.append(([int(cm.group(1))], cm.start(), seg_end))
    return segments


def _merge_small(segments: list[Segment], article_text: str, min_size: int) -> list[Segment]:
    """Merge consecutive segments while the running buffer stays below min_size.

    Segments are contiguous, so a merge is simply (first.start, last.end).
    """
    merged: list[Segment] = []
    for nums, start, end in segments:
        if merged:
            prev_nums, prev_start, prev_end = merged[-1]
            if len(article_text[prev_start:prev_end].strip()) < min_size:
                merged[-1] = (prev_nums + nums, prev_start, end)
                continue
        merged.append((list(nums), start, end))
    return merged


def _split_large(
    segments: list[Segment], article_text: str, max_size: int, min_size: int
) -> list[Segment]:
    """Break segments longer than max_size at the last newline before the limit."""
    out: list[Segment] = []
    for nums, start, end in segments:
        cursor = start
        while end - cursor > max_size:
            cut = cursor + max_size
            nl = article_text.rfind("\n", cursor + min_size, cut)
            if nl == -1:
                nl = cut
            out.append((nums, cursor, nl))
            cursor = nl + 1 if article_text[nl : nl + 1] == "\n" else nl
        out.append((nums, cursor, end))
    return out


def by_clause(
    pages: list[DocumentPage], min_size: int = 200, max_size: int = 800
) -> list[Chunk]:
    """Strategy C — within each Điều, chunk by khoản; merge small, split large."""
    text, offsets = concat_with_offsets(pages)
    doc_id = pages[0].document_id
    source = pages[0].source
    chunks: list[Chunk] = []
    for a in parse_articles(text):
        article_text = text[a["start"] : a["end"]]
        segs = _split_article_clauses(article_text)
        segs = _merge_small(segs, article_text, min_size)
        segs = _split_large(segs, article_text, max_size, min_size)
        segs = [s for s in segs if article_text[s[1] : s[2]].strip()]
        label_counts = Counter(tuple(nums) for nums, _, _ in segs)
        label_seen: Counter[tuple[int, ...]] = Counter()
        for nums, seg_start, seg_end in segs:
            piece = article_text[seg_start:seg_end].strip()
            key = tuple(nums)
            base_label = "preamble" if not nums else "k" + "-".join(str(n) for n in nums)
            label = f"{base_label}#p{label_seen[key]}" if label_counts[key] > 1 else base_label
            label_seen[key] += 1
            abs_start = a["start"] + seg_start
            abs_end = a["start"] + seg_end
            meta = _base_metadata("by_clause", a, [a], abs_start, abs_end, offsets)
            meta.update({"clause_nums": nums, "min_size": min_size, "max_size": max_size})
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}#C#art{a['number']:03d}#{label}",
                    document_id=doc_id,
                    source=source,
                    page=meta["page_start"],
                    text=piece,
                    metadata=meta,
                )
            )
    return chunks
