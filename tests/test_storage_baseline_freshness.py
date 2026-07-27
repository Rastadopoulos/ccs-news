"""Regression tests for scripts/check_storage_baseline_freshness.py.

This script never writes storage-baseline.json -- it only detects and
surfaces candidate updates for a human to review, matching the same
discipline as imperial-register-check.yml and the funding-enrichment
review queue.
"""

import json

import check_storage_baseline_freshness as cs


def _project(name, aliases, reported_mt=None, reported_asof=None):
    return {"name": name, "news_aliases": aliases,
            "reported_cumulative_mt": reported_mt, "reported_asof": reported_asof}


def test_match_headline_finds_project_by_alias():
    projects = [_project("Gorgon", ["Gorgon CCS", "Barrow Island CO2"]),
                _project("Moomba", ["Moomba CCS"])]
    hit = cs.match_headline("Chevron ramps Gorgon CCS injection after outage", projects)
    assert hit is not None and hit["name"] == "Gorgon"


def test_match_headline_is_case_insensitive():
    projects = [_project("Moomba", ["Moomba CCS"])]
    hit = cs.match_headline("SANTOS SAYS MOOMBA CCS DELIVERING EMISSIONS REDUCTION", projects)
    assert hit is not None and hit["name"] == "Moomba"


def test_match_headline_returns_none_when_no_alias_present():
    projects = [_project("Gorgon", ["Gorgon CCS"]), _project("Moomba", ["Moomba CCS"])]
    assert cs.match_headline("Norway announces new CCUS funding round", projects) is None


def test_match_headline_first_project_wins_on_multi_match():
    """A headline mentioning two tracked projects records one match per
    headline (the first alias hit) rather than one row per project -- a
    deliberate simplification, not a bug, since this is a detection signal
    for human review, not an authoritative count."""
    projects = [_project("Gorgon", ["Gorgon CCS"]), _project("Moomba", ["Moomba CCS"])]
    hit = cs.match_headline("Australia's Gorgon CCS and Moomba CCS both mark milestones", projects)
    assert hit["name"] == "Gorgon"


def test_figure_regex_extracts_common_patterns():
    assert cs.FIGURE_RE.search("Moomba stores 2 million tonnes of CO2").group(0) \
        .lower().startswith("2 million tonnes")
    assert cs.FIGURE_RE.search("Gorgon injects 12 Mt to date") is not None
    assert cs.FIGURE_RE.search("stores 2 MtCO2e in Cooper Basin") is not None


def test_figure_regex_returns_none_when_headline_has_no_figure():
    assert cs.FIGURE_RE.search("Santos says Moomba CCS delivering emissions reduction") is None


def test_find_matches_skips_already_seen_urls():
    projects = [_project("Gorgon", ["Gorgon CCS"], reported_mt=12, reported_asof=2026)]
    rows = [("Gorgon CCS hits new milestone", "https://ex.com/a", "https://ex.com/a?x=1")]
    assert cs.find_matches(projects, {"https://ex.com/a"}, rows) == []
    matches = cs.find_matches(projects, set(), rows)
    assert len(matches) == 1
    assert matches[0]["project"] == "Gorgon"
    assert matches[0]["current_reported_mt"] == 12
    assert matches[0]["current_reported_asof"] == 2026


def test_find_matches_attaches_candidate_figure_when_present():
    projects = [_project("Moomba", ["Moomba CCS"])]
    rows = [("Moomba CCS crosses 2 million tonnes stored", "https://ex.com/b", "https://ex.com/b")]
    matches = cs.find_matches(projects, set(), rows)
    assert matches[0]["candidate_figure"].lower().startswith("2 million tonnes")


def test_find_matches_records_none_when_headline_has_no_figure():
    """A project mention with no extractable figure is still a real, useful
    signal -- the script must not drop it just because it can't attach a
    number (headlines-only coverage means many genuine updates won't state
    a figure directly in the headline)."""
    projects = [_project("Moomba", ["Moomba CCS"])]
    rows = [("Santos says Moomba CCS delivering emissions reduction", "https://ex.com/c", "https://ex.com/c")]
    matches = cs.find_matches(projects, set(), rows)
    assert len(matches) == 1
    assert matches[0]["candidate_figure"] is None


def test_seen_state_roundtrips_through_disk(tmp_path):
    path = tmp_path / "seen.json"
    assert cs.load_seen(path) == set()
    cs.save_seen({"https://ex.com/a", "https://ex.com/b"}, path)
    assert cs.load_seen(path) == {"https://ex.com/a", "https://ex.com/b"}


def test_read_candidate_rows_returns_empty_when_db_missing(tmp_path):
    assert cs.read_candidate_rows(tmp_path / "does-not-exist.db") == []


def test_format_html_table_escapes_and_includes_all_fields():
    matches = [{"project": "Gorgon", "headline": "Gorgon CCS <hits> milestone",
                "url": "https://ex.com/a", "candidate_figure": "12 Mt",
                "current_reported_mt": 12, "current_reported_asof": 2026}]
    out = cs.format_html_table(matches)
    assert "&lt;hits&gt;" in out and "<hits>" not in out
    assert "https://ex.com/a" in out
    assert "12 Mt (as of 2026)" in out


def test_format_html_table_handles_no_prior_figure_and_no_candidate():
    matches = [{"project": "Orca / CarbFix (Iceland dedicated site)", "headline": "CarbFix expands",
                "url": "https://ex.com/b", "candidate_figure": None,
                "current_reported_mt": None, "current_reported_asof": None}]
    out = cs.format_html_table(matches)
    assert "no figure on file" in out
    assert "—" in out  # em-dash placeholder for a missing candidate figure


def test_real_storage_baseline_projects_all_have_news_aliases(repo_root):
    """Regression for 2026-07-28: every project needs at least one alias or
    it is invisible to this detector -- silently missing a project defeats
    the entire point of covering 'all projects worldwide.'"""
    projects = cs.load_projects(repo_root / "dashboard" / "data" / "storage-baseline.json")
    missing = [p["name"] for p in projects if not p.get("news_aliases")]
    assert not missing, f"projects with no news_aliases: {missing}"
