"""Regression tests for scripts/_canon.py — the dedup contract every sampler
shares. A silent change here desynchronises samplers A–F, so these tests pin
the documented behaviour exactly."""

from datetime import datetime, timezone

import pytest

from _canon import (
    CCS_KEYWORD_RE,
    canonical_url,
    fuzzy_key,
    is_in_window,
    jaccard,
    source_domain,
)

MEL = timezone.utc  # window tests construct explicit UTC datetimes


# ---------------------------------------------------------------- canonical_url

@pytest.mark.parametrize("raw,expected", [
    # Tracking params stripped, kept params preserved, www stripped.
    ("https://www.reuters.com/business/foo?utm_source=x&id=42#bar",
     "https://reuters.com/business/foo?id=42"),
    # Outlook safelinks unwrapped (the raw URL every Outlook-forwarded item has).
    ("https://aus01.safelinks.protection.outlook.com/?url=https%3A%2F%2Fexample.com%2Fa&data=x",
     "https://example.com/a"),
    # Host lowercased, trailing slash stripped.
    ("https://CARBON-Herald.com/foo/", "https://carbon-herald.com/foo"),
    # Default ports stripped.
    ("https://example.com:443/x", "https://example.com/x"),
    ("http://example.com:80/x", "http://example.com/x"),
    # Root path: trailing slash kept as "/".
    ("https://example.com", "https://example.com/"),
    # Remaining query params sorted for stable identity.
    ("https://example.com/a?b=2&a=1", "https://example.com/a?a=1&b=2"),
    # fbclid / gclid / mc_eid all count as tracking.
    ("https://example.com/a?fbclid=xyz&gclid=1&mc_eid=2", "https://example.com/a"),
    ("", ""),
])
def test_canonical_url(raw, expected):
    assert canonical_url(raw) == expected


def test_canonical_url_is_idempotent():
    u = canonical_url("https://www.Example.com/story/?utm_campaign=x&id=9")
    assert canonical_url(u) == u


def test_safelinks_without_url_param_passes_through():
    raw = "https://aus01.safelinks.protection.outlook.com/?data=only"
    assert canonical_url(raw).startswith("https://aus01.safelinks")


# ---------------------------------------------------------------- source_domain

@pytest.mark.parametrize("url,expected", [
    ("https://www.theguardian.com/environment/x", "theguardian.com"),
    ("https://www.abc.net.au/news/x", "abc.net.au"),
    ("https://www.smh.com.au/x", "smh.com.au"),
    ("https://research.csiro.au/x", "csiro.au"),
    ("https://www.gov.uk/x", "gov.uk"),
    ("", ""),
])
def test_source_domain(url, expected):
    assert source_domain(url) == expected


# ---------------------------------------------------------------- fuzzy_key

def test_fuzzy_key_strips_trailing_source():
    with_src = fuzzy_key("Moomba CCS project achieves milestone – Santos", "Santos")
    without = fuzzy_key("Moomba CCS project achieves milestone")
    assert with_src == without


def test_fuzzy_key_source_only_stripped_from_tail():
    # "Santos" in the middle of the headline must survive.
    key = fuzzy_key("Santos hits Moomba milestone", "Santos")
    assert "santos" in key


def test_fuzzy_key_drops_stopwords_and_dedupes():
    key = fuzzy_key("The a of to in CCS CCS hub")
    assert key == ("ccs", "hub")


def test_fuzzy_key_empty():
    assert fuzzy_key("") == ()


def test_jaccard_bounds():
    assert jaccard([], []) == 1.0
    assert jaccard(["a"], ["a"]) == 1.0
    assert jaccard(["a"], ["b"]) == 0.0
    assert jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)


def test_dedup_threshold_pair_from_readme():
    # The documented contract: Jaccard >= 0.7 on tokenised fuzzy keys.
    a = fuzzy_key("Moomba CCS milestone reached says Santos")
    b = fuzzy_key("Santos says Moomba CCS milestone reached")
    assert jaccard(a, b) >= 0.7


# ---------------------------------------------------------------- window rule

def _dt(*args):
    return datetime(*args, tzinfo=MEL)


class TestWindow:
    """`today` is briefing-day 00:00; floor is 07:00 the previous briefing day."""

    def test_tuesday_24h_window(self):
        today = _dt(2026, 7, 21)  # Tuesday
        assert is_in_window(_dt(2026, 7, 20, 8, 0), today, 2)        # Mon 08:00 in
        assert is_in_window(_dt(2026, 7, 20, 7, 0), today, 2)        # floor inclusive
        assert not is_in_window(_dt(2026, 7, 20, 6, 59), today, 2)   # before floor

    def test_monday_72h_window_reaches_friday_0700(self):
        today = _dt(2026, 7, 20)  # Monday
        assert is_in_window(_dt(2026, 7, 17, 7, 0), today, 1)        # Fri 07:00 in
        assert not is_in_window(_dt(2026, 7, 17, 6, 59), today, 1)
        assert is_in_window(_dt(2026, 7, 18, 12, 0), today, 1)       # Saturday item in

    def test_weekend_offcycle_uses_friday_floor(self):
        sat = _dt(2026, 7, 18)
        sun = _dt(2026, 7, 19)
        assert is_in_window(_dt(2026, 7, 17, 7, 0), sat, 6)
        assert not is_in_window(_dt(2026, 7, 17, 6, 0), sat, 6)
        assert is_in_window(_dt(2026, 7, 17, 7, 0), sun, 7)
        assert not is_in_window(_dt(2026, 7, 17, 6, 0), sun, 7)

    def test_none_pubdate_is_out(self):
        assert not is_in_window(None, _dt(2026, 7, 21), 2)

    def test_naive_datetime_treated_as_utc(self):
        today = _dt(2026, 7, 21)
        naive = datetime(2026, 7, 20, 12, 0)  # no tzinfo
        assert is_in_window(naive, today, 2)


# ---------------------------------------------------------------- keyword regex

@pytest.mark.parametrize("headline", [
    "Carbon capture milestone at Moomba",
    "Class VI permit granted in Louisiana",
    "New DAC plant opens in Texas",
    "CCUS investment up 40%",
    "CO₂ storage expands at Bayou Bend",
    "CO2 pipeline approved in Iowa",
    "Geological sequestration study released",
    "MMV programme begins at Otway",
    "Carbon credit market update for removals",
])
def test_keyword_regex_positives(headline):
    assert CCS_KEYWORD_RE.search(headline), headline


@pytest.mark.parametrize("headline", [
    "Just another energy story",
    "Pterodactyl fossil found",          # must not match DAC inside a word
    "Accusations fly in parliament",     # must not match CCUS inside a word
    "Successful IPO for tech firm",      # no CCS token
    "Classified documents leaked",       # not Class VI
])
def test_keyword_regex_negatives(headline):
    assert not CCS_KEYWORD_RE.search(headline), headline
