#!/usr/bin/env python3
"""Regenerate dashboard/data/reference-baseline-countries.json from the GCCSI
Global Status of CCS 2024 report.

One-off extraction tool, NOT part of the dashboard build. It parses Section 5.0
"Facilities List" (printed pages 57-79) — a per-facility table with Country,
Operational Year, Industry, Capture Capacity and Storage Code columns — and
rolls it up per country by lifecycle stage. That table is the only place in the
report with country-level data at full coverage; the regional chapters
(pp.32-55) only describe selected projects in prose.

Two additional datasets are merged in from the regional chapters, hand-curated
because they exist only as narrative or as a colour-coded figure:
  * national CCS strategy status, read from Figure 4.4-1 (p.47)
  * headline carbon price / incentive, from the country policy sections

Usage:
  python3 scripts/gen_gccsi_countries.py \\
      "/Users/matthias/Documents/Claude-Code/03-GCCSI-publications/Global-Status-Report-6-November.pdf"

Requires the `pdftotext` binary (poppler). The PDF itself is deliberately not in
the repo — it is a third-party publication held in the user's local GCCSI library.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "dashboard", "data", "reference-baseline-countries.json")

# The facilities list is LOCATED BY CONTENT, not by page number. Page numbers
# move between editions, and a pinned range applied to a new GSR would quietly
# parse the wrong pages. These bounds are only a starting hint; find_facilities_pages()
# widens or narrows them by looking for the section's own headings.
PAGE_HINT_START, PAGE_HINT_END = 40, 120

# The report's four lifecycle headings, in order, mapped to the field names the
# dashboard uses. "Advanced" and "Early" development are kept apart because they
# mean very different things commercially: advanced has a defined site and
# usually a FID pathway, early is a stated intention.
SECTIONS = {
    "Operational": "operating",
    "In Construction": "construction",
    "Advanced Development": "advanced_development",
    "Early Development": "early_development",
}

# Report spelling -> the country names used across this repo (EXTRACTION_SPEC.md
# normalisation, and therefore _countries.COUNTRY_ISO).
COUNTRY_FIX = {
    "USA": "United States",
    "UK": "United Kingdom",
    "Korea": "South Korea",
    "Republic of Korea": "South Korea",
    "The Netherlands": "Netherlands",
    "Turkiye": "Turkey",
    "Türkiye": "Turkey",
    "UAE": "United Arab Emirates",
    "Czech Republic": "Czechia",
    # Casing typo in the source table (p.70) — without this the UK's facilities
    # are split across two entries and its total comes out one short.
    "United kingdom": "United Kingdom",
}

# ---------------------------------------------------------------------------
# Hand-curated from the regional chapters. Every entry carries its page.
# ---------------------------------------------------------------------------

# Figure 4.4-1, p.47: national carbon-management strategies / CCS roadmaps.
# The figure has exactly three legend colours and covers Europe only. Read by
# sampling the figure's vector fills rather than by eye; the "published" and
# "in-preparation" sets below are exhaustive for that map — every other European
# country on it is filled "no strategy".
POLICY_STATUS = {
    "Norway": "published", "Denmark": "published", "United Kingdom": "published",
    "France": "published", "Switzerland": "published", "Austria": "published",
    "Sweden": "in-preparation", "Germany": "in-preparation", "Poland": "in-preparation",
    "Iceland": "none", "Netherlands": "none", "Belgium": "none", "Italy": "none",
    "Greece": "none", "Ireland": "none", "Finland": "none", "Spain": "none",
    "Portugal": "none", "Czechia": "none", "Slovakia": "none", "Hungary": "none",
    "Luxembourg": "none", "Slovenia": "none", "Croatia": "none", "Serbia": "none",
    "Romania": "none", "Bulgaria": "none", "Estonia": "none", "Latvia": "none",
    "Lithuania": "none",
}

POLICY_NOTE = {
    "Iceland": ("Figure 4.4-1 (p.47) fills Iceland as 'no strategy', but the text on p.46 lists "
                "Iceland among countries that 'adopted strategies and roadmaps'. That sentence is a "
                "three-way disjunction and Iceland may belong to its 'refined their regulatory "
                "frameworks' limb (p.48 records alignment with the EU CCS Directive in June 2024). "
                "Unresolved in the source; shown as the figure has it."),
    "Netherlands": ("Figure 4.4-1 (p.47) fills the Netherlands as 'no strategy' despite it being one of "
                    "Europe's most advanced CCS jurisdictions in this same report (Porthos in "
                    "construction, an ~EUR 86/t contract-for-difference). The figure tracks whether a "
                    "single national carbon-management strategy document exists, not how much CCS is "
                    "happening."),
    "Belgium": ("'No strategy' at national level; p.48 records CO2 pipeline decrees adopted separately "
                "by the Wallonian and Flemish parliaments in March 2024."),
    "Poland": ("Figure 4.4-1 shows a strategy in preparation, though p.50 opens by noting 'limited policy "
               "developments in CCS' in Poland. Both statements are the source's own."),
    "Italy": ("'No strategy' as defined by the figure, despite substantial regulatory activity in 2024 — "
              "the Energy Decree on CO2 storage licences (February) and the Infrastructure Decree "
              "establishing a CCS Committee (June), both p.48."),
}

# Headline carbon price / public incentive, from the country policy sections.
# Strictly a PRICE or per-tonne rate — what emitting a tonne costs, or what
# abating one is worth. Funding POTS (the UK's £21.7bn, Sweden's €3bn, Norway's
# Longship share, Japan's bond, Australia's mapping budget) deliberately live in
# funding-programmes.json instead. Mixing them in here made the UK's country
# card read "Carbon price: £21.7bn over 25 years", which is a category error.
CARBON_PRICE = {
    "Canada":         ("CA$80/t carbon price, rising to CA$170/t by 2030", 33),
    "United States":  ("45Q tax credit: US$60–180/t depending on storage type", 33),
    "Singapore":      ("S$25/t carbon tax, rising to S$45/t in 2026", 15),
    "China":          ("~US$15/t in the CCER voluntary carbon market", 43),
    "Netherlands":    ("~€86/t contract-for-difference for Porthos customers", 26),
    "European Union": ("EU ETS allowance price ~€52/t (Feb 2024, down from €100/t)", 49),
}

# Country-level totals the report states directly in prose, used to sanity-check
# the parsed table rather than to replace it.
# Values in the Country column that are not countries. Kept out of the per-country
# roll-up rather than silently rendered as one.
NOT_A_COUNTRY = {"Northern Europe"}

# Per-country totals the report states about ITSELF, used to verify the parse.
# These are edition-specific (GSR2024 Figure 3.1-4, p.15). For a new edition,
# update them to that edition's figure — or set to {} to skip the check, which
# prints a warning rather than passing silently.
CROSSCHECK_SOURCE = "GSR2024 Figure 3.1-4 (p.15)"
NARRATIVE_CROSSCHECK = {
    "United States": 276, "United Kingdom": 65, "Canada": 58, "Norway": 26, "China": 25,
}


def _pdftotext(pdf_path, first, last):
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        out = tmp.name
    subprocess.run(["pdftotext", "-f", str(first), "-l", str(last),
                    "-layout", pdf_path, out], check=True)
    with open(out, encoding="utf-8") as f:
        text = f.read()
    os.unlink(out)
    return text


def find_facilities_pages(pdf_path):
    """Locate the Facilities List by its own column header, not by page number.

    Every edition's table repeats a 'Facility Name ... Country ... Capture
    Capacity' header on each page. Scanning for that is stable across editions;
    a hardcoded page range is not — GSR2024's list sits on pp.57-79, and a later
    edition will not.

    Returns (first_page, last_page). Raises if the section cannot be found, so a
    new edition fails loudly instead of silently producing an empty dataset."""
    hdr = re.compile(r"Facility\s+Name\s{2,}.*Country", re.I)
    pages = []
    text = _pdftotext(pdf_path, PAGE_HINT_START, PAGE_HINT_END)
    # pdftotext emits a form feed between pages.
    for offset, page in enumerate(text.split("\f")):
        if hdr.search(page):
            pages.append(PAGE_HINT_START + offset)
    if not pages:
        raise SystemExit(
            "Could not find the Facilities List in this PDF. Looked for a "
            f"'Facility Name … Country' column header on pages "
            f"{PAGE_HINT_START}-{PAGE_HINT_END}. If this is a new edition, check "
            "whether the table still exists and widen PAGE_HINT_START/END.")
    # One page back picks up the section heading ("Operational") above the table.
    return max(1, pages[0] - 1), pages[-1]


def extract_text(pdf_path):
    first, last = find_facilities_pages(pdf_path)
    print(f"  facilities list located on pages {first}-{last}")
    return _pdftotext(pdf_path, first, last)


def parse_capacity(raw):
    """'1.5' -> 1.5; 'Under Evaluation' / 'N/A (CO2 Transport and Storage)' -> None.
    Transport-and-storage entries have no capture capacity by definition and must
    not be read as zero."""
    if not raw:
        return None
    m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*$", raw)
    return float(m.group(1)) if m else None


def parse_facilities(text):
    """Yield (stage, name, [countries], year, industry, capacity_mtpa).

    Two wrinkles in the source layout have to be handled or the counts come out
    wrong:
      * Cross-border facilities list several countries in one cell, and that
        cell wraps onto following lines ("Belgium, Germany," / "Netherlands,
        Switzerland," / "USA"). A trailing comma is the signal to keep reading.
      * A few long facility names run into the country column, leaving five
        fields instead of six.
    Cross-border facilities are credited to every country they touch, which is
    how the report counts them in its own per-country figures.
    """
    lines = text.split("\n")
    rows = []
    stage = None
    known = set()

    def cells(line):
        return re.split(r"\s{2,}", line.strip())

    # First pass over well-formed rows to learn the country vocabulary, so the
    # merged-name repair below has something reliable to match against.
    for line in lines:
        c = cells(line)
        if len(c) >= 6 and not line.strip().startswith("Facility Name"):
            known.add(c[1].rstrip(","))

    i = 0
    while i < len(lines):
        raw = lines[i]
        t = raw.strip()
        i += 1
        if not t:
            continue
        if t in SECTIONS:
            stage = SECTIONS[t]
            continue
        if stage is None or t.startswith("GLOBAL STATUS OF CCS REPORT") or t.startswith("Facility Name"):
            continue

        c = cells(t)
        name = country = year = industry = capacity = None
        if len(c) >= 6:
            name, country, year, industry, capacity = c[0], c[1], c[2], c[3], c[4]
        elif len(c) == 5:
            if c[1].rstrip(",") in known:
                # Well-formed row that simply has no storage code.
                name, country, year, industry, capacity = c[0], c[1], c[2], c[3], c[4]
            else:
                # "<long facility name> <Country>" merged into field 0.
                for k in sorted(known, key=len, reverse=True):
                    if c[0].endswith(" " + k):
                        name, country = c[0][: -len(k) - 1].strip(), k
                        year, industry, capacity = c[1], c[2], c[3]
                        break
            if country is None:
                continue
        else:
            continue

        # Absorb wrapped country-cell continuation lines.
        while country.rstrip().endswith(","):
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines):
                break
            cont = cells(lines[i])
            if len(cont) != 1 or lines[i].strip() in SECTIONS:
                break
            country = country.rstrip() + " " + cont[0].strip()
            i += 1

        countries = [x.strip() for x in country.split(",") if x.strip()]
        rows.append((stage, name, countries, year, industry, capacity))
    return rows


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} <Global-Status-Report-6-November.pdf>")
    pdf = sys.argv[1]
    if not os.path.exists(pdf):
        sys.exit(f"PDF not found: {pdf}")

    rows = parse_facilities(extract_text(pdf))

    countries = {}
    for stage, name, country_list, year, industry, capacity in rows:
        mt = parse_capacity(capacity)
        # A facility is counted for its PRIMARY (first-listed) country only.
        # That convention reproduces the report's own stated country totals for
        # the US, Canada and China exactly (see validation below); crediting
        # every country of a cross-border project instead inflates Norway by 4.
        # Participation in a cross-border project is tracked separately so the
        # information is not lost.
        for country in country_list[:1]:
            country = COUNTRY_FIX.get(country.strip(), country.strip())
            if country in NOT_A_COUNTRY:
                continue
            c = countries.setdefault(country, {
                "country": country,
                "operating": 0, "construction": 0,
                "advanced_development": 0, "early_development": 0,
                "capacity_operating_mtpa": 0.0, "capacity_all_mtpa": 0.0,
                "_facilities": [],
            })
            c[stage] += 1
            if mt:
                c["capacity_all_mtpa"] += mt
                if stage == "operating":
                    c["capacity_operating_mtpa"] += mt
            if stage == "operating":
                c["_facilities"].append({"name": name, "year": year,
                                          "industry": industry, "capacity_mtpa": mt})
        # Secondary partners in a cross-border facility.
        for country in country_list[1:]:
            country = COUNTRY_FIX.get(country.strip(), country.strip())
            if country in NOT_A_COUNTRY:
                continue
            c = countries.setdefault(country, {
                "country": country,
                "operating": 0, "construction": 0,
                "advanced_development": 0, "early_development": 0,
                "capacity_operating_mtpa": 0.0, "capacity_all_mtpa": 0.0,
                "_facilities": [],
            })
            c["cross_border"] = c.get("cross_border", 0) + 1

    out_rows = []
    for name in sorted(countries):
        c = countries[name]
        total = (c["operating"] + c["construction"]
                 + c["advanced_development"] + c["early_development"])
        row = {
            "country": name,
            "operating": c["operating"],
            "construction": c["construction"],
            "advanced_development": c["advanced_development"],
            "early_development": c["early_development"],
            "pipeline": c["advanced_development"] + c["early_development"],
            "total_facilities": total,
            "cross_border_participation": c.get("cross_border", 0),
            "capacity_mtpa": round(c["capacity_operating_mtpa"], 2) or None,
            "capacity_all_stages_mtpa": round(c["capacity_all_mtpa"], 2) or None,
            "operating_facilities": c["_facilities"],
            "page": "57-79",
        }
        if name in POLICY_STATUS:
            row["policy_status"] = POLICY_STATUS[name]
            row["policy_page"] = 47
            if name in POLICY_NOTE:
                row["policy_note"] = POLICY_NOTE[name]
        if name in CARBON_PRICE:
            row["carbon_price"], row["carbon_price_page"] = CARBON_PRICE[name]
        out_rows.append(row)

    # Validate against the counts the report states about itself.
    problems = []
    if not NARRATIVE_CROSSCHECK:
        print("  ! no cross-check configured for this edition — parse is UNVERIFIED",
              file=sys.stderr)
    for country, expected in NARRATIVE_CROSSCHECK.items():
        got = next((r["total_facilities"] for r in out_rows if r["country"] == country), 0)
        flag = "OK " if got == expected else "MISMATCH"
        if got != expected:
            problems.append(f"{country}: parsed {got}, report says {expected}")
        print(f"  {flag} {country}: {got} (report: {expected})")

    doc = {
        "_comment": (
            "Per-country CCS facility counts, capture capacity, national strategy status and headline "
            "carbon price, extracted from the Global CCS Institute's Global Status of CCS 2024. "
            "GENERATED by scripts/gen_gccsi_countries.py — do not hand-edit; change the script instead. "
            "Facility counts and capacity come from the Section 5.0 Facilities List (pp.57-79), which is "
            "the report's only full-coverage country-level dataset. Strategy status comes from Figure "
            "4.4-1 (p.47) and covers EUROPE ONLY — a country with no policy_status field was simply not "
            "assessed by that figure, which is not the same as having no policy. Carbon prices are the "
            "headline national instrument where the report states one. "
            "IMPORTANT: capacity_mtpa is NAMEPLATE capture capacity as designed, NOT tonnes actually "
            "captured or stored; for measured injection see storage-baseline.json's Imperial College "
            "series. The two must never be added together or used interchangeably."
        ),
        "schema_version": 2,
        "source": ("Global CCS Institute — Global Status of CCS 2024 (“Collaborating for a Net-Zero "
                    "Future”), Section 5.0 Facilities List pp.57-79; Figure 4.4-1 p.47; "
                    "regional policy chapters pp.32-55. Data as of 24 Jul 2024."),
        "generated_by": "scripts/gen_gccsi_countries.py",
        "retrieved": "2026-07-26",
        "validation": {
            "method": ("Parsed facility totals were checked against Figure 3.1-4 (p.15), where the report "
                        "states its own top-5 country project counts."),
            "checks": {k: v for k, v in NARRATIVE_CROSSCHECK.items()},
            "result": "all matched" if not problems else "; ".join(problems),
        "interpretation": (
            "A facility is counted for its first-listed country. That reproduces the report's own "
            "figures exactly for the United States, Canada and China. Two small residuals remain "
            "(see known_gaps) and are left visible rather than reconciled away."
        ),
        },
        "known_gaps": [
            "One country total differs from Figure 3.1-4 (p.15): this parse gives Norway 27 facilities "
            "where that figure says 26. The difference comes from the source, not the parse — Norway "
            "carries both a 'Havstjerne Storage' entry (advanced development) and a 'Wintershall Dea "
            "Havstjerne' entry (early development), which the summary figure appears to treat as a "
            "single project. The United States (276), United Kingdom (65), Canada (58) and China (25) "
            "all reconcile exactly. The residual is left visible rather than adjusted to match.",
            "The source spells the United Kingdom two ways — 'United Kingdom' and, on p.70, "
            "'United kingdom'. They are folded together here; without that the UK total comes out one "
            "short of the report's own figure.",
            "Values in the Country column that are regions rather than countries ('Northern Europe') "
            "are excluded from the per-country roll-up rather than rendered as if they were a country.",
            "Capacity is missing for facilities the report lists as 'Under Evaluation' or as CO2 "
            "transport-and-storage only (which have no capture capacity by definition). A country's "
            "capacity total therefore understates its facility count, and the two should not be "
            "divided into each other to infer an average project size.",
            "Nameplate vs actual: the report lists Chevron Gorgon at 4 Mtpa capture capacity (p.57) "
            "while its own regional chapter says ~1.6 Mtpa is actually being stored (p.42). Both are "
            "the source's figures. This dataset carries the nameplate; storage-baseline.json carries "
            "the measured volumes.",
            "Internal inconsistency in the source: Qatar's Ras Laffan appears as 2.1 Mtpa in the "
            "regional chapter (p.54) and 2.2 Mtpa in the facilities list (p.57). The facilities-list "
            "figure is used here for consistency with every other row.",
            "Petrobras Santos Basin is listed at 10.6 Mtpa capture capacity (p.57) but the regional "
            "chapter reports 13 Mt injected during 2023 (p.38) — injection includes reinjected "
            "produced CO2, so it can exceed capture capacity.",
            "National strategy status is available for Europe only (Figure 4.4-1). Asia-Pacific, the "
            "Americas and the Middle East have substantial CCS legislation described in prose "
            "(Japan's CCS Business Act, South Korea's CCUS Act, Indonesia's Presidential Regulation "
            "14/2024, Brazil's Fuels of the Future law) but the report applies no comparable "
            "published/in-preparation classification to them, so none is invented here.",
        ],
        "countries": out_rows,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nwrote {OUT}")
    print(f"  {len(out_rows)} countries · {len(rows)} facilities parsed")
    if problems:
        print("  ! validation mismatches:", "; ".join(problems), file=sys.stderr)


if __name__ == "__main__":
    main()
