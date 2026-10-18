# Interview points

- **The gap it fills:** "Every agent demo ends at the answer. In production the answer has to land somewhere — a dashboard, a report file, someone's inbox — and each destination has different rules. This repo makes delivery a first-class layer instead of an afterthought."
- **Design decision:** "One `dispatch()` entry point runs policy checks *before* the channel sends. A denied delivery raises with the policy ID cited and is still audit-logged — the log records what was blocked, not just what went through."
- **Idempotency:** "Dashboard feeds get re-delivered on retries. The table channel upserts by result id, so re-delivery replaces instead of duplicating — tested explicitly."
- **Audit:** "Hash-chained log, genesis-anchored, with a `verify()` that replays the chain. Tamper with one entry and every later hash breaks — there's a test that does exactly that."
- **Email without network:** "The SMTP client is injected. Tests use a ten-line `FakeSMTP`; no test has ever touched a network, and no credential lives in the repo."
- **Numbers:** "42 tests, all green. Sample run: 455-char chat message, 1 dashboard row after re-delivery, 928-byte HTML report, 4-entry audit chain verified intact."
