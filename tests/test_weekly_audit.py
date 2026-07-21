"""Regression tests for scripts/weekly_audit.py — the Saturday recall report.

Runs the real pipeline over synthetic per-day trace files in a temp audit dir,
covering: suffix→sampler mapping, shelly/IEAGHG rerouting, junk-domain
exclusion, the A★ (search-only) Chapman independence rule, kept-flag handling,
Chapman arithmetic, drift persistence, and the H1-becomes-email-subject
contract that email-audit.yml depends on."""

import json
from datetime import date

import pytest

import weekly_audit
from weekly_audit import (
    chapman,
    load_json_dumps,
    sampler_sets,
    week_dates,
)


@pytest.fixture()
def audit_env(monkeypatch, tmp_path):
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    junk = tmp_path / "junk_domains.txt"
    junk.write_text("# comment\nlinkedin.com\n\n")
    monkeypatch.setattr(weekly_audit, "AUDIT_DIR", audit_dir)
    monkeypatch.setattr(weekly_audit, "DB_PATH", audit_dir / "candidates.db")
    monkeypatch.setattr(weekly_audit, "JUNK_DOMAINS_PATH", junk)
    return audit_dir


def _row(url, headline="H", domain="ex.com", **extra):
    return {"canonical_url": url, "raw_url": url, "headline": headline,
            "source_domain": domain, "fuzzy_key": headline.lower(), **extra}


def test_week_dates_is_seven_days_ending_inclusive():
    dates = week_dates(date(2026, 7, 18))
    assert len(dates) == 7
    assert dates[0] == "2026-07-12" and dates[-1] == "2026-07-18"


def test_chapman_formula():
    # N̂ = (Nx+1)(Ny+1)/(M+1) − 1
    assert chapman(9, 9, 4) == pytest.approx(19.0)
    assert chapman(0, 5, 0) != chapman(0, 5, 0)  # NaN when a sampler is empty


def test_suffix_mapping_and_reroutes(audit_env):
    d = "2026-07-13"
    (audit_env / f"{d}-rss.json").write_text(json.dumps([_row("https://b.com/1")]))
    (audit_env / f"{d}-alerts.json").write_text(json.dumps([_row("https://c.com/1")]))
    (audit_env / f"{d}-shadow.json").write_text(json.dumps([
        _row("https://d.com/in", in_window=True),
        _row("https://d.com/out", in_window=False),  # must be excluded
    ]))
    (audit_env / f"{d}-candidates.json").write_text(json.dumps([
        _row("https://a.com/kept", kept=True),
        _row("https://a.com/rejected", kept=False),   # considered but not briefed
        _row("https://e.com/shelly", kept=True, found_via="shelly_digest"),
        _row("https://f.com/ieaghg", kept=True, found_via="ieaghg_newsletter"),
        _row("https://junk.com/x", kept=True, domain="linkedin.com"),  # junk excluded
    ]))

    by_day, ran = load_json_dumps([d], {"linkedin.com"})
    sets = sampler_sets(by_day)

    assert sets["B"] == {"https://b.com/1"}
    assert sets["C"] == {"https://c.com/1"}
    assert sets["D"] == {"https://d.com/in"}
    assert sets["E"] == {"https://e.com/shelly"}
    assert sets["F"] == {"https://f.com/ieaghg"}
    # A: only kept rows, junk excluded, shelly/ieaghg rerouted away.
    assert sets["A"] == {"https://a.com/kept"}
    assert ran == {"B": {d}, "C": {d}, "D": {d}, "A": {d}}


def test_a_pure_excludes_floor_ingested_items(audit_env):
    """Chapman independence: items the routine ingested from the RSS floor or
    Google Alerts must not count in A★ (they are not independent of B/C)."""
    d = "2026-07-14"
    (audit_env / f"{d}-candidates.json").write_text(json.dumps([
        _row("https://a.com/searched", kept=True, found_via="search_query"),
        _row("https://a.com/legacy", kept=True),                    # pre-change rows
        _row("https://a.com/from-rss", kept=True, found_via="rss"),
        _row("https://a.com/from-alerts", kept=True, found_via="google_alerts"),
    ]))
    sets = sampler_sets(load_json_dumps([d], set())[0])
    assert sets["A"] == {"https://a.com/searched", "https://a.com/legacy",
                         "https://a.com/from-rss", "https://a.com/from-alerts"}
    assert sets["A_pure"] == {"https://a.com/searched", "https://a.com/legacy"}


