# Security policy

This is a portfolio demo project. If you find a security issue, please open
a GitHub issue rather than using it against a live system.

Notes for adopters:

- Never commit SMTP credentials. The email channel takes an injected SMTP
  client; use your platform's secret store in production.
- The `table` channel writes a local SQLite file; put access controls on it
  if the feed carries sensitive data.
- PII detection is regex-based and best-effort — treat it as a safety net,
  not a guarantee.
