#!/usr/bin/env python3
"""Build the CCS Intelligence Dashboard from extracted briefing facts.

Reads structured fact records produced by the extraction layer:
  * dashboard/data/facts-backfill.jsonl   — one-time frozen history (all briefings so far)
  * dashboard/data/raw/*.jsonl            — per-briefing raw extractions (backfill staging)
  * dashboard/data/quarterly/*.jsonl      — periodic external reports (e.g. GCCSI quarterly
                                            updates), extracted on arrival, same schema
  * audit/*-facts.json                    — ongoing per-day emissions from the daily routine

...normalises money to A$ (fixed reference rates from dashboard/data/fx_rates.json),
dedups across days (reusing scripts/_canon.py), excludes `radar` items from time-series
counts, and renders a single self-contained HTML file (inline SVG charts, no external deps):

  * dashboard/index.html                  — the live rolling dashboard
  * dashboard/snapshots/YYYY-MM-DD.html   — dated board-ready snapshot (pass --snapshot DATE)

Usage:
  python scripts/build_dashboard.py                 # rebuild dashboard/index.html
  python scripts/build_dashboard.py --snapshot 2026-07-11   # also write a dated snapshot

Design notes:
  * No external dependencies beyond the standard library + scripts/_canon.py.
  * Charts are hand-rendered inline SVG so the file works offline, over email, and as a
    Claude Artifact (strict CSP: no external hosts).
  * Every figure traces to its source item; commitment-status weighting keeps announced
    money from being conflated with committed/spent money.
"""

from __future__ import annotations

import glob
import html
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime

# Reuse the repo's canonicalisation + dedup helpers (single source of truth).
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from _canon import canonical_url, fuzzy_key, jaccard  # noqa: E402
from _countries import (COUNTRY_ISO, NON_COUNTRY_TOKENS, split_compound,  # noqa: E402
                         CONTINENT_GROUPS, GROUP_ORDER)
import _worldmap as W  # noqa: E402  (generated — see scripts/gen_worldmap.py)
import _curation  # noqa: E402  (curated CSV datasets — see scripts/_curation.py)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "dashboard", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
QUARTERLY_DIR = os.path.join(DATA_DIR, "quarterly")
AUDIT_DIR = os.path.join(ROOT, "audit")
OUT_HTML = os.path.join(ROOT, "dashboard", "index.html")
SNAP_DIR = os.path.join(ROOT, "dashboard", "snapshots")

# Commitment-status weights: how much of a headline figure we treat as "real money"
# for the money-committed trendlines. Announced intentions are discounted; cancelled
# money is tracked separately as a negative signal (never added to positive totals).
STATUS_WEIGHT = {
    "announced": 0.25,
    "allocated": 0.75,
    "committed": 1.00,
    "spent": 1.00,
    "cancelled": 0.0,   # tracked separately, not summed into positive commitment
    "na": 0.0,
}

REGION_ORDER = ["APAC", "China", "India", "North America", "Europe-UK",
                "Middle East", "Latin America", "Africa", "Global"]

# Peer jurisdictions for the Australia benchmark panel.
PEER_COUNTRIES = ["Australia", "United States", "United Kingdom", "European Union",
                  "Canada", "Norway", "Japan", "South Korea", "Malaysia", "China"]

PALETTE = ["#1f6f8b", "#e8a87c", "#41729f", "#c06c84", "#5b8c5a", "#d9a441",
           "#8e6c88", "#3a7ca5", "#c1666b", "#6d9dc5", "#a37b73", "#7fb069"]

# Countries whose landmass is sub-pixel on a world map — drawn as an explicit
# marker dot as well as (where it exists) their outline, so they stay visible
# and hoverable. Qatar and Singapore are both material CCS jurisdictions.
MICRO_ISO = {"SG", "QA", "BH"}

# Plain-English expansions of the storage taxonomy. Used verbatim in the map
# legend and the country card — the terms mean nothing to a non-specialist
# reader on their own, and "EOR" in particular reads as jargon.
STORAGE_CLASS_LABEL = {
    "dedicated": "Dedicated storage",
    "associated": "Associated reinjection",
    "eor": "Enhanced oil recovery",
}
STORAGE_CLASS_DEF = {
    "dedicated": "CO₂ injected into rock formations for the sole purpose of keeping it underground permanently.",
    "associated": "CO₂ separated during gas production and pumped back into the reservoir it came from.",
    "eor": "CO₂ pumped into ageing oilfields to push out more oil. The CO₂ stays underground, but producing more oil is the commercial driver.",
}


# ---------------------------------------------------------------------------
# Load + normalise
# ---------------------------------------------------------------------------

