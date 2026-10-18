"""Tests for the five-area security assessment report. All deterministic,
stdlib only."""

import os

import pytest

from deliver.assessment import (
    AREAS,
    SEVERITIES,
    Assessment,
    AssessmentError,
    Finding,
    build_report,
    render_html,
)


# ---------------------------------------------------------------- fixtures

def make_finding(**overrides):
    base = dict(
        severity="high",
        area="effective_privilege",
        title="Standing admin on svc-etl",
        detail="svc-etl holds write on prod-db with no expiry.",
        recommendation="Convert to just-in-time elevation with 1h expiry.",
        proven_by="test_jit_expiry_enforced",
    )
    base.update(overrides)
    return Finding(**base)


def make_assessment(**overrides):
    base = dict(
        title="Q4 identity assessment",
        surface={"identities": 14, "agents": 6, "tools": 22,
                 "scopes": 31, "secrets": 9},
        findings=[
            make_finding(severity="critical", area="effective_privilege",
                         title="Orphaned admin key",
                         proven_by="test_orphan_detection"),
            make_finding(severity="low", area="security_themes",
                         title="Rotation overdue 31d",
                         proven_by="test_rotation_check"),
            make_finding(severity="high", area="emerging_themes",
                         title="Unregistered agent calling prod",
                         proven_by="test_shadow_detected"),
            make_finding(severity="medium", area="security_themes",
                         title="MFA not enforced on vault",
                         proven_by="test_mfa_policy"),
        ],
        generated_at="2026-10-18T09:00:00+00:00",
    )
    base.update(overrides)
    return Assessment(**base)


# ------------------------------------------------------- validation: Finding

def test_finding_rejects_bad_severity():
    with pytest.raises(AssessmentError):
        make_finding(severity="urgent")


def test_finding_rejects_bad_area():
    with pytest.raises(AssessmentError):
        make_finding(area="network")


def test_finding_rejects_empty_proven_by():
    with pytest.raises(AssessmentError):
        make_finding(proven_by="   ")


def test_finding_rejects_bad_status():
    with pytest.raises(AssessmentError):
        make_finding(status="ignored")


def test_finding_defaults_to_open():
    assert make_finding().status == "open"


# ---------------------------------------------------- validation: Assessment

def test_assessment_rejects_non_finding():
    with pytest.raises(AssessmentError):
        Assessment(findings=["not-a-finding"])


def test_assessment_rejects_negative_surface_count():
    with pytest.raises(AssessmentError):
        Assessment(surface={"agents": -1})


def test_assessment_rejects_empty_title():
    with pytest.raises(AssessmentError):
        Assessment(title="  ")


# ------------------------------------------------------------------ ranking

def test_ranked_findings_severity_order():
    ranked = make_assessment().ranked_findings()
    severities = [f.severity for _, f in ranked]
    assert severities == ["critical", "high", "medium", "low"]
    assert [rank for rank, _ in ranked] == [1, 2, 3, 4]


def test_ranked_findings_stable_within_severity():
    a = make_assessment(findings=[
        make_finding(severity="high", title="First"),
        make_finding(severity="high", title="Second"),
    ])
    ranked = a.ranked_findings()
    assert [f.title for _, f in ranked] == ["First", "Second"]


# ------------------------------------------------------------------- stats

def test_counts_by_area():
    counts = make_assessment().counts_by_area()
    assert counts["effective_privilege"] == 1
    assert counts["security_themes"] == 2
    assert counts["emerging_themes"] == 1
    assert counts["overview"] == 0
    assert counts["findings"] == 0
    assert set(counts) == set(AREAS)


def test_counts_by_severity():
    counts = make_assessment().counts_by_severity()
    assert counts == {"critical": 1, "high": 1, "medium": 1, "low": 1}
    assert set(counts) == set(SEVERITIES)


def test_summary_aggregates():
    s = make_assessment().summary()
    assert s["total_findings"] == 4
    assert s["critical_and_high"] == 2
    assert s["open"] == 4
    assert s["surface"]["agents"] == 6


def test_to_dict_roundtrip_shape():
    d = make_assessment().to_dict()
    assert d["title"] == "Q4 identity assessment"
    assert len(d["findings"]) == 4
    assert d["findings"][0]["proven_by"] == "test_orphan_detection"
    assert d["summary"]["total_findings"] == 4


# ---------------------------------------------------------------- rendering

def test_render_contains_all_five_sections():
    html = render_html(make_assessment())
    for heading in ("Overview", "Effective privilege", "Security themes",
                    "Emerging themes", "Findings explorer"):
        assert heading in html


def test_render_explorer_shows_every_detection():
    # The explorer must list all 4 findings even though none has
    # area="findings".
    html = render_html(make_assessment())
    explorer = html.split("Findings explorer", 1)[1]
    for title in ("Orphaned admin key", "Rotation overdue 31d",
                  "Unregistered agent calling prod", "MFA not enforced on vault"):
        assert title in explorer


def test_render_thematic_section_filters_by_area():
    html = render_html(make_assessment())
    sec = html.split("2 · Effective privilege", 1)[1].split("<h2>", 1)[0]
    assert "Orphaned admin key" in sec
    assert "Rotation overdue 31d" not in sec


def test_render_escapes_html():
    a = make_assessment(findings=[
        make_finding(title="<script>alert(1)</script>",
                     detail="<b>bold</b>",
                     recommendation="x & y",
                     proven_by="test_xss"),
    ])
    html = render_html(a)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "x &amp; y" in html


def test_render_empty_assessment():
    a = Assessment(title="Empty", surface={}, findings=[],
                   generated_at="2026-10-18T09:00:00+00:00")
    html = render_html(a)
    assert "Total findings: 0" in html
    assert "No surface composition provided." in html
    assert "No findings in this area." in html
    for heading in ("Overview", "Effective privilege", "Security themes",
                    "Emerging themes", "Findings explorer"):
        assert heading in html


def test_render_shows_proven_by():
    html = render_html(make_assessment())
    assert "<code>test_orphan_detection</code>" in html


# ------------------------------------------------------------------- build

def test_build_report_writes_file(tmp_path):
    out = str(tmp_path / "assessment.html")
    receipt = build_report(make_assessment(), out)
    assert os.path.isfile(out)
    assert receipt["bytes"] > 1000
    assert receipt["summary"]["total_findings"] == 4
    with open(out, encoding="utf-8") as fh:
        content = fh.read()
    assert "Q4 identity assessment" in content


def test_build_report_rejects_empty_path():
    with pytest.raises(AssessmentError):
        build_report(make_assessment(), "   ")
