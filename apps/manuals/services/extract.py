"""Turn a PDF into per-page text that keeps reading order, tables and sections.

The manuals in this dataset are born-digital. Three layout facts drive the logic:

* Every page carries a repeated header line that is metadata, not content.
* Prose starts at the page's left margin; table cells start at their own column's
  x position. That horizontal offset, not vertical spacing, is what reliably
  separates table content from paragraphs -- a wrapped cell and a wrapped
  paragraph have almost the same line pitch in these documents.
* A table row's cells wrap independently and are vertically centred, so one
  logical row arrives as several interleaved PyMuPDF lines. Rows are therefore
  anchored on the first column, and the remaining cells attached by proximity.

A page with no table degrades to plain paragraph lines through the same code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf

COLUMN_GAP_POINTS = 8.0
"""Horizontal gap above which neighbouring text is a separate table column."""

MARGIN_TOLERANCE = 2.0
"""How far a line may start from the page margin and still count as prose."""

TABLE_REGION_GAP_RATIO = 2.5
"""Vertical gap, in line heights, that ends one table and starts another."""

ANCHOR_MERGE_RATIO = 1.5
"""Vertical gap, in line heights, below which two first-column cells are one row."""

MAX_HEADING_CHARS = 90
HEADING_SIZE_RATIO = 1.1
BOILERPLATE_PAGE_FRACTION = 0.6
_DIGITS = re.compile(r"\d+")
_WS = re.compile(r"\s+")


@dataclass
class Section:
    title: str
    text: str
    char_start: int
    char_end: int


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    sections: list[Section] = field(default_factory=list)


@dataclass
class _VisualLine:
    index: int
    spans: list[dict]
    y0: float
    y1: float

    @property
    def center(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return max(self.y1 - self.y0, 1.0)

    @property
    def x0(self) -> float:
        return self.spans[0]["bbox"][0]


@dataclass
class _Line:
    text: str
    size: float
    bold: bool
    is_row: bool
    x0: float
    center: float
    is_heading: bool = False


def _boilerplate_key(text: str) -> str:
    return _DIGITS.sub("#", text.strip().lower())


def _visual_lines(page) -> list[_VisualLine]:
    lines: list[_VisualLine] = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
            if not spans:
                continue
            spans.sort(key=lambda s: s["bbox"][0])
            lines.append(
                _VisualLine(
                    index=0,
                    spans=spans,
                    y0=min(s["bbox"][1] for s in spans),
                    y1=max(s["bbox"][3] for s in spans),
                )
            )
    lines.sort(key=lambda line: (line.center, line.x0))
    for position, line in enumerate(lines):
        line.index = position
    return lines


def _page_margin(lines: list[_VisualLine]) -> float:
    """The x position where most lines start, i.e. the prose left margin."""
    counts: dict[float, int] = {}
    for line in lines:
        x0 = round(line.x0, 1)
        counts[x0] = counts.get(x0, 0) + 1
    return max(counts, key=lambda x: (counts[x], -x)) if counts else 0.0


def _body_size(lines: list[_VisualLine], margin: float) -> float:
    """Modal font size of left-aligned text, weighted by how much text uses it."""
    size_chars: dict[float, int] = {}
    for line in lines:
        for span in line.spans:
            if abs(span["bbox"][0] - margin) <= MARGIN_TOLERANCE:
                size = round(span["size"], 1)
                size_chars[size] = size_chars.get(size, 0) + len(span["text"])
    return max(size_chars, key=lambda size: size_chars[size]) if size_chars else 11.0


def _is_one_text_run(
    left: list[dict], right: list[dict], line_of: dict[int, _VisualLine]
) -> bool:
    """True when two x-clusters are one continuous run of text on the same line.

    Keeps the page header, whose page number is a span butted up against the
    label, from being read as a second table column.
    """
    for left_span in left:
        for right_span in right:
            if line_of[id(left_span)].index != line_of[id(right_span)].index:
                continue
            if right_span["bbox"][0] - left_span["bbox"][2] <= COLUMN_GAP_POINTS:
                return True
    return False


def _cell_text(cluster: list[dict], line_of: dict[int, _VisualLine]) -> str:
    """Read one cell: contiguous spans within a line, then wrapped lines in order."""
    by_line: dict[int, list[dict]] = {}
    for span in cluster:
        by_line.setdefault(line_of[id(span)].index, []).append(span)
    fragments = [
        "".join(s["text"] for s in sorted(spans, key=lambda s: s["bbox"][0]))
        for _, spans in sorted(by_line.items())
    ]
    return _WS.sub(" ", " ".join(fragments)).strip()


def _cells(spans: list[dict], line_of: dict[int, _VisualLine]) -> list[str]:
    """Group a logical row's spans into table cells, left to right."""
    ordered = sorted(spans, key=lambda s: (s["bbox"][0], line_of[id(s)].center))
    clusters: list[list[dict]] = []
    for span in ordered:
        if clusters and span["bbox"][0] - clusters[-1][0]["bbox"][0] <= COLUMN_GAP_POINTS:
            clusters[-1].append(span)
            continue
        clusters.append([span])

    merged: list[list[dict]] = []
    for cluster in clusters:
        if merged and _is_one_text_run(merged[-1], cluster, line_of):
            merged[-1].extend(cluster)
            continue
        merged.append(cluster)

    return [cell for cell in (_cell_text(c, line_of) for c in merged) if cell]