def load_fx():
    with open(os.path.join(DATA_DIR, "fx_rates.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg["rates"], cfg.get("as_of", "")


def load_reference():
    """Load the external GCCSI baseline (optional — returns None if absent)."""
    path = os.path.join(DATA_DIR, "reference-baseline.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_storage_baseline():
    """Load the cumulative-storage baseline (GCCSI × Imperial reconciliation; optional)."""
    path = os.path.join(DATA_DIR, "storage-baseline.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_reference_countries():
    """Per-country GCCSI facility counts, capacity and policy status.

    Source of truth is dashboard/data/curation/gccsi-countries.csv, written by
    scripts/gen_gccsi_countries.py from the Global Status report. Returns None
    when absent so the GCCSI map layers render as "no data" rather than the
    build failing."""
    return _curation.load_reference_countries()


def load_funding_enrichment():
    """Re-extraction overlay for money-carrying records: who funds it, what the
    figure measures, over what period, and whether it duplicates another
    record. Empty overlay means corpus figures are used raw."""
    return _curation.load_funding_enrichment()


def load_funding_programmes():
    """Standing government CCS funding programmes."""
    return _curation.load_funding_programmes()


def load_project_locations():
    """Indicative map coordinates for the storage-register projects. Without it
    the map simply draws no project pins."""
    return _curation.load_project_locations()


def _iter_records():
    """Yield raw records from all sources."""
    backfill = os.path.join(DATA_DIR, "facts-backfill.jsonl")
    sources = []
    if os.path.exists(backfill):
        sources.append(backfill)
    sources += sorted(glob.glob(os.path.join(RAW_DIR, "*.jsonl")))
    # Periodic external reports (e.g. GCCSI quarterly updates) — same schema, extracted
    # on arrival rather than daily. Centrally deduped against the daily corpus like everything else.
    quarterly_sources = sorted(glob.glob(os.path.join(QUARTERLY_DIR, "*.jsonl")))
    sources += quarterly_sources
    quarterly_set = set(quarterly_sources)
    for path in sources:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  ! skipping bad JSONL line in {os.path.basename(path)}: {e}",
                          file=sys.stderr)
                    continue
                if path in quarterly_set:
                    # All of a quarterly report's items share one ingestion-date
                    # stamp (the date the file landed), not a real per-item news
                    # date — a week-by-week trend chart would show a false spike
                    # in whatever week the report happened to be processed.
                    rec["_periodic_report"] = True
                yield rec
    # Ongoing per-day emissions (JSON arrays).
    for path in sorted(glob.glob(os.path.join(AUDIT_DIR, "*-facts.json"))):
        with open(path, encoding="utf-8") as f:
            try:
                arr = json.load(f)
            except json.JSONDecodeError as e:
                print(f"  ! skipping bad facts file {os.path.basename(path)}: {e}",
                      file=sys.stderr)
                continue
            for rec in arr:
                yield rec


def load_records(fx):
    """Load, normalise A$, and dedup all records. Returns (fresh, radar, stats)."""
    seen_urls = {}          # canonical_url -> record
    kept = []
    dropped_dupes = 0
    for rec in _iter_records():
        # Normalise money to A$.
        amt = rec.get("amount")
        cur = rec.get("currency")
        if amt is not None and cur in fx:
            rec["amount_aud"] = round(amt * fx[cur])
        elif amt is not None and cur not in fx:
            rec["amount_aud"] = None
            rec["_fx_missing"] = cur
        else:
            rec["amount_aud"] = None
        kept.append(rec)

    # Dedup: keep earliest fresh occurrence. Sort so fresh<radar and earlier date first.
    kept.sort(key=lambda r: (r.get("briefing_date", ""),
                             0 if r.get("item_status") == "fresh" else 1))
    deduped = []
    fuzz_index = []  # list of (fuzzy tuple, primary_org)
    for rec in kept:
        url = rec.get("url") or ""
        cu = canonical_url(url) if url else ""
        is_dupe = False
        if cu and cu in seen_urls:
            is_dupe = True
        else:
            fk = fuzzy_key(rec.get("headline", ""), rec.get("source"))
            orgs = rec.get("organisations") or []
            primary = (orgs[0].lower() if orgs else "")
            for (ofk, oorg) in fuzz_index:
                if jaccard(fk, ofk) >= 0.7 and (not primary or not oorg or primary == oorg):
                    is_dupe = True
                    break
            if not is_dupe:
                fuzz_index.append((fk, primary))
        if is_dupe:
            dropped_dupes += 1
            continue
        if cu:
            seen_urls[cu] = rec
        deduped.append(rec)

    # Apply the funding re-extraction overlay. Doing it here means every view
    # downstream — KPIs, map, region tables — sees the same corrected money.
    enrich = load_funding_enrichment()
    dup_dropped = 0
    for rec in deduped:
        e = enrich.get(rec.get("id"))
        if not e:
            continue
        rec["_funder_type"] = e.get("funder_type")
        rec["_basis"] = e.get("basis")
        rec["_period_years"] = e.get("period_years")
        rec["_funding_note"] = e.get("note")
        if e.get("force_status"):
            rec["_status_was"] = rec.get("commitment_status")
            rec["commitment_status"] = e["force_status"]
        if e.get("duplicate_of"):
            # The news item is real and stays in the corpus; its money is not
            # new money, so the amount is removed rather than the record.
            # Capacity is excluded the same way and for the same reason — a
            # restated project's Mtpa is not new capacity either, and until
            # 2026-07-28 this side of the same known duplicate (e.g. the
            # Pathways Alliance pair) was still being summed into pipeline_cap.
            rec["_dup_of"] = e["duplicate_of"]
            rec["_amount_aud_excluded"] = rec.get("amount_aud")
            rec["amount_aud"] = None
            rec["_capacity_mtpa_excluded"] = rec.get("capacity_mtpa")
            rec["capacity_mtpa"] = None
            dup_dropped += 1
    if dup_dropped:
        print(f"  · {dup_dropped} duplicate money figures excluded from totals "
              f"(same commitment reported twice)", file=sys.stderr)

    fresh = [r for r in deduped if r.get("item_status") == "fresh"]
    radar = [r for r in deduped if r.get("item_status") == "radar"]

    # The overlay is keyed by record id, so it only ever covers the records that
    # existed when it was last reviewed. New money arriving afterwards is counted
    # in full by default — the safe direction for a total, but it means the audit
    # silently decays. Surface the backlog on every build.
    #
    # Scoped to `fresh` on purpose: radar items carry money but are excluded from
    # every total, so flagging them would be noise that trains people to ignore
    # this warning.
    UNREVIEWED.clear()
    UNREVIEWED.extend(r for r in fresh if r.get("amount_aud") and r.get("id") not in enrich)
    if UNREVIEWED:
        print(f"  ! {len(UNREVIEWED)} money figure(s) not yet classified in "
              f"funding-enrichment.json — counted in full for now:", file=sys.stderr)
        for r in UNREVIEWED[:8]:
            print(f"      {r.get('id')}  {r.get('currency')} {r.get('amount'):,.0f}"
                  f"  {r.get('headline','')[:60]}", file=sys.stderr)
        if len(UNREVIEWED) > 8:
            print(f"      … and {len(UNREVIEWED) - 8} more", file=sys.stderr)
    stats = {"total_loaded": len(kept), "deduped": len(deduped),
             "dropped_dupes": dropped_dupes, "fresh": len(fresh), "radar": len(radar)}
    return fresh, radar, stats


def committed_aud(rec):
    """Status-weighted A$ figure for positive commitment totals (0 if none/cancelled).

    Also drops anything the funding re-extraction found is not a CCS funding
    flow — a whole-economy investment total, a lawsuit value, a merger synergy
    target, or a supplier sub-contract already inside a project's capex. Without
    this the same money is counted twice, or money that was never CCS funding is
    counted at all."""
    a = rec.get("amount_aud")
    if a is None:
        return 0.0
    basis = rec.get("_basis")
    if basis and basis not in FUNDING_BASES:
        return 0.0
    w = STATUS_WEIGHT.get(rec.get("commitment_status", "na"), 0.0)
    return a * w


# Bases that represent an actual flow of money into CCS. Market aggregates,
# legal claims, merger synergies and supplier sub-contracts are excluded: the
# first three are not CCS funding, and the last is spend already counted inside
# a project's capex.
FUNDING_BASES = {"government-funding", "private-investment", "project-capex"}


def funding_flow(rec):
    """A$ this record contributes to funding totals, or 0.

    Applies the re-extraction overlay: duplicates have already had their amount
    removed at load time, and anything that is not a genuine CCS funding flow is
    filtered out here."""
    if rec.get("_basis") and rec["_basis"] not in FUNDING_BASES:
        return 0.0
    return rec.get("amount_aud") or 0.0


def is_public_money(rec):
    return rec.get("_funder_type") in ("government", "mixed")


# Money records with no entry in funding-enrichment.json. Populated during load
# and surfaced on the dashboard so the review backlog is visible, not just logged.
UNREVIEWED = []


FIRM_STATUS = {"committed", "spent"}          # capacity in projects that are real
PIPELINE_STATUS = {"announced", "allocated"}  # capacity still speculative


def capacity(rec):
    """CO2 capture/storage capacity in Mtpa for this item (0 if none)."""
    c = rec.get("capacity_mtpa")
    return c if isinstance(c, (int, float)) and c > 0 else 0.0


# Signal-feed buckets. Rule-based over existing fields (no extra data) — priority-ordered,
# first match wins. Transparent heuristic, noted on the dashboard; the goal is to turn a flat
# "high relevance" list into something the CEO can act on Monday. A per-item LLM-assigned bucket
# is the higher-fidelity future option (would need re-extraction).
def signal_bucket(r):
    it = r.get("instrument_type") or ""
    sec = r.get("section") or ""
    vc = set(r.get("value_chain") or [])
    ots = set(r.get("org_types") or [])
    if it in ("policy", "incentive", "tax-credit") or r.get("target_year"):
        return "Policy & advocacy hooks"
    if (vc & {"storage", "transport"}) and it in (
            "offtake", "MoU-JV", "infrastructure", "project-milestone", "project-FID"):
        return "Storage customers & cross-border demand"
    if it == "offtake":
        return "Storage customers & cross-border demand"
    if (ots & {"OG-major", "NOC", "developer"}) and it in (
            "project-FID", "project-milestone", "project-cancellation"):
        return "Competitor & peer project moves"
    if sec == "technology" or (vc & {"DAC", "BECCS", "mineralisation", "utilisation", "marine-CDR"}):
        return "Technology threats & substitutes"
    if it in ("investment", "M&A", "MoU-JV"):
        return "Partnership & investment targets"
    return "Other high-relevance"


SIGNAL_ORDER = [
    "Policy & advocacy hooks",
    "Storage customers & cross-border demand",
    "Competitor & peer project moves",
    "Technology threats & substitutes",
    "Partnership & investment targets",
    "Other high-relevance",
]


# ---------------------------------------------------------------------------
# Formatting + SVG helpers
# ---------------------------------------------------------------------------

def fmt_aud(v):
    if v is None or v == 0:
        return "—"
    av = abs(v)
    if av >= 1e9:
        return f"A${v/1e9:.2f}bn"
    if av >= 1e6:
        return f"A${v/1e6:.1f}m"
    if av >= 1e3:
        return f"A${v/1e3:.0f}k"
    return f"A${v:.0f}"


def esc(s):
    return html.escape(str(s if s is not None else ""))


# Currency symbols for the pre-conversion reference. INR is shown in crore (the unit CCS
# announcements use in India); other currencies in bn/m.
CUR_SYM = {"USD": "US$", "EUR": "€", "GBP": "£", "AUD": "A$", "CAD": "C$", "NOK": "kr",
           "JPY": "¥", "CNY": "RMB", "SGD": "S$", "BRL": "R$", "INR": "₹", "AED": "AED",
           "SAR": "SAR", "DKK": "kr"}
POSITIVE_STATUS = {"announced", "allocated", "committed", "spent"}


def fmt_native(amount, cur):
    """Format a money figure in its original currency (true pre-conversion reference)."""
    sym = CUR_SYM.get(cur, (cur + " ") if cur else "")
    if cur == "INR":
        return f"₹{amount/1e7:,.0f} cr"      # crore = 1e7; ₹200bn → ₹20,000 cr
    if amount >= 1e9:
        return f"{sym}{amount/1e9:.2f}bn"
    if amount >= 1e6:
        return f"{sym}{amount/1e6:.0f}m"
    return f"{sym}{amount:,.0f}"


def native_ref(records, fx, max_cur=3):
    """Original-currency reference for a group: face value (positive-status only) of each
    currency present, largest first, plus the reconciling A$ face total in parentheses."""
    by_cur = defaultdict(float)
    for r in records:
        if r.get("commitment_status") in POSITIVE_STATUS and r.get("amount") and r.get("currency"):
            by_cur[r["currency"]] += r["amount"]
    if not by_cur:
        return "—"
    ordered = sorted(by_cur.items(), key=lambda kv: -(kv[1] * fx.get(kv[0], 0)))
    parts = [fmt_native(a, c) for c, a in ordered[:max_cur]]
    if len(ordered) > max_cur:
        parts.append("…")
    face_aud = sum(a * fx.get(c, 0) for c, a in ordered)
    return " + ".join(parts) + f" ({fmt_aud(round(face_aud))} face)"


def hbar_chart(rows, unit="", max_val=None, height_each=26, width=520, label_w=180):
    """Horizontal bar chart. rows = [(label, value, tooltip)]. Returns SVG string."""
    if not rows:
        return '<p class="muted">No data.</p>'
    if max_val is None:
        max_val = max((v for _, v, *_ in rows), default=0) or 1
    bar_w = width - label_w - 90
    h = height_each * len(rows) + 8
    parts = [f'<svg viewBox="0 0 {width} {h}" width="100%" role="img" class="chart">']
    for i, row in enumerate(rows):
        label, val = row[0], row[1]
        tip = row[2] if len(row) > 2 else f"{label}: {val}"
        y = i * height_each + 4
        w = int((val / max_val) * bar_w) if max_val else 0
        color = PALETTE[i % len(PALETTE)]
        parts.append(f'<title>{esc(tip)}</title>')
        parts.append(
            f'<text x="{label_w-8}" y="{y+height_each/2+4}" text-anchor="end" '
            f'class="bl">{esc(label)}</text>')
        parts.append(
            f'<rect x="{label_w}" y="{y+3}" width="{max(w,1)}" height="{height_each-10}" '
            f'rx="3" fill="{color}"><title>{esc(tip)}</title></rect>')
        vlabel = fmt_aud(val) if unit == "aud" else f"{val:g}{unit}"
        parts.append(
            f'<text x="{label_w+max(w,1)+6}" y="{y+height_each/2+4}" class="vl">{esc(vlabel)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def sparkline_multi(series, width=760, height=180, unit=""):
    """series = [(name, [(x_label, value), ...])]. Line chart over shared ordered x."""
    if not series:
        return '<p class="muted">No data.</p>'
    xs = [x for x, _ in series[0][1]]
    n = len(xs)
    if n == 0:
        return '<p class="muted">No data.</p>'
    all_vals = [v for _, pts in series for _, v in pts]
    vmax = max(all_vals + [1])
    pad_l, pad_b, pad_t, pad_r = 44, 34, 12, 12
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_b - pad_t

    def px(i):
        return pad_l + (plot_w * (i / (n - 1)) if n > 1 else plot_w / 2)

    def py(v):
        return pad_t + plot_h - (plot_h * (v / vmax) if vmax else 0)

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" class="chart">']
    # y gridlines
    for g in range(0, 5):
        gv = vmax * g / 4
        gy = py(gv)
        parts.append(f'<line x1="{pad_l}" y1="{gy:.0f}" x2="{width-pad_r}" y2="{gy:.0f}" class="grid"/>')
        lab = fmt_aud(gv) if unit == "aud" else f"{gv:g}"
        parts.append(f'<text x="{pad_l-6}" y="{gy+3:.0f}" text-anchor="end" class="ax">{esc(lab)}</text>')
    # x labels (thin them out)
    step = max(1, n // 8)
    for i, xl in enumerate(xs):
        if i % step == 0 or i == n - 1:
            parts.append(f'<text x="{px(i):.0f}" y="{height-pad_b+16}" text-anchor="middle" class="ax">{esc(xl)}</text>')
    # lines
    for si, (name, pts) in enumerate(series):
        color = PALETTE[si % len(PALETTE)]
        d = " ".join(f"{'M' if i==0 else 'L'}{px(i):.1f},{py(v):.1f}" for i, (_, v) in enumerate(pts))
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.2"/>')
        for i, (_, v) in enumerate(pts):
            parts.append(f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="2.6" fill="{color}"><title>{esc(name)} {esc(xs[i])}: {esc(fmt_aud(v) if unit=="aud" else v)}</title></circle>')
    parts.append("</svg>")
    # legend
    leg = " ".join(
        f'<span class="lg"><span class="sw" style="background:{PALETTE[si%len(PALETTE)]}"></span>{esc(name)}</span>'
        for si, (name, _) in enumerate(series))
    return "".join(parts) + f'<div class="legend">{leg}</div>'


def _displace_markers(markers, min_gap=11.0):
    """Push overlapping map markers apart so each stays individually hoverable.

    At world scale several real sites land within a few pixels of each other —
    Qatar's Ras Laffan against Bahrain, Sleipner against Northern Lights,
    Boundary Dam against Weyburn. Left alone they cover each other and the top
    one wins every mouse event.

    Markers closer than min_gap are grouped (single-linkage) and fanned evenly
    around their shared centre; each keeps a leader line back to its true
    position, which is the standard cartographic displacement convention — the
    marker moves, the stated location does not. Markers with no neighbour are
    left exactly where they belong.
    """
    n = len(markers)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if math.hypot(markers[i]["x"] - markers[j]["x"],
                          markers[i]["y"] - markers[j]["y"]) < min_gap:
                union(i, j)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    for members in clusters.values():
        if len(members) < 2:
            continue
        cx = sum(markers[i]["x"] for i in members) / len(members)
        cy = sum(markers[i]["y"] for i in members) / len(members)
        # Radius that guarantees min_gap between neighbours on the ring.
        k = len(members)
        radius = max(min_gap * 0.75, (min_gap / 2) / math.sin(math.pi / k))
        # Order by true bearing so the fan keeps roughly the real relative layout.
        members.sort(key=lambda i: math.atan2(markers[i]["y"] - cy, markers[i]["x"] - cx))
        for slot, i in enumerate(members):
            angle = (2 * math.pi * slot / k) - math.pi / 2
            markers[i]["dx"] = cx + radius * math.cos(angle)
            markers[i]["dy"] = cy + radius * math.sin(angle)
            markers[i]["moved"] = True


def country_contour_map(map_data):
    """Real-geography world map: vendored Natural Earth country outlines
    (scripts/_worldmap.py, Robinson projection) with per-country shading driven
    client-side by the pill controls, plus a pin for every named CO2 storage
    project placed at its real coordinates.

    Returns (svg, payload) where payload is the JSON blob of per-country data
    the pill JS reads. Keeping the data in one JSON island rather than smeared
    across dozens of data-* attributes keeps the SVG readable and lets the
    hover card show rich per-country detail (named projects, both tonnage
    bases, policy status) that attributes could not carry cleanly.

    Countries with no CCS data still render, in a muted "no data" fill — a
    world map that silently omits most of the world would misrepresent how
    concentrated CCS activity actually is."""
    by_iso = {d["iso2"]: d for d in map_data.values()}
    parts = [f'<svg viewBox="0 0 {W.VIEWBOX_W} {W.VIEWBOX_H}" width="100%" '
             f'role="img" aria-label="World map of CCS activity by country" '
             f'class="chart worldmap" id="ccs-map">']
    parts.append(f'<rect x="0" y="0" width="{W.VIEWBOX_W}" height="{W.VIEWBOX_H}" class="ocean"/>')

    # Country shapes. Tracked countries carry data-country so the JS can find them.
    parts.append('<g class="countries">')
    for iso, d in sorted(W.COUNTRY_PATH.items()):
        rec = by_iso.get(iso)
        if rec:
            parts.append(f'<path d="{d}" class="cshape has-data" data-country="{esc(rec["name"])}">'
                         f'<title>{esc(rec["name"])}</title></path>')
        else:
            parts.append(f'<path d="{d}" class="cshape no-data"/>')
    parts.append('</g>')

    # Markers: one per storage project, plus a ring for any microstate that is
    # too small to see. Collected before drawing because several of them overlap
    # at world scale (Qatar's project sits on top of Qatar and Bahrain; Sleipner
    # nearly on Northern Lights) and have to be pushed apart to stay clickable.
    markers = []
    seen_pins = set()
    for rec in sorted(map_data.values(), key=lambda r: r["name"]):
        for pr in rec["storage"].get("projects", []):
            if pr.get("lat") is None or pr.get("lon") is None:
                continue
            # A cross-border project is one physical site: draw it once.
            if pr["name"] in seen_pins:
                continue
            seen_pins.add(pr["name"])
            x, y = W.project_lonlat(pr["lon"], pr["lat"])
            tip = f'{pr["name"]} — {STORAGE_CLASS_LABEL.get(pr["class"], pr["class"])}'
            if pr.get("place"):
                tip += f' ({pr["place"]})'
            markers.append({"x": x, "y": y, "kind": "pin", "cls": pr["class"],
                            "country": rec["name"], "project": pr["name"], "tip": tip})

    pinned_countries = {m["country"] for m in markers}
    for iso, rec in sorted(by_iso.items()):
        pt = W.LABEL_POINT.get(iso)
        # Skip the ring where the country already carries project pins — the pins
        # make it visible, and a ring underneath them just adds a collision.
        if not pt or iso not in MICRO_ISO or rec["name"] in pinned_countries:
            continue
        markers.append({"x": pt[0], "y": pt[1], "kind": "dot", "cls": None,
                        "country": rec["name"], "project": None,
                        "tip": f'{rec["name"]} — too small to shade at this scale'})

    _displace_markers(markers)

    # Leader lines first so they sit under the markers they point to.
    parts.append('<g class="leaders">')
    for m in markers:
        if m.get("moved"):
            parts.append(f'<line x1="{m["x"]:.1f}" y1="{m["y"]:.1f}" '
                         f'x2="{m["dx"]:.1f}" y2="{m["dy"]:.1f}" class="leader"/>')
            parts.append(f'<circle cx="{m["x"]:.1f}" cy="{m["y"]:.1f}" r="0.9" class="truept"/>')
    parts.append('</g>')

    parts.append('<g class="pins">')
    for m in markers:
        cx, cy = (m["dx"], m["dy"]) if m.get("moved") else (m["x"], m["y"])
        attrs = f'data-country="{esc(m["country"])}"'
        if m["project"]:
            attrs += f' data-project="{esc(m["project"])}"'
        cls = f'pin pin-{esc(m["cls"])}' if m["kind"] == "pin" else "microdot"
        # An invisible, larger hit target so tightly-spaced markers stay easy to
        # click; the visible circle stays small so the map does not get muddy.
        parts.append(f'<g class="marker" {attrs}><title>{esc(m["tip"])}</title>'
                     f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" class="hit"/>'
                     f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.4" class="{cls}"/></g>')
    parts.append('</g>')
    parts.append('</svg>')

    payload = json.dumps(
        {"countries": {d["name"]: d for d in map_data.values()}},
        ensure_ascii=True, separators=(",", ":"),
    ).replace("<", "\\u003c")
    return "".join(parts), payload


# ---------------------------------------------------------------------------
# World map — per-country aggregation across the three source layers.
# Each function draws from exactly ONE source; build_country_map_data() merges
# them keyed by country name but never blends their values into one number
# (see storage-baseline.json's signed-off "two labelled series, never blended"
# convention, which the storage-class layer below extends to the map).
# ---------------------------------------------------------------------------

def map_news_activity(country_cnt, country_val, country_recs):
    """CO2CRC-news-tracking layer, per country.

    NOTE ON WORDING: these are *news developments* — announcements, milestones,
    funding decisions reported in the press — NOT projects and NOT facilities.

    Money is split by who is paying (public vs private) and filtered to genuine
    CCS funding flows via the re-extraction overlay, so a whole-economy
    investment figure, a lawsuit, a merger synergy target or a supplier
    sub-contract can no longer land in a country's funding total. Amounts are
    as-stated with no period normalisation, which is why these are labelled as
    money *reported in this window* and never as a funding position — for that
    see the standing programmes layer."""
    out = {}
    for c, recs in country_recs.items():
        pub = priv = 0.0
        for r in recs:
            if r.get("commitment_status") not in ("allocated", "committed", "spent"):
                continue
            amt = funding_flow(r)
            if not amt:
                continue
            if is_public_money(r):
                pub += amt
            else:
                priv += amt
        out[c] = {
            "developments": country_cnt.get(c, 0),
            "weighted_aud": round(country_val.get(c, 0)),
            "public_aud": round(pub),
            "private_aud": round(priv),
        }
    return out


def map_funding_programmes(fprog, fx):
    """Standing government CCS funding programmes, per country.

    This is the funding measure that means something: a total, the period it
    runs over, and how much has actually been awarded where a source says so.
    The news corpus cannot produce it, because a programme announced before the
    corpus window simply is not in the corpus."""
    if not fprog:
        return {}
    out = defaultdict(lambda: {"total_aud": 0.0, "awarded_aud": 0.0,
                                "ccs_specific_aud": 0.0, "programmes": []})
    for p in fprog.get("programmes", []):
        rate = fx.get(p.get("currency"), 0)
        amt = (p.get("amount") or 0) * rate
        awarded = (p.get("awarded_to_date") or 0) * rate
        e = out[p["country"]]
        e["total_aud"] += amt
        e["awarded_aud"] += awarded
        if p.get("scope") == "ccs-specific":
            e["ccs_specific_aud"] += amt
        e["programmes"].append({
            "programme": p.get("programme"),
            "funder": p.get("funder"),
            "amount": p.get("amount"),
            "currency": p.get("currency"),
            "amount_aud": round(amt),
            "period_years": p.get("period_years"),
            "annual_aud": round(amt / p["period_years"]) if p.get("period_years") else None,
            "awarded_to_date": p.get("awarded_to_date"),
            "awarded_aud": round(awarded) if awarded else None,
            "awarded_pct": (round(100 * p["awarded_to_date"] / p["amount"])
                             if p.get("awarded_to_date") and p.get("amount") else None),
            "awarded_note": p.get("awarded_note"),
            "scope": p.get("scope"),
            "status": p.get("status"),
            "note": p.get("note"),
        })
    for e in out.values():
        e["total_aud"] = round(e["total_aud"])
        e["awarded_aud"] = round(e["awarded_aud"])
        e["ccs_specific_aud"] = round(e["ccs_specific_aud"])
    return dict(out)


def map_storage_register(sref, plocs):
    """Imperial x GCCSI storage-register layer, per country.

    Gives each country its dedicated/associated/EOR project counts, the named
    projects themselves (with map coordinates for pins), and the two cumulative
    tonnage totals kept strictly apart: measured_total_mt is Imperial College's
    MEASURED actual injection; reported_total_mt is the GCCSI/operator REPORTED
    figure. They answer different questions and are never summed together.

    storage-baseline.json's one compound country ("United States/Canada") is
    credited to BOTH countries via split_compound()."""
    if not sref:
        return {}
    locs = (plocs or {}).get("locations", {})
    out = defaultdict(lambda: {"dedicated": 0, "associated": 0, "eor": 0,
                                "projects": [], "measured_total_mt": 0.0,
                                "reported_total_mt": 0.0})
    for p in sref.get("projects", []):
        cls = p.get("class", "eor")
        name = p.get("name")
        loc = locs.get(name) or {}
        measured = p.get("measured_actual_cumulative_mt")
        reported = p.get("reported_cumulative_mt")
        for country in split_compound(p.get("country", "")):
            e = out[country]
            e[cls] += 1
            e["projects"].append({
                "name": name,
                "class": cls,
                "capacity_mtpa": p.get("capacity_mtpa"),
                "start_year": p.get("start_year"),
                "measured_mt": measured,
                "reported_mt": reported,
                "lat": loc.get("lat"),
                "lon": loc.get("lon"),
                "place": loc.get("place"),
            })
            if isinstance(measured, (int, float)):
                e["measured_total_mt"] += measured
            if isinstance(reported, (int, float)):
                e["reported_total_mt"] += reported
    for e in out.values():
        e["measured_total_mt"] = round(e["measured_total_mt"], 2)
        e["reported_total_mt"] = round(e["reported_total_mt"], 2)
    return dict(out)


def map_gccsi_country(ref_countries):
    """GCCSI Global-Status-of-CCS layer, per country: facility counts by
    lifecycle stage, stated capture capacity, national carbon-management-
    strategy status, and headline carbon price / incentive.

    Returns {} if the country-level extraction file is absent, so those map
    layers simply render as "no data" rather than breaking the build."""
    if not ref_countries:
        return {}
    out = {}
    for row in ref_countries.get("countries", []):
        out[row["country"]] = {
            "operating": row.get("operating"),
            "construction": row.get("construction"),
            "pipeline": row.get("pipeline"),
            "capacity_mtpa": row.get("capacity_mtpa"),
            "capacity_note": row.get("capacity_note"),
            "policy_status": row.get("policy_status"),
            "policy_note": row.get("policy_note"),
            "carbon_price": row.get("carbon_price"),
            "note": row.get("note"),
        }
    return out


def build_country_map_data(country_cnt, country_val, country_recs, sref,
                            ref_countries, plocs, fprog=None, fx=None):
    """Merge the three source layers into one per-country record, keyed by
    country name and resolved to an ISO code for map rendering.

    The layers stay namespaced ("news" / "gccsi" / "storage") rather than being
    flattened, so no figure can be read without knowing which organisation
    produced it — the same discipline the storage-baseline reconciliation
    already applies to tonnage.

    A country present in only one layer still gets a map entry. A country is
    dropped only if it has no ISO code, and that is logged, never silent.
    Returns (merged, eu_aggregate, region_totals)."""
    news = map_news_activity(country_cnt, country_val, country_recs)
    storage = map_storage_register(sref, plocs)
    gccsi = map_gccsi_country(ref_countries)
    funding = map_funding_programmes(fprog, fx or {})
    eu_aggregate = news.get("European Union")

    all_countries = (set(news) | set(storage) | set(gccsi) | set(funding)) - NON_COUNTRY_TOKENS
    unmapped = sorted(c for c in all_countries if c not in COUNTRY_ISO)
    if unmapped:
        print(f"  ! countries missing from _countries.COUNTRY_ISO (skipped from map): {unmapped}",
              file=sys.stderr)

    merged = {}
    for c in sorted(all_countries):
        if c not in COUNTRY_ISO:
            continue
        merged[c] = {
            "name": c,
            "iso2": COUNTRY_ISO[c],
            "region": CONTINENT_GROUPS.get(c, "Other"),
            "news": news.get(c, {}),
            "gccsi": gccsi.get(c, {}),
            "storage": storage.get(c, {}),
            "funding": funding.get(c, {}),
        }

    # Continent roll-up — "how much is happening per region", the question the
    # per-country view can't answer at a glance.
    #
    # Storage projects are deduplicated BY NAME before being counted or summed.
    # A cross-border project is deliberately credited to both its countries in
    # the per-country layer, so naively adding those country totals would count
    # it — and its tonnage — twice in any roll-up.
    region_totals = {}
    for grp in GROUP_ORDER:
        members = [d for d in merged.values() if d["region"] == grp]
        uniq = {}
        for d in members:
            for pr in d["storage"].get("projects", []):
                uniq.setdefault(pr["name"], pr)
        region_totals[grp] = {
            "countries": len(members),
            "developments": sum(d["news"].get("developments", 0) for d in members),
            "public_aud": sum(d["news"].get("public_aud", 0) for d in members),
            "private_aud": sum(d["news"].get("private_aud", 0) for d in members),
            "programme_aud": sum(d["funding"].get("total_aud", 0) for d in members),
            "storage_projects": len(uniq),
            "measured_mt": round(sum(p["measured_mt"] for p in uniq.values()
                                     if isinstance(p.get("measured_mt"), (int, float))), 2),
            "operating": sum(d["gccsi"].get("operating") or 0 for d in members),
        }
    return merged, eu_aggregate, region_totals


# ---------------------------------------------------------------------------
# Aggregations + view rendering
# ---------------------------------------------------------------------------

def iso_week(d):
    y, w, _ = datetime.strptime(d, "%Y-%m-%d").isocalendar()
    return f"{y}-W{w:02d}"


def render(fresh, radar, stats, fx, fx_asof, build_dt, ref=None, sref=None,
           ref_countries=None, plocs=None, fprog=None):
    dates = sorted({r["briefing_date"] for r in fresh})
    span = f"{dates[0]} → {dates[-1]}" if dates else "no data"

    # --- Headline KPIs ---
    total_committed = sum(committed_aud(r) for r in fresh)
    # Face value = positive commitments only (announced→spent). Excludes `na` (context/
    # market-aggregate/cost-saving figures) and `cancelled` so non-commitments never inflate it.
    POSITIVE = {"announced", "allocated", "committed", "spent"}
    total_announced_face = sum(funding_flow(r) for r in fresh
                               if r.get("commitment_status") in POSITIVE)
    cancelled_val = sum(r.get("amount_aud") or 0 for r in fresh
                        if r.get("commitment_status") == "cancelled")
    n_items = len(fresh)
    high_rel = [r for r in fresh if r.get("co2crc_relevance") == "high"]
    firm_cap = sum(capacity(r) for r in fresh if r.get("commitment_status") in FIRM_STATUS)
    pipeline_cap = sum(capacity(r) for r in fresh if r.get("commitment_status") in PIPELINE_STATUS)

    # --- View 1: geography ---
    region_val = Counter()
    region_cnt = Counter()
    region_recs = defaultdict(list)
    for r in fresh:
        reg = r.get("region") or "Global"
        region_val[reg] += committed_aud(r)
        region_cnt[reg] += 1
        region_recs[reg].append(r)
    geo_rows = [(reg, region_val[reg], f"{reg}: {fmt_aud(region_val[reg])} across {region_cnt[reg]} developments")
                for reg in REGION_ORDER if region_cnt[reg]]
    geo_rows.sort(key=lambda x: -x[1])
    geo_cnt_rows = sorted([(reg, region_cnt[reg]) for reg in region_cnt], key=lambda x: -x[1])
    # Region table with the original-currency reference (before A$ conversion).
    region_tbl = [(reg, region_val[reg], native_ref(region_recs[reg], fx))
                  for reg, _, _ in geo_rows]

    country_val = Counter()
    country_cnt = Counter()
    country_recs = defaultdict(list)
    for r in fresh:
        for c in (r.get("countries") or []):
            country_val[c] += committed_aud(r)
            country_cnt[c] += 1
            country_recs[c].append(r)
    top_countries = [c for c, _ in country_val.most_common() if country_val[c] > 0][:10]
    country_tbl = [(c, country_val[c], native_ref(country_recs[c], fx)) for c in top_countries]

    # World map data (all 3 layers, merged but never blended — see the map_* docstrings above).
    map_data, eu_aggregate, region_totals = build_country_map_data(
        country_cnt, country_val, country_recs, sref, ref_countries, plocs, fprog, fx)

    # --- View 2: where the money goes ---
    instr_val = Counter()
    instr_cnt = Counter()
    for r in fresh:
        it = r.get("instrument_type") or "other"
        instr_val[it] += committed_aud(r)
        instr_cnt[it] += 1
    instr_rows = sorted(
        [(it, instr_val[it], f"{it}: {fmt_aud(instr_val[it])} · {instr_cnt[it]} developments")
         for it in instr_cnt], key=lambda x: -x[1])
    instr_cnt_rows = sorted([(it, instr_cnt[it]) for it in instr_cnt], key=lambda x: -x[1])

    vc_cnt = Counter()
    for r in fresh:
        for v in (r.get("value_chain") or []):
            if v not in ("not-applicable",):
                vc_cnt[v] += 1
    vc_rows = sorted([(v, c) for v, c in vc_cnt.items()], key=lambda x: -x[1])

    # --- View 3: actors ---
    org_cnt = Counter()
    org_type_of = {}
    for r in fresh:
        for i, o in enumerate(r.get("organisations") or []):
            org_cnt[o] += 1
            ots = r.get("org_types") or []
            if i < len(ots) and o not in org_type_of:
                org_type_of[o] = ots[i]
    top_orgs = org_cnt.most_common(12)
    org_rows = [(o, c, f"{o} ({org_type_of.get(o,'?')}): {c} mentions") for o, c in top_orgs]

    # O&G major posture: advancing vs retreating
    og_advancing, og_retreating = [], []
    for r in fresh:
        ots = r.get("org_types") or []
        if "OG-major" in ots or "NOC" in ots:
            if r.get("commitment_status") == "cancelled" or r.get("instrument_type") == "project-cancellation":
                og_retreating.append(r)
            elif r.get("instrument_type") not in ("litigation", "other"):
                og_advancing.append(r)

    # --- View 4: deployment-mandate tracker ---
    mandates = [r for r in fresh if r.get("target_year")]
    mandates.sort(key=lambda r: (r.get("target_year") or 9999))

    # --- View 5: Australia benchmark ---
    peer_val = Counter()
    peer_cnt = Counter()
    peer_recs = defaultdict(list)
    for r in fresh:
        for c in (r.get("countries") or []):
            if c in PEER_COUNTRIES:
                peer_val[c] += committed_aud(r)
                peer_cnt[c] += 1
                peer_recs[c].append(r)
    peer_rows = [(c, peer_cnt[c], f"{c}: {peer_cnt[c]} developments · {fmt_aud(peer_val[c])}")
                 for c in PEER_COUNTRIES if peer_cnt[c]]
    peer_rows.sort(key=lambda x: -x[1])
    peer_tbl = [(c, peer_val[c], peer_cnt[c], native_ref(peer_recs[c], fx))
                for c in sorted(PEER_COUNTRIES, key=lambda c: -peer_val[c]) if peer_cnt[c]]
    au_items = [r for r in fresh if "Australia" in (r.get("countries") or [])]
    apac_watch = [r for r in fresh if r.get("region") in ("APAC", "China", "India")
                  and "Australia" not in (r.get("countries") or [])]

    # --- View 6: momentum & sentiment ---
    media = [r for r in fresh if r.get("section") == "media" or r.get("sentiment")]
    sent_cnt = Counter(r.get("sentiment") for r in media if r.get("sentiment"))

    # weekly item-count momentum. Periodic reports (e.g. a GCCSI quarterly update)
    # land as one batch under a single ingestion-date stamp, not real day-by-day
    # news — including them would show a false newsflow spike in whatever week
    # they happened to be processed, not a real acceleration in CCS activity.
    trend_fresh = [r for r in fresh if not r.get("_periodic_report")]
    wk_cnt = Counter(iso_week(r["briefing_date"]) for r in trend_fresh)
    weeks = sorted(wk_cnt)
    momentum_series = [("Developments / week", [(w.split("-W")[1], wk_cnt[w]) for w in weeks])]

    # weekly committed A$ by top-3 regions — same periodic-report exclusion, and
    # for the same reason (a batch ingestion date is not a real weekly signal).
    top3 = [reg for reg, _ in Counter(
        {reg: region_val[reg] for reg in region_val}).most_common(3)]
    wk_reg = defaultdict(lambda: defaultdict(float))
    for r in trend_fresh:
        wk_reg[r.get("region") or "Global"][iso_week(r["briefing_date"])] += committed_aud(r)
    money_series = [(reg, [(w.split("-W")[1], wk_reg[reg].get(w, 0)) for w in weeks])
                    for reg in top3]

    # --- View 7: capacity committed (Mtpa) ---
    cap_reg = Counter()
    cap_vc = Counter()
    CAP_STATUS = FIRM_STATUS | PIPELINE_STATUS  # exclude `na` targets/market-aggregates & cancelled
    for r in fresh:
        cval = capacity(r)
        if cval <= 0 or r.get("commitment_status") not in CAP_STATUS:
            continue
        cap_reg[r.get("region") or "Global"] += cval
        segs = [v for v in (r.get("value_chain") or []) if v != "not-applicable"]
        for v in segs:
            cap_vc[v] += cval / len(segs)  # split evenly across an item's segments
    cap_reg_rows = sorted([(k, round(v, 2), f"{k}: {v:.1f} Mtpa") for k, v in cap_reg.items()],
                          key=lambda x: -x[1])
    cap_vc_rows = sorted([(k, round(v, 2)) for k, v in cap_vc.items()], key=lambda x: -x[1])

    # --- View 8: CO2CRC signal feed (segmented, high + medium relevance) ---
    feed_pool = sorted([r for r in fresh if r.get("co2crc_relevance") in ("high", "medium")],
                       key=lambda r: (r.get("co2crc_relevance") != "high", r["briefing_date"]),
                       reverse=False)
    feed_pool.sort(key=lambda r: r["briefing_date"], reverse=True)
    buckets = defaultdict(list)
    for r in feed_pool:
        buckets[signal_bucket(r)].append(r)

    # ============================ HTML ============================
    P = []
    A = P.append

    def kpi(label, value, sub="", src=None):
        # src = (href, short-label) → renders a "source table" link inside the card
        srch = (f'<div class="ksrc"><a href="{esc(src[0])}">{esc(src[1])} →</a></div>'
                if src else "")
        return (f'<div class="kpi"><div class="kv">{esc(value)}</div>'
                f'<div class="kl">{esc(label)}</div>'
                f'{f"<div class=kss>{esc(sub)}</div>" if sub else ""}{srch}</div>')

    # Every section states which organisation's data it rests on. Three sources
    # feed this dashboard and they measure genuinely different things, so a
    # reader who cannot tell them apart will draw wrong conclusions — the
    # provenance chip is therefore mandatory, not decorative.
    SRC_CHIP = {
        "co2crc": ("src-co2crc", "CO2CRC news tracking",
                   "Compiled by CO2CRC from daily monitoring of the CCS trade and financial press."),
        "gccsi": ("src-gccsi", "GCCSI Global Status of CCS",
                  "Global CCS Institute’s annual survey of commercial CCS facilities worldwide."),
        "imperial": ("src-imperial", "Imperial College London",
                     "The London Register of Subsurface CO₂ Storage — measured injection volumes."),
    }

    def sources_line(*keys):
        chips = []
        for k in keys:
            cls, label, tip = SRC_CHIP[k]
            chips.append(f'<span class="srcchip {cls}" title="{esc(tip)}">{esc(label)}</span>')
        return f'<div class="srcline"><span class="srclabel">Data source</span>{"".join(chips)}</div>'

    def section(title, subtitle="", anchor="", sources=()):
        idattr = f' id="{anchor}"' if anchor else ""
        A(f'<h2{idattr}>{esc(title)}</h2>')
        if sources:
            A(sources_line(*sources))
        if subtitle:
            A(f'<p class="sub">{esc(subtitle)}</p>')

    def item_list(recs, limit=12, show_why=False):
        if not recs:
            A('<p class="muted">No developments recorded in this window.</p>')
            return
        A('<ul class="items">')
        for r in recs[:limit]:
            money = fmt_aud(r.get("amount_aud")) if r.get("amount_aud") else ""
            st = r.get("commitment_status", "")
            badge = f'<span class="badge b-{esc(st)}">{esc(st)}</span>' if st and st != "na" else ""
            mbadge = f'<span class="badge b-money">{esc(money)}</span>' if money else ""
            url = r.get("url") or ""
            head = esc(r.get("headline", ""))
            head = f'<a href="{esc(url)}" target="_blank" rel="noopener">{head}</a>' if url else head
            why = (f'<div class="why">↳ {esc(r.get("co2crc_note"))}</div>'
                   if show_why and r.get("co2crc_note") else "")
            regc = " · ".join(filter(None, [r.get("region"), ", ".join(r.get("countries") or [])[:60] if r.get("countries") else ""]))
            A(f'<li><div class="ih">{head} {badge}{mbadge}</div>'
              f'<div class="im">{esc(r.get("briefing_date"))} · {esc(regc)} · '
              f'{esc(r.get("instrument_type"))} · {esc(r.get("source"))}</div>{why}</li>')
        A('</ul>')

    A(f'<title>Global CCS Dashboard by CO2CRC</title>')
    A(f'<meta name="description" content="Global CCS Dashboard by CO2CRC — trend intelligence from the daily briefing corpus plus the GCCSI Global Status of CCS report and the London Register of Subsurface CO2 Storage, through the CO2CRC/CO2Tech strategic lens.">')
    A(f'<meta name="author" content="Dr Matthias Raab">')
    A(STYLE)
    A('<div class="wrap">')
    A('<header>')
    A('<div class="eyebrow">CO2CRC · CO2Tech — Strategic Intelligence</div>')
    A('<h1>Global CCS Dashboard by CO2CRC</h1>')
    A(f'<p class="meta">Corpus: <b>{len(dates)}</b> briefings · {esc(span)} · '
      f'{stats["fresh"]} tracked developments ({stats["dropped_dupes"]} duplicate reports merged) · '
      f'built {esc(build_dt)}</p>')
    A('<p class="disclaimer">Corpus figures are extracted from press-summary briefings (not audited '
      'financials); global storage baselines are drawn from two sources that measure different things — '
      'the GCCSI <i>Global Status of CCS</i> report (reported project capacity) and the Imperial College '
      '<i>London Register of Subsurface CO₂ Storage</i> (independently measured actual tonnes). '
      '<b>They are shown side by side but never added together or reconciled into one number</b> — see '
      '<a href="#v2c">View 2c</a> for why, and how much they diverge. '
      'Money normalised to A$ at fixed reference rates (as of '
      f'{esc(fx_asof)}); commitment status weights announced vs committed money. '
      'Every headline figure links to the table it comes from; every development links to its source. '
      'For board &amp; senior-stakeholder situational awareness.</p>')
    A('</header>')

    # KPI strip
    A('<div class="kpis">')
    if sref:
        _bw_steps = sref.get("bridge_waterfall", {}).get("steps", [])
        _dedicated_step = next((s for s in _bw_steps if s.get("basis") == "derived actual"), None)
        _eor_step = next((s for s in _bw_steps if "EOR projects" in (s.get("label") or "")), None)
        _idd = sref.get("series", {}).get("imperial_dedicated_derived", {})
        _dedicated_mt = _dedicated_step.get("mt") if _dedicated_step else _idd.get("cumulative_mt_approx", "—")
        _eor_mt = abs(_eor_step["mt"]) if _eor_step and isinstance(_eor_step.get("mt"), (int, float)) else "—"
        A(kpi("CO₂ stored to date — dedicated", f"{_dedicated_mt} Mt",
              "measured actual, delivery-factor-adjusted to ~Jun-2025", ("#v2c", "Reconciliation · View 2c")))
        A(kpi("CO₂ stored to date — via EOR", f"~{_eor_mt} Mt",
              "measured actual, ~2020 vintage — most recent reconciled figure", ("#v2c", "Reconciliation · View 2c")))
    prog_total = sum(d["funding"].get("total_aud", 0) for d in map_data.values())
    prog_awarded = sum(d["funding"].get("awarded_aud", 0) for d in map_data.values())
    prog_countries = sum(1 for d in map_data.values() if d["funding"].get("total_aud"))
    A(kpi("Government funding committed", fmt_aud(prog_total),
          f"whole-of-life totals across {prog_countries} countries, not annual",
          ("#map", "Funding programmes · map")))
    A(kpi("Of that, awarded so far", fmt_aud(prog_awarded),
          "only four programmes publish a drawdown figure", ("#map", "Funding programmes · map")))
    A(kpi("New money reported (window)", fmt_aud(total_committed),
          "status-weighted; this news window only", ("#v1", "By region · View 1")))
    A(kpi("Face value (window)", fmt_aud(total_announced_face),
          "same window, undiscounted", ("#v-all", "All developments · View 10")))
    A(kpi("Money withdrawn", fmt_aud(cancelled_val),
          "cancelled projects and surrendered funding", ("#at-risk", "At-risk detail table")))
    A(kpi("Capture capacity — firm", f"{firm_cap:.1f} Mtpa",
          "million tonnes a year, already operating or committed", ("#v8", "Capacity · View 8")))
    A(kpi("Capture capacity — planned", f"{pipeline_cap:.1f} Mtpa",
          "announced or funded, not yet committed", ("#v8", "Capacity · View 8")))
    A(kpi("Tracked developments", str(n_items),
          "news events in this window, not a project count", ("#v-all", "All developments · View 10")))
    A(kpi("High relevance to CO2CRC", str(len(high_rel)),
          "flagged for strategic attention", ("#v9", "Signal feed · View 9")))
    A('</div>')

    # World map — hero section, before the numbered views. Deliberately broader
    # than View 1 (which is news-corpus geography only): the map layers CO2CRC's
    # own tracking together with the GCCSI and Imperial datasets, so the pills are
    # grouped by WHO produced each number rather than by what it measures.
    A('<h2 id="map">Where CCS is happening worldwide</h2>')
    A('<p class="sub">Every country is shaded by whichever measure you pick below. The measures come from '
      'three different organisations and are deliberately kept apart — the buttons are grouped by source, '
      'and the caption under the map always restates which dataset you are looking at. '
      'Hover or tap any country for its full record; the dots mark individual CO\u2082 storage projects '
      'at their real locations.</p>')

    A('<div class="card mapcard">')
    A('<div class="pillgroups">')
    A('<div class="pillgroup"><div class="pillgrouphd">Government funding programmes</div><div class="pillbar">'
      '<button type="button" class="pill" data-mode="programmes">Total committed</button>'
      '<button type="button" class="pill" data-mode="drawdown">Awarded to date</button>'
      '</div></div>')
    A('<div class="pillgroup"><div class="pillgrouphd">GCCSI Global Status of CCS 2024</div><div class="pillbar">'
      '<button type="button" class="pill" data-mode="operating">Facilities operating</button>'
      '<button type="button" class="pill" data-mode="capacity">Capture capacity</button>'
      '<button type="button" class="pill" data-mode="policy">National CCS policy</button>'
      '</div></div>')
    A('<div class="pillgroup"><div class="pillgrouphd">Storage register (Imperial &amp; GCCSI)</div><div class="pillbar">'
      '<button type="button" class="pill" data-mode="storageclass">Type of storage</button>'
      '<button type="button" class="pill" data-mode="stored">CO\u2082 stored to date</button>'
      '</div></div>')
    A('<div class="pillgroup"><div class="pillgrouphd">CO2CRC news tracking (this window)</div><div class="pillbar">'
      '<button type="button" class="pill" data-mode="developments">Tracked developments</button>'
      '<button type="button" class="pill" data-mode="publicnew">New public money</button>'
      '<button type="button" class="pill" data-mode="privatenew">New private money</button>'
      '</div></div>')
    A('</div>')

    A('<div class="maplayout">')
    svg, payload = country_contour_map(map_data)
    A(f'<div class="mapwrap">{svg}</div>')
    n_map_countries = len(map_data)
    n_store_projects = 0  # set below, after dedup
    # Deduplicate by project name for the same reason the region roll-up does:
    # a project shared by two countries is one physical site, one tonnage.
    _uniq_projects = {}
    for d in map_data.values():
        for pr in d["storage"].get("projects", []):
            _uniq_projects.setdefault(pr["name"], pr)
    world_measured = round(sum(p["measured_mt"] for p in _uniq_projects.values()
                               if isinstance(p.get("measured_mt"), (int, float))), 1)
    n_store_projects = len(_uniq_projects)
    world_default = (
        '<div class="cc-name">Worldwide</div>'
        '<div class="cc-region">All tracked countries</div>'
        '<div class="cc-sec"><div class="cc-hd">In this window</div>'
        f'<div class="cc-row"><span>Countries with activity</span><b>{n_map_countries}</b></div>'
        f'<div class="cc-row"><span>Tracked developments</span><b>{n_items}</b></div>'
        f'<div class="cc-row"><span>Money committed</span><b>{esc(fmt_aud(total_committed))}</b></div>'
        '</div>'
        '<div class="cc-sec"><div class="cc-hd">CO\u2082 storage register</div>'
        f'<div class="cc-row"><span>Named projects</span><b>{n_store_projects}</b></div>'
        f'<div class="cc-row"><span>Measured stored</span><b>{world_measured} Mt</b></div>'
        '</div>'
        '<div class="cc-hint">Hover or tap any country for its own record.</div>')
    A(f'<aside class="countrycard" id="ccs-country-card">{world_default}</aside>')
    A('</div>')
    A(f'<script type="application/json" id="ccs-map-data">{payload}</script>')

    A('<div class="maplegend"></div>')
    A('<p class="mapsource"></p>')

    # Continent roll-up — the "per region" question the country view can't answer.
    A('<table class="tbl regionroll"><thead><tr><th>Region</th>'
      '<th class="num">Countries</th><th class="num">Developments<br><span class="th-sub">this window</span></th>'
      '<th class="num">Government programmes<br><span class="th-sub">whole-of-life total</span></th>'
      '<th class="num">New money<br><span class="th-sub">reported this window</span></th>'
      '<th class="num">Storage projects</th>'
      '<th class="num">CO\u2082 stored<br><span class="th-sub">measured</span></th></tr></thead><tbody>')
    for grp in GROUP_ORDER:
        t = region_totals.get(grp, {})
        if not t.get("countries"):
            continue
        A(f'<tr><td class="rgn">{esc(grp)}</td>'
          f'<td class="num">{t["countries"]}</td>'
          f'<td class="num">{t["developments"]}</td>'
          f'<td class="num">{esc(fmt_aud(t["programme_aud"]))}</td>'
          f'<td class="num">{esc(fmt_aud(t["public_aud"] + t["private_aud"]))}</td>'
          f'<td class="num">{t["storage_projects"]}</td>'
          f'<td class="num">{t["measured_mt"] or "—"}{" Mt" if t["measured_mt"] else ""}</td></tr>')
    A('</tbody></table>')
    if eu_aggregate and eu_aggregate.get("developments"):
        A(f'<div class="eubadge"><b>European Union (bloc-level):</b> '
          f'{eu_aggregate["developments"]} tracked developments · '
          f'{fmt_aud(eu_aggregate.get("public_aud", 0))} new public money reported. '
          f'Counted separately because these are EU-wide actions (Innovation Fund awards, '
          f'EU directives) that the source never attributed to an individual member state — '
          f'splitting them across France, Germany and the rest would invent detail that does not exist.</div>')
    A('</div>')

    if UNREVIEWED:
        A(f'<p class="fnote warnnote"><b>{len(UNREVIEWED)} money figure(s) awaiting review.</b> '
          f'Every money figure on this dashboard is classified by who is paying, what it measures and '
          f'the period it covers, so that whole-economy totals, legal claims and duplicate reports stay '
          f'out of funding numbers. Figures added since the last review are counted in full until '
          f'someone classifies them, so the funding totals above may be overstated. '
          f'Pending: {esc(", ".join(r.get("id","?") for r in UNREVIEWED[:12]))}'
          f'{" …" if len(UNREVIEWED) > 12 else ""}. '
          f'Classify them in <code>dashboard/data/funding-enrichment.json</code>.</p>')
    A('<p class="fnote"><b>Two different funding questions.</b> <i>Government funding programmes</i> is a '
      'stock: what a government has committed in total, whenever it was announced, over the whole life of '
      'the programme. The UK\u2019s \u00a321.7bn runs for 25 years, so it is roughly \u00a3870m a year on average \u2014 '
      'never read a programme total as an annual budget. <i>New money reported</i> is a flow: what turned up '
      'in the news during this window alone. A programme announced inside the window appears in both, which '
      'is correct \u2014 they are answering different questions, not double-counting. Programmes announced '
      'before the window appear only in the first, which is exactly why the second must never be read as a '
      'country\u2019s funding position.</p>')
    A('<p class="fnote"><b>How to read this map.</b> Shading is relative to the countries shown, not an '
      'absolute world scale, so a dark country leads <i>this</i> dataset rather than hitting some threshold. '
      'Grey means no data for the selected measure, which is not the same as zero activity — GCCSI\u2019s '
      'regional chapters often describe a country\u2019s projects in prose without giving a country-level '
      'number, and those gaps are recorded in <code>known_gaps</code> in '
      '<code>reference-baseline-countries.json</code> rather than filled with estimates. '
      'Storage-project dots are placed at indicative coordinates (good to a few tens of kilometres, which '
      'is under one pixel at this scale) and cover the storage register only — not every CCS facility '
      'worldwide. Where a project has both a GCCSI-reported and an Imperial-measured tonnage, the country '
      'card shows both separately; they measure different things and are never added together '
      '(see View 2c for the full reconciliation).</p>')

    # Key terms — placed immediately after the map, which is where a reader first
    # meets "Mtpa", "dedicated storage" and the commitment stages.
    A('<h2 id="terms">Key terms used on this dashboard</h2>')
    A('<p class="sub">CCS reporting mixes several vocabularies that look interchangeable but are not. '
      'These are the distinctions that most often cause figures to be misread.</p>')
    A('<div class="card"><dl class="glossary">')
    TERMS = [
        ("CCS / CCUS",
         "Carbon capture and storage: separating CO\u2082 at an industrial site and injecting it into deep rock "
         "for permanent containment. The U in CCUS adds <i>utilisation</i> — using the CO\u2082 for something "
         "before or instead of storing it."),
        ("Tracked development",
         "One CCS news event picked up by CO2CRC's daily monitoring — a funding announcement, a permit, a "
         "final investment decision, a cancellation. <b>It is not a project.</b> A single project generates "
         "many developments over its life, and some developments concern no project at all."),
        ("Facility vs project",
         "GCCSI counts <i>facilities</i> — physical installations that capture or store CO\u2082. The storage "
         "register counts <i>storage projects</i>, a narrower set. The two totals differ legitimately and "
         "should never be added together."),
        ("Mtpa",
         "Millions of tonnes per year — the standard unit for how much CO\u2082 a plant can capture or a site "
         "can take annually. <span class=\'eg\'>For scale: 1 Mtpa is roughly the annual emissions of a "
         "small coal power unit.</span>"),
        ("Capture capacity vs CO\u2082 stored",
         "Capacity is the nameplate design rate — what a facility <i>could</i> handle. Stored is what actually "
         "went underground. Measured storage has consistently run 19–30% below reported capacity, so the two "
         "must never be used interchangeably."),
        ("Funding — what it means here",
         "Unless a figure is explicitly labelled private, <b>funding on this dashboard means public money</b>: "
         "a government, region, agency or public bank committing funds. Company capital, venture rounds and "
         "bank facilities are tracked too, but shown separately \u2014 a government pledging \u00a321bn and a "
         "developer raising $12m are not the same kind of event and are never added together."),
        ("Programme total vs annual spend",
         "A funding programme total covers its whole life. The UK\u2019s \u00a321.7bn runs <b>over 25 years</b>, so it "
         "is around \u00a3870m a year on average \u2014 and the profile is not even, with construction-heavy early "
         "years. Reading a multi-decade total as this year\u2019s budget overstates it by an order of magnitude, "
         "which is why every programme on this dashboard carries its period."),
        ("Committed vs awarded to date",
         "<b>Committed</b> is what a government has promised. <b>Awarded</b> is what has actually gone out the "
         "door. The gap is often large: of the United States\u2019 US$12.5bn infrastructure-law carbon pot, "
         "<b>about 18% had been awarded or was in negotiation</b> nearly three years after the law passed. "
         "Only four programmes here publish a drawdown figure at all \u2014 a blank means unpublished, not zero."),
        ("CCS-specific vs CCS-eligible",
         "Some pots exist for CCS (the UK clusters). Others are broader decarbonisation funds where CCS is "
         "merely one eligible use \u2014 Canada\u2019s Growth Fund, the EU Innovation Fund, Australia\u2019s subsurface "
         "mapping. Counting an eligible pot\u2019s full value as CCS money overstates it, so the two are labelled "
         "separately."),
        ("Announced → allocated → committed → spent",
         "The four stages money passes through. <b>Announced</b> is an intention; <b>allocated</b> is set aside "
         "in a budget; <b>committed</b> is contractually locked in; <b>spent</b> has actually been paid out. "
         "Treating an announcement as real money is the single most common error in CCS investment reporting."),
        ("Weighted vs face value",
         "Because those stages are not equivalent, headline totals here discount early-stage money: "
         "announcements count at 25%, allocations at 75%, firm commitments and spending at 100%. "
         "\u2018Face value\u2019 totals count every figure in full, with no discount."),
        ("Dedicated storage",
         "CO\u2082 injected into rock formations for the sole purpose of keeping it underground permanently. "
         "<span class=\'eg\'>Sleipner, Quest, Northern Lights.</span>"),
        ("Associated reinjection",
         "CO\u2082 separated during gas production and pumped straight back into the reservoir it came from. "
         "It stays underground, but the driver is gas processing, not climate. "
         "<span class=\'eg\'>Santos Basin pre-salt, Ras Laffan.</span>"),
        ("Enhanced oil recovery (EOR)",
         "CO\u2082 pumped into ageing oilfields to push out more oil. Most CO\u2082 injected worldwide to date has "
         "gone this way. It is genuine geological storage, but producing more oil is the commercial reason "
         "for it — which is why it is counted separately. <span class=\'eg\'>Weyburn-Midale, Shute Creek.</span>"),
        ("A$ and conversion",
         "All money is converted to Australian dollars at fixed reference rates so figures stay comparable "
         "between rebuilds. Every table also shows the original currency, because the conversion is a "
         "convenience, not the source figure."),
        ("Storage resource vs storage used",
         "A country's storage <i>resource</i> is the geological space thought to be available, often measured "
         "in gigatonnes. What has been <i>used</i> is a tiny fraction of it. Large resource figures describe "
         "potential, not achievement."),
        ("MMV / MRV",
         "Monitoring, measurement and verification (also called monitoring, reporting and verification) — "
         "confirming that injected CO₂ stays underground where it was put, over decades. This is CO2CRC's "
         "own core specialty via the Otway International Test Centre, so items tagged with it are flagged as "
         "directly relevant to CO2CRC's commercial offer."),
        ("DAC",
         "Direct air capture — pulling CO₂ straight out of the ambient atmosphere, rather than from a "
         "power plant or factory's flue gas. Far more expensive per tonne than capturing a concentrated "
         "industrial stream, but usable anywhere, independent of a nearby emission source."),
        ("BECCS",
         "Bioenergy with carbon capture and storage — burning biomass (wood, crop waste) for energy and "
         "capturing the resulting CO₂. Because the biomass absorbed that carbon while growing, a working "
         "BECCS plant can be net carbon-negative, not just low-emission."),
        ("NZIA",
         "The EU's Net Zero Industry Act — the regulation setting the bloc's CO₂ injection-capacity target "
         "(50 Mtpa by 2030) and deadlines for major emitters to secure storage access (Article 23)."),
        ("Class VI",
         "The US EPA well classification for a CO₂ injection well built for permanent geological storage — "
         "distinct from the Class II wells used for enhanced oil recovery. A Class VI permit is the regulatory "
         "gate a dedicated (non-EOR) US storage project must clear before it can inject."),
    ]
    for term, definition in TERMS:
        A(f'<div class="gterm"><dt>{term}</dt><dd>{definition}</dd></div>')
    A('</dl></div>')

    # View 1
    section("1 · Geography of commitment",
            "Where CCS money is being committed and where activity is concentrating, based on the news "
            "developments CO2CRC tracked in this window. Each figure is also shown in the currency it was "
            "originally announced in, before conversion to Australian dollars.",
            anchor="v1", sources=("co2crc",))

    def geo_table(rows, first_col):
        h = [f'<table class="tbl geo"><thead><tr><th>{esc(first_col)}</th>'
             '<th>Committed A$</th><th>Original-currency commitments (face)</th></tr></thead><tbody>']
        for name, val, nat in rows:
            h.append(f'<tr><td>{esc(name)}</td><td class="num">{esc(fmt_aud(val))}</td>'
                     f'<td class="nat">{esc(nat)}</td></tr>')
        h.append('</tbody></table>')
        return "".join(h)

    A('<div class="grid2">')
    A(f'<div class="card"><h3>Committed A$ by region</h3>{hbar_chart([(a,b) for a,b,_ in geo_rows] and geo_rows, unit="aud")}</div>')
    A(f'<div class="card"><h3>Developments by region (count)</h3>{hbar_chart(geo_cnt_rows)}</div>')
    A('</div>')
    A(f'<div class="card"><h3>By region — with original-currency reference</h3>{geo_table(region_tbl, "Region")}</div>')
    A(f'<div class="card"><h3>Top countries — committed A$ &amp; original currency</h3>{geo_table(country_tbl, "Country")}</div>')
    A('<p class="fnote">“Committed A$” is status-weighted (announced 0.25 / allocated 0.75 / committed·spent 1.0). '
      'The original-currency column is the <b>face value</b> of positive-status commitments (announced→spent) '
      'in each native currency, with its unweighted A$ equivalent in parentheses — your reference before conversion. '
      f'Rates fixed as of {esc(fx_asof)}; INR shown in crore.</p>')

    # How much of the window's money is actually real vs merely announced —
    # the status-weighting fnote above states the discount scheme; this table
    # is where a reader sees the actual split it produces.
    STATUS_ORDER = ["announced", "allocated", "committed", "spent"]
    STATUS_LABEL = {"announced": "Announced", "allocated": "Allocated",
                     "committed": "Committed", "spent": "Spent"}
    status_cnt = Counter()
    status_face = defaultdict(float)
    for r in fresh:
        st = r.get("commitment_status")
        if st in STATUS_ORDER:
            status_cnt[st] += 1
            status_face[st] += funding_flow(r)
    total_face_positive = sum(status_face.values())
    A('<div class="card"><h3>New money reported — by commitment status (face value, this window)</h3>')
    A('<table class="tbl"><thead><tr><th>Status</th><th>Weight applied</th><th class="num">Items</th>'
      '<th class="num">Face-value A$</th><th class="num">Share of face value</th></tr></thead><tbody>')
    for st in STATUS_ORDER:
        face = status_face.get(st, 0)
        share = f"{face / total_face_positive * 100:.0f}%" if total_face_positive else "—"
        A(f'<tr><td>{esc(STATUS_LABEL[st])}</td><td class="num">{STATUS_WEIGHT[st]:.0%}</td>'
          f'<td class="num">{status_cnt.get(st, 0)}</td><td class="num">{esc(fmt_aud(face))}</td>'
          f'<td class="num">{share}</td></tr>')
    A('</tbody></table>')
    announced_face = status_face.get("announced", 0)
    announced_share = f"{announced_face / total_face_positive * 100:.0f}%" if total_face_positive else "0%"
    A(f'<p class="fnote">Of the {esc(fmt_aud(total_face_positive))} in this window’s face-value money, '
      f'<b>{announced_share} is still only announced</b> (25% weight in the headline KPIs above, since an '
      f'announcement is an intention, not money that has moved). This is a snapshot of the <i>news window</i> '
      f'only — it says nothing about how much of the standing government funding programmes (map above) has '
      f'been awarded, which is tracked separately per programme.</p></div>')

    # View 2 — GCCSI external baseline
    if ref:
        g = ref.get("global", {})
        section("2 · The global baseline — GCCSI",
                "The standing global picture of real facilities, from the Global CCS Institute's annual survey. "
                "This is the starting point the rest of the dashboard builds on: the news views above add what has "
                "moved since the survey was compiled — new money, new projects, changes of status — that an annual "
                "snapshot cannot yet show. Read the news as additions to this picture; coverage in any one window "
                "is partial, so it extends the baseline rather than replacing it.",
                sources=("gccsi",))
        A('<div class="kpis">')
        A(kpi("Global pipeline (GSR 2025)", f"{g.get('pipeline_facilities','—')} facilities",
              f"{g.get('pipeline_capacity_mtpa','—')} Mtpa total capacity"))
        A(kpi("Operating now", f"{g.get('operating_facilities','—')} facilities",
              f"{g.get('operating_capacity_mtpa','—')} Mtpa"))
        A(kpi("In construction", f"{g.get('in_construction_facilities','—')} facilities",
              f"{g.get('in_construction_capacity_mtpa','—')} Mtpa"))
        A(kpi("Projected 2030 operating", f"~{g.get('projected_2030_operating_capacity_mtpa','—')} Mtpa",
              f">5× today; ~{g.get('planned_capacity_cagr_since_2017_pct','—')}% CAGR since 2017"))
        A('</div>')
        # Edition growth series
        eds = ref.get("editions", [])
        if eds:
            maxf = max(e["facilities"] for e in eds)
            fac_rows = [(e["edition"], e["facilities"]) for e in eds]
            cap_rows = [(e["edition"], e["capacity_mtpa"]) for e in eds]
            A('<div class="grid2">')
            A(f'<div class="card"><h3>Pipeline growth — facilities</h3>{hbar_chart(fac_rows)}</div>')
            A(f'<div class="card"><h3>Pipeline growth — capture capacity (Mtpa)</h3>{hbar_chart(cap_rows)}</div>')
            A('</div>')
        # Region-by-region: GCCSI baseline plus what the news added on top
        A('<div class="card"><h3>Regional baseline (GSR 2024) + what the news added (this window)</h3>')
        A('<table class="tbl"><thead><tr><th>Region</th><th>Operating</th><th>In constr.</th>'
          '<th>Pipeline</th><th>Notable target</th><th>Added this window</th></tr></thead><tbody>')
        for rg in ref.get("regions", []):
            cr = rg.get("corpus_region")
            cnt = region_cnt.get(cr, 0)
            val = region_val.get(cr, 0)
            corpus = (f"{cnt} development{'s' if cnt != 1 else ''} · {fmt_aud(val)}"
                      if cnt else "— none")
            fmtn = lambda x: "—" if x is None else str(x)
            A(f'<tr><td class="rgn">{esc(rg.get("region"))}</td>'
              f'<td class="num">{esc(fmtn(rg.get("operating")))}</td>'
              f'<td class="num">{esc(fmtn(rg.get("construction")))}</td>'
              f'<td class="num">{esc(fmtn(rg.get("pipeline")))}</td>'
              f'<td class="gccsi">{esc(rg.get("target") or "—")}</td>'
              f'<td class="corpus">{esc(corpus)}</td></tr>')
        A('</tbody></table>')
        A('<p class="fnote">Regional counts = number of commercial CCS facilities (GSR 2024, data as of '
          '24 Jul 2024, §4). GCCSI reports facility counts &amp; Mtpa targets by region, not a per-region '
          'operating-capacity table. Hover/see reference-baseline.json for per-region detail &amp; page cites.</p>')
        # US + Middle East call-out — what the news added on top of a large baseline (GSR 2024 edition-consistent)
        us_items = [r for r in fresh if "United States" in (r.get("countries") or [])]
        us_comm = sum(committed_aud(r) for r in us_items)
        us_canc = sum(r.get("amount_aud") or 0 for r in us_items if r.get("commitment_status") == "cancelled")
        A('<p class="fnote">⚑ <b>Reading the US &amp; Middle East rows:</b> both start from a large baseline — the US is '
          'the world’s largest operating fleet (19 of 27 Americas facilities, GSR 2024), and the Middle East &amp; Africa '
          f'has 3 operating + 6 in construction, with Saudi targeting 44 Mtpa by 2035 and ADNOC 10 Mtpa by 2030. '
          f'<b>What the news added this window for the US was net negative:</b> {fmt_aud(us_canc)} cancelled or '
          f'surrendered against {fmt_aud(us_comm)} of new committed capital, across {len(us_items)} developments. '
          'Nothing new for the Middle East &amp; Africa, which leaves that baseline standing as-is until the next signal.</p>')
        # sector projection
        sec_proj = ref.get("sector_projection_2030_mtpa") or {}
        if sec_proj:
            rows = sorted(([k, v] for k, v in sec_proj.items()), key=lambda x: -x[1])
            A(f'<div class="card"><h3>Where capture capacity is heading — GCCSI projected by sector (Mtpa, 2030+)</h3>'
              f'{hbar_chart(rows)}</div>')
        A(f'<p class="fnote">Sources: <a href="{esc(ref.get("url"))}" target="_blank" rel="noopener">GCCSI Global Status of CCS</a> — '
          f'global headline &amp; growth: {esc(ref.get("source_global"))}; regional: {esc(ref.get("source_regional"))}. '
          f'Retrieved {esc(ref.get("retrieved"))}. {esc(ref.get("caveat"))}</p>')

    # View 2c — Cumulative storage delivered: GCCSI (capacity) vs Imperial (actual), with a bridge
    if sref:
        gd = sref.get("series", {}).get("gccsi_dedicated", {})
        ia = sref.get("series", {}).get("imperial_all_storage", {})
        idd = sref.get("series", {}).get("imperial_dedicated_derived", {})
        asum = sref.get("assumptions", {})
        section("2c · CO₂ actually stored — reported figures vs measured tonnes",
                "Two authoritative sources that answer different questions. GCCSI counts dedicated storage "
                "projects and reports their stated volumes. Imperial College London independently measures how "
                "many tonnes actually went underground, across all storage types including enhanced oil "
                "recovery. The two are reconciled step by step below and never merged into a single number.",
                anchor="v2c", sources=("gccsi", "imperial"))
        A('<div class="kpis">')
        A(kpi("GCCSI dedicated (non-EOR)", f"{gd.get('cumulative_qualifier','—')} Mt",
              f"{gd.get('projects_operational','—')} projects · capacity basis · {gd.get('as_of','')}"))
        A(kpi("Imperial — all storage", f"{ia.get('cumulative_mt_to_2024','—')} Mt",
              "incl. EOR · measured actual · to 2024"))
        A(kpi("Imperial — dedicated only", f"~{idd.get('cumulative_mt_approx','—')} Mt",
              f"measured actual · to {idd.get('as_of','')}"))
        df = asum.get("delivery_factor_range", [])
        A(kpi("Capacity→actual factor", f"{df[0]}–{df[1]}" if len(df) == 2 else "—",
              "reported capacity overstates actual (Imperial)"))
        A('</div>')

        # Annual storage rate by class — nameplate capacity vs measured-actual
        # (lifetime average). No source publishes a per-class ACTUAL annual
        # rate directly, so the measured column is derived: each project's
        # measured_actual_cumulative_mt ÷ (measured_asof − start_year), summed
        # per class, over only the projects with both data points. This is a
        # lifetime average, not necessarily this year's rate — labelled as such.
        def _class_rates(cls):
            rows = [p for p in sref.get("projects", []) if p.get("class") == cls]
            cap_vals = [p["capacity_mtpa"] for p in rows if isinstance(p.get("capacity_mtpa"), (int, float))]
            rate_vals = []
            for p in rows:
                m, sy, asof = (p.get("measured_actual_cumulative_mt"), p.get("start_year"),
                               p.get("measured_asof"))
                if (isinstance(m, (int, float)) and isinstance(sy, int)
                        and isinstance(asof, int) and asof > sy):
                    rate_vals.append(m / (asof - sy))
            return (sum(cap_vals), len(cap_vals), sum(rate_vals), len(rate_vals), len(rows))

        A('<div class="card"><h3>Current annual storage rate — nameplate vs measured actual</h3>')
        A('<table class="tbl"><thead><tr><th>Class</th><th class="num">Nameplate capacity (Mtpa)</th>'
          '<th class="num">Measured actual — lifetime avg (Mtpa)</th></tr></thead><tbody>')
        for cls, label in (("dedicated", "Dedicated (non-EOR)"), ("eor", "EOR")):
            cap_sum, cap_n, rate_sum, rate_n, total_n = _class_rates(cls)
            A(f'<tr><td class="rgn">{esc(label)}</td>'
              f'<td class="num">{cap_sum:.1f} <span class="muted">({cap_n}/{total_n} projects)</span></td>'
              f'<td class="num">{rate_sum:.1f} <span class="muted">({rate_n}/{total_n} projects)</span></td></tr>')
        A('</tbody></table>')
        A('<p class="fnote">Nameplate capacity is each project’s stated design rate, summed by class — a '
          'ceiling, not what was actually injected. The measured-actual column is a <b>lifetime average</b> '
          '(each project’s measured cumulative tonnage ÷ years since it started), not a snapshot of the most '
          'recent year specifically — no source publishes a per-class annual actual rate directly, so this is '
          'derived from the same per-project data as the reconciliation bridge below. The project-coverage '
          'fraction shown is a floor, not the full population: projects missing a data point are excluded, '
          'not counted as zero.</p></div>')

        # Reconciliation bridge (waterfall as a table — steps mix +/- and qualitative growth)
        bw = sref.get("bridge_waterfall", {})
        steps = bw.get("steps", [])
        if steps:
            A('<div class="card"><h3>Reconciliation bridge — Imperial actual (2020) → GCCSI pipeline (2025)</h3>')
            A('<table class="tbl"><thead><tr><th>Step</th><th>Mt</th><th>Basis</th></tr></thead><tbody>')
            for s in steps:
                mt = s.get("mt")
                mt_s = s.get("mt_qualifier") or ("—" if mt is None else str(mt))
                A(f'<tr><td>{esc(s.get("label"))}</td><td class="num">{esc(mt_s)}</td>'
                  f'<td class="gccsi">{esc(s.get("basis") or "")}</td></tr>')
            A('</tbody></table>')
            A(f'<p class="fnote">{esc(bw.get("note", ""))}</p></div>')
        # Per-project bridge table, grouped by storage class
        projs = sref.get("projects", [])
        CLASS_LABEL = {"dedicated": "Dedicated (non-EOR)",
                       "associated": "Associated reinjection",
                       "eor": "EOR"}
        A('<div class="card"><h3>Project bridge — capacity vs measured-actual, by storage class</h3>')
        A('<table class="tbl"><thead><tr><th>Project</th><th>Country</th><th>Start</th>'
          '<th>Capacity Mtpa</th><th>Reported cum. Mt (as of)</th><th>Actual cum. Mt</th></tr></thead><tbody>')
        fmtn = lambda x: "—" if x is None else str(x)
        for cls in ("dedicated", "associated", "eor"):
            rows = [p for p in projs if p.get("class") == cls]
            if not rows:
                continue
            A(f'<tr><td colspan="6" style="background:#f4f6f8;font-weight:600">'
              f'{esc(CLASS_LABEL[cls])} — {len(rows)} project{"s" if len(rows) != 1 else ""}</td></tr>')
            for p in rows:
                rep = p.get("reported_cumulative_mt")
                asof = p.get("reported_asof")
                rep_s = "—" if rep is None else (f"{rep} (as of {asof})" if asof else str(rep))
                A(f'<tr><td class="rgn">{esc(p.get("name"))}</td>'
                  f'<td>{esc(p.get("country"))}</td>'
                  f'<td class="num">{esc(fmtn(p.get("start_year")))}</td>'
                  f'<td class="num">{esc(fmtn(p.get("capacity_mtpa")))}</td>'
                  f'<td class="num">{esc(rep_s)}</td>'
                  f'<td class="num">{esc(fmtn(p.get("measured_actual_cumulative_mt")))}</td></tr>')
        A('</tbody></table>')
        A('<p class="fnote">A project’s reported cumulative figure is a snapshot as of the year shown, not '
          'today — a more recent news mention elsewhere on this dashboard reporting a higher tonnage for the '
          'same project is showing real growth since that snapshot, not a contradiction.</p>')
        A(f'<p class="fnote">{esc(sref.get("caveat", ""))}</p></div>')

        # Staleness check — dedicated-class projects feed the headline "CO2
        # stored to date" KPIs and are actively injecting today, so their
        # reported figures are worth periodically re-verifying against the
        # operator's current public reporting. This is the mechanism that
        # would have caught Gorgon/Moomba's figures being a year stale before
        # a human happened to notice by hand (2026-07-28).
        build_year_s = str(build_dt)[:4]
        build_year = int(build_year_s) if build_year_s.isdigit() else None
        stale_projects = [
            (p["name"], p["reported_asof"]) for p in projs
            if p.get("class") == "dedicated" and isinstance(p.get("reported_asof"), int)
            and build_year is not None and build_year - p["reported_asof"] >= 1
        ]
        if stale_projects:
            A('<div class="card warn"><h3>Figures due for a refresh check</h3>')
            A('<p class="fnote">These dedicated-project reported figures are a year or more old — worth '
              'checking against the operator’s current public reporting before relying on them for a board '
              'decision:</p>')
            A('<ul>')
            for name, asof in sorted(stale_projects, key=lambda x: x[1]):
                A(f'<li>{esc(name)} — reported figure as of {asof}</li>')
            A('</ul></div>')
        # Sources + taxonomy + known gaps
        src = sref.get("sources", {})
        gccsi_url = src.get("gccsi_dedicated", {}).get("url", "")
        imp_url = src.get("imperial_register", {}).get("register_url", "")
        gaps = sref.get("known_gaps", [])
        tax_note = sref.get("taxonomy", {}).get("classes", {})
        A(f'<p class="fnote">Sources: '
          f'<a href="{esc(gccsi_url)}" target="_blank" rel="noopener">GCCSI — Safety &amp; Permanence of CO₂ Geological Storage (2025)</a>; '
          f'<a href="{esc(imp_url)}" target="_blank" rel="noopener">Imperial College — London Register of Subsurface CO₂ Storage</a> '
          f'(Zhang, Krevor &amp; Jackson 2022, <i>Env. Sci. Tech. Letters</i>). Retrieved {esc(sref.get("retrieved", ""))}. '
          f'<b>Taxonomy:</b> destination-based 3-way — dedicated (into a non-producing formation) / '
          f'associated (reinjection into a producing reservoir) / EOR. '
          f'The widely-cited “383 Mt since 1996” is Imperial’s <b>all-storage</b> actual total (EOR-dominated), '
          f'not a GCCSI or dedicated-only figure. '
          f'<b>Known gaps:</b> {esc("; ".join(gaps[:3]))}. See <code>storage-baseline.json</code> for the full record.</p>')

    # View 3
    section("3 · Where the money goes",
            "How the tracked commitments split across funding instruments (grants, tax credits, offtake "
            "contracts and so on) and across the stages of the CCS chain — capture, transport, storage and use.",
            sources=("co2crc",))
    A('<div class="grid2">')
    A(f'<div class="card"><h3>Committed A$ by instrument</h3>{hbar_chart([r for r in instr_rows if r[1]>0][:10], unit="aud")}</div>')
    A(f'<div class="card"><h3>Activity by instrument (count)</h3>{hbar_chart(instr_cnt_rows[:10])}</div>')
    A('</div>')
    A('<p class="fnote">The two charts above list different instrument types because they answer different '
      'questions: the left chart only ever shows instruments that carry a committed dollar figure, so types '
      'like policy or R&amp;D — real activity, but with no A$ attached in the source reporting — appear on the '
      'right (by count) and not on the left (by A$). Neither chart is missing data.</p>')
    A(f'<div class="card"><h3>Developments by value-chain segment (count)</h3>{hbar_chart(vc_rows)}</div>')

    # View 4
    section("4 · Actors",
            "Which organisations appear most often, and whether the oil and gas majors and national oil "
            "companies are advancing CCS projects or pulling back from them.",
            sources=("co2crc",))
    A(f'<div class="card"><h3>Most-mentioned organisations</h3>{hbar_chart(org_rows)}</div>')
    A('<div class="grid2">')
    A('<div class="card ok"><h3>O&G majors / NOCs — advancing</h3>')
    item_list(og_advancing, limit=8)
    A('</div>')
    A('<div class="card warn"><h3>O&G majors / NOCs — retreating / at risk</h3>')
    item_list(og_retreating, limit=8)
    A('</div>')
    A('</div>')
    # Capital withdrawn / at-risk detail — substantiates the headline KPI (source table)
    cancelled_recs = sorted([r for r in fresh if r.get("commitment_status") == "cancelled"],
                            key=lambda r: -(r.get("amount_aud") or 0))
    A('<div class="card" id="at-risk"><h3>Capital withdrawn / at risk — all cancellations &amp; surrenders</h3>')
    if cancelled_recs:
        A('<table class="tbl"><thead><tr><th>Date</th><th>Development</th><th>Region</th>'
          '<th>Instrument</th><th class="num">A$</th></tr></thead><tbody>')
        for r in cancelled_recs:
            url = r.get("url") or ""
            head = esc(r.get("headline", ""))
            head = f'<a href="{esc(url)}" target="_blank" rel="noopener">{head}</a>' if url else head
            amt = fmt_aud(r.get("amount_aud")) if r.get("amount_aud") else "—"
            reg = esc(" · ".join(filter(None, [r.get("region"), ", ".join(r.get("countries") or [])])) or "—")
            A(f'<tr><td class="muted">{esc(r.get("briefing_date"))}</td><td>{head}</td>'
              f'<td>{reg}</td><td>{esc(r.get("instrument_type"))}</td>'
              f'<td class="num">{esc(amt)}</td></tr>')
        A('</tbody></table>')
        A(f'<p class="fnote">All {len(cancelled_recs)} items with commitment status = cancelled. These are '
          'excluded from the committed &amp; face-value totals and summed here as a negative signal — the '
          f'source of the “{fmt_aud(cancelled_val)}” headline stat.</p>')
    else:
        A('<p class="muted">No cancellations or surrenders in the current corpus.</p>')
    A('</div>')

    # View 5
    section("5 · Deployment-mandate tracker",
            "Targets and deadlines with a stated year attached — legislated mandates, national goals and "
            "corporate commitments picked up from policy developments in the tracked news.",
            sources=("co2crc",))
    if mandates:
        A('<table class="tbl"><thead><tr><th>Target year</th><th>Jurisdiction</th>'
          '<th>Mandate / deadline</th><th>Instrument</th><th>Seen</th></tr></thead><tbody>')
        for r in mandates:
            cc = ", ".join(r.get("countries") or []) or r.get("region", "")
            A(f'<tr><td class="ty">{esc(r.get("target_year"))}</td><td>{esc(cc)}</td>'
              f'<td>{esc(r.get("headline"))}</td><td>{esc(r.get("instrument_type"))}</td>'
              f'<td class="muted">{esc(r.get("briefing_date"))}</td></tr>')
        A('</tbody></table>')
    else:
        A('<p class="muted">No dated deployment mandates in the current corpus.</p>')

    # View 6
    section("6 · Australia benchmark",
            "How Australia's tracked activity compares with peer jurisdictions, plus the Asia-Pacific "
            "neighbours who are simultaneously competitors for investment and potential customers for "
            "Australian storage.",
            sources=("co2crc",))
    A(f'<div class="card"><h3>Peer jurisdictions — developments (count)</h3>{hbar_chart(peer_rows)}</div>')
    peer_h = ['<div class="card"><h3>Peer jurisdictions — committed A$ &amp; original currency</h3>'
              '<table class="tbl geo"><thead><tr><th>Jurisdiction</th><th>Committed A$</th>'
              '<th>Items</th><th>Original-currency commitments (face)</th></tr></thead><tbody>']
    for c, val, cnt, nat in peer_tbl:
        peer_h.append(f'<tr><td>{esc(c)}</td><td class="num">{esc(fmt_aud(val))}</td>'
                      f'<td class="num">{cnt}</td><td class="nat">{esc(nat)}</td></tr>')
    peer_h.append('</tbody></table></div>')
    A("".join(peer_h))
    A('<div class="card"><h3>Australia — tracked developments</h3>')
    item_list(au_items, limit=8, show_why=True)
    A('</div>')
    A('<div class="card"><h3>APAC cross-border watch (neighbours as competitors & storage customers)</h3>')
    item_list(apac_watch, limit=8, show_why=True)
    A('</div>')

    # View 7
    section("7 · Momentum & social licence",
            "Whether news activity is speeding up or slowing down, how committed money is trending in the "
            "leading regions, and how the press is framing CCS — the early indicator of public acceptance.",
            sources=("co2crc",))
    A('<div class="grid2">')
    A(f'<div class="card"><h3>Newsflow momentum (items / ISO week)</h3>{sparkline_multi(momentum_series)}</div>')
    A(f'<div class="card"><h3>Committed A$ / week — top regions</h3>{sparkline_multi(money_series, unit="aud")}</div>')
    A('</div>')
    A('<p class="fnote">Both trend lines exclude periodic external reports (e.g. a GCCSI quarterly update). '
      'Those land as one batch under a single ingestion-date stamp rather than real day-by-day news, so counting '
      'them here would show a false spike in whatever week the report happened to be processed — not a real '
      'change in CCS newsflow. They are included in every other view on this dashboard.</p>')
    sent_rows = [(s.title(), sent_cnt[s]) for s in ("positive", "neutral", "negative") if sent_cnt.get(s)]
    A('<div class="grid2">')
    A(f'<div class="card"><h3>Media sentiment mix</h3>{hbar_chart(sent_rows) if sent_rows else "<p class=muted>No sentiment-tagged items.</p>"}'
      f'{"<p class=fnote>Based on " + str(len(media)) + " sentiment-tagged items out of " + str(len(fresh)) + " tracked developments — a media-monitoring subsample, not a verdict on all CCS coverage.</p>" if media else ""}</div>')
    A('<div class="card"><h3>Recent social-licence signals</h3>')
    item_list([r for r in media if r.get("sentiment") == "negative"], limit=6)
    A('</div>')
    A('</div>')

    # View 8 — capacity
    section("8 · Capture capacity committed",
            "For CCS, tonnes matter as much as dollars. Capacity is measured in Mtpa — millions of tonnes of "
            "CO₂ per year. \u2018Firm\u2019 means already operating or formally committed; \u2018planned\u2019 means announced "
            "or funded but not yet committed. Figures are as stated in the source reports; cancelled projects "
            "are excluded.",
            anchor="v8", sources=("co2crc",))
    A('<div class="grid2">')
    A(f'<div class="card"><h3>Capacity by region (Mtpa)</h3>{hbar_chart(cap_reg_rows)}</div>')
    A(f'<div class="card"><h3>Capacity by value chain (Mtpa)</h3>{hbar_chart(cap_vc_rows)}</div>')
    A('</div>')

    # View 9 — segmented signal feed
    section("9 · CO2CRC / CO2Tech signal feed",
            f"The developments most relevant to CO2CRC, sorted into themes and annotated with why each one "
            f"matters. Themes are assigned by a transparent rule based on each development's type, sector and "
            f"value-chain segment — not by editorial judgement. Highest priority first. Covers both high "
            f"({len(high_rel)}) and medium relevance ({len(feed_pool) - len(high_rel)}) items — {len(feed_pool)} "
            f"in total, which is why this runs larger than the ‘High relevance’ KPI above, which counts "
            f"high-relevance only.",
            anchor="v9", sources=("co2crc",))
    for b in SIGNAL_ORDER:
        recs = buckets.get(b)
        if not recs:
            continue
        A(f'<div class="card"><h3>{esc(b)} <span class="cnt">{len(recs)}</span></h3>')
        item_list(recs, limit=8, show_why=True)
        A('</div>')

    # View 10 — full corpus table (substantiates the "tracked developments" & face-value headline stats)
    section("10 · All tracked developments",
            f"All {n_items} developments behind every figure above — each with its source link, region, "
            "funding instrument, commitment stage and dollar value where one was stated. This is the "
            "evidence base for the whole dashboard; cancelled entries are listed separately in the "
            "withdrawn-money table in View 4.",
            anchor="v-all", sources=("co2crc",))
    A('<div class="card"><table class="tbl"><thead><tr><th>Date</th><th>Development</th>'
      '<th>Region</th><th>Instrument</th><th>Status</th><th class="num">A$</th></tr></thead><tbody>')
    for r in sorted(fresh, key=lambda r: (r.get("briefing_date", ""), r.get("id", ""))):
        url = r.get("url") or ""
        head = esc(r.get("headline", ""))
        head = f'<a href="{esc(url)}" target="_blank" rel="noopener">{head}</a>' if url else head
        amt = fmt_aud(r.get("amount_aud")) if r.get("amount_aud") else "—"
        reg = esc(" · ".join(filter(None, [r.get("region"), ", ".join(r.get("countries") or [])])) or "—")
        st = r.get("commitment_status", "") or ""
        A(f'<tr><td class="muted">{esc(r.get("briefing_date"))}</td><td>{head}</td>'
          f'<td>{reg}</td><td>{esc(r.get("instrument_type"))}</td>'
          f'<td>{esc(st)}</td><td class="num">{esc(amt)}</td></tr>')
    A('</tbody></table></div>')

    # footer
    A('<footer>')
    miss = sorted({r.get("_fx_missing") for r in fresh if r.get("_fx_missing")})
    if miss:
        A(f'<p class="muted">⚠ Currencies without an FX rate (excluded from A$ totals): {esc(", ".join(miss))}. '
          'Add them to dashboard/data/fx_rates.json.</p>')
    A('<p class="muted">Sources: automated CCS daily briefing corpus. '
      'Extraction spec: dashboard/data/EXTRACTION_SPEC.md · FX: dashboard/data/fx_rates.json · '
      'Rebuilt weekly (Saturday) from the accumulating briefing archive.</p>')
    A('</footer>')
    # Floating section navigation: to-top, previous section, next section.
    A('<nav class="floatnav" aria-label="Section navigation">'
      '<button type="button" data-nav="top" title="Back to top" aria-label="Back to top">⤒</button>'
      '<button type="button" data-nav="prev" title="Previous section" aria-label="Previous section">↑</button>'
      '<button type="button" data-nav="next" title="Next section" aria-label="Next section">↓</button>'
      '<button type="button" data-nav="bottom" title="Go to bottom" aria-label="Go to bottom">⤓</button>'
      '</nav>')
    A("""<script>
(function(){
  var heads = [].slice.call(document.querySelectorAll('.wrap h2'));
  var nav = document.querySelector('.floatnav');
  if(!nav || !heads.length) return;
  var topBtn = nav.querySelector('[data-nav="top"]');
  var prevBtn = nav.querySelector('[data-nav="prev"]');
  var nextBtn = nav.querySelector('[data-nav="next"]');
  var bottomBtn = nav.querySelector('[data-nav="bottom"]');
  var PAD = 12, TOL = 4;
  function goto(y){ window.scrollTo({top: Math.max(0, y), behavior: 'smooth'}); }
  function tops(){ return heads.map(function(h){ return h.getBoundingClientRect().top + window.pageYOffset - PAD; }); }
  function refresh(){
    var cur = window.pageYOffset, ys = tops();
    var atTop = cur <= (ys[0] || 0) - TOL;
    var atEnd = cur >= (document.documentElement.scrollHeight - window.innerHeight - 2);
    topBtn.disabled = atTop;
    prevBtn.disabled = atTop;
    nextBtn.disabled = atEnd && cur > ys[ys.length-1] - TOL;
    bottomBtn.disabled = atEnd;
  }
  nav.addEventListener('click', function(e){
    var b = e.target.closest('button'); if(!b) return;
    var kind = b.getAttribute('data-nav'), cur = window.pageYOffset, ys = tops(), i;
    if(kind === 'top'){ goto(0); return; }
    if(kind === 'bottom'){ goto(document.documentElement.scrollHeight); return; }
    if(kind === 'next'){
      for(i=0;i<ys.length;i++){ if(ys[i] > cur + TOL){ goto(ys[i]); return; } }
      goto(document.documentElement.scrollHeight); return;
    }
    for(i=ys.length-1;i>=0;i--){ if(ys[i] < cur - TOL){ goto(ys[i]); return; } }
    goto(0);
  });
  window.addEventListener('scroll', refresh, {passive:true});
  window.addEventListener('resize', refresh, {passive:true});
  refresh();
})();
</script>""")
    # World-map controller: recolours the single embedded SVG and fills the
    # country card, all client-side off one inline JSON island. No fetch, no CDN.
    A("""<script>
(function(){
  var map = document.getElementById('ccs-map');
  var host = document.querySelector('.pillgroups');
  var dataEl = document.getElementById('ccs-map-data');
  if(!map || !host || !dataEl) return;
  var DATA = JSON.parse(dataEl.textContent).countries;
  var shapes = [].slice.call(map.querySelectorAll('[data-country]'));
  var card = document.getElementById('ccs-country-card');
  var SCALE = ['#e3ebee','#c2d8e0','#93b9c8','#5793a8','#1f6f8b'];

  var CLS = {
    dedicated:   {color:'#1f6f8b', label:'Dedicated storage',
                  def:'CO₂ injected into rock formations for the sole purpose of keeping it underground permanently.'},
    associated:  {color:'#e8a87c', label:'Associated reinjection',
                  def:'CO₂ separated during gas production and pumped back into the reservoir it came from.'},
    eor:         {color:'#5b8c5a', label:'Enhanced oil recovery',
                  def:'CO₂ pumped into ageing oilfields to push out more oil. The CO₂ stays underground, but more oil is the commercial driver.'}
  };
  var POL = {
    'published':      {color:'#1f6f8b', label:'Strategy published',
                       def:'A national carbon-management strategy or CCS roadmap is formally adopted.'},
    'in-preparation': {color:'#e8a87c', label:'Strategy in preparation',
                       def:'A strategy has been announced or drafted but not yet adopted.'},
    'none':           {color:'#c8d2d6', label:'No strategy',
                       def:'No national CCS strategy identified in the GCCSI review.'}
  };

  function get(d, path){
    var parts = path.split('.'), v = d;
    for(var i=0;i<parts.length;i++){ if(v==null) return null; v = v[parts[i]]; }
    return v;
  }

  var MODES = {
    developments: {kind:'quant', path:'news.developments', unit:'count', noun:'developments',
      title:'Tracked developments',
      source:'CO2CRC news tracking — count of CCS news developments (announcements, milestones, funding decisions) recorded in the daily briefing corpus. This counts news, not projects: one project can generate many developments.'},
    publicnew: {kind:'quant', path:'news.public_aud', unit:'aud',
      title:'New public money reported',
      source:'CO2CRC news tracking — government money allocated, committed or spent that was REPORTED IN THIS WINDOW only. It is not a country’s funding position: a programme announced before the window does not appear here. Whole-economy figures, legal claims and supplier sub-contracts are excluded.'},
    privatenew: {kind:'quant', path:'news.private_aud', unit:'aud',
      title:'New private money reported',
      source:'CO2CRC news tracking — company and investor money (corporate capex, venture rounds, bank facilities) reported in this window. Kept separate from public money because the two answer different questions.'},
    programmes: {kind:'quant', path:'funding.total_aud', unit:'aud',
      title:'Government funding programmes',
      source:'Standing government CCS funding programmes — the total each government has committed, including commitments made long before this news window. Totals span the whole life of each programme (the UK’s is 25 years), so they are NOT annual budgets. Hover a country for each programme’s size, period and drawdown.'},
    drawdown: {kind:'quant', path:'funding.awarded_aud', unit:'aud',
      title:'Awarded to date',
      source:'How much of the government funding above has actually been awarded, contracted or paid out, where a source publishes it. Only four programmes publish this. A country showing nothing has no published drawdown figure — which is not the same as having spent nothing.'},
    operating: {kind:'quant', path:'gccsi.operating', unit:'count', noun:'facilities',
      title:'Facilities operating',
      source:'GCCSI Global Status of CCS 2024 — commercial CCS facilities in operation. Only countries the report gives an explicit number for are shaded; grey means the report did not state a country-level count, not that the country has none.'},
    capacity: {kind:'quant', path:'gccsi.capacity_mtpa', unit:'mtpa',
      title:'Capture capacity',
      source:'GCCSI Global Status of CCS 2024 — CO₂ capture capacity in millions of tonnes per year (Mtpa), as stated in the report. Capacity is the nameplate design rate, not what was actually captured.'},
    policy: {kind:'cat-key', path:'gccsi.policy_status', map:POL,
      title:'National CCS policy',
      source:'GCCSI Global Status of CCS 2024 — status of each country’s national carbon-management strategy or CCS roadmap.'},
    storageclass: {kind:'cat-count', fields:['storage.dedicated','storage.associated','storage.eor'],
      keys:['dedicated','associated','eor'], map:CLS,
      title:'Type of storage',
      source:'Storage register (GCCSI project list × Imperial College London measurements) — each country is shaded by the storage type most of its projects use. Dots mark individual projects.'},
    stored: {kind:'quant', path:'storage.measured_total_mt', unit:'mt',
      title:'CO₂ stored to date',
      source:'Imperial College London, London Register of Subsurface CO₂ Storage — cumulative CO₂ actually measured as injected, in millions of tonnes. This is measured delivery, deliberately kept separate from the capacity and reported figures above.'}
  };

  function fmtAud(v){
    if(!v) return 'A$0';
    var a = Math.abs(v);
    if(a >= 1e9) return 'A$' + (v/1e9).toFixed(2) + 'bn';
    if(a >= 1e6) return 'A$' + (v/1e6).toFixed(1) + 'm';
    if(a >= 1e3) return 'A$' + Math.round(v/1e3) + 'k';
    return 'A$' + Math.round(v);
  }
  function fmtVal(v, mode){
    if(mode.unit === 'aud') return fmtAud(v);
    if(mode.unit === 'mtpa') return (Math.round(v*10)/10) + ' Mtpa';
    if(mode.unit === 'mt')   return (Math.round(v*10)/10) + ' Mt';
    return String(Math.round(v));
  }
  function bucket(v, max){
    if(!v || !max) return -1;
    return Math.min(SCALE.length-1, Math.max(0, Math.ceil((v/max)*(SCALE.length-1))-1));
  }
  function esc(s){
    return String(s==null?'':s).replace(/[&<>"]/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  function paint(modeKey){
    var mode = MODES[modeKey];
    if(!mode) return;
    var legend = [], legendTitle = '';

    if(mode.kind === 'quant'){
      var max = 0;
      shapes.forEach(function(el){
        var v = get(DATA[el.getAttribute('data-country')] || {}, mode.path);
        if(typeof v === 'number' && v > max) max = v;
      });
      shapes.forEach(function(el){
        if(el.classList.contains('pin')) return;
        var v = get(DATA[el.getAttribute('data-country')] || {}, mode.path);
        var b = (typeof v === 'number') ? bucket(v, max) : -1;
        el.style.fill = b < 0 ? '' : SCALE[b];
      });
      legendTitle = mode.title + ' per country' + (mode.unit==='aud' ? ' (Australian dollars)' : '');
      legend.push(['#dfe6e9', 'No data reported', 'The source gives no figure for this country — which is not the same as zero.']);
      for(var i=0;i<SCALE.length;i++){
        legend.push([SCALE[i], 'up to ' + fmtVal(max*((i+1)/SCALE.length), mode), '']);
      }
    } else if(mode.kind === 'cat-key'){
      shapes.forEach(function(el){
        if(el.classList.contains('pin')) return;
        var v = get(DATA[el.getAttribute('data-country')] || {}, mode.path);
        var m = v && mode.map[v];
        el.style.fill = m ? m.color : '';
      });
      legendTitle = 'National CCS strategy status';
      for(var k in mode.map){ legend.push([mode.map[k].color, mode.map[k].label, mode.map[k].def]); }
      legend.push(['#dfe6e9', 'Not assessed', 'This country was not covered by the source’s policy review.']);
    } else {
      shapes.forEach(function(el){
        if(el.classList.contains('pin')) return;
        var d = DATA[el.getAttribute('data-country')] || {};
        var counts = mode.fields.map(function(f){ return get(d, f) || 0; });
        var total = counts.reduce(function(a,b){ return a+b; }, 0);
        if(!total){ el.style.fill = ''; return; }
        var key = mode.keys[counts.indexOf(Math.max.apply(null, counts))];
        el.style.fill = mode.map[key].color;
      });
      legendTitle = 'Storage type used by most of the country’s projects';
      mode.keys.forEach(function(k){ legend.push([mode.map[k].color, mode.map[k].label, mode.map[k].def]); });
      legend.push(['#dfe6e9', 'No storage projects on the register', 'No project in this country appears in the storage register.']);
    }

    var leg = document.querySelector('.maplegend');
    if(leg){
      leg.innerHTML = (legendTitle ? '<span class="leg-title">'+esc(legendTitle)+'</span>' : '') +
        legend.map(function(row){
        return '<span><span class="sw" style="background:'+row[0]+'"></span><span><b>'+esc(row[1])+'</b>'+
               (row[2] ? ' — ' + esc(row[2]) : '') + '</span></span>';
      }).join('');
    }
    var src = document.querySelector('.mapsource');
    if(src) src.textContent = 'Showing: ' + mode.title + '. ' + mode.source;
  }

  function row(label, value){
    return '<div class="cc-row"><span>'+esc(label)+'</span><b>'+esc(value)+'</b></div>';
  }

  function showCountry(name, isPinned){
    var d = DATA[name];
    if(!d || !card) return;
    var h = isPinned
      ? '<div class="cc-pinbar"><span>Pinned — scroll for detail</span>'
        + '<button type="button" class="cc-unpin" aria-label="Unpin country">×</button></div>'
      : '';
    h += '<div class="cc-name">'+esc(d.name)+'</div><div class="cc-region">'+esc(d.region)+'</div>';
    var n = d.news || {}, g = d.gccsi || {}, s = d.storage || {};

    h += '<div class="cc-sec"><div class="cc-hd">CO2CRC news tracking</div>';
    if(n.developments){
      h += row('Tracked developments', n.developments);
      h += row('New public money', fmtAud(n.public_aud||0));
      h += row('New private money', fmtAud(n.private_aud||0));
    } else { h += '<div class="cc-none">No developments in this window.</div>'; }
    h += '</div>';

    var f = d.funding || {};
    var progs = f.programmes || [];
    if(progs.length){
      h += '<div class="cc-sec"><div class="cc-hd">Government funding programmes</div>';
      h += row('Total committed', fmtAud(f.total_aud||0));
      if(f.awarded_aud) h += row('Awarded to date', fmtAud(f.awarded_aud));
      progs.forEach(function(p){
        var meta = [];
        if(p.period_years) meta.push('over ' + p.period_years + ' years');
        if(p.annual_aud) meta.push('~' + fmtAud(p.annual_aud) + '/yr average');
        if(p.scope === 'ccs-eligible') meta.push('CCS is one eligible use, not the whole pot');
        var drawn = p.awarded_pct != null
          ? fmtAud(p.awarded_aud) + ' awarded so far (' + p.awarded_pct + '%)'
          : 'no drawdown figure published';
        // An uncapped per-tonne credit has no headline total; rendering it as
        // A$0 would read as "no support", the opposite of the truth.
        var size = p.amount == null
          ? 'Uncapped per-tonne credit — no fixed total'
          : fmtAud(p.amount_aud);
        h += '<div class="cc-proj"><div class="cc-proj-n">'+esc(p.programme)+'</div>'+
             '<div class="cc-proj-m">'+esc(size)+
             (meta.length ? ' · ' + esc(meta.join(' · ')) : '')+
             (p.amount == null ? '' : '<br>'+esc(drawn))+'</div></div>';
      });
      h += '</div>';
    }

    var hasG = (g.operating!=null)||(g.construction!=null)||(g.pipeline!=null)||(g.capacity_mtpa!=null)||g.policy_status||g.carbon_price;
    h += '<div class="cc-sec"><div class="cc-hd">GCCSI Global Status 2024</div>';
    if(hasG){
      if(g.operating!=null)      h += row('Facilities operating', g.operating);
      if(g.construction!=null)   h += row('Under construction', g.construction);
      if(g.pipeline!=null)       h += row('In development', g.pipeline);
      if(g.capacity_mtpa!=null)  h += row('Capture capacity', g.capacity_mtpa + ' Mtpa');
      if(g.policy_status && POL[g.policy_status]) h += row('National strategy', POL[g.policy_status].label);
      if(g.carbon_price)         h += row('Carbon price / incentive', g.carbon_price);
    } else { h += '<div class="cc-none">No country-level figure stated in the 2024 report.</div>'; }
    h += '</div>';

    var projs = s.projects || [];
    h += '<div class="cc-sec"><div class="cc-hd">CO₂ storage projects</div>';
    if(projs.length){
      if(s.measured_total_mt) h += row('Measured stored (Imperial)', s.measured_total_mt + ' Mt');
      if(s.reported_total_mt) h += row('Reported stored (GCCSI)', s.reported_total_mt + ' Mt');
      projs.forEach(function(p){
        var meta = CLS[p['class']] ? CLS[p['class']].label : p['class'];
        if(p.start_year) meta += ' · since ' + p.start_year;
        var t = [];
        if(p.measured_mt!=null) t.push('Imperial measured ' + p.measured_mt + ' Mt');
        if(p.reported_mt!=null) t.push('GCCSI reported ' + p.reported_mt + ' Mt');
        h += '<div class="cc-proj"><div class="cc-proj-n">'+esc(p.name)+'</div>'+
             '<div class="cc-proj-m">'+esc(meta)+(t.length ? '<br>'+esc(t.join(' · ')) : '')+'</div></div>';
      });
    } else { h += '<div class="cc-none">No project on the storage register.</div>'; }
    h += '</div>';
    if(!isPinned){
      h += '<div class="cc-hint">Click a country to keep this open and scroll it.</div>';
    }
    card.innerHTML = h;
    card.classList.toggle('pinned', !!isPinned);
    if(isPinned) card.scrollTop = 0;
  }

  var defaultCard = card ? card.innerHTML : '';
  var pinnedCountry = null;

  function unpin(){
    pinnedCountry = null;
    if(card){ card.innerHTML = defaultCard; card.classList.remove('pinned'); }
    map.querySelectorAll('.hot').forEach(function(e){ e.classList.remove('hot'); });
  }

  function pin(name){
    if(!DATA[name]) return;
    pinnedCountry = name;
    showCountry(name, true);
    map.querySelectorAll('.hot').forEach(function(e){ e.classList.remove('hot'); });
    map.querySelectorAll('[data-country]').forEach(function(e){
      if(e.getAttribute('data-country') === name) e.classList.add('hot');
    });
  }

  shapes.forEach(function(el){
    el.addEventListener('mouseenter', function(){
      // A pinned card stays put — otherwise it is impossible to reach its
      // scrollbar without the pointer leaving the country and wiping it.
      if(!pinnedCountry) showCountry(el.getAttribute('data-country'));
    });
    el.addEventListener('click', function(e){
      e.stopPropagation();
      var name = el.getAttribute('data-country');
      if(pinnedCountry === name){ unpin(); } else { pin(name); }
    });
  });

  map.addEventListener('mouseleave', function(){
    if(!pinnedCountry && card) card.innerHTML = defaultCard;
  });
  // Clicking empty ocean, or Escape, releases the pin.
  map.addEventListener('click', function(){ if(pinnedCountry) unpin(); });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && pinnedCountry) unpin();
  });
  if(card){
    card.addEventListener('click', function(e){
      if(e.target.closest('.cc-unpin')) unpin();
    });
  }

  host.addEventListener('click', function(e){
    var b = e.target.closest('.pill'); if(!b) return;
    [].slice.call(host.querySelectorAll('.pill')).forEach(function(p){ p.classList.remove('active'); });
    b.classList.add('active');
    paint(b.getAttribute('data-mode'));
  });

  var first = host.querySelector('.pill');
  if(first){ first.classList.add('active'); paint(first.getAttribute('data-mode')); }
})();
</script>""")
    A('</div>')
    return "".join(P)


STYLE = """<style>
:root{--ink:#1a2b34;--mut:#6b7c85;--line:#e2e8ea;--bg:#f6f8f9;--card:#fff;--accent:#1f6f8b}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
header{border-bottom:2px solid var(--accent);padding-bottom:16px;margin-bottom:8px}
.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-size:30px;margin:6px 0 8px}
h2{font-size:21px;margin:34px 0 2px;padding-top:14px;border-top:1px solid var(--line)}
h3{font-size:14px;margin:0 0 10px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.cnt{display:inline-block;background:var(--accent);color:#fff;font-size:11px;padding:0 7px;border-radius:9px;margin-left:6px;vertical-align:middle}
.meta{color:var(--mut);font-size:13px;margin:2px 0}
.disclaimer{color:var(--mut);font-size:12px;font-style:italic;margin:8px 0 0;max-width:70ch}
.sub{color:var(--mut);margin:2px 0 12px;font-size:14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin:18px 0 4px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.kv{font-size:22px;font-weight:700;color:var(--accent)}
.kl{font-size:12px;color:var(--mut);margin-top:2px}
.kss{font-size:11px;color:var(--mut);margin-top:3px;font-style:italic}
.ksrc{margin-top:8px;font-size:11px}
.ksrc a{color:var(--accent);text-decoration:none;font-weight:700}
.ksrc a:hover{text-decoration:underline}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:720px){.grid2{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0;overflow-x:auto}
.card.ok{border-left:3px solid #5b8c5a}
.card.warn{border-left:3px solid #c1666b}
.chart{display:block;margin:0 auto;max-width:820px}
.worldmap{max-width:none}
.bl{font-size:12px;fill:var(--ink)}
.vl{font-size:11px;fill:var(--mut)}
.ax{font-size:10px;fill:var(--mut)}
.grid{stroke:var(--line);stroke-width:1}
.legend{margin-top:8px;font-size:12px;color:var(--mut)}
.lg{margin-right:14px;white-space:nowrap}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}
.items{list-style:none;margin:0;padding:0}
.items li{padding:9px 0;border-bottom:1px solid var(--line)}
.items li:last-child{border-bottom:0}
.ih{font-size:14px;font-weight:600}
.ih a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
.ih a:hover{color:var(--accent)}
.im{font-size:12px;color:var(--mut);margin-top:2px}
.why{font-size:12.5px;color:#2b5a3a;margin-top:3px;font-style:italic}
.badge{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:10px;margin-left:5px;font-weight:700;vertical-align:middle}
.b-announced{background:#eef2f4;color:#5a6b74}
.b-allocated{background:#fdf0dd;color:#9a6b1e}
.b-committed{background:#dcefe0;color:#2f6b3c}
.b-spent{background:#cfe8d6;color:#245c31}
.b-cancelled{background:#fbe0e0;color:#a33}
.b-money{background:#e6eff3;color:#1f6f8b}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{text-align:left;padding:8px;border-bottom:2px solid var(--line);color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.tbl td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
.tbl .ty{font-weight:700;color:var(--accent)}
.tbl .rgn{font-weight:700;white-space:nowrap;vertical-align:top}
.tbl .gccsi{font-size:12.5px;line-height:1.45}
.tbl .corpus{font-size:12.5px;color:#8a5a2b;white-space:nowrap;vertical-align:top}
.tbl.geo .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:600}
.tbl.geo .nat{font-variant-numeric:tabular-nums;color:#2b5563;white-space:nowrap}
.fnote{color:var(--mut);font-size:11.5px;font-style:italic;margin:6px 0 0;max-width:80ch}
.muted{color:var(--mut);font-size:13px}
.srcline{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:8px 0 2px}
.srclabel{font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin-right:2px}
.srcchip{display:inline-block;font-size:11px;font-weight:600;padding:2px 9px;border-radius:999px;border:1px solid;cursor:help}
.src-co2crc{color:#1f6f8b;border-color:#b9d4dd;background:#eaf3f6}
.src-gccsi{color:#8a5a2b;border-color:#e6cdae;background:#fbf3e9}
.src-imperial{color:#4a6b45;border-color:#c4d8c0;background:#eef5ec}
.glossary{column-count:3;column-gap:30px;margin:0}
@media(max-width:1000px){.glossary{column-count:2}}
@media(max-width:720px){.glossary{column-count:1}}
.gterm{break-inside:avoid;page-break-inside:avoid;margin:0 0 13px}
.glossary dt{font-weight:700;font-size:12.5px;color:var(--ink);margin:0 0 2px}
.glossary dd{margin:0;font-size:12.5px;color:var(--mut);line-height:1.5}
.glossary dd .eg{color:#8a5a2b;font-style:italic}
.pillgroups{display:flex;flex-wrap:wrap;gap:18px;margin:0 0 16px}
.pillgroup{flex:1 1 210px;min-width:190px}
.pillgrouphd{font-size:10.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--mut);margin:0 0 6px;padding-bottom:4px;border-bottom:1px solid var(--line)}
.pillbar{display:flex;flex-wrap:wrap;gap:6px}
.pill{border:1px solid var(--line);background:var(--card);color:var(--mut);font-size:12.5px;font-weight:600;padding:6px 13px;border-radius:999px;cursor:pointer;transition:background .15s,color .15s,border-color .15s}
.pill:hover{border-color:var(--accent);color:var(--accent)}
.pill.active{background:var(--accent);border-color:var(--accent);color:#fff}
.mapcard{padding:20px}
.maplayout{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:16px;align-items:start}
@media(max-width:820px){.maplayout{grid-template-columns:1fr}}
.mapwrap{min-width:0}
.worldmap{display:block;width:100%;height:auto}
.ocean{fill:#e8eff2}
.cshape{stroke:#fff;stroke-width:.6;transition:fill .2s}
.cshape.no-data{fill:#d3dcdf}
.cshape.has-data{fill:#c2ced3;cursor:pointer}
.cshape.has-data:hover,.cshape.hot{stroke:var(--ink);stroke-width:1.1}
.microdot{fill:#fff;stroke:var(--ink);stroke-width:1.4}
.pin{stroke:#fff;stroke-width:1}
.marker{cursor:pointer}
.marker .hit{fill:transparent;stroke:none}
.marker:hover .pin,.marker:hover .microdot{stroke:var(--ink);stroke-width:1.8}
.leader{stroke:var(--mut);stroke-width:.7;opacity:.65}
.truept{fill:var(--mut);opacity:.75}
.pin-dedicated{fill:#1f6f8b}
.pin-associated{fill:#e8a87c}
.pin-eor{fill:#5b8c5a}
.countrycard{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:#fbfcfd;font-size:12.5px;min-height:170px;max-height:460px;overflow-y:auto}
.cc-empty{color:var(--mut);font-style:italic}
.cc-name{font-size:15px;font-weight:700;color:var(--ink);margin-bottom:1px}
.cc-region{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;margin-bottom:9px}
.cc-sec{margin-top:9px;padding-top:8px;border-top:1px solid var(--line)}
.cc-hd{font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin-bottom:4px}
.cc-row{display:flex;justify-content:space-between;gap:8px;padding:1px 0;color:var(--mut)}
.cc-row b{color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums;text-align:right}
.cc-proj{margin-top:5px;padding-left:9px;border-left:2px solid var(--line)}
.cc-proj-n{font-weight:600;color:var(--ink)}
.cc-proj-m{color:var(--mut);font-size:11.5px}
.cc-none{color:var(--mut);font-style:italic}
.cc-hint{margin-top:11px;padding-top:9px;border-top:1px solid var(--line);color:var(--mut);font-style:italic;font-size:11.5px}
.countrycard.pinned{border-color:var(--accent);box-shadow:0 0 0 2px rgba(31,111,139,.12)}
.cc-pinbar{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:-2px 0 8px;padding:4px 7px;border-radius:6px;background:#e9f2f5;color:var(--accent);font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase}
.cc-unpin{border:0;background:none;color:var(--accent);font-size:15px;line-height:1;cursor:pointer;padding:0 2px}
.cc-unpin:hover{color:var(--ink)}
.maplegend{display:flex;flex-direction:column;gap:6px;margin-top:14px;font-size:12.5px;color:var(--mut)}
.leg-title{font-size:10.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--ink);margin-bottom:2px}
.maplegend span{display:flex;align-items:flex-start}
.maplegend .sw{width:14px;height:14px;min-width:14px;border-radius:3px;display:inline-block;margin-right:7px;margin-top:2px}
.mapsource{color:var(--mut);font-size:11.5px;font-style:italic;margin:8px 0 0;max-width:80ch}
.warnnote{border-left:3px solid #d9a441;background:#fdf8ee;padding:8px 11px;border-radius:0 6px 6px 0;font-style:normal;color:#7a5a1e}
.regionroll{margin-top:16px}
.regionroll .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.th-sub{display:block;font-weight:400;text-transform:none;letter-spacing:0;font-size:10px;opacity:.8}
.eubadge{margin-top:12px;padding:9px 12px;border:1px dashed var(--line);border-radius:8px;font-size:11.5px;line-height:1.5;color:var(--mut);background:#f4f6f8}
footer{margin-top:36px;padding-top:14px;border-top:1px solid var(--line)}
.floatnav{position:fixed;right:18px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:8px;z-index:50}
.floatnav button{width:44px;height:44px;border-radius:50%;border:1px solid var(--line);background:var(--card);color:var(--accent);font-size:19px;line-height:1;cursor:pointer;box-shadow:0 2px 8px rgba(26,43,52,.14);transition:background .15s,color .15s,opacity .15s}
.floatnav button:hover:not(:disabled){background:var(--accent);color:#fff}
.floatnav button:disabled{opacity:.3;cursor:default}
@media print{.floatnav{display:none}}
@media (max-width:520px){.floatnav{right:10px}.floatnav button{width:40px;height:40px}}
</style>"""


def main():
    snapshot = None
    if "--snapshot" in sys.argv:
        i = sys.argv.index("--snapshot")
        if i + 1 < len(sys.argv):
            snapshot = sys.argv[i + 1]

    fx, fx_asof = load_fx()
    fresh, radar, stats = load_records(fx)
    ref = load_reference()
    sref = load_storage_baseline()
    ref_countries = load_reference_countries()
    plocs = load_project_locations()
    fprog = load_funding_programmes()
    build_dt = os.environ.get("BUILD_DATE") or date.today().isoformat()
    body = render(fresh, radar, stats, fx, fx_asof, build_dt, ref, sref,
                  ref_countries, plocs, fprog)
    # `body` is: <title>…<style>…</style> + <div class="wrap">…</div>. Split the head
    # material from the body content at the wrap div to assemble a valid document.
    page = ("<!doctype html><html lang=en><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            + body + "</body></html>").replace(
                '<div class="wrap">', '</head><body><div class="wrap">', 1)

    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Wrote {OUT_HTML}")
    print(f"  {stats['fresh']} fresh items · {stats['radar']} radar · "
          f"{stats['dropped_dupes']} dupes merged")

    if snapshot:
        os.makedirs(SNAP_DIR, exist_ok=True)
        snap_path = os.path.join(SNAP_DIR, f"{snapshot}.html")
        with open(snap_path, "w", encoding="utf-8") as f:
            f.write(page)
        print(f"Wrote snapshot {snap_path}")


if __name__ == "__main__":
    main()
