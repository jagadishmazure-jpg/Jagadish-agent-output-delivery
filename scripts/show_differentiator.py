"""Print what this repo does that in-memory answer formatting does not: it
actually writes to four channels, each behind its own policy, every attempt in
a hash-chained audit, and email that cannot leave the machine by accident."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deliver.channels import EmailChannel, FakeSMTP, dispatch  # noqa: E402
from deliver.demo_helpers import deliver_all, sample_result  # noqa: E402
from deliver.policy import PolicyDenied  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    out = deliver_all(sample_result(), f"{d}/dash.db", d)
    for e in out["audit"].entries:
        print(f"{e['channel']:<6} {e['outcome']}, checks={e['policy_checks']}")
    print("audit chain intact:", out["audit"].verify())

print("default email channel dry_run:", EmailChannel().dry_run)
try:
    dispatch(sample_result(), EmailChannel(smtp_factory=FakeSMTP, host="smtp.example.net", dry_run=False))
except PolicyDenied as e:
    print("remote host without opt-in ->", e.policy_id)
