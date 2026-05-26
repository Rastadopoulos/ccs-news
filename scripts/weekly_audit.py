"""Weekly audit — Saturday recall report for the CCS-news pipeline.

Reads:
  audit/candidates.db         — shared store (samples + items)
  audit/YYYY-MM-DD-rss.json   — daily RSS-floor dumps (sampler B)
  audit/YYYY-MM-DD-candidates.json — production routine trace (sampler A)
  (Phase 2+) audit/YYYY-MM-DD-shadow.json  — shadow LLM sampler (D)
  Shelly's digest items already live in candidates.json with
  found_via="shelly_digest" — they are folded into sampler E.

Produces:
  audit/YYYY-MM-DD-recall-report.html
  audit/YYYY-MM-DD-recall-report.md

The Markdown's H1 becomes the email subject (the email-audit.yml workflow
reads it identically to the briefing pipeline).

Metrics:
  1. Pooled recall      = |A ∩ U| / |U|
  2. Floor recall       = |A ∩ B| / |B|
  3. (Phase 2+) Chapman absolute-recall estimator over pairs of samplers
  4. Source-coverage matrix
  5. Missed-items table
  6. Drift table — last 12 weeks of (1)+(2)

Run locally:   python3 scripts/weekly_audit.py [--week-ending YYYY-MM-DD]
Run in CI:     .github/workflows/weekly-audit.yml (cron Saturday morning AEST)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _canon import jaccard  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = REPO_ROOT / "audit"
DB_PATH = AUDIT_DIR / "candidates.db"
MELBOURNE = ZoneInfo("Australia/Melbourne")

SAMPLER_NAMES = {
    "A": "Production routine",
    "B": "RSS floor",
    "C": "Google Alerts",
    "D": "Shadow LLM",
    "E": "Shelly Murrell digest",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--week-ending", help="ISO date for Saturday of the week (default: today Melbourne)")
    return p.parse_args()


def week_dates(week_ending: date) -> list[str]:
    """Return the 7 ISO date strings ending at `week_ending` inclusive."""
    return [(week_ending - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]


def load_json_dumps(dates: list[str]) -> dict[str, dict[str, list[dict]]]:
    """Return {date: {sampler_id: [rows]}} from the per-day JSON dumps that
    exist on disk. Missing files are silently treated as empty.

    Mapping of filename suffix to sampler:
      -rss.json         -> B
      -candidates.json  -> A (or E if row.found_via=='shelly_digest')
      -shadow.json      -> D
      -alerts.json      -> C
    """
    out: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for d in dates:
        for suffix, sampler in (("rss", "B"), ("candidates", "A"),
                                ("shadow", "D"), ("alerts", "C")):
            path = AUDIT_DIR / f"{d}-{suffix}.json"
            if not path.exists():
                continue
            try:
                rows = json.loads(path.read_text())
            except json.JSONDecodeError:
                print(f"[WARN] malformed JSON: {path}", file=sys.stderr)
                continue
            for r in rows:
                if not r.get("canonical_url"):
                    continue
                if sampler == "A" and r.get("found_via") == "shelly_digest":
                    out[d]["E"].append(r)
                else:
                    if sampler in ("B", "C"):
                        # Floor + Alerts only write in-window items.
                        r = dict(r); r["kept"] = True; r["in_window"] = True
                    elif sampler == "D":
                        # Shadow trace writes all considered items with explicit
                        # `kept` flags; trust the file but enforce in_window True
                        # for sampler-set membership (the audit treats sampler D
                        # as contributing only the in-window subset).
                        if not r.get("in_window"):
                            continue
                    out[d][sampler].append(r)
    return out


def sampler_sets(by_day: dict[str, dict[str, list[dict]]]) -> dict[str, set[str]]:
    """Flatten the by-day dict into one set per sampler. Keys are canonical_url."""
    sets: dict[str, set[str]] = defaultdict(set)
    for d, samplers in by_day.items():
        for sid, rows in samplers.items():
            for r in rows:
                # Sampler A only contributes items it actually kept (briefed).
                if sid == "A" and not r.get("kept", False):
                    continue
                sets[sid].add(r["canonical_url"])
    return sets


def dedup_against(union: set[str], by_day: dict[str, dict[str, list[dict]]]) -> dict[str, dict]:
    """Best-effort fuzzy dedup: collapse near-duplicate canonical_urls in the
    union via Jaccard >= 0.7 on fuzzy_key tokens. Returns {canonical_url: row}
    keeping the first-seen row per cluster."""
    by_url: dict[str, dict] = {}
    fuzzy: dict[str, frozenset[str]] = {}
    for d in sorted(by_day.keys()):
        for sid, rows in by_day[d].items():
            for r in rows:
                cu = r.get("canonical_url")
                if not cu or cu not in union:
                    continue
                if cu in by_url:
                    continue
                tokens = frozenset((r.get("fuzzy_key") or "").split(","))
                # Compare against existing clusters.
                merged = False
                for existing_cu, existing_tokens in fuzzy.items():
                    if jaccard(tokens, existing_tokens) >= 0.7:
                        # Already represented — alias by replacing in the union.
                        merged = True
                        break
                if not merged:
                    by_url[cu] = r
                    fuzzy[cu] = tokens
    return by_url


def chapman(nx: int, ny: int, m: int) -> float:
    """Chapman estimator: N̂ = (Nx+1)(Ny+1)/(M+1) − 1."""
    if nx == 0 or ny == 0:
        return float("nan")
    return (nx + 1) * (ny + 1) / (m + 1) - 1


def render_report(week_ending: date,
                  sets: dict[str, set[str]],
                  union: set[str],
                  union_rows: dict[str, dict],
                  missed: list[dict],
                  source_coverage: list[dict],
                  drift_rows: list[dict]) -> tuple[str, str]:
    A = sets.get("A", set())
    B = sets.get("B", set())

    pooled_recall = (len(A & union) / len(union)) if union else 0.0
    floor_recall = (len(A & B) / len(B)) if B else float("nan")

    # Chapman across all populated sampler pairs that include A.
    chapman_pairs: list[tuple[str, str, float]] = []
    for partner in ("B", "C", "D", "E"):
        if partner in sets and sets[partner]:
            est = chapman(len(A), len(sets[partner]), len(A & sets[partner]))
            chapman_pairs.append((partner, SAMPLER_NAMES[partner], est))
    # Median estimate
    estimates = [e for _, _, e in chapman_pairs if e == e]  # filter NaN
    abs_recall: float | None = None
    if estimates:
        estimates.sort()
        median_est = estimates[len(estimates) // 2]
        if median_est > 0:
            abs_recall = len(A) / median_est

    # ------------------------------------------------------------------ MD
    title = f"CCS recall audit — week ending {week_ending.isoformat()} — pooled recall {pooled_recall:.0%}"
    md_lines = [f"# {title}", ""]
    md_lines.append("## Headline metrics")
    md_lines.append("")
    md_lines.append(f"- **Pooled recall** (A ∩ U / U): **{pooled_recall:.0%}**  ({len(A & union)} of {len(union)})")
    md_lines.append(f"- **Floor recall** (A ∩ B / B): " + (f"**{floor_recall:.0%}**  ({len(A & B)} of {len(B)})" if B else "_no RSS floor items this week_"))
    if abs_recall is not None:
        md_lines.append(f"- **Estimated absolute recall** (Chapman, median of {len(estimates)} pair-estimates): **{abs_recall:.0%}**")
    md_lines.append("")
    md_lines.append("## Sampler sizes")
    md_lines.append("")
    md_lines.append("| Sampler | Items |")
    md_lines.append("|---|---:|")
    for sid in ("A", "B", "C", "D", "E"):
        md_lines.append(f"| {sid} · {SAMPLER_NAMES[sid]} | {len(sets.get(sid, set()))} |")
    md_lines.append(f"| **Union U** | **{len(union)}** |")
    md_lines.append("")
    if chapman_pairs:
        md_lines.append("## Chapman pair-estimates")
        md_lines.append("")
        md_lines.append("| Pair | Overlap | Estimated N |")
        md_lines.append("|---|---:|---:|")
        for sid, name, est in chapman_pairs:
            overlap = len(A & sets[sid])
            md_lines.append(f"| A × {sid} ({name}) | {overlap} | {est:.0f} |")
        md_lines.append("")

    md_lines.append(f"## Top missed items ({len(missed)} total)")
    md_lines.append("")
    if not missed:
        md_lines.append("_No items in U that A did not capture._")
    else:
        for m in missed[:10]:
            md_lines.append(
                f"- **{m['headline']}** — {m['source_domain']} · "
                f"found via _{m['found_via']}_ · [link]({m['raw_url']})"
            )
    md_lines.append("")

    md_lines.append("## Source-coverage matrix")
    md_lines.append("")
    md_lines.append("| Source | Published (B+C+D+E) | Captured by A | Capture rate |")
    md_lines.append("|---|---:|---:|---:|")
    for row in source_coverage[:25]:
        rate = (row["captured"] / row["published"]) if row["published"] else 0
        md_lines.append(f"| {row['source_domain']} | {row['published']} | {row['captured']} | {rate:.0%} |")
    md_lines.append("")

    if drift_rows:
        md_lines.append("## Drift — last 12 weeks")
        md_lines.append("")
        md_lines.append("| Week ending | Pooled recall | Floor recall |")
        md_lines.append("|---|---:|---:|")
        for r in drift_rows[-12:]:
            md_lines.append(f"| {r['week_ending']} | {r['pooled']:.0%} | {r['floor']:.0%} |")
        md_lines.append("")

    md_lines.append("_— Auto-audit_")
    md = "\n".join(md_lines)

    # ------------------------------------------------------------------ HTML
    style = (
        "body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;"
        "max-width:760px;margin:0 auto;padding:24px;color:#222;line-height:1.5;font-size:16px}"
        "h1{font-size:22px}h2{font-size:17px;margin-top:24px}"
        "table{border-collapse:collapse;width:100%;margin:12px 0}"
        "th,td{border:1px solid #ddd;padding:6px 10px;text-align:left;font-size:14px}"
        "th{background:#f4f4f4}a{color:#0a4}"
        "@media print{a{color:#000;text-decoration:none}}"
    )
    html_doc = _md_to_html(md, title, style)
    return md, html_doc


import html as _html_mod  # noqa: E402
import re as _re_mod  # noqa: E402


def _inline_md_to_html(text: str) -> str:
    """Convert inline Markdown ([link](url), **bold**, _italic_) to HTML.

    Order matters: links first (to avoid eating ** inside link text), then bold,
    then italic. All non-link text is HTML-escaped before formatting markers are
    re-introduced.
    """
    # Split into link / non-link spans.
    pattern = _re_mod.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    out_parts: list[str] = []
    last = 0
    for m in pattern.finditer(text):
        out_parts.append(_format_runs(_html_mod.escape(text[last:m.start()])))
        out_parts.append(
            f'<a href="{_html_mod.escape(m.group(2), quote=True)}">'
            f'{_format_runs(_html_mod.escape(m.group(1)))}</a>'
        )
        last = m.end()
    out_parts.append(_format_runs(_html_mod.escape(text[last:])))
    return "".join(out_parts)


def _format_runs(escaped_text: str) -> str:
    """Apply **bold** and _italic_ (and *italic*) to already-escaped text."""
    escaped_text = _re_mod.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped_text)
    escaped_text = _re_mod.sub(r"(?<![A-Za-z0-9_])_([^_]+)_(?![A-Za-z0-9_])",
                               r"<em>\1</em>", escaped_text)
    escaped_text = _re_mod.sub(r"(?<!\*)\*([^*\s][^*]*?)\*(?!\*)", r"<em>\1</em>", escaped_text)
    return escaped_text


def _md_to_html(md: str, title: str, style: str) -> str:
    """Convert the limited Markdown subset produced by render_report to HTML.

    Supports: # / ## headings, - bulleted lists, | …  | tables with a
    --- separator row, **bold**, _italic_, [text](url), and blank-line paragraph
    separation.
    """
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if line.startswith("# "):
            out.append(f"<h1>{_inline_md_to_html(line[2:])}</h1>"); i += 1; continue
        if line.startswith("## "):
            out.append(f"<h2>{_inline_md_to_html(line[3:])}</h2>"); i += 1; continue

        # Bulleted list — consume contiguous "- " lines.
        if line.startswith("- "):
            out.append("<ul>")
            while i < len(lines) and lines[i].startswith("- "):
                out.append(f"<li>{_inline_md_to_html(lines[i][2:])}</li>")
                i += 1
            out.append("</ul>")
            continue

        # Table — consume contiguous "| … |" lines; the second is the separator.
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            if len(table_lines) >= 2:
                header_cells = [c.strip() for c in table_lines[0].strip("|").split("|")]
                # Skip separator row (table_lines[1]).
                out.append("<table>")
                out.append("<tr>" + "".join(
                    f"<th>{_inline_md_to_html(c)}</th>" for c in header_cells
                ) + "</tr>")
                for row in table_lines[2:]:
                    cells = [c.strip() for c in row.strip("|").split("|")]
                    out.append("<tr>" + "".join(
                        f"<td>{_inline_md_to_html(c)}</td>" for c in cells
                    ) + "</tr>")
                out.append("</table>")
            continue

        if stripped == "":
            i += 1; continue

        out.append(f"<p>{_inline_md_to_html(line)}</p>")
        i += 1

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_html_mod.escape(title)}</title><style>{style}</style></head><body>"
        + "\n".join(out)
        + f"<p style='color:#888;font-size:12px'>Generated {datetime.now(MELBOURNE).isoformat()}</p>"
        "</body></html>"
    )


def compute_missed_and_coverage(union: set[str],
                                union_rows: dict[str, dict],
                                sets: dict[str, set[str]]) -> tuple[list[dict], list[dict]]:
    A = sets.get("A", set())
    missed_urls = union - A
    missed: list[dict] = []
    for cu in missed_urls:
        r = union_rows.get(cu)
        if not r:
            continue
        # Determine which sampler(s) found it.
        found_in = [sid for sid in ("B", "C", "D", "E") if cu in sets.get(sid, set())]
        missed.append({
            "canonical_url": cu,
            "headline": r.get("headline", "(no headline)"),
            "source_domain": r.get("source_domain", ""),
            "raw_url": r.get("raw_url") or cu,
            "found_via": ",".join(found_in) or "?",
        })
    missed.sort(key=lambda x: (x["source_domain"], x["headline"]))

    coverage: dict[str, dict[str, int]] = defaultdict(lambda: {"published": 0, "captured": 0})
    for cu in union:
        r = union_rows.get(cu) or {}
        dom = r.get("source_domain", "")
        coverage[dom]["published"] += 1
        if cu in A:
            coverage[dom]["captured"] += 1
    cov_rows = [{"source_domain": d, **v} for d, v in coverage.items()]
    cov_rows.sort(key=lambda x: (-x["published"], x["source_domain"]))
    return missed, cov_rows


def load_drift(current_week_ending: date, current_pooled: float, current_floor: float) -> list[dict]:
    """Append today's metrics to audit/drift.json and return the rolling list."""
    drift_path = AUDIT_DIR / "drift.json"
    rows: list[dict] = []
    if drift_path.exists():
        try:
            rows = json.loads(drift_path.read_text())
        except json.JSONDecodeError:
            rows = []
    rows = [r for r in rows if r["week_ending"] != current_week_ending.isoformat()]
    rows.append({
        "week_ending": current_week_ending.isoformat(),
        "pooled": current_pooled,
        "floor": current_floor if current_floor == current_floor else 0.0,
    })
    rows.sort(key=lambda r: r["week_ending"])
    drift_path.write_text(json.dumps(rows, indent=2))
    return rows


