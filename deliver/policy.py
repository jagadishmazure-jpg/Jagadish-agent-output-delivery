"""Delivery policies: what may go where.

Policies are checked BEFORE any channel sends. A denial raises PolicyDenied
with the policy ID cited, so the caller (and the audit log) always knows
exactly which rule fired.
"""

from __future__ import annotations

from .pii import scan_result

MAX_CHAT_ROWS = 20


class PolicyDenied(Exception):
    """Raised when a delivery policy blocks a channel."""

    def __init__(self, policy_id: str, reason: str):
        super().__init__(f"{policy_id}: {reason}")
        self.policy_id = policy_id
        self.reason = reason


def check(result, channel_name: str) -> None:
    """Enforce delivery policies for (result, channel). Raises PolicyDenied."""
    if channel_name == "email":
        hits = scan_result(result)
        if hits:
            kinds = sorted({kind for kind, _, _ in hits})
            raise PolicyDenied(
                "POL-EMAIL-01",
                f"result contains PII ({', '.join(kinds)}); "
                "email delivery is denied — use chat or table",
            )
    if channel_name == "chat":
        rows = result.total_rows()
        if rows > MAX_CHAT_ROWS:
            raise PolicyDenied(
                "POL-CHAT-02",
                f"result has {rows} rows (limit {MAX_CHAT_ROWS} for chat); "
                "use report or table",
            )


POLICIES = (
    ("POL-EMAIL-01", "PII-containing results cannot be emailed"),
    ("POL-CHAT-02", f"results with more than {MAX_CHAT_ROWS} rows cannot go to chat"),
    ("POL-EMAIL-03", "real sends go to a loopback SMTP server unless allow_remote_host=True"),
    ("POL-EMAIL-04", "real SMTP sends are refused under CI"),
)

_CHANNEL_CHECKS = {
    "email": ["POL-EMAIL-01", "POL-EMAIL-03", "POL-EMAIL-04"],
    "chat": ["POL-CHAT-02"],
}


def checks_for(channel_name: str) -> list:
    """Policy IDs that actually apply to a channel (for the audit entry)."""
    return list(_CHANNEL_CHECKS.get(channel_name, []))
