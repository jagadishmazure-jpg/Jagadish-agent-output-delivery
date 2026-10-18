# Jagadish-agent-output-delivery

First-class output delivery for agent results: one validated `AgentResult` delivered to **chat**, **table** (dashboard feed), **report** (HTML), or **email** — with delivery policies enforced before anything sends and a hash-chained audit log of every delivery and denial.

> **Status:** runs offline and in CI only. Email uses `smtplib`; tests use an in-memory `FakeSMTP` — no network is ever touched.
> **Disclaimer:** independent portfolio project. Not affiliated with or endorsed by any real company. All data is synthetic demo data invented for illustration.

## Recruiter summary

- **Problem:** agents answer in chat but never *deliver* — no dashboard feed, no report file, no email, and no policy saying what may go where.
- **Approach:** a validated `AgentResult` (tables, figures, citations) plus four channels behind one `dispatch()` entry point; policies (`POL-EMAIL-01`: no PII by email; `POL-CHAT-02`: ≤20 rows in chat) deny before sending; every outcome lands in a hash-chained audit log.
- **Proof:** 42 tests pass, including idempotent table re-delivery, both policy denials, `FakeSMTP` capture, and audit tamper detection. Sample run: chat message 455 chars, dashboard table 1 row after re-delivery, HTML report 928 bytes, 4 audit entries verified intact.

## How it works

1. An agent builds an `AgentResult` — validated at construction (non-empty id/title/summary, well-formed tables, numeric figures).
2. The caller picks a channel and calls `dispatch(result, channel, audit=audit)`.
3. `dispatch()` runs `policy.check()` first. A denial raises `PolicyDenied` with the policy ID cited and is audit-logged — the channel never sends.
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

Real output from the sample run (`deliver_all`): four receipts, one per channel, and an audit chain of 4 entries that `verify()` confirms intact.

## Channels

| Channel | What it does |
|---|---|
| `chat` | Markdown message: title, summary, key figures, tables, citations |
| `table` | SQLite `agent_result_deliveries` table (dashboard feed); upsert by result id — re-delivery never duplicates |
| `report` | Standalone HTML file in a deliverables dir (summary, figures, tables, sources); HTML-escaped |
| `email` | `smtplib` send; tests inject `FakeSMTP` so nothing leaves the machine |

## Guardrails

- **POL-EMAIL-01** — results containing PII (email/phone/SSN) cannot be emailed; use chat or table.
- **POL-CHAT-02** — results with more than 20 table rows cannot go to chat; use report or table.
- Policies run before sending; denials are audit-logged with the policy ID.
- The audit log is hash-chained (`sha256`, `GENESIS`-anchored); `verify()` detects tampering.
- Report HTML escapes all content (tested against `<script>` injection).

## Limitations and known failures

- `FakeSMTP` only stands in for `smtplib.SMTP`; real delivery needs real SMTP credentials (never committed).
- Chat rendering is plain Markdown — no per-platform (Teams/Slack) formatting.
- Table channel stores one JSON payload per result; it is a feed, not a warehouse.
- PII detection is regex-based; novel formats can slip through (kept visible as a limitation, not a claim).

## How to run

```bash
python3 -m pytest tests/ -v        # 42 tests
python3 scripts/count_tests.py     # prints the real total
```

Optional Streamlit demo: `pip install streamlit && streamlit run demo/app.py` (imports streamlit lazily; all logic is tested in `deliver/demo_helpers.py`).

## Built / Written-not-run / Planned

| Status | Item |
|---|---|
| Built | `AgentResult` validation, 4 channels, 2 delivery policies, hash-chained audit, demo helpers, 42 tests |
| Written-not-run | `.github/workflows/ci.yml` (for the GitHub repo; not executed locally) |
| Planned | Teams/Slack channel formatters, scheduled digest delivery, per-recipient policy profiles |

## Docs

- `knowledge/domain-notes.md` — why delivery is a first-class agent concern
- `knowledge/architecture.md` — Mermaid architecture diagram
- `docs/implementation-guide.md` — adopt the pattern in your own agents
- `docs/interview-points.md` — how to talk about this in interviews
- `docs/threat-model.md` — STRIDE-lite threat model

## Inspiration

The problem framing (agents must *deliver* results to chat, tables, reports,
and email — not just answer) is inspired by the data-agent pattern from
recent industry literature on practical AI agents. All design, code, and
docs here are original.
