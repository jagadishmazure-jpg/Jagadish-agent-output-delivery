"""Five-area security assessment reports.

Flat finding lists are hard to act on: analysts, leaders, and auditors need
different cuts of the same data. The assessment structure groups every
finding into one of five areas so each audience gets its view:

1. ``overview`` — composition of the assessed surface
   (counts: identities, agents, tools, scopes, secrets).
2. ``effective_privilege`` — privilege themes: who holds what, concentration
   risks, and indirect paths an attacker could exploit.
3. ``security_themes`` — foundational safeguards: are the basics present and
   effective (vaulting, rotation, just-in-time access, confirmation gates)?
4. ``emerging_themes`` — the newest, fastest-moving risks (AI agent
   identities, secret sprawl in automation, unattended tool grants).
5. ``findings`` — the findings explorer: every detection with severity,
   priority rank, recommended action, and status.

Every finding names its proof (``proven_by``): the test or check that proves
the claim. A claim without a proof is not admitted.
"""

from __future__ import annotations

import html
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone


SEVERITIES = ("critical", "high", "medium", "low")
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

AREAS = (
    "overview",
    "effective_privilege",
    "security_themes",
    "emerging_themes",
    "findings",
)

AREA_TITLES = {
    "overview": "1 · Overview — assessed surface",
    "effective_privilege": "2 · Effective privilege",
    "security_themes": "3 · Security themes",
    "emerging_themes": "4 · Emerging themes",
    "findings": "5 · Findings explorer",
}

AREA_BLURBS = {
    "overview": (
        "What was assessed: the composition of the identity and privilege "
        "surface under review."
    ),
    "effective_privilege": (
        "Who holds what: privilege concentration, standing access, and "
        "indirect paths an attacker could exploit."
    ),
    "security_themes": (
        "Foundational safeguards: whether the basics — vaulting, rotation, "
        "just-in-time access, confirmation gates — are present and effective."
    ),
    "emerging_themes": (
        "The newest, fastest-moving risks: AI agent identities, secret sprawl "
        "in automation, and unattended tool grants."
    ),
    "findings": (
        "Every detection, severity-sorted with a priority rank, a recommended "
        "action, and the proof behind the claim — regardless of thematic area."
    ),
}


