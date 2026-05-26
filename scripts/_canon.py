"""Shared canonicalisation + dedup helpers for the CCS-news audit pipeline.

Every sampler (rss_collector, weekly_audit, daily_audit, alerts_ingest, and the
production routine via its candidates.json trace) MUST dedupe identically.
This module is the single source of truth for:

  * canonical_url(url)         — strip query/fragment, lowercase host, unwrap
                                  aus01.safelinks.protection.outlook.com and
                                  Google News redirects.
  * fuzzy_key(headline, source) — lowercase, strip trailing " – {source}",
                                  tokenise to a sorted tuple. Used for Jaccard
                                  similarity comparison.
  * jaccard(a, b)              — token-set Jaccard similarity in [0, 1].
  * is_in_window(pub_dt, today, dow) — apply the 24h (Tue–Fri) / 72h (Mon)
                                  recency rule. dow is ISO weekday 1..7.
  * source_domain(url)         — registrable domain (best-effort, no TLD list).
  * CCS_KEYWORD_RE             — compiled regex for CCS relevance filtering.

No external dependencies beyond the standard library. Designed to be importable
from any script in scripts/ (sys.path includes the directory at runtime).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse, urlunparse

# ---------------------------------------------------------------------------
# CCS relevance regex. Word-boundary-aware to avoid matching "dactyl" for DAC,
# "ccusset" for CCUS, etc. Tuned against ~200 headlines from Shelly's digests
# and Carbon Herald daily archives.
# ---------------------------------------------------------------------------
CCS_KEYWORD_RE = re.compile(
    r"""
    (?:
        carbon[\s\-]?cap(?:ture|tor)              # carbon capture / capturing / captor
      | \bCCS\b | \bCCUS\b | \bCCUS\b
      | CO[2₂][\s\-]?(?:storage|sequestration|transport|injection|pipeline)
      | direct[\s\-]?air[\s\-]?capture
      | \bDAC\b
      | class[\s\-]?VI
      | geological[\s\-]?(?:storage|sequestration)
      | \bMRV\b | \bMMV\b
      | (?:CO[2₂]|carbon)[\s\-]?(?:hub|offtake|removal|credit)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _unwrap_safelinks(url: str) -> str:
    """If `url` is an aus01.safelinks.protection.outlook.com wrapper, return the
    underlying URL from its ?url= parameter. Otherwise return `url` unchanged."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    host = parsed.netloc.lower()
    if "safelinks.protection.outlook.com" in host:
        qs = parse_qs(parsed.query)
        if "url" in qs and qs["url"]:
            return unquote(qs["url"][0])
    if host == "news.google.com" and parsed.path.startswith("/articles/"):
        # Google News redirect — pull `url=` param if present.
        qs = parse_qs(parsed.query)
        if "url" in qs and qs["url"]:
            return unquote(qs["url"][0])
    return url


# Tracking parameters that should never affect canonical identity.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "mc_cid", "mc_eid", "fbclid", "gclid", "igshid", "ref", "ref_src",
    "spm", "src", "from", "share", "_gl",
}


def canonical_url(url: str) -> str:
    """Return a canonical form of `url` suitable for dedup keying.

    Steps: unwrap safelinks/Google News redirects, lowercase host, strip
    default ports, drop fragment, drop tracking query params, sort remaining
    query params, strip trailing slash from the path (except for the root).
    """
    if not url:
        return ""
    url = _unwrap_safelinks(url.strip())
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    scheme = parsed.scheme.lower() or "https"
    host = parsed.netloc.lower()
    # Strip explicit default ports.
    if host.endswith(":80") and scheme == "http":
        host = host[:-3]
    if host.endswith(":443") and scheme == "https":
        host = host[:-4]
    # Strip leading www. for consistency.
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    # Filter + sort query params.
    kept_qs: list[tuple[str, str]] = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
            else:
                k, v = pair, ""
            if k.lower() in _TRACKING_PARAMS:
                continue
            kept_qs.append((k, v))
        kept_qs.sort()
    query = "&".join(f"{k}={v}" if v else k for k, v in kept_qs)
    return urlunparse((scheme, host, path, "", query, ""))


def source_domain(url: str) -> str:
    """Return the registrable-ish domain — last two labels for common TLDs,
    last three for known second-level TLDs (.co.uk, .com.au, etc.).
    Best-effort heuristic; we do not pull in tldextract to keep dependencies
    minimal."""
    try:
        host = urlparse(canonical_url(url)).netloc
    except ValueError:
        return ""
    if not host:
        return ""
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "net", "org", "gov", "edu", "ac"} \
            and parts[-1] in {"uk", "au", "nz", "za", "sg", "jp", "kr", "in"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "at", "for", "and", "or", "but",
    "with", "by", "from", "as", "is", "are", "was", "were", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "their", "they",
    "he", "she", "we", "you", "i", "s",
}


def fuzzy_key(headline: str, source: str | None = None) -> tuple[str, ...]:
    """Return a sorted tuple of significant tokens for Jaccard comparison.

    Strips trailing " – {source}" (en/em dash variants) before tokenising, so
    that "Foo Bar – Reuters" and "Foo Bar" produce identical keys.
    """
    if not headline:
        return ()
    text = headline
    if source:
        for sep in [" – ", " — ", " - ", " | "]:
            tail = f"{sep}{source}"
            if text.endswith(tail):
                text = text[: -len(tail)]
                break
    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    tokens = [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    return tuple(sorted(set(tokens)))


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard similarity in [0, 1] for two iterables of tokens."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


# ---------------------------------------------------------------------------
# Recency window — mirrors the routine prompt exactly.
# ---------------------------------------------------------------------------

def is_in_window(pub_dt: datetime, today: datetime, dow: int) -> bool:
    """`today` is the briefing's TODAY at 00:00 Melbourne. `dow` is ISO weekday
    1..7 (Mon=1). Tue–Fri (dow 2..5): item must be within 24h of `today`'s
    07:00 (i.e. since yesterday 07:00). Mon (dow 1): since 17:00 Friday
    (~72h). Sat/Sun (6/7): treated like Monday (same 72h floor) — primarily
    for off-cycle test runs.
    """
    if pub_dt is None:
        return False
    if pub_dt.tzinfo is None:
        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
    if dow in (2, 3, 4, 5):
        # 24h window ending at today's 07:00 local (approximate with 'now').
        floor = today - timedelta(hours=24)
    else:
        # Monday or weekend: from 17:00 previous Friday.
        # `today` is Monday 00:00 → Friday 17:00 is 2d 7h earlier.
        days_back = (dow - 5) % 7 or 3  # Mon→3, Sat→1, Sun→2
        floor = today - timedelta(days=days_back, hours=7)
    return pub_dt >= floor


# ---------------------------------------------------------------------------
# Lightweight self-test — run `python scripts/_canon.py` to verify.
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    samples = [
        ("https://www.reuters.com/business/foo?utm_source=x&id=42#bar",
         "https://reuters.com/business/foo?id=42"),
        ("https://aus01.safelinks.protection.outlook.com/?url=https%3A%2F%2Fexample.com%2Fa&data=x",
         "https://example.com/a"),
        ("https://CARBON-Herald.com/foo/",
         "https://carbon-herald.com/foo"),
    ]
    for raw, expected in samples:
        got = canonical_url(raw)
        flag = "OK " if got == expected else "FAIL"
        print(f"{flag} canonical_url: {raw!r} -> {got!r} (expected {expected!r})")

    print("\nfuzzy_key examples:")
    print(fuzzy_key("Moomba CCS project achieves milestone – Santos", "Santos"))
    print(fuzzy_key("Moomba CCS project achieves milestone"))
    print(f"jaccard between them: {jaccard(*[fuzzy_key('Moomba CCS milestone', 'Santos'), fuzzy_key('CCS milestone at Moomba')]):.2f}")

    print("\nCCS_KEYWORD_RE matches:")
    for h in ["Carbon capture milestone", "Class VI permit granted", "DAC plant opens",
              "Just another energy story", "CCUS investment up", "CO₂ storage at Bayou"]:
        print(f"  {bool(CCS_KEYWORD_RE.search(h)):>5}  {h!r}")