def test_malformed_trace_file_is_skipped_not_fatal(audit_env, capsys):
    d = "2026-07-15"
    (audit_env / f"{d}-rss.json").write_text("{broken")
    (audit_env / f"{d}-alerts.json").write_text(json.dumps([_row("https://c.com/1")]))
    by_day, ran = load_json_dumps([d], set())
    assert sampler_sets(by_day)["C"] == {"https://c.com/1"}
    assert "malformed JSON" in capsys.readouterr().err


def test_end_to_end_report_and_drift(audit_env, monkeypatch, capsys):
    """Full main() over a synthetic week: report files written, headline
    metrics correct, drift.json updated, H1 present for the email subject."""
    week_ending = "2026-07-18"
    d = "2026-07-16"
    (audit_env / f"{d}-rss.json").write_text(json.dumps([
        _row("https://b.com/hit", headline="Captured story"),
        _row("https://b.com/miss", headline="Missed story"),
    ]))
    (audit_env / f"{d}-candidates.json").write_text(json.dumps([
        _row("https://b.com/hit", headline="Captured story", kept=True,
             found_via="search_query"),
    ]))

    monkeypatch.setattr("sys.argv", ["weekly_audit.py", "--week-ending", week_ending])
    assert weekly_audit.main() == 0

    md_path = audit_env / f"{week_ending}-recall-report.md"
    html_path = audit_env / f"{week_ending}-recall-report.html"
    assert md_path.exists() and html_path.exists()

    md = md_path.read_text()
    # H1 (email subject contract) with the pooled-recall number in it.
    assert md.startswith(f"# CCS recall audit — week ending {week_ending}")
    # 1 of 2 union items captured -> 50% pooled and floor recall.
    assert "**50%**" in md
    assert "Missed story" in md

    drift = json.loads((audit_env / "drift.json").read_text())
    assert drift[-1]["week_ending"] == week_ending
    assert drift[-1]["pooled"] == pytest.approx(0.5)
    assert drift[-1]["floor"] == pytest.approx(0.5)

    html = html_path.read_text()
    assert html.startswith("<!doctype html>")
    assert "Missed story" in html


def test_drift_rerun_replaces_same_week(audit_env, monkeypatch):
    week_ending = "2026-07-18"
    (audit_env / "drift.json").write_text(json.dumps([
        {"week_ending": "2026-07-11", "pooled": 0.8, "floor": 0.9},
        {"week_ending": week_ending, "pooled": 0.1, "floor": 0.1},
    ]))
    rows = weekly_audit.load_drift(date(2026, 7, 18), 0.5, 0.6)
    assert [r["week_ending"] for r in rows] == ["2026-07-11", week_ending]
    assert rows[-1]["pooled"] == 0.5


def test_holiday_lists_stay_in_sync(repo_root):
    """deadman-check.yml hard-codes the Victorian public-holiday list and must
    match both routine prompts (README: 'the holiday list must be kept in
    sync with the production prompt')."""
    import re
    date_re = re.compile(r"\b(2026-\d{2}-\d{2})\b")

    def holidays_of(text, marker):
        for line in text.splitlines():
            if marker in line:
                return set(date_re.findall(line))
        return set()

    deadman = (repo_root / ".github" / "workflows" / "deadman-check.yml").read_text()
    production = (repo_root / "docs" / "routine-prompts" / "production.md").read_text()
    shadow = (repo_root / "docs" / "routine-prompts" / "shadow-sampler.md").read_text()

    hol_deadman = holidays_of(deadman, "HOLIDAYS=")
    hol_prod = holidays_of(production, "Holidays:")
    hol_shadow = holidays_of(shadow, "Holidays:")

    assert hol_deadman, "no HOLIDAYS= line found in deadman-check.yml"
    assert hol_deadman == hol_prod, "deadman-check holidays diverge from production prompt"
    assert hol_deadman == hol_shadow, "deadman-check holidays diverge from shadow prompt"
