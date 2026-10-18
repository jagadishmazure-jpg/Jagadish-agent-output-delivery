# Jagadish-agent-output-delivery

First-class output delivery for agent results: one validated `AgentResult` delivered to **chat**, **table** (dashboard feed), **report** (HTML), or **email** — with delivery policies enforced before anything sends and a hash-chained audit log of every delivery and denial.

> **Status:** runs offline. Email is a **dry run by default**; real sending needs an explicit opt-in, and CI refuses it. Tests use an in-memory `FakeSMTP`, so no network is ever touched.
> **Disclaimer:** independent portfolio project. Not affiliated with or endorsed by any real company. All data is synthetic demo data invented for illustration.

## Recruiter summary

- **Problem:** agents answer in chat but never *deliver* — no dashboard feed, no report file, no email, and no policy saying what may go where.
- **Approach:** a validated `AgentResult` (tables, figures, citations) plus four channels behind one `dispatch()` entry point; per-channel policies (`POL-EMAIL-01`: no PII by email; `POL-EMAIL-03`/`04`: no remote or CI sending without opt-in; `POL-CHAT-02`: ≤20 rows in chat) deny before sending; every outcome lands in a hash-chained audit log.
- **Proof:** all tests pass (real total below), including idempotent table re-delivery, every policy denial, `FakeSMTP` capture, CI refusal of real SMTP, and audit tamper detection.

## How it works

1. An agent builds an `AgentResult` — validated at construction (non-empty id/title/summary, well-formed tables, numeric figures).
2. The caller picks a channel and calls `dispatch(result, channel, audit=audit)`.
3. `dispatch()` runs `policy.check()` and the channel's own `preflight()` first. A denial raises `PolicyDenied` with the policy ID cited and is audit-logged — the channel never sends, and no SMTP client is created.
4. The channel delivers and returns a `DeliveryReceipt`; the audit log chains the entry.

```python
from deliver.channels import ChatChannel, dispatch
from deliver.demo_helpers import sample_result
from deliver.audit import DeliveryAudit

audit = DeliveryAudit()
receipt = dispatch(sample_result(), ChatChannel(), audit=audit)
print(receipt.detail["message"][:80])
# # Overnight incident summary
```

Real output, rendered from a fresh run in CI (each audit entry lists only the checks that apply to that channel):

<!-- run: python scripts/show_differentiator.py -->
```text
chat   delivered, checks=['POL-CHAT-02']
table  delivered, checks=[]
report delivered, checks=[]
email  delivered, checks=['POL-EMAIL-01', 'POL-EMAIL-03', 'POL-EMAIL-04']
audit chain intact: True
default email channel dry_run: True
remote host without opt-in -> POL-EMAIL-03
```
<!-- /run -->

## Channels

| Channel | What it does |
|---|---|
| `chat` | Markdown message: title, summary, key figures, tables, citations |
| `table` | SQLite `agent_result_deliveries` table (dashboard feed); upsert by result id — re-delivery never duplicates |
| `report` | Standalone HTML file in a deliverables dir (summary, figures, tables, sources); HTML-escaped |
| `email` | Dry run by default (message built, nothing sent). Opt-in sending goes to a local test SMTP server; tests inject `FakeSMTP` |

## Email safety

Sending mail is the one channel with effects outside the machine, so it is
off unless you ask for it twice:

| Setting | Behaviour |
|---|---|
| `EmailChannel()` | **Dry run.** Builds and returns the message; no SMTP client is created |
| `dry_run=False` | Sends only to a **loopback** host (`localhost`, `127.0.0.1`, `::1`), e.g. a local test server: `pip install aiosmtpd && python -m aiosmtpd -n -l localhost:8025`, then `EmailChannel(port=8025, dry_run=False)` |
| non-loopback `host` | Denied with **POL-EMAIL-03** unless `allow_remote_host=True` is also passed |
| `CI` or `GITHUB_ACTIONS` set | Real `smtplib.SMTP` is refused with **POL-EMAIL-04**, whatever the other flags say. CI only ever uses `FakeSMTP` |
| credentials | None. The code has no login call, the repo holds no SMTP settings, and CI has no mail secrets (gitleaks runs on every push) |

