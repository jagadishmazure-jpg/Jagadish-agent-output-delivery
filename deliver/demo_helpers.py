"""Demo helpers: deterministic sample results and an all-channels runner.

All logic the Streamlit demo needs lives here (stdlib only) so it is fully
testable without the UI.
"""

from __future__ import annotations

from .audit import DeliveryAudit
from .channels import (ChatChannel, EmailChannel, FakeSMTP, ReportChannel,
                       TableChannel, dispatch)
from .result import AgentResult


def sample_result() -> AgentResult:
    """A deterministic sample result used by the demo and the docs."""
    return AgentResult(
        id="RES-2026-0042",
        title="Overnight incident summary",
        summary=(
            "Three incidents were triaged overnight. Two were resolved by the "
            "on-call team; one remains open pending a field visit."
        ),
        tables=[
            {
                "name": "incidents",
                "columns": ["id", "severity", "status", "minutes_to_ack"],
                "rows": [
                    ["INC-101", "P1", "resolved", 4],
                    ["INC-102", "P2", "resolved", 11],
                    ["INC-103", "P2", "open", 9],
                ],
            }
        ],
        figures={"resolved": 2, "open": 1, "mean_ack_minutes": 8.0},
        citations=["sop-01.md §Triage", "shift-log §2026-10-17"],
        generated_at="2026-10-18T06:00:00+00:00",
    )


def deliver_all(result: AgentResult, db_path: str, out_dir: str,
                smtp_factory=FakeSMTP, to_addrs=("ops@example.com",)) -> dict:
    """Deliver one result to all four channels. Returns receipts + audit."""
    audit = DeliveryAudit()
    channels = [
        ChatChannel(),
        TableChannel(db_path),
        ReportChannel(out_dir),
        EmailChannel(smtp_factory=smtp_factory, to_addrs=to_addrs,
                     dry_run=False),
    ]
    receipts = {}
    for channel in channels:
        receipts[channel.name] = dispatch(result, channel, audit=audit)
    return {"receipts": receipts, "audit": audit, "email_client": channels[3].smtp}
