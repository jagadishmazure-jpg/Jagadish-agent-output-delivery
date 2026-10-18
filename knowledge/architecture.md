# Architecture

```mermaid
flowchart LR
    Agent -->|builds| Result[AgentResult<br/>validated at construction]
    Result --> Dispatch[dispatch()]
    Dispatch --> Policy{policy.check()}
    Policy -->|denied| Denied[PolicyDenied<br/>+ audit log]
    Policy -->|allowed| Channel{channel}
    Channel -->|chat| Chat[Markdown message]
    Channel -->|table| Table[SQLite feed<br/>upsert by id]
    Channel -->|report| Report[HTML file]
    Channel -->|email| Email[smtplib / FakeSMTP]
    Chat --> Audit[Hash-chained audit log]
    Table --> Audit
    Report --> Audit
    Email --> Audit
```

`dispatch()` is the only entry point: policy first, channel second, audit
always. Channels share one interface (`name` + `deliver(result)`), so adding
a fifth channel means implementing two methods — no changes to policy or
audit code.
