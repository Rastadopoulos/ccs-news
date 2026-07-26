#!/usr/bin/env python3
"""Round-trip the hand-curated dashboard data through Excel-friendly CSV.

Three datasets on this dashboard are maintained by hand rather than extracted:

  * funding-programmes.json   — standing government CCS funding pots
  * funding-enrichment.json   — per-record funding classification
  * project-locations.json    — map coordinates for storage projects

They are small, judgement-heavy, and they are the files most likely to need
editing when a new commitment is announced. Editing them as raw JSON is fiddly
and easy to break; editing them as a spreadsheet is not.

    python3 scripts/curation_io.py export      # JSON -> dashboard/data/curation/*.csv
    ... edit the CSVs in Excel ...
    python3 scripts/curation_io.py import      # CSV -> JSON, with validation
    python3 scripts/curation_io.py import --dry-run   # validate only, write nothing

WHAT THIS DELIBERATELY DOES NOT DO: it does not make the CSVs the source of
truth. The JSON stays canonical, stays in git, and keeps the parts a spreadsheet
cannot hold — the `_comment` provenance headers, the `definitions` blocks and the
`known_gaps` arrays. Import replaces ONLY the row data and leaves that prose
untouched, so a round-trip through Excel can never quietly delete a caveat.

Import refuses to write anything if any row fails validation, so a typo in a
country name or a currency code cannot reach the dashboard.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _countries import COUNTRY_ISO, NON_COUNTRY_TOKENS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "dashboard", "data")
CSV_DIR = os.path.join(DATA_DIR, "curation")

# Excel needs a BOM to read UTF-8 correctly, and this data is full of €, £, ø, ₹.
ENCODING = "utf-8-sig"

VALID_SCOPE = {"ccs-specific", "ccs-eligible"}
VALID_PROG_STATUS = {"announced", "committed", "operating"}
VALID_FUNDER = {"government", "private", "mixed", "none"}
VALID_BASIS = {"government-funding", "private-investment", "project-capex",
               "supplier-contract", "market-aggregate", "not-ccs-funding", "cancelled"}


# --------------------------------------------------------------------------- helpers

def _fx_currencies():
    with open(os.path.join(DATA_DIR, "fx_rates.json"), encoding="utf-8") as f:
        return set(json.load(f)["rates"])


def _load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _save(name, doc):
    path = os.path.join(DATA_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path


def _num(value, field, row_id, errors, keep_float=False):
    """Blank stays null — a missing figure is not zero, and this dashboard leans
    on that distinction throughout.

    Whole numbers come back as int, not float. Excel round-trips everything as a
    float, and letting that through rewrote every amount from 556100000 to
    556100000.0 — harmless arithmetically, but it churns the JSON and the
    dashboard's embedded data payload on every import.

    keep_float forces the opposite for quantities that are inherently decimal:
    a longitude of -103.0 must not collapse to -103, which reads like someone
    dropped the precision."""
    if value is None or str(value).strip() == "":
        return None
    try:
        n = float(str(value).replace(",", "").strip())
    except ValueError:
        errors.append(f"{row_id}: {field} is not a number: {value!r}")
        return None
    if keep_float:
        return n
    return int(n) if n == int(n) else n


def _write_csv(path, fieldnames, rows):
    with open(path, "w", encoding=ENCODING, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fieldnames})


def _read_csv(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding=ENCODING, newline="") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------- programmes

PROG_FIELDS = ["country", "programme", "funder", "amount", "currency",
               "period_start", "period_end", "period_years", "scope", "status",
               "announced", "awarded_to_date", "awarded_asof", "awarded_note",
               "source", "page", "corpus_id", "quote", "note"]


def export_programmes():
    doc = _load("funding-programmes.json")
    _write_csv(os.path.join(CSV_DIR, "funding-programmes.csv"),
               PROG_FIELDS, doc["programmes"])
    return len(doc["programmes"])


def import_programmes(errors, currencies):
    rows = _read_csv(os.path.join(CSV_DIR, "funding-programmes.csv"))
    if rows is None:
        return None
    out = []
    for i, r in enumerate(rows, start=2):          # +2: header row, 1-based
        rid = f"funding-programmes.csv row {i} ({r.get('programme') or '?'})"
        country = (r.get("country") or "").strip()
        if country not in COUNTRY_ISO and country not in NON_COUNTRY_TOKENS:
            errors.append(f"{rid}: unknown country {country!r} — add it to "
                          f"scripts/_countries.py or fix the spelling")
        cur = (r.get("currency") or "").strip()
        if cur and cur not in currencies:
            errors.append(f"{rid}: currency {cur!r} has no rate in fx_rates.json")
        if not (r.get("source") or "").strip():
            errors.append(f"{rid}: every programme needs a source")
        scope = (r.get("scope") or "").strip()
        if scope not in VALID_SCOPE:
            errors.append(f"{rid}: scope must be one of {sorted(VALID_SCOPE)}, got {scope!r}")
        status = (r.get("status") or "").strip()
        if status and status not in VALID_PROG_STATUS:
            errors.append(f"{rid}: status must be one of {sorted(VALID_PROG_STATUS)}, got {status!r}")

        amount = _num(r.get("amount"), "amount", rid, errors)
        awarded = _num(r.get("awarded_to_date"), "awarded_to_date", rid, errors)
        if amount is not None and awarded is not None and awarded > amount:
            errors.append(f"{rid}: awarded_to_date ({awarded:,.0f}) exceeds the "
                          f"programme total ({amount:,.0f})")
        years = _num(r.get("period_years"), "period_years", rid, errors)
        if amount is not None and years is None and (r.get("period_end") or "").strip():
            errors.append(f"{rid}: has a period_end but no period_years — the dashboard "
                          f"needs the year count to annualise the total")

        rec = {
            "country": country,
            "programme": (r.get("programme") or "").strip(),
            "funder": (r.get("funder") or "").strip(),
            "amount": amount,
            "currency": cur or None,
            "period_start": _num(r.get("period_start"), "period_start", rid, errors),
            "period_end": _num(r.get("period_end"), "period_end", rid, errors),
            "period_years": years,
            "scope": scope,
            "status": status,
            "awarded_to_date": awarded,
        }
        for opt in ("announced", "awarded_asof", "awarded_note", "source",
                    "corpus_id", "quote", "note"):
            v = (r.get(opt) or "").strip()
            if v:
                rec[opt] = v
        page = _num(r.get("page"), "page", rid, errors)
        if page is not None:
            rec["page"] = page
        out.append(rec)
    return out


# --------------------------------------------------------------------------- enrichment

ENR_FIELDS = ["record_id", "funder_type", "basis", "period_years", "period_note",
              "duplicate_of", "force_status", "govt_share_aud", "note"]


def export_enrichment():
    doc = _load("funding-enrichment.json")
    rows = []
    for rid, v in doc["records"].items():
        row = {"record_id": rid}
        row.update(v)
        rows.append(row)
    rows.sort(key=lambda r: r["record_id"])
    _write_csv(os.path.join(CSV_DIR, "funding-enrichment.csv"), ENR_FIELDS, rows)
    return len(rows)


def import_enrichment(errors):
    rows = _read_csv(os.path.join(CSV_DIR, "funding-enrichment.csv"))
    if rows is None:
        return None
    ids = {(r.get("record_id") or "").strip() for r in rows}
    out = {}
    for i, r in enumerate(rows, start=2):
        rid_key = (r.get("record_id") or "").strip()
        rid = f"funding-enrichment.csv row {i} ({rid_key or '?'})"
        if not rid_key:
            errors.append(f"{rid}: record_id is required")
            continue
        ft = (r.get("funder_type") or "").strip()
        if ft not in VALID_FUNDER:
            errors.append(f"{rid}: funder_type must be one of {sorted(VALID_FUNDER)}, got {ft!r}")
        basis = (r.get("basis") or "").strip()
        if basis not in VALID_BASIS:
            errors.append(f"{rid}: basis must be one of {sorted(VALID_BASIS)}, got {basis!r}")
        dup = (r.get("duplicate_of") or "").strip()
        if dup and dup not in ids:
            errors.append(f"{rid}: duplicate_of points at {dup!r}, which is not in this file")
        if dup == rid_key:
            errors.append(f"{rid}: duplicate_of points at itself")
        if not (r.get("note") or "").strip():
            errors.append(f"{rid}: note is required — it is the audit trail for this judgement")

        rec = {"funder_type": ft, "basis": basis,
               "period_years": _num(r.get("period_years"), "period_years", rid, errors)}
        for opt in ("period_note", "duplicate_of", "force_status", "note"):
            v = (r.get(opt) or "").strip()
            if v:
                rec[opt] = v
        share = _num(r.get("govt_share_aud"), "govt_share_aud", rid, errors)
        if share is not None:
            rec["govt_share_aud"] = share
        out[rid_key] = rec
    return out


# --------------------------------------------------------------------------- locations

LOC_FIELDS = ["project", "lat", "lon", "place"]


def export_locations():
    doc = _load("project-locations.json")
    rows = [{"project": k, **v} for k, v in doc["locations"].items()]
    _write_csv(os.path.join(CSV_DIR, "project-locations.csv"), LOC_FIELDS, rows)
    return len(rows)


def import_locations(errors):
    rows = _read_csv(os.path.join(CSV_DIR, "project-locations.csv"))
    if rows is None:
        return None
    try:
        sb = _load("storage-baseline.json")
        known = {p["name"] for p in sb.get("projects", [])}
    except Exception:
        known = set()
    out = {}
    for i, r in enumerate(rows, start=2):
        name = (r.get("project") or "").strip()
        rid = f"project-locations.csv row {i} ({name or '?'})"
        if not name:
            errors.append(f"{rid}: project name is required")
            continue
        if known and name not in known:
            errors.append(f"{rid}: no project called {name!r} in storage-baseline.json — "
                          f"the name must match exactly or the pin is never drawn")
        lat = _num(r.get("lat"), "lat", rid, errors, keep_float=True)
        lon = _num(r.get("lon"), "lon", rid, errors, keep_float=True)
        if lat is None or lon is None:
            errors.append(f"{rid}: lat and lon are both required")
        else:
            if not -90 <= lat <= 90:
                errors.append(f"{rid}: latitude {lat} is out of range")
            if not -180 <= lon <= 180:
                errors.append(f"{rid}: longitude {lon} is out of range")
        out[name] = {"lat": lat, "lon": lon, "place": (r.get("place") or "").strip()}
    return out


# --------------------------------------------------------------------------- commands

def cmd_export():
    os.makedirs(CSV_DIR, exist_ok=True)
    counts = {
        "funding-programmes.csv": export_programmes(),
        "funding-enrichment.csv": export_enrichment(),
        "project-locations.csv": export_locations(),
    }
    print(f"Exported to {CSV_DIR}")
    for name, n in counts.items():
        print(f"  {name:28} {n} rows")
    print("\nEdit in Excel, then: python3 scripts/curation_io.py import")
    print("The JSON keeps its provenance headers and known_gaps — those are not in the CSVs\n"
          "and are preserved on import.")
    return 0


def cmd_import(dry_run=False):
    if not os.path.isdir(CSV_DIR):
        sys.exit(f"No CSVs found at {CSV_DIR}. Run `export` first.")
    errors = []
    currencies = _fx_currencies()

    programmes = import_programmes(errors, currencies)
    enrichment = import_enrichment(errors)
    locations = import_locations(errors)

    if errors:
        print(f"{len(errors)} problem(s) found — nothing written:\n", file=sys.stderr)
        for e in errors:
            print(f"  · {e}", file=sys.stderr)
        return 1

    written = []
    if programmes is not None:
        doc = _load("funding-programmes.json")
        doc["programmes"] = programmes          # metadata/known_gaps preserved
        if not dry_run:
            written.append((_save("funding-programmes.json", doc), len(programmes)))
    if enrichment is not None:
        doc = _load("funding-enrichment.json")
        doc["records"] = enrichment
        if not dry_run:
            written.append((_save("funding-enrichment.json", doc), len(enrichment)))
    if locations is not None:
        doc = _load("project-locations.json")
        doc["locations"] = locations
        if not dry_run:
            written.append((_save("project-locations.json", doc), len(locations)))

    if dry_run:
        print("Validation passed. Nothing written (--dry-run).")
    else:
        print("Validation passed. Written:")
        for path, n in written:
            print(f"  {os.path.relpath(path, ROOT):45} {n} rows")
        print("\nRebuild to see the effect: python3 scripts/build_dashboard.py")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export", help="write the curated JSON out as CSV")
    imp = sub.add_parser("import", help="read the CSVs back, with validation")
    imp.add_argument("--dry-run", action="store_true", help="validate only")
    args = ap.parse_args()
    return cmd_export() if args.cmd == "export" else cmd_import(args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
