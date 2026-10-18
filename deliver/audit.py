"""Hash-chained delivery audit log.

Every delivery (and every policy denial) is appended with a SHA-256 hash
chained to the previous entry. verify() replays the chain; any tampering
with an earlier entry breaks every hash after it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash_entry(entry: dict) -> str:
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DeliveryAudit:
    """Append-only, tamper-evident log of deliveries."""

    def __init__(self):
        self.entries: list = []

    def log(self, result_id: str, channel: str, outcome: str,
            policy_checks: list | None = None, detail: dict | None = None,
            at: str | None = None) -> dict:
        """Append one entry. outcome is 'delivered' or 'denied'."""
        entry = {
            "seq": len(self.entries),
            "at": at or _utcnow(),
            "result_id": result_id,
            "channel": channel,
            "outcome": outcome,
            "policy_checks": list(policy_checks or []),
            "detail": dict(detail or {}),
            "prev": self.entries[-1]["hash"] if self.entries else "GENESIS",
        }
        entry["hash"] = _hash_entry({k: v for k, v in entry.items() if k != "hash"})
        self.entries.append(entry)
        return entry

    def verify(self) -> bool:
        """Return True iff the whole chain is intact."""
        prev = "GENESIS"
        for i, entry in enumerate(self.entries):
            if entry.get("seq") != i or entry.get("prev") != prev:
                return False
            recomputed = _hash_entry(
                {k: v for k, v in entry.items() if k != "hash"}
            )
            if recomputed != entry.get("hash"):
                return False
            prev = entry["hash"]
        return True
