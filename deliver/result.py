"""AgentResult: the validated unit of work an agent hands to the delivery layer.

A result carries everything a downstream channel needs — a human-readable
summary, structured tables, key figures, and citations — in one validated
object. Validation happens at construction so a malformed result can never
reach a channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


class ResultError(ValueError):
    """Raised when an AgentResult fails validation."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AgentResult:
    """Validated container for one agent output.

    tables: list of {"name": str, "columns": [str, ...], "rows": [[...], ...]}.
    figures: mapping of key-number name -> number shown in chat/reports.
    citations: list of source strings, e.g. "sop-02.md §Dispatch".
    """

    id: str
    title: str
    summary: str
    tables: list = field(default_factory=list)
    figures: dict = field(default_factory=dict)
    citations: list = field(default_factory=list)
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ResultError("id must be a non-empty string")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ResultError("title must be a non-empty string")
        if "\n" in self.title or "\r" in self.title:
            # The title becomes an email Subject header (RES-TITLE-01).
            raise ResultError("title must be a single line")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ResultError("summary must be a non-empty string")
        if not isinstance(self.tables, list):
            raise ResultError("tables must be a list")
        for i, table in enumerate(self.tables):
            self._validate_table(i, table)
        if not isinstance(self.figures, dict):
            raise ResultError("figures must be a dict")
        for key, value in self.figures.items():
            if not isinstance(key, str) or not key.strip():
                raise ResultError(f"figures keys must be non-empty strings (got {key!r})")
            if not isinstance(value, (int, float)):
                raise ResultError(f"figures[{key!r}] must be a number (got {value!r})")
        if not isinstance(self.citations, list) or any(
            not isinstance(c, str) for c in self.citations
        ):
            raise ResultError("citations must be a list of strings")
        if not self.generated_at:
            self.generated_at = _utcnow()
        elif not isinstance(self.generated_at, str):
            raise ResultError("generated_at must be an ISO-8601 string")

    @staticmethod
    def _validate_table(index: int, table: object) -> None:
        label = f"tables[{index}]"
        if not isinstance(table, dict):
            raise ResultError(f"{label} must be a dict")
        name = table.get("name")
        columns = table.get("columns")
        rows = table.get("rows")
        if not isinstance(name, str) or not name.strip():
            raise ResultError(f"{label} needs a non-empty 'name'")
        if not isinstance(columns, list) or not columns or any(
            not isinstance(c, str) for c in columns
        ):
            raise ResultError(f"{label} needs a non-empty 'columns' list of strings")
        if not isinstance(rows, list):
            raise ResultError(f"{label} needs a 'rows' list")
        for r, row in enumerate(rows):
            if not isinstance(row, (list, tuple)) or len(row) != len(columns):
                raise ResultError(
                    f"{label} row {r} must have {len(columns)} cells "
                    f"(got {len(row) if isinstance(row, (list, tuple)) else 'non-list'})"
                )

    def total_rows(self) -> int:
        """Total data rows across all tables."""
        return sum(len(t["rows"]) for t in self.tables)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "tables": [
                {"name": t["name"], "columns": list(t["columns"]),
                 "rows": [list(r) for r in t["rows"]]}
                for t in self.tables
            ],
            "figures": dict(self.figures),
            "citations": list(self.citations),
            "generated_at": self.generated_at,
        }