def _make_line(
    spans: list[dict], line_of: dict[int, _VisualLine], center: float
) -> _Line | None:
    cells = _cells(spans, line_of)
    if not cells:
        return None
    return _Line(
        text=" | ".join(cells),
        size=max(round(s["size"], 1) for s in spans),
        bold=any("bold" in s["font"].lower() for s in spans),
        is_row=len(cells) > 1,
        x0=min(s["bbox"][0] for s in spans),
        center=center,
    )


def _table_regions(table_lines: list[_VisualLine]) -> list[list[_VisualLine]]:
    """Split indented lines into separate tables on a large vertical gap."""
    regions: list[list[_VisualLine]] = []
    for line in table_lines:
        if regions:
            previous = regions[-1][-1]
            if line.center - previous.center <= TABLE_REGION_GAP_RATIO * previous.height:
                regions[-1].append(line)
                continue
        regions.append([line])
    return regions


def _table_rows(region: list[_VisualLine], line_of: dict[int, _VisualLine]) -> list[_Line]:
    """Rebuild one table's logical rows, anchored on its first column."""
    first_column = min(line.x0 for line in region)
    anchors: list[list[_VisualLine]] = []
    for line in region:
        if line.x0 - first_column > COLUMN_GAP_POINTS:
            continue
        if anchors:
            previous = anchors[-1][-1]
            if line.center - previous.center <= ANCHOR_MERGE_RATIO * previous.height:
                anchors[-1].append(line)
                continue
        anchors.append([line])
    if not anchors:
        anchors = [[line] for line in region]

    centers = [sum(line.center for line in group) / len(group) for group in anchors]
    buckets: list[list[dict]] = [[] for _ in anchors]
    for line in region:
        nearest = min(range(len(centers)), key=lambda i: abs(centers[i] - line.center))
        buckets[nearest].extend(line.spans)

    rows = (
        _make_line(spans, line_of, center)
        for spans, center in zip(buckets, centers)
        if spans
    )
    return [row for row in rows if row is not None]


def _page_lines(page) -> list[_Line]:
    visual = _visual_lines(page)
    if not visual:
        return []
    margin = _page_margin(visual)
    line_of = {id(span): line for line in visual for span in line.spans}

    prose: list[_Line] = []
    table_lines: list[_VisualLine] = []
    for line in visual:
        if abs(line.x0 - margin) <= MARGIN_TOLERANCE:
            made = _make_line(line.spans, line_of, line.center)
            if made is not None:
                prose.append(made)
        else:
            table_lines.append(line)

    rows = [
        row for region in _table_regions(table_lines) for row in _table_rows(region, line_of)
    ]
    return sorted(prose + rows, key=lambda line: line.center)


def _mark_headings(lines: list[_Line], body_size: float) -> None:
    for line in lines:
        line.is_heading = (
            not line.is_row
            and len(line.text) <= MAX_HEADING_CHARS
            and not line.text.endswith(".")
            and (line.bold or line.size > body_size * HEADING_SIZE_RATIO)
        )


def _boilerplate_keys(doc) -> set[str]:
    """Lines that repeat on most pages are headers/footers, not content."""
    counts: dict[str, int] = {}
    for page in doc:
        seen: set[str] = set()
        for line in _page_lines(page):
            key = _boilerplate_key(line.text)
            if key and key not in seen:
                seen.add(key)
                counts[key] = counts.get(key, 0) + 1
    threshold = max(2, round(doc.page_count * BOILERPLATE_PAGE_FRACTION))
    return {key for key, count in counts.items() if count >= threshold}


def extract_pages(pdf_path: str) -> list[ExtractedPage]:
    """Extract every page as cleaned text split into sections. Page numbers are 1-based."""
    with pymupdf.open(pdf_path) as doc:
        drop_keys = _boilerplate_keys(doc)
        pages: list[ExtractedPage] = []
        for index in range(doc.page_count):
            page = doc[index]
            visual = _visual_lines(page)
            lines = [
                line
                for line in _page_lines(page)
                if _boilerplate_key(line.text) not in drop_keys
            ]
            _mark_headings(lines, _body_size(visual, _page_margin(visual)))
            pages.append(
                ExtractedPage(
                    page_number=index + 1,
                    text="\n".join(line.text for line in lines),
                    sections=_build_sections(lines),
                )
            )
    return pages


def _build_sections(lines: list[_Line]) -> list[Section]:
    """Group lines under their heading, tracking offsets into the page text."""
    sections: list[Section] = []
    title = ""
    buffer: list[str] = []
    start = 0
    cursor = 0

    def flush(end: int) -> None:
        if buffer:
            sections.append(
                Section(title=title, text="\n".join(buffer), char_start=start, char_end=end)
            )

    for line in lines:
        if line.is_heading and buffer:
            flush(cursor - 1)
            buffer = []
            start = cursor
            title = line.text
        elif line.is_heading:
            start = cursor
            title = line.text
        buffer.append(line.text)
        cursor += len(line.text) + 1
    flush(max(cursor - 1, start))
    return sections
