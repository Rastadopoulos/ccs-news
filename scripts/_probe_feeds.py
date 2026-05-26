"""Probe candidate RSS/Atom feed URLs with feedparser to find ones that yield
real entries. Single-use helper; not committed to repo.

Run:  .venv/bin/python scripts/_probe_feeds.py
"""

from __future__ import annotations
import feedparser
import sys
import urllib.parse


CANDIDATES = {
    # publisher -> [candidate URLs]
    "Reuters (Google News)": [
        "https://news.google.com/rss/search?q=site%3Areuters.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "Bloomberg Green (direct)": [
        "https://feeds.bloomberg.com/green/news.rss",
    ],
    "DOE/FECM (Google News)": [
        "https://news.google.com/rss/search?q=site%3Aenergy.gov+%28%22carbon+capture%22+OR+CCUS+OR+CCS%29&hl=en-US&gl=US&ceid=US%3Aen",
    ],
    "NETL (Google News)": [
        "https://news.google.com/rss/search?q=site%3Anetl.doe.gov&hl=en-US&gl=US&ceid=US%3Aen",
    ],
    "EU Commission Climate (Google News)": [
        "https://news.google.com/rss/search?q=site%3Aec.europa.eu+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en&gl=EU&ceid=EU%3Aen",
    ],
    "DCCEEW (Google News)": [
        "https://news.google.com/rss/search?q=site%3Adcceew.gov.au+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "UK CCSA": [
        "https://www.ccsassociation.org/news/feed/",
        "https://www.ccsassociation.org/feed",
        "https://news.google.com/rss/search?q=site%3Accsassociation.org&hl=en-GB&gl=GB&ceid=GB%3Aen",
    ],
    "Carbon Capture Journal": [
        "https://www.carboncapturejournal.com/rss.aspx",
        "https://news.google.com/rss/search?q=site%3Acarboncapturejournal.com&hl=en-GB&gl=GB&ceid=GB%3Aen",
    ],
    "Australian Pipeliner (Google News)": [
        "https://news.google.com/rss/search?q=site%3Apipeliner.com.au&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "Upstream Online (Google News)": [
        "https://news.google.com/rss/search?q=site%3Aupstreamonline.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-GB&gl=GB&ceid=GB%3Aen",
    ],
    "Global CCS Institute": [
        "https://www.globalccsinstitute.com/news-media/insights-blog/feed/",
        "https://www.globalccsinstitute.com/feed",
        "https://news.google.com/rss/search?q=site%3Aglobalccsinstitute.com&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "Equinor (Google News)": [
        "https://news.google.com/rss/search?q=site%3Aequinor.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en&gl=NO&ceid=NO%3Aen",
    ],
    "Shell (Google News)": [
        "https://news.google.com/rss/search?q=site%3Ashell.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-GB&gl=GB&ceid=GB%3Aen",
    ],
    "Santos (Google News)": [
        "https://news.google.com/rss/search?q=site%3Asantos.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "Woodside (Google News)": [
        "https://news.google.com/rss/search?q=site%3Awoodside.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "ExxonMobil (Google News)": [
        "https://news.google.com/rss/search?q=site%3Aexxonmobil.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-US&gl=US&ceid=US%3Aen",
    ],
    "Occidental (Google News)": [
        "https://news.google.com/rss/search?q=site%3Aoxy.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-US&gl=US&ceid=US%3Aen",
    ],
    "Aker Carbon Capture": [
        "https://akercarboncapture.com/news/feed/",
        "https://news.google.com/rss/search?q=site%3Aakercarboncapture.com&hl=en&gl=NO&ceid=NO%3Aen",
    ],
    "Climeworks": [
        "https://climeworks.com/news.rss",
        "https://news.google.com/rss/search?q=site%3Aclimeworks.com&hl=en&gl=CH&ceid=CH%3Aen",
    ],
    "Mirage News": [
        "https://www.miragenews.com/feed/",
        "https://news.google.com/rss/search?q=site%3Amiragenews.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "EurekAlert (energy/environment)": [
        "https://www.eurekalert.org/rss/atmospheric_science.xml",
        "https://www.eurekalert.org/rss.xml",
        "https://news.google.com/rss/search?q=site%3Aeurekalert.org+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-US&gl=US&ceid=US%3Aen",
    ],
    "Guardian environment": [
        "https://www.theguardian.com/environment/carbon-capture-and-storage/rss",
    ],
    "ABC News (au) — environment": [
        "https://www.abc.net.au/news/feed/2942460/rss.xml",
        "https://news.google.com/rss/search?q=site%3Aabc.net.au+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "AFR (Google News)": [
        "https://news.google.com/rss/search?q=site%3Aafr.com+%28%22carbon+capture%22+OR+CCS+OR+CCUS%29&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    # broad CCS Google News searches (catch publishers we'd otherwise miss)
    "Google News — CCS (au)": [
        "https://news.google.com/rss/search?q=%28%22carbon+capture%22+OR+CCS+OR+CCUS%29+%28Australia+OR+Otway+OR+Moomba+OR+Bonaparte%29&hl=en-AU&gl=AU&ceid=AU%3Aen",
    ],
    "Google News — CCS (global)": [
        "https://news.google.com/rss/search?q=%22carbon+capture+and+storage%22+OR+CCUS&hl=en&gl=US&ceid=US%3Aen",
    ],
}


def probe(name: str, urls: list[str]) -> tuple[str, int]:
    for url in urls:
        try:
            d = feedparser.parse(url, request_headers={"User-Agent": "ccs-news-audit/1.0"})
        except Exception as exc:
            print(f"  ERROR {url}: {exc!r}", file=sys.stderr)
            continue
        entries = len(d.entries or [])
        bozo = bool(d.bozo) and not entries
        flag = "OK " if entries > 0 and not bozo else "BAD"
        print(f"  {flag} {entries:>3} entries  {url}")
        if entries > 0:
            return url, entries
    return "", 0


def main() -> int:
    print(f"# Probing {len(CANDIDATES)} publisher buckets")
    winners: dict[str, str] = {}
    for name, urls in CANDIDATES.items():
        print(f"\n## {name}")
        url, n = probe(name, urls)
        if url:
            winners[name] = url
    print("\n# WINNERS")
    for name, url in winners.items():
        print(f"  {name}\n    {url}")
    print(f"\n# {len(winners)}/{len(CANDIDATES)} buckets have a working feed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
