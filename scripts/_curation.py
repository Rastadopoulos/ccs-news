"""Read the curated CSV datasets — the source of truth for everything on this
dashboard that is maintained rather than extracted.

Four datasets live as CSV in dashboard/data/curation/:

    funding-programmes.csv   standing government CCS funding pots
    funding-enrichment.csv   per-record classification of every money figure
    project-locations.csv    map coordinates for the storage projects
    gccsi-countries.csv      per-country facility counts, capacity, policy

CSV rather than JSON because these are genuinely tabular, because they open in
Excel without a conversion step, and because a one-line diff in a review shows
exactly which figure moved. The prose that cannot fit in a row — what each column
means, the known gaps, the source conventions — lives in curation/NOTES.md.

Two datasets deliberately stay JSON: storage-baseline.json and
reference-baseline.json. Their reconciliation waterfall and two-series structure
are not tables, and their caveats are rendered into the dashboard rather than
being maintainer notes.

Loaders here return the same shapes the build already expected from the JSON, so
the rest of the pipeline did not have to change when the format did.
"""

from __future__ import annotations

import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "dashboard", "data")
CSV_DIR = os.path.join(DATA_DIR, "curation")

# Excel writes and expects a BOM on UTF-8; this data is full of €, £, ø and ₹.
ENCODING = "utf-8-sig"

# Numeric columns. NUMERIC returns a whole number as int and a fractional one as
# float — period_years is 25 for the UK clusters but 2.5 for the Viking grant, and
# both must survive. ALWAYS_FLOAT keeps its decimal type even when whole, because
# a longitude rendered as -103 instead of -103.0, or a capacity as 4 instead of
# 4.0, reads as dropped precision.
NUMERIC = {
    "amount", "awarded_to_date", "period_start", "period_end", "period_years",
    "page", "policy_page", "carbon_price_page", "govt_share_aud",
    "operating", "construction", "advanced_development", "early_development",
    "pipeline", "total_facilities", "cross_border_participation",
}
ALWAYS_FLOAT = {"lat", "lon", "capacity_mtpa", "capacity_all_stages_mtpa"}


def _coerce(field, raw):
    """Empty stays None. A missing figure is not zero, and the dashboard leans on
    that distinction throughout — a country with no published drawdown must not
    render as having drawn down nothing."""
    if raw is None:
        return None
    s = raw.strip()
    if s == "":
        return None
    if field in NUMERIC or field in ALWAYS_FLOAT:
        try:
            n = float(s.replace(",", ""))
        except ValueError:
            return s
        if field in ALWAYS_FLOAT:
            return n
        return int(n) if n == int(n) else n
    return s


def read_rows(name):
    """Read one curated CSV into typed dicts. Missing file -> empty list, so a
    dataset that has not been created yet degrades to 'no data' rather than
    breaking the build."""
    path = os.path.join(CSV_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding=ENCODING, newline="") as f:
        return [{k: _coerce(k, v) for k, v in row.items() if k}
                for row in csv.DictReader(f)]


def write_rows(name, fieldnames, rows):
    """Write one curated CSV. Used by the generators that produce these datasets
    from source PDFs, and by anything that maintains them programmatically."""
    os.makedirs(CSV_DIR, exist_ok=True)
    path = os.path.join(CSV_DIR, name)
    with open(path, "w", encoding=ENCODING, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fieldnames})
    return path


# --------------------------------------------------------------------------- loaders

def load_funding_programmes():
    rows = read_rows("funding-programmes.csv")
    return {"programmes": rows} if rows else None


def load_funding_enrichment():
    """Keyed by the fact-record id it classifies."""
    out = {}
    for r in read_rows("funding-enrichment.csv"):
        rid = r.get("record_id")
        if not rid:
            continue
        out[rid] = {k: v for k, v in r.items() if k != "record_id" and v is not None}
    return out


def load_project_locations():
    out = {}
    for r in read_rows("project-locations.csv"):
        name = r.get("project")
        if not name:
            continue
        out[name] = {"lat": r.get("lat"), "lon": r.get("lon"),
                     "place": r.get("place") or ""}
    return {"locations": out} if out else None


def load_reference_countries():
    rows = read_rows("gccsi-countries.csv")
    return {"countries": rows} if rows else None
