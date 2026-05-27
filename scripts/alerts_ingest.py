"""Sampler C — Google Alerts ingester for the CCS-news audit pipeline.

Polls a dedicated Gmail inbox via IMAP for recent Google Alerts emails,
parses each one to extract article URLs and headlines, applies the same
recency window as the briefing routine, and upserts surviving items to
audit/candidates.db (sampler_id='C'). Also writes audit/${TODAY}-alerts.json
so the daily / weekly audits don't need to round-trip the DB.

Setup and the canonical list of configured alerts live in
docs/google-alerts.md. That file is the source of truth — update it in
the same commit when you add, remove, or modify an alert in the
Google Alerts UI.

Quick-reference for the wiring:
  - Repo secrets GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set; see
    docs/secrets.md for what each one is and how to rotate.
  - Repo variable ALERTS_INGEST_ENABLED=true must be set, otherwise the
    cron-driven workflow stays dormant.
  - Each alert in the Google Alerts UI must deliver to the address held
    in GMAIL_ADDRESS, with frequency 'As-it-happens', sources 'Automatic'.

Run locally:
  GMAIL_ADDRESS=... GMAIL_APP_PASSWORD=... python3 scripts/alerts_ingest.py

Run in CI:
  .github/workflows/alerts-ingest.yml (cron every 30 min)

Failure modes (all non-blocking):
  - secrets missing → log warning, write empty alerts.json, exit 0.
  - IMAP login fails → log warning, write empty alerts.json, exit 0.
  - No new alerts since last run → write empty file (or skip the day if file
    already has items from earlier in the day).

The ingester is idempotent over a single day: re-running merges into the
day's alerts.json without losing prior entries.
"""

from __future__ import annotations

import email
import imaplib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _canon import (  # noqa: E402
    CCS_KEYWORD_RE,
    canonical_url,
    fuzzy_key,
    is_in_window,
    source_domain,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = REPO_ROOT / "audit"
DB_PATH = AUDIT_DIR / "candidates.db"
MELBOURNE = ZoneInfo("Australia/Melbourne")
IMAP_HOST = "imap.gmail.com"
SEARCH_DAYS = 2  # look back 2 days each run; idempotent dedup handles overlap

GOOGLE_ALERT_FROM = "googlealerts-noreply@google.com"


class _AlertParser(HTMLParser):
    """Extract (headline, redirect_url) pairs from a Google Alerts email.

    Google Alerts wraps every article link in a tracking redirect of the form
    https://www.google.com/url?rct=j&sa=t&url=<real_url>&ct=ga&...  — the
    real URL is in the `url=` query parameter.
    """

    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str]] = []
        self._capture_href: str | None = None
        self._text_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            d = dict(attrs)
            href = d.get("href", "")
            if "google.com/url" in href and "url=" in href:
                self._capture_href = href
                self._text_buf = []

    def handle_endtag(self, tag):
        if tag == "a" and self._capture_href:
            text = "".join(self._text_buf).strip()
            text = re.sub(r"\s+", " ", text)
            if text:
                self.items.append((text, self._capture_href))
            self._capture_href = None
            self._text_buf = []

    def handle_data(self, data):
        if self._capture_href is not None:
            self._text_buf.append(data)


def _extract_redirect_target(href: str) -> str:
    try:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        if "url" in qs and qs["url"]:
            return unquote(qs["url"][0])
    except ValueError:
        pass
    return href


