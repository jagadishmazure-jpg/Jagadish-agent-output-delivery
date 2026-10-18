"""Tests for agent output delivery: result validation, four channels, policies,
audit chain, dispatcher, and demo helpers. All deterministic, stdlib only."""

import os
import sqlite3

import pytest

from deliver import policy
from deliver.audit import DeliveryAudit
from deliver.channels import (ChatChannel, EmailChannel, FakeSMTP,
                              ReportChannel, TableChannel, dispatch)
from deliver.demo_helpers import deliver_all, sample_result
from deliver.pii import contains_pii, find_pii, scan_result
from deliver.policy import MAX_CHAT_ROWS, PolicyDenied
from deliver.result import AgentResult, ResultError


# ---------------------------------------------------------------- fixtures

def make_result(**overrides):
    base = dict(
        id="RES-1",
        title="Daily ops summary",
        summary="All systems nominal.",
        tables=[{
            "name": "kpis",
            "columns": ["metric", "value"],
            "rows": [["uptime_pct", 99.9], ["incidents", 0]],
        }],
        figures={"uptime_pct": 99.9},
        citations=["runbook §1"],
        generated_at="2026-10-18T06:00:00+00:00",
    )
    base.update(overrides)
    return AgentResult(**base)


def big_result(n=25):
    return make_result(
        id="RES-BIG",
        tables=[{
            "name": "events",
            "columns": ["id", "detail"],
            "rows": [[f"E-{i}", f"detail-{i}"] for i in range(n)],
        }],
    )


def pii_result():
    return make_result(
        id="RES-PII",
        summary="Escalated to jane.doe@example.com after the call.",
        tables=[{
            "name": "contacts",
            "columns": ["name", "phone"],
            "rows": [["Jane", "(555) 123-4567"]],
        }],
    )


# ---------------------------------------------------------------- result validation

def test_result_builds_and_reports_row_count():
    r = make_result()
    assert r.total_rows() == 2
    assert r.to_dict()["id"] == "RES-1"


def test_result_rejects_empty_id():
    with pytest.raises(ResultError):
        make_result(id="  ")


def test_result_rejects_empty_title():
    with pytest.raises(ResultError):
        make_result(title="")


def test_result_rejects_empty_summary():
    with pytest.raises(ResultError):
        make_result(summary="")


def test_result_rejects_ragged_table_row():
    with pytest.raises(ResultError):
        make_result(tables=[{
            "name": "t", "columns": ["a", "b"], "rows": [["only-one"]],
        }])


def test_result_rejects_table_without_columns():
    with pytest.raises(ResultError):
        make_result(tables=[{"name": "t", "columns": [], "rows": []}])


def test_result_rejects_non_numeric_figure():
    with pytest.raises(ResultError):
        make_result(figures={"x": "many"})


def test_result_rejects_non_string_citation():
    with pytest.raises(ResultError):
        make_result(citations=["ok", 42])


def test_result_defaults_generated_at():
    r = AgentResult(id="x", title="t", summary="s")
    assert r.generated_at  # auto-filled ISO timestamp


# ---------------------------------------------------------------- chat channel

def test_chat_renders_markdown():
    receipt = ChatChannel().deliver(make_result())
    msg = receipt.detail["message"]
    assert msg.startswith("# Daily ops summary")
    assert "All systems nominal." in msg
    assert "| metric | value |" in msg
    assert "| uptime_pct | 99.9 |" in msg
    assert "- **uptime_pct**: 99.9" in msg
    assert "runbook §1" in msg


def test_chat_receipt_fields():
    receipt = ChatChannel().deliver(make_result())
    assert receipt.channel == "chat"
    assert receipt.result_id == "RES-1"
    assert receipt.detail["chars"] > 0


def test_chat_handles_result_without_tables():
    r = make_result(tables=[])
    msg = ChatChannel().deliver(r).detail["message"]
    assert "# Daily ops summary" in msg
    assert "|" not in msg.replace("runbook §1", "")


# ---------------------------------------------------------------- table channel

def test_table_writes_and_counts_rows(tmp_path):
    db = str(tmp_path / "feed.db")
    receipt = TableChannel(db).deliver(make_result())
    assert receipt.detail["table_rows"] == 1
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT result_id, title FROM agent_result_deliveries").fetchone()
    conn.close()
    assert row == ("RES-1", "Daily ops summary")


