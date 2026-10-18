# Implementation guide

How to add first-class delivery to your own agents.

## 1. Model the result, not the message

Define one validated container per agent output. Validate at construction:
ids and titles non-empty, tables well-formed (columns match every row),
figures numeric. A malformed result must never reach a channel — fail at
build time, not at send time.

## 2. One dispatch entry point

```python
receipt = dispatch(result, channel, audit=audit)
```

`dispatch()` runs policy checks first, then the channel, then audit-logs the
outcome. Never let callers invoke `channel.deliver()` directly in
production code — the policy gate is the point.

## 3. Write policies as data + one check function

Each policy gets an ID (`POL-EMAIL-01`), a plain-language description, and
a check that raises `PolicyDenied(policy_id, reason)`. Start with two:

- PII-containing results cannot be emailed (scan summary + table cells).
- Oversized results cannot go to chat (row-count threshold).

Denied deliveries are audit-logged with the policy ID — the log shows what
was *blocked*, not just what was sent.

## 4. Make table delivery idempotent

Dashboard feeds get re-delivered (retries, replays). Upsert by result id
(`INSERT ... ON CONFLICT DO UPDATE`) so re-delivery replaces rather than
duplicates. Test it: deliver twice, assert one row.

## 5. Keep the audit log tamper-evident

Chain each entry's SHA-256 to the previous entry's hash, anchored at a
`GENESIS` entry. Provide `verify()`. Log denials too — a blocked send is
as audit-relevant as a successful one.

## 6. Test the email path without a network

Inject the SMTP client. A 10-line `FakeSMTP` capturing `EmailMessage`
objects gives you full coverage of subject/body/recipients with zero
network. Real credentials never enter the repo.
