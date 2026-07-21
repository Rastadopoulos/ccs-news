"""Regression tests for scripts/rss_collector.py (sampler B).

Network is stubbed: feedparser.parse is monkeypatched, so the suite runs in
the sandbox (no outbound HTTP) and deterministically covers the failure modes
seen in production: off-window items leaking in, keyword misses, Google News
homepage/nav entries, duplicate storms, and non-idempotent re-runs."""

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest

import rss_collector
from rss_collector import collect, open_db, upsert


TODAY = datetime(2026, 7, 21, tzinfo=timezone.utc)  # briefing-day 00:00, a Tuesday
DOW = 2


class Entry(dict):
    """feedparser entries behave like dicts with attribute access."""
    __getattr__ = dict.get


class Feed:
    def __init__(self, entries, bozo=False):
        self.entries = entries
        self.bozo = bozo
        self.bozo_exception = Exception("boom") if bozo else None


def _entry(title, link, published=None, summary="", source_href=None):
    e = Entry(title=title, link=link, summary=summary)
    if published is not None:
        e["published_parsed"] = time.struct_time(published.timetuple())
    if source_href:
        e["source"] = {"href": source_href}
    return e


IN_WINDOW = datetime(2026, 7, 20, 22, 0, tzinfo=timezone.utc)
OUT_OF_WINDOW = datetime(2026, 7, 18, 6, 0, tzinfo=timezone.utc)


@pytest.fixture()
def fake_feeds(monkeypatch, tmp_path):
    """Install a fake feeds.yml + a canned feedparser.parse."""
    feeds_yml = tmp_path / "feeds.yml"
    monkeypatch.setattr(rss_collector, "FEEDS_PATH", feeds_yml)

    def install(feed_defs, parsed_by_url):
        import yaml
        feeds_yml.write_text(yaml.safe_dump({"feeds": feed_defs}))
        monkeypatch.setattr(
            rss_collector.feedparser, "parse",
            lambda url, request_headers=None: parsed_by_url.get(url, Feed([])),
        )
    return install


def test_collect_filters_keyword_window_and_dedups(fake_feeds):
    entries = [
        _entry("Carbon capture milestone at Moomba", "https://ex.com/a?utm_source=t", IN_WINDOW),
        # Duplicate of the same story by canonical URL.
        _entry("Carbon capture milestone at Moomba", "https://www.ex.com/a", IN_WINDOW),
        # Duplicate by fuzzy key, different URL.
        _entry("Carbon capture milestone at Moomba", "https://other.com/b", IN_WINDOW),
        # CCS-relevant but stale.
        _entry("CCUS investment doubles", "https://ex.com/old", OUT_OF_WINDOW),
        # Fresh but not CCS.
        _entry("Football final tonight", "https://ex.com/sport", IN_WINDOW),
        # No publication date at all -> treated as out of window.
        _entry("DAC plant announced", "https://ex.com/nodate"),
    ]
    fake_feeds([{"name": "T", "url": "u1", "tier": 1}], {"u1": Feed(entries)})
    rows = collect(TODAY, DOW)
    assert len(rows) == 1
    assert rows[0]["canonical_url"] == "https://ex.com/a"
    assert rows[0]["feed_name"] == "T"


def test_collect_prefers_google_news_source_domain(fake_feeds):
    e = _entry("CO2 storage hub approved", "https://news.google.com/articles/xyz",
               IN_WINDOW, source_href="https://www.reuters.com")
    fake_feeds([{"name": "G", "url": "u", "tier": 2}], {"u": Feed([e])})
    rows = collect(TODAY, DOW)
    assert rows and rows[0]["source_domain"] == "reuters.com"


def test_collect_drops_publisher_homepage_entries(fake_feeds):
    # Google News sometimes surfaces "Carbon Capture Journal - carboncapturejournal.com".
    e = _entry("carboncapturejournal.com news", "https://carboncapturejournal.com/",
               IN_WINDOW, source_href="https://carboncapturejournal.com")
    fake_feeds([{"name": "G", "url": "u", "tier": 2}], {"u": Feed([e])})
    assert collect(TODAY, DOW) == []


def test_collect_skips_unparseable_feed_but_keeps_others(fake_feeds, capsys):
    good = _entry("Carbon capture news today", "https://ex.com/x", IN_WINDOW)
    fake_feeds(
        [{"name": "Bad", "url": "ub", "tier": 1}, {"name": "Good", "url": "ug", "tier": 1}],
        {"ub": Feed([], bozo=True), "ug": Feed([good])},
    )
    rows = collect(TODAY, DOW)
    assert len(rows) == 1
    assert "unparseable" in capsys.readouterr().err


def test_collect_respects_always_filter(fake_feeds):
    # ccs_filter: always -> no keyword gate (Carbon Herald pattern in feeds.yml).
    e = _entry("Industry newsletter roundup", "https://ex.com/r", IN_WINDOW)
    fake_feeds([{"name": "CH", "url": "u", "tier": 1, "ccs_filter": "always"}],
               {"u": Feed([e])})
    assert len(collect(TODAY, DOW)) == 1


def test_upsert_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(rss_collector, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(rss_collector, "DB_PATH", tmp_path / "candidates.db")
    row = {
        "canonical_url": "https://ex.com/a", "raw_url": "https://ex.com/a",
        "headline": "H", "source_domain": "ex.com",
        "publication_date": IN_WINDOW.isoformat(), "fuzzy_key": "h",
        "feed_name": "T", "feed_tier": 1,
    }
    conn = open_db()
    try:
        upsert(conn, [row], "2026-07-21")
        upsert(conn, [row], "2026-07-21")  # re-run same day must not duplicate
        items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        samples = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
        sampler = conn.execute("SELECT DISTINCT sampler_id FROM samples").fetchone()[0]
    finally:
        conn.close()
    assert (items, samples, sampler) == (1, 1, "B")


def test_db_schema_matches_alerts_ingest_schema():
    """rss_collector and alerts_ingest each carry a copy of the shared schema;
    if they drift the second one to run silently loses columns."""
    import alerts_ingest
    norm = lambda s: " ".join(s.split())
    assert norm(rss_collector.SCHEMA) == norm(alerts_ingest.SCHEMA)


def test_real_feeds_yml_is_wellformed(repo_root):
    """The production config must parse and every feed needs name/url/tier."""
    import yaml
    cfg = yaml.safe_load((repo_root / "config" / "feeds.yml").read_text())
    assert cfg["feeds"], "no feeds configured"
    seen_names = set()
    for f in cfg["feeds"]:
        # Tiers in live use: 1, 2, 2b, 3, 4, 5 (int or string).
        assert f.get("name") and f.get("url") and f.get("tier") is not None, f
        assert f.get("ccs_filter", "regex") in ("regex", "always"), f
        assert f["url"].startswith("http"), f
        assert f["name"] not in seen_names, f"duplicate feed name: {f['name']}"
        seen_names.add(f["name"])