class AssessmentError(ValueError):
    """Raised when an Assessment or Finding fails validation."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Finding:
    """One validated security finding.

    severity: critical | high | medium | low.
    area: one of the five assessment areas.
    proven_by: names the test or check that proves the claim.
    status: open | acknowledged | remediated (defaults to open).
    """

    severity: str
    area: str
    title: str
    detail: str
    recommendation: str
    proven_by: str
    status: str = "open"

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise AssessmentError(
                f"severity must be one of {SEVERITIES} (got {self.severity!r})"
            )
        if self.area not in AREAS:
            raise AssessmentError(
                f"area must be one of {AREAS} (got {self.area!r})"
            )
        for attr in ("title", "detail", "recommendation", "proven_by"):
            value = getattr(self, attr)
            if not isinstance(value, str) or not value.strip():
                raise AssessmentError(f"{attr} must be a non-empty string")
        if self.status not in ("open", "acknowledged", "remediated"):
            raise AssessmentError(
                "status must be open, acknowledged, or remediated "
                f"(got {self.status!r})"
            )


@dataclass
class Assessment:
    """A validated five-area security assessment.

    findings: list of Finding objects.
    surface: composition of the assessed surface, e.g.
        {"identities": 14, "agents": 6, "tools": 22, "scopes": 31, "secrets": 9}.
    title / generated_at: report metadata.
    """

    findings: list = field(default_factory=list)
    surface: dict = field(default_factory=dict)
    title: str = "Security assessment"
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise AssessmentError("title must be a non-empty string")
        if not isinstance(self.findings, list):
            raise AssessmentError("findings must be a list")
        for i, finding in enumerate(self.findings):
            if not isinstance(finding, Finding):
                raise AssessmentError(
                    f"findings[{i}] must be a Finding (got {type(finding).__name__})"
                )
        if not isinstance(self.surface, dict):
            raise AssessmentError("surface must be a dict")
        for key, value in self.surface.items():
            if not isinstance(key, str) or not key.strip():
                raise AssessmentError(f"surface keys must be non-empty strings (got {key!r})")
            if not isinstance(value, int) or value < 0:
                raise AssessmentError(
                    f"surface[{key!r}] must be a non-negative int (got {value!r})"
                )
        if not self.generated_at:
            self.generated_at = _utcnow()
        elif not isinstance(self.generated_at, str):
            raise AssessmentError("generated_at must be an ISO-8601 string")

    # ------------------------------------------------------------------ stats

    def counts_by_area(self) -> dict:
        """Number of findings in each of the five areas."""
        counts = {area: 0 for area in AREAS}
        for finding in self.findings:
            counts[finding.area] += 1
        return counts

    def counts_by_severity(self) -> dict:
        """Number of findings at each severity."""
        counts = {sev: 0 for sev in SEVERITIES}
        for finding in self.findings:
            counts[finding.severity] += 1
        return counts

    def ranked_findings(self) -> list:
        """Findings sorted by severity (critical first), then by input order.

        Each entry is (priority_rank, finding); rank starts at 1.
        """
        ordered = sorted(
            enumerate(self.findings),
            key=lambda pair: (SEVERITY_RANK[pair[1].severity], pair[0]),
        )
        return [(rank + 1, finding) for rank, (_, finding) in enumerate(ordered)]

    def summary(self) -> dict:
        """Aggregate stats for dashboards and report headers."""
        by_sev = self.counts_by_severity()
        return {
            "title": self.title,
            "generated_at": self.generated_at,
            "total_findings": len(self.findings),
            "by_area": self.counts_by_area(),
            "by_severity": by_sev,
            "critical_and_high": by_sev["critical"] + by_sev["high"],
            "open": sum(1 for f in self.findings if f.status == "open"),
            "surface": dict(self.surface),
        }

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "generated_at": self.generated_at,
            "surface": dict(self.surface),
            "findings": [
                {
                    "severity": f.severity,
                    "area": f.area,
                    "title": f.title,
                    "detail": f.detail,
                    "recommendation": f.recommendation,
                    "proven_by": f.proven_by,
                    "status": f.status,
                }
                for f in self.findings
            ],
            "summary": self.summary(),
        }


# ------------------------------------------------------------------ rendering

def _esc(value: object) -> str:
    return html.escape(str(value))


def render_html(assessment: Assessment) -> str:
    """Render the assessment as a standalone HTML document."""
    esc = _esc
    summary = assessment.summary()
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{esc(assessment.title)}</title>"
        "<style>body{font-family:sans-serif;max-width:900px;margin:2em auto}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #ccc;padding:6px;text-align:left}"
        ".critical{color:#b00020;font-weight:bold}"
        ".high{color:#c25e00;font-weight:bold}</style>"
        "</head><body>",
        f"<h1>{esc(assessment.title)}</h1>",
        f"<p><small>Generated {esc(assessment.generated_at)}</small></p>",
        "<h2>Summary</h2><ul>",
        f"<li>Total findings: {summary['total_findings']}</li>",
        f"<li>Critical + high: {summary['critical_and_high']}</li>",
        f"<li>Open: {summary['open']}</li>",
        "</ul>",
        "<h3>By severity</h3><table><tr><th>Severity</th><th>Count</th></tr>",
    ]
    for sev in SEVERITIES:
        parts.append(
            f"<tr><td class='{esc(sev)}'>{esc(sev)}</td>"
            f"<td>{summary['by_severity'][sev]}</td></tr>"
        )
    parts.append("</table>")

    ranked = assessment.ranked_findings()
    rank_of = {id(f): rank for rank, f in ranked}

    for area in AREAS:
        parts.append(f"<h2>{esc(AREA_TITLES[area])}</h2>")
        parts.append(f"<p>{esc(AREA_BLURBS[area])}</p>")
        if area == "overview":
            if assessment.surface:
                parts.append("<table><tr><th>Surface element</th><th>Count</th></tr>")
                for key in sorted(assessment.surface):
                    parts.append(
                        f"<tr><td>{esc(key)}</td><td>{assessment.surface[key]}</td></tr>"
                    )
                parts.append("</table>")
            else:
                parts.append("<p><i>No surface composition provided.</i></p>")
        else:
            if area == "findings":
                # The explorer shows every detection, severity-sorted.
                area_findings = [f for _, f in ranked]
            else:
                area_findings = [f for _, f in ranked if f.area == area]
            if not area_findings:
                parts.append("<p><i>No findings in this area.</i></p>")
                continue
            parts.append(
                "<table><tr><th>#</th><th>Severity</th><th>Finding</th>"
                "<th>Detail</th><th>Recommendation</th><th>Proof</th>"
                "<th>Status</th></tr>"
            )
            # Priority rank is global (across all areas); show it here.
            for finding in area_findings:
                parts.append(
                    "<tr>"
                    f"<td>{rank_of[id(finding)]}</td>"
                    f"<td class='{esc(finding.severity)}'>{esc(finding.severity)}</td>"
                    f"<td><b>{esc(finding.title)}</b></td>"
                    f"<td>{esc(finding.detail)}</td>"
                    f"<td>{esc(finding.recommendation)}</td>"
                    f"<td><code>{esc(finding.proven_by)}</code></td>"
                    f"<td>{esc(finding.status)}</td>"
                    "</tr>"
                )
            parts.append("</table>")

    parts.append("</body></html>")
    return "\n".join(parts)


def build_report(assessment: Assessment, out_path: str) -> dict:
    """Write the HTML assessment report to ``out_path``.

    Returns a receipt dict with path, byte size, and summary stats.
    """
    if not isinstance(out_path, str) or not out_path.strip():
        raise AssessmentError("out_path must be a non-empty string")
    parent = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(parent, exist_ok=True)
    content = render_html(assessment)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return {
        "path": os.path.abspath(out_path),
        "bytes": len(content.encode("utf-8")),
        "summary": assessment.summary(),
    }
