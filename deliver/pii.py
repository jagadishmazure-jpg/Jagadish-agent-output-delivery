"""PII detection used by delivery policies.

Scans result text (summary, table cells, figure labels) for email addresses,
phone numbers, and SSNs. Dates such as 2026-10-18 are explicitly NOT treated
as PII.
"""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)\s?|\d{3}[-.\s]?)\d{3}[-.\s]?\d{4}\b"
)
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

_PATTERNS = (("email", EMAIL_RE), ("phone", PHONE_RE), ("ssn", SSN_RE))


def find_pii(text: str) -> list:
    """Return [(kind, matched_text), ...] for PII found in text."""
    hits = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text or ""):
            hits.append((kind, match.group(0)))
    return hits


def contains_pii(text: str) -> bool:
    return bool(find_pii(text))


def _iter_text(result) -> "list[str]":
    """Yield every human-readable string inside an AgentResult."""
    yield result.summary
    yield result.title
    for table in result.tables:
        yield table["name"]
        yield from table["columns"]
        for row in table["rows"]:
            for cell in row:
                yield str(cell)
    for key in result.figures:
        yield key
    yield from result.citations


def scan_result(result) -> list:
    """Return [(kind, matched_text, location), ...] for PII in a result."""
    hits = []
    for text in _iter_text(result):
        for kind, matched in find_pii(text):
            hits.append((kind, matched, text[:60]))
    return hits
