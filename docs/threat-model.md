# Threat model (STRIDE-lite)

| Threat | Where | Mitigation | Test |
|---|---|---|---|
| PII exfiltrated via email | `EmailChannel` | `POL-EMAIL-01` denies PII results before sending | `test_dispatch_denies_before_sending_and_audits` |
| Oversized dump pasted into chat | `ChatChannel` | `POL-CHAT-02` caps chat at 20 rows | `test_policy_denies_large_table_to_chat_with_id` |
| HTML/JS injection in report | `ReportChannel` | `html.escape` on all content | `test_report_escapes_html_injection` |
| Duplicate dashboard rows on retry | `TableChannel` | upsert by result id | `test_table_redelivery_is_idempotent` |
| Audit log tampering | `DeliveryAudit` | SHA-256 hash chain, `verify()` | `test_audit_detects_tampering` |
| Credential leak | email config | no credentials in repo; SMTP injected, `FakeSMTP` in tests | n/a (process) |
| Regex PII miss on novel formats | `pii.py` | documented limitation; patterns cover email/phone/SSN | `test_pii_phone_formats` |

Out of scope: transport security of real SMTP (deployer's responsibility),
access control on the SQLite feed and deliverables directory.
