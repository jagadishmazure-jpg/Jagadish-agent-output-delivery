"""Delivery channels: chat, table, report, email.

Every channel exposes the same interface — ``name`` and
``deliver(result) -> DeliveryReceipt`` — so callers (and the demo) can treat
them uniformly. Use ``dispatch()`` as the entry point: it enforces the
delivery policies BEFORE the channel sends, and records the outcome in the
audit log.
"""

from __future__ import annotations

import html
import json
import os
import smtplib
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage

from . import policy
from .policy import PolicyDenied


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class DeliveryReceipt:
    result_id: str
    channel: str
    delivered_at: str
    detail: dict = field(default_factory=dict)


class ChatChannel:
    """Formats a result as a Markdown message for chat UIs."""

    name = "chat"

    def deliver(self, result) -> DeliveryReceipt:
        lines = [f"# {result.title}", "", result.summary, ""]
        if result.figures:
            lines.append("## Key figures")
            for key, value in result.figures.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")
        for table in result.tables:
            lines.append(f"## {table['name']}")
            lines.append("| " + " | ".join(table["columns"]) + " |")
            lines.append("| " + " | ".join("---" for _ in table["columns"]) + " |")
            for row in table["rows"]:
                lines.append("| " + " | ".join(str(c) for c in row) + " |")
            lines.append("")
        if result.citations:
            lines.append("_Sources: " + "; ".join(result.citations) + "_")
        message = "\n".join(lines).rstrip() + "\n"
        return DeliveryReceipt(
            result_id=result.id,
            channel=self.name,
            delivered_at=_utcnow(),
            detail={"message": message, "chars": len(message)},
        )


class TableChannel:
    """Writes result rows to a SQLite table that feeds dashboards.

    Schema-validated and idempotent: re-delivering the same result id
    upserts the row instead of duplicating it.
    """

    name = "table"
    TABLE_SQL = (
        "CREATE TABLE IF NOT EXISTS agent_result_deliveries ("
        "result_id TEXT PRIMARY KEY, "
        "title TEXT NOT NULL, "
        "summary TEXT NOT NULL, "
        "payload TEXT NOT NULL, "
        "delivered_at TEXT NOT NULL)"
    )

    def __init__(self, db_path: str):
        self.db_path = db_path

    def deliver(self, result) -> DeliveryReceipt:
        payload = json.dumps(result.to_dict(), sort_keys=True)
        delivered_at = _utcnow()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(self.TABLE_SQL)
            conn.execute(
                "INSERT INTO agent_result_deliveries "
                "(result_id, title, summary, payload, delivered_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(result_id) DO UPDATE SET "
                "title=excluded.title, summary=excluded.summary, "
                "payload=excluded.payload, delivered_at=excluded.delivered_at",
                (result.id, result.title, result.summary, payload, delivered_at),
            )
            conn.commit()
            count = conn.execute(
                "SELECT COUNT(*) FROM agent_result_deliveries"
            ).fetchone()[0]
        finally:
            conn.close()
        return DeliveryReceipt(
            result_id=result.id,
            channel=self.name,
            delivered_at=delivered_at,
            detail={"db_path": self.db_path, "table_rows": count},
        )


class ReportChannel:
    """Generates a standalone HTML report file in a deliverables directory."""

    name = "report"

    def __init__(self, out_dir: str):
        self.out_dir = out_dir

    def _render(self, result) -> str:
        esc = html.escape
        parts = [
            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>{esc(result.title)}</title></head><body>",
            f"<h1>{esc(result.title)}</h1>",
            f"<p>{esc(result.summary)}</p>",
            f"<p><small>Generated {esc(result.generated_at)} · id {esc(result.id)}</small></p>",
        ]
        if result.figures:
            parts.append("<h2>Key figures</h2><ul>")
            for key, value in result.figures.items():
                parts.append(f"<li><b>{esc(key)}</b>: {esc(str(value))}</li>")
            parts.append("</ul>")
        for table in result.tables:
            parts.append(f"<h2>{esc(table['name'])}</h2>")
            parts.append("<table border='1' cellpadding='4'><thead><tr>")
            parts.extend(f"<th>{esc(c)}</th>" for c in table["columns"])
            parts.append("</tr></thead><tbody>")
            for row in table["rows"]:
                parts.append("<tr>" + "".join(f"<td>{esc(str(c))}</td>" for c in row) + "</tr>")
            parts.append("</tbody></table>")
        if result.citations:
            parts.append("<h2>Sources</h2><ul>")
            parts.extend(f"<li>{esc(c)}</li>" for c in result.citations)
            parts.append("</ul>")
        parts.append("</body></html>")
        return "\n".join(parts)

    def deliver(self, result) -> DeliveryReceipt:
        os.makedirs(self.out_dir, exist_ok=True)
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in result.id)
        path = os.path.join(self.out_dir, f"{safe_id}.html")
        content = self._render(result)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return DeliveryReceipt(
            result_id=result.id,
            channel=self.name,
            delivered_at=_utcnow(),
            detail={"path": path, "bytes": len(content.encode("utf-8"))},
        )