def test_table_redelivery_is_idempotent(tmp_path):
    db = str(tmp_path / "feed.db")
    ch = TableChannel(db)
    ch.deliver(make_result())
    receipt = ch.deliver(make_result())  # same id again
    assert receipt.detail["table_rows"] == 1  # not duplicated


def test_table_upsert_updates_payload(tmp_path):
    db = str(tmp_path / "feed.db")
    ch = TableChannel(db)
    ch.deliver(make_result())
    ch.deliver(make_result(summary="Updated summary."))
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT summary FROM agent_result_deliveries").fetchall()
    conn.close()
    assert rows == [("Updated summary.",)]


def test_table_stores_full_payload_json(tmp_path):
    import json
    db = str(tmp_path / "feed.db")
    TableChannel(db).deliver(make_result())
    conn = sqlite3.connect(db)
    payload = json.loads(conn.execute(
        "SELECT payload FROM agent_result_deliveries").fetchone()[0])
    conn.close()
    assert payload["figures"] == {"uptime_pct": 99.9}
    assert payload["tables"][0]["rows"][0] == ["uptime_pct", 99.9]


# ---------------------------------------------------------------- report channel

def test_report_writes_html_file(tmp_path):
    out = str(tmp_path / "deliverables")
    receipt = ReportChannel(out).deliver(make_result())
    path = receipt.detail["path"]
    assert os.path.isfile(path)
    assert path.endswith("RES-1.html")
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    assert "<h1>Daily ops summary</h1>" in content
    assert "<td>uptime_pct</td>" in content
    assert "99.9" in content


def test_report_escapes_html_injection():
    import tempfile
    with tempfile.TemporaryDirectory() as out:
        r = make_result(summary="<script>alert('x')</script>")
        path = ReportChannel(out).deliver(r).detail["path"]
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    assert "<script>" not in content
    assert "&lt;script&gt;" in content


def test_report_receipt_reports_bytes(tmp_path):
    receipt = ReportChannel(str(tmp_path)).deliver(make_result())
    assert receipt.detail["bytes"] > 500


# ---------------------------------------------------------------- email channel

def test_email_sends_via_fake_smtp():
    ch = EmailChannel(smtp_factory=FakeSMTP, to_addrs=("a@example.com",),
                      dry_run=False)
    receipt = ch.deliver(make_result())
    assert len(ch.smtp.sent) == 1
    msg = ch.smtp.sent[0]
    assert msg["Subject"] == "[agent] Daily ops summary"
    assert msg["To"] == "a@example.com"
    assert "All systems nominal." in msg.get_content()
    assert receipt.detail["subject"] == "[agent] Daily ops summary"


def test_email_defaults_to_dry_run():
    ch = EmailChannel(smtp_factory=FakeSMTP, to_addrs=("a@example.com",))
    receipt = ch.deliver(make_result())
    assert receipt.detail["dry_run"] is True
    assert ch.smtp is None  # never connected


def test_email_opt_in_sends():
    ch = EmailChannel(smtp_factory=FakeSMTP, to_addrs=("a@example.com",),
                      dry_run=False)
    ch.deliver(make_result())
    assert ch.smtp is not None and len(ch.smtp.sent) == 1


def test_email_body_includes_figures_and_citations():
    ch = EmailChannel(smtp_factory=FakeSMTP, dry_run=False)
    ch.deliver(make_result())
    body = ch.smtp.sent[0].get_content()
    assert "uptime_pct: 99.9" in body
    assert "runbook §1" in body


def test_email_supports_multiple_recipients():
    ch = EmailChannel(smtp_factory=FakeSMTP,
                      to_addrs=("a@example.com", "b@example.com"))
    receipt = ch.deliver(make_result())
    assert receipt.detail["to"] == ["a@example.com", "b@example.com"]


# ---------------------------------------------------------------- policies

def test_policy_denies_pii_to_email_with_id():
    with pytest.raises(PolicyDenied) as exc:
        policy.check(pii_result(), "email")
    assert exc.value.policy_id == "POL-EMAIL-01"


def test_policy_allows_clean_result_to_email():
    policy.check(make_result(), "email")  # no raise


def test_policy_denies_large_table_to_chat_with_id():
    with pytest.raises(PolicyDenied) as exc:
        policy.check(big_result(25), "chat")
    assert exc.value.policy_id == "POL-CHAT-02"
    assert "25" in exc.value.reason


def test_policy_allows_table_at_chat_limit():
    policy.check(big_result(MAX_CHAT_ROWS), "chat")  # exactly at limit: ok


