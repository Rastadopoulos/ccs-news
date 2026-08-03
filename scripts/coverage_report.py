#!/usr/bin/env python3
"""Produce a daily technical collection-coverage report.

An empty result is only called ``no verified news`` when the scheduled sampler
files are present and healthy.  Missing or malformed collection evidence always
wins and yields ``partial coverage`` or ``collection impaired``.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit"
OUT = ROOT / "dashboard" / "data" / "coverage"
SAMPLERS = {
    "production candidates": "candidates.json",
    "RSS floor": "rss.json",
    "Google Alerts": "alerts.json",
    "shadow sampler": "shadow.json",
}


def scheduled(day: date) -> bool:
    return day.weekday() < 5


def load(path: Path) -> tuple[list[dict], str]:
    if not path.exists():
        return [], "missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], "malformed"
    if not isinstance(value, list):
        return [], "malformed"
    return value, "reachable"


def verification(row: dict) -> str:
    explicit = str(row.get("verification_status") or "").lower()
    if explicit in ("verified", "item-link", "reachable"):
        return "verified"
    if explicit in ("blocked", "failed", "unverified", "retry"):
        return "failed"
    if row.get("pub_date") or row.get("publication_date") or row.get("in_window") is True:
        return "verified"
    return "unknown"


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build(as_of: date, window: int, audit_dir: Path) -> dict:
    days = []
    retry = []
    for offset in range(window - 1, -1, -1):
        day = as_of - timedelta(days=offset)
        if not scheduled(day):
            continue
        date_s = day.isoformat()
        feeds = []
        for name, suffix in SAMPLERS.items():
            path = audit_dir / f"{date_s}-{suffix}"
            data, reach = load(path)
            verified = sum(verification(row) == "verified" for row in data)
            failures = sum(verification(row) == "failed" for row in data)
            unknown = sum(verification(row) == "unknown" for row in data)
            feeds.append({
                "source": name, "scheduled": True, "attempted": reach != "missing",
                "reachable": reach == "reachable", "technical_status": reach,
                "articles_retrieved": len(data), "publication_dates_verified": verified,
                "verification_failures": failures, "verification_unknown": unknown,
                "file": display_path(path),
            })
            for row in data:
                if verification(row) in ("failed", "unknown"):
                    retry.append({
                        "date": date_s, "source": name,
                        "url": row.get("canonical_url") or row.get("raw_url") or row.get("url") or "",
                        "headline": row.get("headline") or "",
                        "verification_status": row.get("verification_status") or "unknown",
                    })
        facts = audit_dir / f"{date_s}-facts.json"
        fact_rows, fact_status = load(facts)
        missing = sum(feed["technical_status"] == "missing" for feed in feeds)
        broken = sum(feed["technical_status"] == "malformed" for feed in feeds)
        retrieved = sum(feed["articles_retrieved"] for feed in feeds)
        verified = sum(feed["publication_dates_verified"] for feed in feeds)
        if missing == len(feeds) or broken or fact_status in ("missing", "malformed"):
            status = "collection impaired"
        elif missing:
            status = "partial coverage"
        elif verified == 0 and not fact_rows:
            status = "no verified news"
        else:
            status = "normal coverage"
        days.append({
            "date": date_s, "status": status, "feeds": feeds,
            "briefing_facts": len(fact_rows), "facts_file_status": fact_status,
            "articles_retrieved_across_samplers": retrieved,
            "publication_dates_verified_across_samplers": verified,
            "missing_scheduled_sampler_files": missing,
        })
    severity = {"normal coverage": 0, "no verified news": 0,
                "partial coverage": 1, "collection impaired": 2}
    overall = max((row["status"] for row in days), key=lambda value: severity[value],
                  default="collection impaired")
    latest_fact = max((row["date"] for row in days if row["briefing_facts"]), default="")
    lag = (as_of - date.fromisoformat(latest_fact)).days if latest_fact else None
    return {
        "as_of": as_of.isoformat(), "generated_at": datetime.now().astimezone().isoformat(),
        "status": overall, "latest_fact_date": latest_fact,
        "calendar_days_since_latest_facts": lag,
        "collection_stopped_or_behind": bool(lag is None or lag > 1),
        "quiet_day_rule": "No verified news is permitted only when every scheduled sampler is healthy.",
        "days": days, "retry_candidates": retry,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--window", type=int, default=14)
    ap.add_argument("--audit-dir", type=Path, default=AUDIT)
    ap.add_argument("--output-dir", type=Path, default=OUT)
    ap.add_argument("--strict", action="store_true", help="exit non-zero when collection is impaired")
    args = ap.parse_args()
    report = build(date.fromisoformat(args.date), args.window, args.audit_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "retry-candidates.json").write_text(
        json.dumps(report["retry_candidates"], indent=2) + "\n", encoding="utf-8")
    print(f"Coverage: {report['status']}; latest facts {report['latest_fact_date'] or 'none'}")
    return 2 if args.strict and report["status"] == "collection impaired" else 0


if __name__ == "__main__":
    raise SystemExit(main())