class FakeSMTP:
    """In-memory stand-in for smtplib.SMTP used by tests (no network).

    Usage: EmailChannel(smtp_factory=FakeSMTP, ...), then inspect
    ``channel.smtp.sent`` for captured EmailMessage objects.
    """

    def __init__(self, *args, **kwargs):
        self.sent: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send_message(self, msg):
        self.sent.append(msg)


class EmailChannel:
    """Sends the result as an email via smtplib.

    ``smtp_factory`` defaults to ``smtplib.SMTP``; tests pass ``FakeSMTP``
    so no network is touched.

    SAFETY: dry-run is ON by default — ``deliver()`` logs the message
    instead of connecting. Pass ``dry_run=False`` with an explicit host
    to actually send. No credentials are stored here; pass them via the
    ``smtp_factory`` if needed (never commit them).
    """

    name = "email"

    def __init__(self, smtp_factory=smtplib.SMTP, host="localhost", port=25,
                 from_addr="agents@example.com", to_addrs=("ops@example.com",),
                 dry_run=True):
        self.smtp_factory = smtp_factory
        self.host = host
        self.port = port
        self.from_addr = from_addr
        self.to_addrs = tuple(to_addrs)
        self.dry_run = dry_run
        self.smtp = None  # last used client (lets tests inspect FakeSMTP.sent)

    def _build_message(self, result) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = f"[agent] {result.title}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        body = [result.summary, ""]
        if result.figures:
            body.append("Key figures:")
            for key, value in result.figures.items():
                body.append(f"  {key}: {value}")
            body.append("")
        body.append(f"Result id: {result.id} · generated {result.generated_at}")
        if result.citations:
            body.append("Sources: " + "; ".join(result.citations))
        msg.set_content("\n".join(body))
        return msg

    def deliver(self, result) -> DeliveryReceipt:
        msg = self._build_message(result)
        if self.dry_run:
            return DeliveryReceipt(
                result_id=result.id,
                channel=self.name,
                delivered_at=_utcnow(),
                detail={"to": list(self.to_addrs), "subject": msg["Subject"],
                        "dry_run": True},
            )
        client = self.smtp_factory(self.host, self.port)
        self.smtp = client
        if hasattr(client, "__enter__"):
            with client as smtp:
                smtp.send_message(msg)
        else:
            client.send_message(msg)
        return DeliveryReceipt(
            result_id=result.id,
            channel=self.name,
            delivered_at=_utcnow(),
            detail={"to": list(self.to_addrs), "subject": msg["Subject"]},
        )


CHANNELS = {
    "chat": ChatChannel,
    "table": TableChannel,
    "report": ReportChannel,
    "email": EmailChannel,
}


def dispatch(result, channel, audit=None) -> DeliveryReceipt:
    """Policy-check, deliver, and audit-log. Raises PolicyDenied on denial.

    ``channel`` is a channel instance (e.g. ChatChannel()). Unknown channel
    names raise ValueError.
    """
    name = getattr(channel, "name", None)
    if name not in CHANNELS:
        raise ValueError(f"unknown channel: {name!r}")
    try:
        policy.check(result, name)
    except PolicyDenied as denied:
        if audit is not None:
            audit.log(result.id, name, "denied",
                      policy_checks=[denied.policy_id],
                      detail={"reason": denied.reason})
        raise
    receipt = channel.deliver(result)
    if audit is not None:
        audit.log(result.id, name, "delivered",
                  policy_checks=["POL-EMAIL-01", "POL-CHAT-02"],
                  detail=dict(receipt.detail))
    return receipt