def test_policy_denies_one_over_chat_limit():
    with pytest.raises(PolicyDenied):
        policy.check(big_result(MAX_CHAT_ROWS + 1), "chat")


def test_policy_allows_large_table_to_report_and_table():
    r = big_result(100)
    policy.check(r, "report")
    policy.check(r, "table")


def test_policy_allows_pii_to_chat_and_table():
    r = pii_result()
    policy.check(r, "chat")
    policy.check(r, "table")


# ---------------------------------------------------------------- pii detection

def test_pii_finds_email_phone_ssn():
    assert find_pii("mail jane.doe@example.com")[0][0] == "email"
    assert find_pii("call (555) 123-4567")[0][0] == "phone"
    assert find_pii("ssn 123-45-6789")[0][0] == "ssn"


def test_pii_phone_formats():
    for text in ["(555) 123-4567", "+1 (555) 123-4567", "555.123.4567",
                 "555-123-4567"]:
        assert contains_pii(text), text


def test_pii_leaves_dates_alone():
    assert not contains_pii("generated 2026-10-18")
    assert not contains_pii("on 2026-10-18T06:00:00")


def test_scan_result_finds_pii_in_table_cells():
    hits = scan_result(pii_result())
    kinds = {k for k, _, _ in hits}
    assert kinds == {"email", "phone"}


# ---------------------------------------------------------------- audit

def test_audit_chain_verifies():
    audit = DeliveryAudit()
    audit.log("R1", "chat", "delivered", at="2026-10-18T06:00:00+00:00")
    audit.log("R1", "email", "denied", policy_checks=["POL-EMAIL-01"],
              at="2026-10-18T06:01:00+00:00")
    assert audit.verify()
    assert audit.entries[1]["prev"] == audit.entries[0]["hash"]


def test_audit_detects_tampering():
    audit = DeliveryAudit()
    audit.log("R1", "chat", "delivered", at="2026-10-18T06:00:00+00:00")
    audit.log("R1", "table", "delivered", at="2026-10-18T06:01:00+00:00")
    audit.entries[0]["channel"] = "email"  # tamper
    assert not audit.verify()


def test_audit_entry_fields():
    audit = DeliveryAudit()
    entry = audit.log("R9", "report", "delivered",
                      policy_checks=["POL-EMAIL-01"],
                      detail={"path": "/tmp/x.html"},
                      at="2026-10-18T06:00:00+00:00")
    assert entry["seq"] == 0
    assert entry["prev"] == "GENESIS"
    assert len(entry["hash"]) == 64


# ---------------------------------------------------------------- dispatcher

def test_dispatch_routes_and_audits(tmp_path):
    audit = DeliveryAudit()
    receipt = dispatch(make_result(), ChatChannel(), audit=audit)
    assert receipt.channel == "chat"
    assert audit.entries[0]["outcome"] == "delivered"
    assert audit.verify()


def test_dispatch_denies_before_sending_and_audits():
    audit = DeliveryAudit()
    ch = EmailChannel(smtp_factory=FakeSMTP)
    with pytest.raises(PolicyDenied) as exc:
        dispatch(pii_result(), ch, audit=audit)
    assert exc.value.policy_id == "POL-EMAIL-01"
    assert ch.smtp is None  # never sent
    assert audit.entries[0]["outcome"] == "denied"
    assert audit.verify()


def test_dispatch_rejects_unknown_channel():
    class Weird:
        name = "pigeon"
    with pytest.raises(ValueError):
        dispatch(make_result(), Weird())


def test_dispatch_large_table_to_chat_denied_even_if_channel_would_send():
    with pytest.raises(PolicyDenied):
        dispatch(big_result(50), ChatChannel())


# ---------------------------------------------------------------- demo helpers

def test_sample_result_is_valid_and_deterministic():
    a, b = sample_result(), sample_result()
    assert a.to_dict() == b.to_dict()
    assert a.total_rows() == 3


def test_deliver_all_hits_four_channels(tmp_path):
    out = deliver_all(sample_result(), str(tmp_path / "feed.db"),
                      str(tmp_path / "reports"))
    receipts = out["receipts"]
    assert set(receipts) == {"chat", "table", "report", "email"}
    assert all(r.result_id == "RES-2026-0042" for r in receipts.values())
    assert out["audit"].verify()
    assert len(out["email_client"].sent) == 1
    assert os.path.isfile(receipts["report"].detail["path"])