def _msg_html(msg: Message) -> str:
    """Return the text/html part of an email message, or '' if none."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                try:
                    return payload.decode(charset, errors="replace")
                except LookupError:
                    return payload.decode("utf-8", errors="replace")
        return ""
    if msg.get_content_type() == "text/html":
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except LookupError:
            return payload.decode("utf-8", errors="replace")
    return ""


def _msg_date(msg: Message) -> datetime | None:
    raw = msg.get("Date")
    if not raw:
        return None
    try:
        return email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


def fetch_alert_messages(addr: str, password: str) -> list[Message]:
    """Fetch Google Alerts emails from the past SEARCH_DAYS days."""
    M = imaplib.IMAP4_SSL(IMAP_HOST)
    try:
        M.login(addr, password)
    except imaplib.IMAP4.error as exc:
        print(f"[WARN] IMAP login failed: {exc}", file=sys.stderr)
        return []
    try:
        M.select("INBOX")
        since = (datetime.now(timezone.utc).date()
                 - __import__("datetime").timedelta(days=SEARCH_DAYS)).strftime("%d-%b-%Y")
        typ, data = M.search(None, f'(FROM "{GOOGLE_ALERT_FROM}" SINCE {since})')
        if typ != "OK":
            return []
        ids = (data[0] or b"").split()
        msgs: list[Message] = []
        for mid in ids:
            typ, msg_data = M.fetch(mid, "(RFC822)")
            if typ != "OK" or not msg_data:
                continue
            raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else None
            if not raw:
                continue
            msgs.append(email.message_from_bytes(raw))
        return msgs
    finally:
        try:
            M.close()
        except Exception:
            pass
        M.logout()


def extract_items(messages: list[Message],
                  today_local: datetime, dow: int) -> list[dict]:
    """Parse each message, surface candidate (headline, url) pairs, filter."""
    rows: list[dict] = []
    seen_canon: set[str] = set()
    seen_fuzzy: set[tuple[str, ...]] = set()

    for msg in messages:
        msg_dt = _msg_date(msg)
        html_body = _msg_html(msg)
        if not html_body:
            continue
        parser = _AlertParser()
        try:
            parser.feed(html_body)
        except Exception as exc:
            print(f"[WARN] HTML parse error: {exc}", file=sys.stderr)
            continue
        for headline, wrapped in parser.items:
            real_url = _extract_redirect_target(wrapped)
            if not real_url or not headline:
                continue
            # Combine headline + URL for keyword check. Google Alerts queries
            # may sometimes catch off-topic items.
            if not CCS_KEYWORD_RE.search(headline + " " + real_url):
                continue
            # Use the message date as a best-effort proxy for publication date.
            # Google Alerts emails arrive close to article publication time.
            pub = msg_dt
            if pub is None or not is_in_window(pub, today_local, dow):
                continue
            curl = canonical_url(real_url)
            fkey = fuzzy_key(headline, None)
            if curl in seen_canon:
                continue
            if fkey and fkey in seen_fuzzy:
                continue
            seen_canon.add(curl)
            if fkey:
                seen_fuzzy.add(fkey)
            rows.append({
                "canonical_url": curl,
                "raw_url": real_url,
                "headline": headline,
                "source_domain": source_domain(real_url),
                "publication_date": pub.astimezone(timezone.utc).isoformat()
                                    if pub else None,
                "fuzzy_key": ",".join(fkey),
                "found_via": "google_alerts",
            })
    return rows


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
               VALUES (?, 'C', ?, 1, 1, NULL, 'google_alerts')""",
            (r["canonical_url"], sample_date),
        )
    conn.commit()


def merge_with_existing(rows: list[dict], dump_path: Path) -> list[dict]:
    """Merge new rows with whatever is already in today's alerts.json so
    re-runs accumulate rather than overwrite."""
    if not dump_path.exists():
        return rows
    try:
        existing = json.loads(dump_path.read_text())
    except json.JSONDecodeError:
        return rows
    by_url = {r["canonical_url"]: r for r in existing}
    for r in rows:
        by_url[r["canonical_url"]] = r
    merged = list(by_url.values())
    merged.sort(key=lambda x: (x["source_domain"], x["headline"]))
    return merged


def main() -> int:
    addr = os.environ.get("GMAIL_ADDRESS", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    now_mel = datetime.now(MELBOURNE)
    today_local = now_mel.replace(hour=0, minute=0, second=0, microsecond=0)
    dow = now_mel.isoweekday()
    sample_date = today_local.date().isoformat()
    dump_path = AUDIT_DIR / f"{sample_date}-alerts.json"

    if not addr or not password:
        print("[WARN] GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set; writing empty alerts.json")
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        if not dump_path.exists():
            dump_path.write_text("[]\n")
        return 0

    msgs = fetch_alert_messages(addr, password)
    print(f"[INFO] fetched {len(msgs)} Google Alerts emails")
    rows = extract_items(msgs, today_local, dow)
    print(f"[INFO] {len(rows)} in-window CCS items extracted")

    merged = merge_with_existing(rows, dump_path)
    dump_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    print(f"[INFO] wrote {dump_path.relative_to(REPO_ROOT)} ({len(merged)} total)")

    conn = open_db()
    try:
        upsert(conn, rows, sample_date)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