def main() -> int:
    args = parse_args()
    if args.week_ending:
        week_ending = date.fromisoformat(args.week_ending)
    else:
        week_ending = datetime.now(MELBOURNE).date()
    dates = week_dates(week_ending)

    by_day = load_json_dumps(dates)
    sets = sampler_sets(by_day)
    union = set().union(*sets.values()) if sets else set()
    union_rows = dedup_against(union, by_day)
    # union is now potentially larger than the dedup'd set; reduce to dedup'd keys.
    union = set(union_rows.keys())

    missed, coverage = compute_missed_and_coverage(union, union_rows, sets)
    A, B = sets.get("A", set()), sets.get("B", set())
    pooled_recall = (len(A & union) / len(union)) if union else 0.0
    floor_recall = (len(A & B) / len(B)) if B else float("nan")
    drift_rows = load_drift(week_ending, pooled_recall, floor_recall)

    md, html_doc = render_report(week_ending, sets, union, union_rows, missed, coverage, drift_rows)

    out_md = AUDIT_DIR / f"{week_ending.isoformat()}-recall-report.md"
    out_html = AUDIT_DIR / f"{week_ending.isoformat()}-recall-report.html"
    out_md.write_text(md)
    out_html.write_text(html_doc)
    print(f"[INFO] wrote {out_md.name} and {out_html.name}")
    print(f"[INFO] pooled recall={pooled_recall:.0%}  floor recall={floor_recall:.0%}  missed={len(missed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
