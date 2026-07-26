# CCS Intelligence Dashboard

A running, evidence-based read on global CCS momentum, built from the daily CCS-briefing corpus and
viewed through the CO2CRC / CO2Tech strategic lens. For the *why* and the agreed scope, see
[`SCOPE.md`](SCOPE.md).

**Output:** [`index.html`](index.html) — a single self-contained HTML file (inline SVG charts, no
external dependencies; opens in any browser, emails cleanly, works as a Claude Artifact). Dated
board snapshots are archived in [`snapshots/`](snapshots/).

## How it works

```
 briefing .md files  ──►  extraction (LLM)  ──►  facts records  ──►  build_dashboard.py  ──►  index.html
 (repo root, daily)       per EXTRACTION_SPEC       (JSON)            (dedup, A$, charts)      + snapshot
```

1. **Extraction** turns each briefing's prose into structured records per
   [`data/EXTRACTION_SPEC.md`](data/EXTRACTION_SPEC.md) — the single source of truth for the schema,
   controlled vocabularies, FX handling and dedup rules.
   - **History (frozen):** [`data/facts-backfill.jsonl`](data/facts-backfill.jsonl) — a one-time
     backfill of every briefing from 24 May 2026 onward. Do not regenerate casually; it carries
     central-QA corrections (see below).
   - **Ongoing:** the daily production routine emits `audit/YYYY-MM-DD-facts.json` alongside each
     briefing (see `docs/routine-prompts/production.md`, output step E2).
   - **Periodic external reports:** GCCSI quarterly updates (and similar periodic reports the user
     drops into the local `03-GCCSI-publications/` folder) are extracted on arrival into
     `data/quarterly/YYYY-QN.jsonl` — see EXTRACTION_SPEC.md's "Output location" section for the
     convention, including the manual duplicate-check step against the daily corpus (these reports
     have no per-item URLs and use different headline wording than the press, so the automatic
     dedup below does NOT catch overlaps — check by org + event before adding a new quarter's file).
     A local scheduled task (`gccsi-publications-watch`, Mondays) checks that folder for new files
     and pings the user, since it's local-only and neither GitHub Actions nor the cloud briefing
     routine can see it.
2. **`scripts/build_dashboard.py`** reads the backfill + all `audit/*-facts.json` + all
   `data/quarterly/*.jsonl`, normalises money to A$ (fixed rates in
   [`data/fx_rates.json`](data/fx_rates.json)), dedups across days (reusing `scripts/_canon.py`),
   excludes `radar` items from time-series, and renders `index.html`.
3. **Weekly rebuild** — `.github/workflows/weekly-audit.yml` rebuilds the dashboard and writes a dated
   snapshot every Saturday (Melbourne), committing both to `main`.
4. **Weekly email** — committing that dated snapshot triggers `.github/workflows/email-dashboard.yml`,
   which emails the self-contained dashboard as an attachment via Resend (same pattern as the briefing
   and audit emails). Trigger it manually anytime from the Actions tab (`workflow_dispatch`).

## Rebuild locally

```sh
.venv/bin/python scripts/build_dashboard.py                 # refresh index.html
.venv/bin/python scripts/build_dashboard.py --snapshot 2026-07-11   # + a dated board snapshot
```

No dependencies beyond the standard library + `scripts/_canon.py`, `scripts/_countries.py` and the
generated `scripts/_worldmap.py`.

## The world map

The page opens with a real-geography world map of CCS activity, above the numbered views. Countries
are shaded by whichever measure the reader selects, and the selector buttons are **grouped by data
source** so no figure can be read without knowing who produced it:

| Group | Measures | Source |
|---|---|---|
| Government funding programmes | Total committed · Awarded to date | `data/funding-programmes.json` |
| GCCSI Global Status of CCS 2024 | Facilities operating · Capture capacity · National CCS policy | `data/reference-baseline-countries.json` |
| Storage register | Type of storage · CO₂ stored to date | `data/storage-baseline.json` (GCCSI × Imperial) |
| CO2CRC news tracking (this window) | Tracked developments · New public money · New private money | this repo's briefing corpus |

Hovering a country opens a card with its full record, kept in the same three labelled sections. Dots
mark the individual storage projects in the register, placed at indicative coordinates from
`data/project-locations.json`. A per-region roll-up sits under the map, and a **Key terms** section
follows it defining every piece of vocabulary the dashboard uses (tracked development vs facility vs
project, Mtpa, capacity vs stored, the four commitment stages, the three storage types).

Two generated files back the map; regenerate them only when the underlying source changes:

```sh
# country outlines — Natural Earth 110m, public domain, simplified + Robinson-projected
curl -o /tmp/ne110m.geojson https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson
python3 scripts/gen_worldmap.py /tmp/ne110m.geojson          # -> scripts/_worldmap.py

# per-country facility counts, capacity, policy status, carbon price
python3 scripts/gen_gccsi_countries.py "../03-GCCSI-publications/Global-Status-Report-6-November.pdf"
```

`gen_gccsi_countries.py` parses the report's Section 5.0 Facilities List (pp.57-79, ~629 facilities)
and validates its per-country totals against the report's own Figure 3.1-4: the United States (276),
United Kingdom (65), Canada (58) and China (25) reconcile exactly; Norway comes out at 27 against a
stated 26, a source-internal difference that is documented in the file's `known_gaps` rather than
adjusted away. The script prints the check on every run.

## The nine views

1. Geography of commitment · 2. Global reality check — GCCSI baseline · 2c. Cumulative storage
delivered (GCCSI × Imperial) · 3. Where the money goes · 4. Actors (incl. O&G-major
advancing/retreating) · 5. Deployment-mandate tracker · 6. Australia benchmark · 7. Momentum & social
licence · 8. Capacity committed (Mtpa) · 9. Segmented CO2CRC/CO2Tech signal feed.

Every section carries a **data-source chip** naming the organisation behind its figures.

View 2c reconciles two cumulative-storage sources that measure different things — GCCSI's dedicated
(non-EOR) project count (capacity basis) and Imperial College's *London Register of Subsurface CO₂
Storage* (measured actual tonnes, all storage types) — as two labelled series joined by a documented
bridge, under a destination-based 3-way taxonomy (dedicated / associated / EOR). Data:
`data/storage-baseline.json`. The Imperial source is watched **monthly** by
`.github/workflows/imperial-register-check.yml` (emails on change via Resend).

View 2 overlays an external authoritative benchmark — the Global CCS Institute *Global Status of CCS*
report (`data/reference-baseline.json`) — so a quiet news window for a region (e.g. the US or Middle
East) is not misread as real-world inactivity. It is dual-sourced and labelled by edition: the global
headline + growth series are **GSR 2025** (from GCCSI's published figures), and the region-by-region
facility counts & targets are **GSR 2024** (§4, data as of 24 Jul 2024) — the latest edition with a
verifiable regional breakdown in the CO2CRC GCCSI library (`03-GCCSI-publications/`). GCCSI reports
regional facility counts + Mtpa targets, not a per-region capacity table. Refresh `reference-baseline.json`
when a newer edition's regional chapters become available locally.

## Funding: two different questions

The dashboard reports funding two ways, and conflating them was a real defect found in July 2026.

**Government funding programmes** (`data/funding-programmes.json`) is a **stock**: what a government has
committed in total, whenever announced, over the whole life of the programme — with the period and, where
published, how much has actually been awarded. The UK's £21.7bn runs **over 25 years** (~£870m/yr average).
Of the United States' US$12.5bn infrastructure-law carbon pot, **about 18% had been awarded** as at June 2024.
Only four programmes publish a drawdown figure; a blank means unpublished, never zero.

**New money reported** is a **flow**: money that surfaced in the news during the current window only. It is
not a funding position. Before this split existed the map showed the UK's committed funding as **A$8.8m** —
its £21.7bn predates the corpus window entirely, so the corpus could not see it.

Every money figure is now re-extracted through `data/funding-enrichment.json`, which records for each record
who is paying (`funder_type`), what the figure measures (`amount_basis`), the period it spans, and whether it
duplicates another record. That overlay removes from funding totals: whole-economy investment aggregates, ETS
cost savings, lawsuit values, merger synergy targets, supplier sub-contracts already inside a project's capex,
and three confirmed double-counts (Pathways, India's CCUS scheme, Spain's PERTE round). Applying it moved the
headline weighted total from A$35.47bn to **A$28.09bn** and face value from A$71.76bn to **A$50.01bn**.

## Keeping the data current

| Source | Detection | Update | Cadence |
|---|---|---|---|
| **CO2CRC briefings** | — | fully automatic | corpus grows **daily**; dashboard rebuilds **Saturday 08:00 Melbourne** (`weekly-audit.yml`) |
| **Imperial register** | automatic | **manual** | fingerprint check **1st of each month** (`imperial-register-check.yml`) emails on change |
| **GCCSI publications** | automatic | **manual** | local task `gccsi-publications-watch`, **Mondays**, classifies new files and names the next step |

Two things about the weekly rebuild are easy to misread. It reads the **entire accumulated corpus**
every time — backfill plus every `audit/*-facts.json` plus every `quarterly/*.jsonl` — so the dashboard
is cumulative over the whole corpus span, not a report on the past seven days. And it renders whatever
data files are committed: if a generated file is missing, the build succeeds and quietly drops that map
layer rather than failing.

Both external checks are **change detectors, not updaters**. They tell you something moved; a human
decides what to do. Imperial alerts arrive from the same Resend sender whose dashboard mail has landed
in Junk before — worth checking there.

### When a new GCCSI report arrives

Drop it in `03-GCCSI-publications/`. Monday's watcher runs
`scripts/check_gccsi_publications.py`, classifies it and pushes a notification naming the action:

- **Quarterly update** → extract to `data/quarterly/YYYY-QN.jsonl`, with the manual duplicate
  cross-check against the daily corpus. Automatic dedup catches none of these (0 of 23 on Q2-2026).
- **Global Status Report** → re-run `scripts/gen_gccsi_countries.py`. The facilities list is located by
  its column header, so repagination is handled — but the edition-specific `NARRATIVE_CROSSCHECK`
  targets and the hand-read `POLICY_STATUS` figure must be updated, or the parse is unverified.

Run it by hand any time: `python3 scripts/check_gccsi_publications.py`

### Funding review backlog

`data/funding-enrichment.json` classifies each money figure by funder, basis and period. It is keyed by
record id, so it only covers records reviewed to date — **new money is counted in full until classified**.
Every build prints the backlog, the dashboard shows a warning banner while any exists, and
`test_unreviewed_money_is_surfaced_not_silently_counted` fails if the queue is non-empty.

## Reading the numbers (important caveats)

- **Funding means public money** unless labelled private. Government pledges and company capital are
  tracked separately and never summed.
- **A programme total is not an annual budget.** Always read it with its period.
- **Committed ≠ awarded.** The gap between a pledge and money out the door is often most of the pot.
- **Announced ≠ committed ≠ spent.** Money is status-weighted (announced 0.25 / allocated 0.75 /
  committed·spent 1.0); cancellations are tracked separately as a negative signal, never summed in.
- **A$ at fixed reference rates** (as of 2026-06-30) — an assumption pending Finance review. Change
  `data/fx_rates.json` and rebuild to update every figure.
- **Coverage bias.** The corpus reflects the briefing's English-language source skew — Europe-UK,
  North America and APAC dominate; China/India/MENA/Africa/LatAm are under-represented vs reality.
  Absence of evidence is not evidence of absence.
- **Mandate tracker is incidental**, not an exhaustive register of legislated CCS-dependent targets.
- **Not audited financials** — a best-effort read of press summaries.
- **A tracked development is not a project.** The corpus counts news events; one project generates
  many developments over its life. Facility counts (GCCSI) and storage-project counts (the register)
  are different populations again, and the three must never be added together.
- **Nameplate capacity ≠ tonnes stored.** GCCSI capacity is design rate; Imperial's register is
  measured injection, which has run 19–30% below reported capacity. The map keeps them on separate
  buttons for that reason.
- **Grey on the map means "not reported", not zero** — GCCSI's regional chapters often describe a
  country's projects without giving a country-level number.

## Central QA

Extraction is faithful to the prose, but some source figures are market aggregates, cost-savings, or
projected requirements rather than discrete commitments. These are corrected centrally (amount/capacity
nulled or status set to `na`) and the correction is recorded in the record's `extractor_note`. Applied
so far: State-of-CDR US$11.5bn market aggregate; JERA US$4bn project-cost-vs-charter; Morecambe £1.8bn
economic-contribution projection; Europe 320 Mtpa 2050 shipping-requirement study.
