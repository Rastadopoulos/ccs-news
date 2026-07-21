"""Regression tests for scripts/alerts_ingest.py (sampler C).

Covers the failure modes that matter for an unattended IMAP ingester:
Google-Alerts HTML parsing, redirect unwrapping, charset fallbacks, the
window/keyword gates, idempotent same-day merging, and — critically for the
sandbox/network-allowlist assumption — that missing credentials degrade
gracefully without ever opening a network connection."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import pytest

import alerts_ingest
from alerts_ingest import (
    _AlertParser,
    _extract_redirect_target,
    _msg_html,
    extract_items,
    merge_with_existing,
)

TODAY = datetime(2026, 7, 21, tzinfo=timezone.utc)  # Tuesday 00:00
DOW = 2
IN_WINDOW_DATE = "Mon, 20 Jul 2026 22:00:00 +0000"
STALE_DATE = "Fri, 10 Jul 2026 09:00:00 +0000"

ALERT_HTML = """
<html><body>
<a href="https://www.google.com/url?rct=j&sa=t&url=https%3A%2F%2Fexample.com%2Fccs-story&ct=ga">
  <span>Carbon capture hub</span> announced in Victoria
</a>
<a href="https://www.google.com/url?rct=j&sa=t&url=https%3A%2F%2Fexample.com%2Foff-topic&ct=ga">
  Local football results
</a>
<a href="https://www.google.com/alerts/edit">Edit this alert</a>
<a href="https://plain-link.example.com/x">not a google redirect</a>
</body></html>
"""


def _alert_email(html_body: str, date_hdr: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "Google Alerts <googlealerts-noreply@google.com>"
    msg["Subject"] = "Google Alert - carbon capture"
    msg["Date"] = date_hdr
    msg.set_content("plaintext fallback")
    msg.add_alternative(html_body, subtype="html")
    return msg


# ---------------------------------------------------------------- HTML parsing

def test_alert_parser_extracts_only_redirect_links():
    p = _AlertParser()
    p.feed(ALERT_HTML)
    texts = [t for t, _ in p.items]
    assert "Carbon capture hub announced in Victoria" in texts
    assert "Local football results" in texts
    assert all("Edit this alert" != t for t in texts)
    assert all("not a google redirect" != t for t in texts)


def test_extract_redirect_target():
    wrapped = ("https://www.google.com/url?rct=j&sa=t"
               "&url=https%3A%2F%2Fexample.com%2Fccs-story&ct=ga")
    assert _extract_redirect_target(wrapped) == "https://example.com/ccs-story"
    # Non-redirect hrefs pass through untouched.
    assert _extract_redirect_target("https://example.com/x") == "https://example.com/x"


def test_msg_html_handles_unknown_charset():
    from email.message import Message
    msg = Message()
    msg["Date"] = IN_WINDOW_DATE
    msg["Content-Type"] = 'text/html; charset="x-bogus-charset"'
    msg.set_payload("<p>Carbon capture</p>".encode("utf-8"))
    assert "Carbon capture" in _msg_html(msg)


# ---------------------------------------------------------------- extraction

def test_extract_items_applies_keyword_and_window():
    fresh = _alert_email(ALERT_HTML, IN_WINDOW_DATE)
    stale = _alert_email(ALERT_HTML, STALE_DATE)
    rows = extract_items([fresh, stale], TODAY, DOW)
    # Only the CCS headline from the in-window message survives.
    assert len(rows) == 1
    r = rows[0]
    assert r["canonical_url"] == "https://example.com/ccs-story"
    assert r["found_via"] == "google_alerts"
    assert r["source_domain"] == "example.com"


def test_extract_items_dedups_across_messages():
    m1 = _alert_email(ALERT_HTML, IN_WINDOW_DATE)
    m2 = _alert_email(ALERT_HTML, IN_WINDOW_DATE)
    rows = extract_items([m1, m2], TODAY, DOW)
    assert len(rows) == 1


def test_extract_items_skips_messages_without_html():
    msg = EmailMessage()
    msg["Date"] = IN_WINDOW_DATE
    msg.set_content("plain text only")
    assert extract_items([msg], TODAY, DOW) == []


# ---------------------------------------------------------------- merging

def test_merge_with_existing_accumulates(tmp_path):
    dump = tmp_path / "alerts.json"
    dump.write_text(json.dumps([
        {"canonical_url": "https://a.com/1", "headline": "A", "source_domain": "a.com"},
    ]))
    merged = merge_with_existing(
        [{"canonical_url": "https://b.com/2", "headline": "B", "source_domain": "b.com"}],
        dump,
    )
    assert {r["canonical_url"] for r in merged} == {"https://a.com/1", "https://b.com/2"}


def test_merge_with_existing_survives_malformed_file(tmp_path):
    dump = tmp_path / "alerts.json"
    dump.write_text("{not json")
    rows = [{"canonical_url": "https://b.com/2", "headline": "B", "source_domain": "b.com"}]
    assert merge_with_existing(rows, dump) == rows


def test_merge_newer_row_wins(tmp_path):
    dump = tmp_path / "alerts.json"
    dump.write_text(json.dumps([
        {"canonical_url": "https://a.com/1", "headline": "old", "source_domain": "a.com"},
    ]))
    merged = merge_with_existing(
        [{"canonical_url": "https://a.com/1", "headline": "new", "source_domain": "a.com"}],
        dump,
    )
    assert len(merged) == 1 and merged[0]["headline"] == "new"


# ------------------------------------------------- graceful degradation (no net)

def test_main_without_credentials_never_touches_network(tmp_path, monkeypatch):
    """The sandbox/network-allowlist contract: with no Gmail secrets the script
    must exit 0, write an empty alerts.json, and never open an IMAP socket."""
    monkeypatch.setattr(alerts_ingest, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(alerts_ingest, "DB_PATH", tmp_path / "candidates.db")
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

    def _boom(*a, **k):  # any IMAP construction is a test failure
        raise AssertionError("IMAP4_SSL called without credentials")
    monkeypatch.setattr(alerts_ingest.imaplib, "IMAP4_SSL", _boom)

    assert alerts_ingest.main() == 0
    dumps = list(tmp_path.glob("*-alerts.json"))
    assert len(dumps) == 1
    assert json.loads(dumps[0].read_text()) == []


def test_main_without_credentials_preserves_existing_dump(tmp_path, monkeypatch):
    """A credential outage mid-day must not clobber items ingested earlier."""
    monkeypatch.setattr(alerts_ingest, "AUDIT_DIR", tmp_path)
    monkeypatch.setattr(alerts_ingest, "DB_PATH", tmp_path / "candidates.db")
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)

    from zoneinfo import ZoneInfo
    sample_date = datetime.now(ZoneInfo("Australia/Melbourne")).date().isoformat()
    dump = tmp_path / f"{sample_date}-alerts.json"
    existing = [{"canonical_url": "https://a.com/1", "headline": "A", "source_domain": "a.com"}]
    dump.write_text(json.dumps(existing))

    assert alerts_ingest.main() == 0
    assert json.loads(dump.read_text()) == existing
