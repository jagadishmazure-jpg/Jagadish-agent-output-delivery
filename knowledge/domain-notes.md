# Domain notes: why output delivery is a first-class agent concern

Most agent demos end at "the agent answered". In production, an answer that
goes nowhere is a dead end. Real operations need the result to *land*
somewhere useful:

- **Chat** — the human in the loop sees it now.
- **Table** — a dashboard feed the team watches all day.
- **Report** — a file someone can forward, file, or audit.
- **Email** — the stakeholder who was never in the chat.

Each destination has different constraints. Chat cannot swallow a 500-row
table. Email must never carry PII. A dashboard feed must survive
re-delivery without duplicating rows. These are not UI details — they are
delivery policies, and they belong next to the agent, enforced before
anything sends.

The second half of delivery is proof: *what* was delivered, *where*,
*when*, and *which policies were checked*. A hash-chained log makes that
proof tamper-evident, which is what turns "the agent sent it" into an
auditable fact.
