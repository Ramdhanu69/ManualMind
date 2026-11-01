"""Citation verification.

The text shown to a user as a quote is always copied from the stored chunk, never
from the model's output. A model that paraphrases keeps its citation but loses the
`quote_verified` flag; a model that invents a chunk id loses the citation entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

FALLBACK_QUOTE_CHARS = 200
FUZZY_MATCH_THRESHOLD = 0.9

_CHARACTER_FOLDING = {
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "―": "-",
    " ": " ",
}


@dataclass
class VerifiedCitation:
    chunk_id: int
    quote: str
    quote_verified: bool


def _normalize(text: str) -> tuple[str, list[int]]:
    """Fold quotes/dashes and collapse whitespace, mapping back to original offsets."""
    output: list[str] = []
    offsets: list[int] = []
    previous_was_space = True
    for index, raw in enumerate(text):
        character = _CHARACTER_FOLDING.get(raw, raw)
        if character.isspace():
            if previous_was_space:
                continue
            output.append(" ")
            offsets.append(index)
            previous_was_space = True
            continue
        output.append(character.lower())
        offsets.append(index)
        previous_was_space = False
    while output and output[-1] == " ":
        output.pop()
        offsets.pop()
    return "".join(output), offsets


def _span(text: str, offsets: list[int], start: int, length: int) -> str:
    """Slice the original text for a match found in its normalized form."""
    if length <= 0 or start >= len(offsets):
        return ""
    end_index = min(start + length - 1, len(offsets) - 1)
    return text[offsets[start] : offsets[end_index] + 1].strip()


def locate_quote(quote: str, chunk_text: str) -> tuple[str, bool]:
    """Find the model's quote inside the stored chunk.

    Returns the text to display and whether it matched. Exact substring first,
    then a sliding fuzzy window; otherwise the start of the chunk, unverified.
    """
    fallback = chunk_text[:FALLBACK_QUOTE_CHARS].strip()
    if not quote or not quote.strip():
        return fallback, False

    needle, _ = _normalize(quote)
    haystack, offsets = _normalize(chunk_text)
    if not needle or not haystack:
        return fallback, False

    position = haystack.find(needle)
    if position != -1:
        return _span(chunk_text, offsets, position, len(needle)), True

    width = len(needle)
    if width <= len(haystack):
        best_ratio = 0.0
        best_start = -1
        matcher = SequenceMatcher(autojunk=False)
        matcher.set_seq2(needle)
        for start in range(0, len(haystack) - width + 1):
            window = haystack[start : start + width]
            matcher.set_seq1(window)
            if matcher.quick_ratio() < FUZZY_MATCH_THRESHOLD:
                continue
            ratio = matcher.ratio()
            if ratio > best_ratio:
                best_ratio, best_start = ratio, start
        if best_ratio >= FUZZY_MATCH_THRESHOLD:
            return _span(chunk_text, offsets, best_start, width), True

    return fallback, False


def verify_citations(
    raw_citations: list, context_texts: dict[int, str]
) -> list[VerifiedCitation]:
    """Keep only citations whose chunk id was actually retrieved, in model order.

    A chunk id outside the provided context is dropped: the system can never show
    a source it did not retrieve. A valid chunk id with an unmatchable quote is
    kept, with the stored chunk's own text substituted for the quote.
    """
    verified: list[VerifiedCitation] = []
    seen: set[int] = set()
    for raw in raw_citations or []:
        if not isinstance(raw, dict):
            continue
        try:
            chunk_id = int(raw.get("chunk_id"))
        except (TypeError, ValueError):
            continue
        if chunk_id not in context_texts or chunk_id in seen:
            continue
        seen.add(chunk_id)
        quote, matched = locate_quote(str(raw.get("quote") or ""), context_texts[chunk_id])
        verified.append(
            VerifiedCitation(chunk_id=chunk_id, quote=quote, quote_verified=matched)
        )
    return verified