`to_addrs` must be non-empty, and a title containing a line break is
rejected when the result is built, so a header cannot be injected.

## Guardrails

- **POL-EMAIL-01** — results containing PII (email/phone/SSN/card number) cannot be emailed; use chat or table.
- **POL-EMAIL-03 / POL-EMAIL-04** — see Email safety above.
- **POL-CHAT-02** — results with more than 20 table rows cannot go to chat; use report or table.
- Policies run before sending; denials are audit-logged with the policy ID.
- The audit log is hash-chained (`sha256`, `GENESIS`-anchored); `verify()` detects tampering.
- Report HTML escapes all content (tested against `<script>` injection); chat table cells escape `|` and line breaks.
- Report filenames stay unique when an id needs sanitizing (`a/b` and `a_b` do not overwrite each other).

## Limitations and known failures

- Real delivery to a mail provider would need authentication, which this repo deliberately does not implement; it is a design for the delivery layer, not a mail client.
- Chat rendering is plain Markdown — no per-platform chat formatting.
- Table channel stores one JSON payload per result; it is a feed, not a warehouse.
- PII detection is regex-based; novel formats can slip through (kept visible as a limitation, not a claim).

## How to run

```bash
python3 -m pytest tests/ -v
python3 scripts/count_tests.py     # prints the real total
```

<!-- run: python scripts/count_tests.py -->
```text
56 tests collected
```
<!-- /run -->

Optional Streamlit demo: `pip install streamlit && streamlit run demo/app.py` (imports streamlit lazily; all logic is tested in `deliver/demo_helpers.py`).

## Built / Written-not-run / Planned

| Status | Item |
|---|---|
| Built | `AgentResult` validation, 4 channels, 4 delivery policies, email safety guards, hash-chained audit, demo helpers, tests, CI (tests, ruff, docs, brand check, gitleaks, CodeQL) |
| Planned | Per-platform chat formatters, scheduled digest delivery, per-recipient policy profiles |

## Docs

- `knowledge/domain-notes.md` — why delivery is a first-class agent concern
- `knowledge/architecture.md` — Mermaid architecture diagram
- `docs/implementation-guide.md` — adopt the pattern in your own agents
- `docs/interview-points.md` — how to talk about this in interviews
- `docs/threat-model.md` — STRIDE-lite threat model

## How this differs from governed-data-agent

`Jagadish-governed-data-agent` shapes an answer as chat, table or report
*in memory* and returns it. This repo is the step after that: it actually
writes the result somewhere (SQLite upsert, an HTML file, an email), each
channel behind its own policy, every attempt in a hash-chained audit. The
format ideas overlap; the delivery, the per-channel policies and the email
safety guards do not exist there.

## Standardization review (2026-10-18)

Bugs found in review and fixed, each with a regression test in
`tests/test_deliver.py` (section "review fixes"):

| ID | Bug | Fix |
|---|---|---|
| POL-EMAIL-03/04 | `dry_run=False` alone could send to any host, including from CI | Loopback only unless `allow_remote_host=True`; real SMTP refused under CI |
| PII-CARD-01 | Card numbers were not detected, so a result containing one could be emailed | Card pattern added to PII detection |
| RES-TITLE-01 | A title with a line break crashed the email build after the policy check, with no audit entry | Rejected when the result is built |
| AUDIT-CHECKS-01 | Audit entries listed policy IDs that did not apply to the channel | Each entry lists that channel's checks |
| CHAT-CELL-01 | `|` or a line break in a cell broke the chat table | Escaped |
| RPT-PATH-01 | `a/b` and `a_b` wrote the same report file | Hash suffix when the id is sanitized |
| DOC-COUNT-01 | README claimed 42 tests; there were 44 | Counts are now printed by `scripts/count_tests.py` and checked in CI |

## Why this exists

Agents usually stop at a chat answer. Real teams also need the result in a
dashboard table, a report file, or an email, with rules about what may go
where. That framing, and all design, code and docs here, are original to
this repo.
