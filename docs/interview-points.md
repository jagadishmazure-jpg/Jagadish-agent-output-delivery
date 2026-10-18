# Interview points

- **The gap it fills:** "Every agent demo ends at the answer. In production the answer has to land somewhere — a dashboard, a report file, someone's inbox — and each destination has different rules. This repo makes delivery a first-class layer instead of an afterthought."
- **Design decision:** "One `dispatch()` entry point runs policy checks *before* the channel sends. A denied delivery raises with the policy ID cited and is still audit-logged — the log records what was blocked, not just what went through."
- **Idempotency:** "Dashboard feeds get re-delivered on retries. The table channel upserts by result id, so re-delivery replaces instead of duplicating — tested explicitly."
- **Audit:** "Hash-chained log, genesis-anchored, with a `verify()` that replays the chain. Tamper with one entry and every later hash breaks — there's a test that does exactly that."
- **Email without network:** "The SMTP client is injected. Tests use a ten-line `FakeSMTP`; no test has ever touched a network, and no credential lives in the repo."
- **Email safety:** "Email is a dry run by default. Real sending needs `dry_run=False` and goes only to a loopback test server unless `allow_remote_host=True`; under CI a real SMTP client is refused outright."
- **Numbers:** "All tests green (`scripts/count_tests.py` prints the total). Sample run: four channels delivered, 4-entry audit chain verified intact."
