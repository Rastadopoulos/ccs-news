"""Weekly freshness check for dashboard/data/storage-baseline.json.

Scans the RSS floor's accumulated audit/candidates.db for headlines
mentioning a named storage project (via each project's news_aliases),
extracts a candidate cumulative-Mt figure where the headline states one,
and reports anything new since the last run for human review.

This is detection only -- it never writes storage-baseline.json. Same
"detect, surface, human decides" discipline as imperial-register-check.yml
and the funding-enrichment review queue: a human always confirms the figure
and edits the JSON by hand.

Coverage note: this only ever sees a headline, not full article text (that's
all rss_collector.py persists), so a real update with no number in its
headline still surfaces as "project mentioned, no figure found" rather than
being silently missed -- worth a look either way, just without a candidate
number attached.

Run locally:  python3 scripts/check_storage_baseline_freshness.py
Run in CI:    .github/workflows/storage-baseline-check.yml
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "audit" / "candidates.db"
STORAGE_BASELINE_PATH = REPO_ROOT / "dashboard" / "data" / "storage-baseline.json"
SEEN_PATH = REPO_ROOT / "dashboard" / "data" / ".storage-project-alerts-seen.json"

# A number immediately followed by a tonnage unit, e.g. "2 million tonnes",
# "12 Mt", "1.3 MtCO2e". Best-effort only -- a miss just means no candidate
# figure is attached to the match, not that the match itself is dropped.
FIGURE_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:million\s+tonnes?|million\s+tons?|Mt(?:CO2e?)?\b)",
    re.IGNORECASE,
)


def load_projects(path: Path = STORAGE_BASELINE_PATH) -> list[dict]:
    data = json.loads(path.read_text())
    return data["projects"]


def load_seen(path: Path = SEEN_PATH) -> set[str]:
    if path.exists():
        return set(json.loads(path.read_text()))
    return set()


def save_seen(seen: set[str], path: Path = SEEN_PATH) -> None:
    path.write_text(json.dumps(sorted(seen), indent=2) + "\n")


def match_headline(headline: str, projects: list[dict]) -> dict | None:
    """Return the first project this headline's aliases match, or None."""
    low = headline.lower()
    for p in projects:
        aliases = p.get("news_aliases") or []
        if any(alias.lower() in low for alias in aliases):
            return p
    return None


def find_matches(projects: list[dict], seen: set[str], rows: list[tuple]) -> list[dict]:
    """rows: iterable of (headline, canonical_url, raw_url) from candidates.db."""
    matches = []
    for headline, canonical_url, raw_url in rows:
        if canonical_url in seen:
            continue
        project = match_headline(headline, projects)
        if project is None:
            continue
        fig = FIGURE_RE.search(headline)
        matches.append({
            "project": project["name"],
            "headline": headline,
            "url": raw_url,
            "canonical_url": canonical_url,
            "candidate_figure": fig.group(0) if fig else None,
            "current_reported_mt": project.get("reported_cumulative_mt"),
            "current_reported_asof": project.get("reported_asof"),
        })
    return matches


def read_candidate_rows(db_path: Path = DB_PATH) -> list[tuple]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT headline, canonical_url, raw_url FROM items").fetchall()
    finally:
        conn.close()


def format_html_table(matches: list[dict]) -> str:
    """Render matches as an HTML table for the alert email. Kept here (not
    inlined in the workflow YAML) so it's a plain, testable function rather
    than a multi-line python -c string nested inside a bash heredoc inside a
    YAML block scalar -- three layers of indentation-sensitive nesting that
    is fragile to hand-edit correctly."""
    import html as html_mod

    rows_html = []
    for m in matches:
        proj = html_mod.escape(m["project"])
        head = html_mod.escape(m["headline"])
        url = html_mod.escape(m["url"])
        fig = html_mod.escape(m["candidate_figure"] or "—")
        cur, asof = m.get("current_reported_mt"), m.get("current_reported_asof")
        cur_s = html_mod.escape(f"{cur} Mt (as of {asof})" if cur is not None else "no figure on file")
        rows_html.append(f"<tr><td>{proj}</td><td><a href=\"{url}\">{head}</a></td>"
                          f"<td>{fig}</td><td>{cur_s}</td></tr>")
    return ("<table border=1 cellpadding=6 cellspacing=0>"
            "<tr><th>Project</th><th>Headline</th><th>Candidate figure</th><th>Current baseline</th></tr>"
            + "".join(rows_html) + "</table>")


def main() -> int:
    projects = load_projects()
    seen = load_seen()
    rows = read_candidate_rows()
    matches = find_matches(projects, seen, rows)

    if "--html" in sys.argv:
        src = sys.argv[sys.argv.index("--html") + 1]
        with open(src) as f:
            print(format_html_table(json.load(f)))
        return 0

    if matches:
        seen.update(m["canonical_url"] for m in matches)
        save_seen(seen)
        print(json.dumps(matches, indent=2))
        print(f"\n{len(matches)} new project mention(s) found.", file=sys.stderr)
    else:
        print("[]")
        print("No new project mentions since last check.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
