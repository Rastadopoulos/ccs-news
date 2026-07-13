#!/usr/bin/env python3
"""Build the CCS Intelligence Dashboard from extracted briefing facts.

Reads structured fact records produced by the extraction layer:
  * dashboard/data/facts-backfill.jsonl   — one-time frozen history (all briefings so far)
  * dashboard/data/raw/*.jsonl            — per-briefing raw extractions (backfill staging)
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
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime

# Reuse the repo's canonicalisation + dedup helpers (single source of truth).
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from _canon import canonical_url, fuzzy_key, jaccard  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "dashboard", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
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


def _iter_records():
    """Yield raw records from all sources."""
    backfill = os.path.join(DATA_DIR, "facts-backfill.jsonl")
    sources = []
    if os.path.exists(backfill):
        sources.append(backfill)
    sources += sorted(glob.glob(os.path.join(RAW_DIR, "*.jsonl")))
    for path in sources:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    print(f"  ! skipping bad JSONL line in {os.path.basename(path)}: {e}",
                          file=sys.stderr)
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

    fresh = [r for r in deduped if r.get("item_status") == "fresh"]
    radar = [r for r in deduped if r.get("item_status") == "radar"]
    stats = {"total_loaded": len(kept), "deduped": len(deduped),
             "dropped_dupes": dropped_dupes, "fresh": len(fresh), "radar": len(radar)}
    return fresh, radar, stats


def committed_aud(rec):
    """Status-weighted A$ figure for positive commitment totals (0 if none/cancelled)."""
    a = rec.get("amount_aud")
    if a is None:
        return 0.0
    w = STATUS_WEIGHT.get(rec.get("commitment_status", "na"), 0.0)
    return a * w


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


# ---------------------------------------------------------------------------
# Aggregations + view rendering
# ---------------------------------------------------------------------------

def iso_week(d):
    y, w, _ = datetime.strptime(d, "%Y-%m-%d").isocalendar()
    return f"{y}-W{w:02d}"


def render(fresh, radar, stats, fx, fx_asof, build_dt, ref=None, sref=None):
    dates = sorted({r["briefing_date"] for r in fresh})
    span = f"{dates[0]} → {dates[-1]}" if dates else "no data"

    # --- Headline KPIs ---
    total_committed = sum(committed_aud(r) for r in fresh)
    # Face value = positive commitments only (announced→spent). Excludes `na` (context/
    # market-aggregate/cost-saving figures) and `cancelled` so non-commitments never inflate it.
    POSITIVE = {"announced", "allocated", "committed", "spent"}
    total_announced_face = sum(r.get("amount_aud") or 0 for r in fresh
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
    geo_rows = [(reg, region_val[reg], f"{reg}: {fmt_aud(region_val[reg])} across {region_cnt[reg]} items")
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

    # --- View 2: where the money goes ---
    instr_val = Counter()
    instr_cnt = Counter()
    for r in fresh:
        it = r.get("instrument_type") or "other"
        instr_val[it] += committed_aud(r)
        instr_cnt[it] += 1
    instr_rows = sorted(
        [(it, instr_val[it], f"{it}: {fmt_aud(instr_val[it])} · {instr_cnt[it]} items")
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
    peer_rows = [(c, peer_cnt[c], f"{c}: {peer_cnt[c]} items · {fmt_aud(peer_val[c])}")
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

    # weekly item-count momentum
    wk_cnt = Counter(iso_week(r["briefing_date"]) for r in fresh)
    weeks = sorted(wk_cnt)
    momentum_series = [("Items / week", [(w.split("-W")[1], wk_cnt[w]) for w in weeks])]

    # weekly committed A$ by top-3 regions
    top3 = [reg for reg, _ in Counter(
        {reg: region_val[reg] for reg in region_val}).most_common(3)]
    wk_reg = defaultdict(lambda: defaultdict(float))
    for r in fresh:
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

    def section(title, subtitle="", anchor=""):
        idattr = f' id="{anchor}"' if anchor else ""
        A(f'<h2{idattr}>{esc(title)}</h2>')
        if subtitle:
            A(f'<p class="sub">{esc(subtitle)}</p>')

    def item_list(recs, limit=12, show_why=False):
        if not recs:
            A('<p class="muted">No items in the current corpus.</p>')
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
    A(STYLE)
    A('<div class="wrap">')
    A('<header>')
    A('<div class="eyebrow">CO2CRC · CO2Tech — Strategic Intelligence</div>')
    A('<h1>Global CCS Dashboard by CO2CRC</h1>')
    A(f'<p class="meta">Corpus: <b>{len(dates)}</b> briefings · {esc(span)} · '
      f'{stats["fresh"]} tracked items ({stats["dropped_dupes"]} duplicates merged) · '
      f'built {esc(build_dt)}</p>')
    A('<p class="disclaimer">Corpus figures are extracted from press-summary briefings (not audited '
      'financials); global storage baselines are drawn from the GCCSI <i>Global Status of CCS</i> report '
      'and the Imperial College <i>London Register of Subsurface CO₂ Storage</i>. '
      'Money normalised to A$ at fixed reference rates (as of '
      f'{esc(fx_asof)}); commitment status weights announced vs committed money. '
      'Every headline figure links to the table it comes from; every item links to its source. '
      'For board &amp; senior-stakeholder situational awareness.</p>')
    A('</header>')

    # KPI strip
    A('<div class="kpis">')
    A(kpi("Committed (status-weighted)", fmt_aud(total_committed),
          "announced discounted; cancelled excluded", ("#v1", "By region · View 1")))
    A(kpi("Face value of positive commitments", fmt_aud(total_announced_face),
          "all statuses, unweighted", ("#v-all", "All developments · View 10")))
    A(kpi("Capital withdrawn / at risk", fmt_aud(cancelled_val),
          "cancellations & surrenders", ("#at-risk", "At-risk detail table")))
    A(kpi("Firm capacity", f"{firm_cap:.1f} Mtpa", "committed / operating", ("#v8", "Capacity · View 8")))
    A(kpi("Pipeline capacity", f"{pipeline_cap:.1f} Mtpa", "announced / allocated", ("#v8", "Capacity · View 8")))
    A(kpi("Tracked developments", str(n_items), "", ("#v-all", "All developments · View 10")))
    A(kpi("High-relevance to CO2CRC", str(len(high_rel)), "", ("#v9", "Signal feed · View 9")))
    A('</div>')

    # View 1
    section("1 · Geography of commitment",
            "Where CCS capital is being committed (status-weighted A$) and where activity is concentrating. "
            "The original currency is shown behind every region and country as a true pre-conversion reference.",
            anchor="v1")

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
    A(f'<div class="card"><h3>Activity by region (item count)</h3>{hbar_chart(geo_cnt_rows)}</div>')
    A('</div>')
    A(f'<div class="card"><h3>By region — with original-currency reference</h3>{geo_table(region_tbl, "Region")}</div>')
    A(f'<div class="card"><h3>Top countries — committed A$ &amp; original currency</h3>{geo_table(country_tbl, "Country")}</div>')
    A('<p class="fnote">“Committed A$” is status-weighted (announced 0.25 / allocated 0.75 / committed·spent 1.0). '
      'The original-currency column is the <b>face value</b> of positive-status commitments (announced→spent) '
      'in each native currency, with its unweighted A$ equivalent in parentheses — your reference before conversion. '
      f'Rates fixed as of {esc(fx_asof)}; INR shown in crore.</p>')

    # View 2 — GCCSI external baseline
    if ref:
        g = ref.get("global", {})
        section("2 · Global reality check — GCCSI baseline",
                "External benchmark from the Global CCS Institute Global Status of CCS reports. The corpus "
                "tracks recent news flow (A$); this is the authoritative global project pipeline. Read the "
                "geography views above against it — a quiet news window is not real-world inactivity.")
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
        # Region-by-region: GCCSI facilities/targets vs what our corpus caught
        A('<div class="card"><h3>Regional facilities &amp; targets (GSR 2024) vs corpus coverage (this window)</h3>')
        A('<table class="tbl"><thead><tr><th>Region</th><th>Operating</th><th>In constr.</th>'
          '<th>Pipeline</th><th>Notable target</th><th>Our corpus</th></tr></thead><tbody>')
        for rg in ref.get("regions", []):
            cr = rg.get("corpus_region")
            cnt = region_cnt.get(cr, 0)
            val = region_val.get(cr, 0)
            corpus = (f"{cnt} item{'s' if cnt != 1 else ''} · {fmt_aud(val)}"
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
        # US + Middle East call-out (the two gaps that prompted this) — GSR 2024 edition-consistent
        us_items = [r for r in fresh if "United States" in (r.get("countries") or [])]
        us_comm = sum(committed_aud(r) for r in us_items)
        us_canc = sum(r.get("amount_aud") or 0 for r in us_items if r.get("commitment_status") == "cancelled")
        A('<p class="fnote">⚑ <b>Why the US &amp; Middle East look thin in the geography views:</b> the corpus caught '
          f'{len(us_items)} US items this window, but only {fmt_aud(us_comm)} of committed capital — its biggest US '
          f'dollar stories were <b>retreats</b> ({fmt_aud(us_canc)} cancelled/surrendered). GCCSI shows the US as the '
          'world’s largest operating fleet (19 of 27 Americas facilities, GSR 2024). The Middle East &amp; Africa had '
          'zero in-window items, yet GCCSI shows 3 operating + 6 in construction, Saudi targeting 44 Mtpa by 2035 and '
          'ADNOC 10 Mtpa by 2030. The gap is <b>news-flow timing &amp; source bias, not real-world absence</b>.</p>')
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
        section("2c · Cumulative storage delivered — pipeline vs actual tonnes",
                "Two authoritative sources measured on different bases: GCCSI counts dedicated (non-EOR) "
                "projects (capacity-leaning); Imperial's London Register measures actual tonnes injected "
                "(all storage types). Reconciled by the bridge below — never blended into one number.")
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
          '<th>Capacity Mtpa</th><th>Reported cum. Mt</th><th>Actual cum. Mt</th></tr></thead><tbody>')
        fmtn = lambda x: "—" if x is None else str(x)
        for cls in ("dedicated", "associated", "eor"):
            rows = [p for p in projs if p.get("class") == cls]
            if not rows:
                continue
            A(f'<tr><td colspan="6" style="background:#f4f6f8;font-weight:600">'
              f'{esc(CLASS_LABEL[cls])} — {len(rows)} project{"s" if len(rows) != 1 else ""}</td></tr>')
            for p in rows:
                A(f'<tr><td class="rgn">{esc(p.get("name"))}</td>'
                  f'<td>{esc(p.get("country"))}</td>'
                  f'<td class="num">{esc(fmtn(p.get("start_year")))}</td>'
                  f'<td class="num">{esc(fmtn(p.get("capacity_mtpa")))}</td>'
                  f'<td class="num">{esc(fmtn(p.get("reported_cumulative_mt")))}</td>'
                  f'<td class="num">{esc(fmtn(p.get("measured_actual_cumulative_mt")))}</td></tr>')
        A('</tbody></table>')
        A(f'<p class="fnote">{esc(sref.get("caveat", ""))}</p></div>')
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
            "Split of commitments across policy instruments and the CCS value chain.")
    A('<div class="grid2">')
    A(f'<div class="card"><h3>Committed A$ by instrument</h3>{hbar_chart([r for r in instr_rows if r[1]>0][:10], unit="aud")}</div>')
    A(f'<div class="card"><h3>Activity by instrument (count)</h3>{hbar_chart(instr_cnt_rows[:10])}</div>')
    A('</div>')
    A(f'<div class="card"><h3>Value-chain focus (item count)</h3>{hbar_chart(vc_rows)}</div>')

    # View 4
    section("4 · Actors",
            "Who is most active — and whether the oil & gas majors / NOCs are advancing or retreating.")
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
            "Legislated targets & deadlines requiring CCS deployment — surfaced from policy items.")
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
            "Australia's activity against peer jurisdictions, plus the APAC cross-border watch.")
    A(f'<div class="card"><h3>Peer jurisdictions — activity (item count)</h3>{hbar_chart(peer_rows)}</div>')
    peer_h = ['<div class="card"><h3>Peer jurisdictions — committed A$ &amp; original currency</h3>'
              '<table class="tbl geo"><thead><tr><th>Jurisdiction</th><th>Committed A$</th>'
              '<th>Items</th><th>Original-currency commitments (face)</th></tr></thead><tbody>']
    for c, val, cnt, nat in peer_tbl:
        peer_h.append(f'<tr><td>{esc(c)}</td><td class="num">{esc(fmt_aud(val))}</td>'
                      f'<td class="num">{cnt}</td><td class="nat">{esc(nat)}</td></tr>')
    peer_h.append('</tbody></table></div>')
    A("".join(peer_h))
    A('<div class="card"><h3>Australia — tracked items</h3>')
    item_list(au_items, limit=8, show_why=True)
    A('</div>')
    A('<div class="card"><h3>APAC cross-border watch (neighbours as competitors & storage customers)</h3>')
    item_list(apac_watch, limit=8, show_why=True)
    A('</div>')

    # View 7
    section("7 · Momentum & social licence",
            "Newsflow momentum, committed-A$ trend by leading region, and media sentiment.")
    A('<div class="grid2">')
    A(f'<div class="card"><h3>Newsflow momentum (items / ISO week)</h3>{sparkline_multi(momentum_series)}</div>')
    A(f'<div class="card"><h3>Committed A$ / week — top regions</h3>{sparkline_multi(money_series, unit="aud")}</div>')
    A('</div>')
    sent_rows = [(s.title(), sent_cnt[s]) for s in ("positive", "neutral", "negative") if sent_cnt.get(s)]
    A('<div class="grid2">')
    A(f'<div class="card"><h3>Media sentiment mix</h3>{hbar_chart(sent_rows) if sent_rows else "<p class=muted>No sentiment-tagged items.</p>"}</div>')
    A('<div class="card"><h3>Recent social-licence signals</h3>')
    item_list([r for r in media if r.get("sentiment") == "negative"], limit=6)
    A('</div>')
    A('</div>')

    # View 8 — capacity
    section("8 · Capacity committed (Mtpa)",
            "For CCS, tonnes matter as much as dollars. Firm = committed/operating; pipeline = "
            "announced/allocated. Capacity as stated in the source items; cancellations excluded.",
            anchor="v8")
    A('<div class="grid2">')
    A(f'<div class="card"><h3>Capacity by region (Mtpa)</h3>{hbar_chart(cap_reg_rows)}</div>')
    A(f'<div class="card"><h3>Capacity by value chain (Mtpa)</h3>{hbar_chart(cap_vc_rows)}</div>')
    A('</div>')

    # View 9 — segmented signal feed
    section("9 · CO2CRC / CO2Tech signal feed",
            "High & medium strategic-relevance items, grouped into actionable buckets (rule-based) "
            "with the 'why it matters' read. Priority order — start at the top.",
            anchor="v9")
    for b in SIGNAL_ORDER:
        recs = buckets.get(b)
        if not recs:
            continue
        A(f'<div class="card"><h3>{esc(b)} <span class="cnt">{len(recs)}</span></h3>')
        item_list(recs, limit=8, show_why=True)
        A('</div>')

    # View 10 — full corpus table (substantiates the "tracked developments" & face-value headline stats)
    section("10 · All tracked developments",
            f"The full {n_items}-item corpus behind the headline count — every tracked development with its "
            "source link, region, instrument, commitment status and A$ where stated. This is the evidence "
            "base for the views above; positive-status amounts here are what the face-value stat totals "
            "(cancelled items are broken out in the at-risk table).",
            anchor="v-all")
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
    A('</div>')
    return "".join(P)


STYLE = """<style>
:root{--ink:#1a2b34;--mut:#6b7c85;--line:#e2e8ea;--bg:#f6f8f9;--card:#fff;--accent:#1f6f8b}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:960px;margin:0 auto;padding:28px 20px 60px}
header{border-bottom:2px solid var(--accent);padding-bottom:16px;margin-bottom:8px}
.eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-size:30px;margin:6px 0 8px}
h2{font-size:21px;margin:34px 0 2px;padding-top:14px;border-top:1px solid var(--line)}
h3{font-size:14px;margin:0 0 10px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.cnt{display:inline-block;background:var(--accent);color:#fff;font-size:11px;padding:0 7px;border-radius:9px;margin-left:6px;vertical-align:middle}
.meta{color:var(--mut);font-size:13px;margin:2px 0}
.disclaimer{color:var(--mut);font-size:12px;font-style:italic;margin:8px 0 0;max-width:70ch}
.sub{color:var(--mut);margin:2px 0 12px;font-size:14px}
.kpis{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0 4px}
.kpi{flex:1 1 150px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
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
.chart{display:block;margin:0 auto}
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
.fnote{color:var(--mut);font-size:11.5px;font-style:italic;margin:6px 2px 0;max-width:80ch}
.muted{color:var(--mut);font-size:13px}
footer{margin-top:36px;padding-top:14px;border-top:1px solid var(--line)}
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
    build_dt = os.environ.get("BUILD_DATE") or date.today().isoformat()
    body = render(fresh, radar, stats, fx, fx_asof, build_dt, ref, sref)
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
