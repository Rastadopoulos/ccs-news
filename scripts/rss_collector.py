"""Sampler B — deterministic RSS/Atom floor collector for the CCS-news audit.

Reads config/feeds.yml, polls each feed, filters by CCS_KEYWORD_RE, applies
the 24h/72h recency window, and upserts surviving items into the shared
audit/candidates.db SQLite store under sampler_id='B'. Also writes a per-day
JSON dump audit/${TODAY}-rss.json so the daily and weekly audits don't have
to round-trip the DB for short-horizon queries.

Run locally:  python3 scripts/rss_collector.py
Run in CI:    .github/workflows/rss-floor.yml (cron weekday mornings AEST)

Designed to be idempotent — re-running for the same day overwrites the JSON
dump and re-upserts DB rows (PRIMARY KEY collisions resolved by REPLACE).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import feedparser  # type: ignore[import-untyped]
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _canon import (  # noqa: E402
    CCS_KEYWORD_RE,
    canonical_url,
    fuzzy_key,
    is_in_window,
    source_domain,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDS_PATH = REPO_ROOT / "config" / "feeds.yml"
AUDIT_DIR = REPO_ROOT / "audit"
DB_PATH = AUDIT_DIR / "candidates.db"
MELBOURNE = ZoneInfo("Australia/Melbourne")


SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    canonical_url    TEXT PRIMARY KEY,
    fuzzy_key        TEXT NOT NULL,
    headline         TEXT NOT NULL,
    source_domain    TEXT NOT NULL,
    publication_date TEXT,
    first_seen_at    TEXT NOT NULL,
    raw_url          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS samples (
    canonical_url    TEXT NOT NULL,
    sampler_id       TEXT NOT NULL,
    sample_date      TEXT NOT NULL,
    in_window        INTEGER NOT NULL,
    kept_by_sampler  INTEGER NOT NULL,
    reject_reason    TEXT,
    found_via        TEXT,
    PRIMARY KEY (canonical_url, sampler_id, sample_date)
);

CREATE INDEX IF NOT EXISTS idx_samples_date ON samples (sample_date);
CREATE INDEX IF NOT EXISTS idx_items_domain ON items (source_domain);
"""


def open_db() -> sqlite3.Connection:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def parse_pubdate(entry) -> datetime | None:
    """Extract a timezone-aware publication datetime from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        struct = getattr(entry, attr, None)
        if struct:
            try:
                return datetime(*struct[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def collect(today_local: datetime, dow: int) -> list[dict]:
    """Poll all feeds and return the surviving (in-window, CCS-relevant) items."""
    cfg = yaml.safe_load(FEEDS_PATH.read_text())
    rows: list[dict] = []
    seen_canon: set[str] = set()

    for feed_cfg in cfg["feeds"]:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        tier = feed_cfg["tier"]
        ccs_filter = feed_cfg.get("ccs_filter", "regex")
        try:
            parsed = feedparser.parse(url, request_headers={"User-Agent": "ccs-news-audit/1.0"})
        except Exception as exc:  # pragma: no cover
            print(f"[WARN] feed fetch failed: {name} ({exc})", file=sys.stderr)
            continue
        if parsed.bozo and not parsed.entries:
            print(f"[WARN] feed unparseable, no entries: {name} ({parsed.bozo_exception!r})",
                  file=sys.stderr)
            continue

        for entry in parsed.entries:
            headline = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not headline or not link:
                continue
            if ccs_filter == "regex" and not CCS_KEYWORD_RE.search(
                    headline + " " + (entry.get("summary") or "")):
                continue
            pub = parse_pubdate(entry)
            in_window = bool(pub and is_in_window(pub, today_local, dow))
            if not in_window:
                continue  # Floor sampler only stores in-window items.
            curl = canonical_url(link)
            if curl in seen_canon:
                continue
            seen_canon.add(curl)
            rows.append({
                "canonical_url": curl,
                "raw_url": link,
                "headline": headline,
                "source_domain": source_domain(link),
                "publication_date": pub.astimezone(timezone.utc).isoformat()
                                    if pub else None,
                "fuzzy_key": ",".join(fuzzy_key(headline, name)),
                "feed_name": name,
                "feed_tier": tier,
            })
    return rows


def upsert(conn: sqlite3.Connection, rows: list[dict], sample_date: str) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    for r in rows:
        conn.execute(
            """INSERT OR IGNORE INTO items
               (canonical_url, fuzzy_key, headline, source_domain,
                publication_date, first_seen_at, raw_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (r["canonical_url"], r["fuzzy_key"], r["headline"], r["source_domain"],
             r["publication_date"], now_iso, r["raw_url"]),
        )
        conn.execute(
            """INSERT OR REPLACE INTO samples
               (canonical_url, sampler_id, sample_date, in_window,
                kept_by_sampler, reject_reason, found_via)
               VALUES (?, 'B', ?, 1, 1, NULL, ?)""",
            (r["canonical_url"], sample_date, f"rss:{r['feed_name']}"),
        )
    conn.commit()


def main() -> int:
    now_mel = datetime.now(MELBOURNE)
    today_local = now_mel.replace(hour=0, minute=0, second=0, microsecond=0)
    dow = now_mel.isoweekday()
    sample_date = today_local.date().isoformat()

    rows = collect(today_local, dow)
    print(f"[INFO] {len(rows)} in-window CCS items collected for {sample_date} (dow={dow})")

    conn = open_db()
    try:
        upsert(conn, rows, sample_date)
    finally:
        conn.close()

    dump_path = AUDIT_DIR / f"{sample_date}-rss.json"
    dump_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"[INFO] wrote {dump_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
