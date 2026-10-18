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

## Structured assessments for security findings

Flat finding lists serve nobody well: the analyst needs severity order, the
leader needs themes, the auditor needs proof. The five-area assessment
(`deliver/assessment.py`) is one report cut five ways:

1. **Overview** — what was assessed (surface composition).
2. **Effective privilege** — who holds what, and the indirect paths.
3. **Security themes** — are the foundational safeguards actually working?
4. **Emerging themes** — the risks moving fastest (agent identities, secret
   sprawl).
5. **Findings explorer** — every detection, severity-sorted, priority-ranked.

The standing rule carries over from delivery: every finding names its proof
(`proven_by`). A claim without a named test or check is rejected at
construction — the same way a result without validation never reaches a
channel.
