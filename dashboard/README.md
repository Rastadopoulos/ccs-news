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
2. **`scripts/build_dashboard.py`** reads the backfill + all `audit/*-facts.json`, normalises money to
   A$ (fixed rates in [`data/fx_rates.json`](data/fx_rates.json)), dedups across days (reusing
   `scripts/_canon.py`), excludes `radar` items from time-series, and renders `index.html`.
3. **Weekly rebuild** — `.github/workflows/weekly-audit.yml` rebuilds the dashboard and writes a dated
   snapshot every Saturday (Melbourne), committing both to `main`.

## Rebuild locally

```sh
.venv/bin/python scripts/build_dashboard.py                 # refresh index.html
.venv/bin/python scripts/build_dashboard.py --snapshot 2026-07-11   # + a dated board snapshot
```

No dependencies beyond the standard library + `scripts/_canon.py`.

## The nine views

1. Geography of commitment · 2. Global reality check — GCCSI baseline · 3. Where the money goes
· 4. Actors (incl. O&G-major advancing/retreating) · 5. Deployment-mandate tracker · 6. Australia
benchmark · 7. Momentum & social licence · 8. Capacity committed (Mtpa) · 9. Segmented CO2CRC/CO2Tech
signal feed.

View 2 overlays an external authoritative benchmark — the Global CCS Institute *Global Status of CCS*
report (`data/reference-baseline.json`) — so a quiet news window for a region (e.g. the US or Middle
East) is not misread as real-world inactivity. Refresh it annually when GCCSI publishes.

## Reading the numbers (important caveats)

- **Announced ≠ committed ≠ spent.** Money is status-weighted (announced 0.25 / allocated 0.75 /
  committed·spent 1.0); cancellations are tracked separately as a negative signal, never summed in.
- **A$ at fixed reference rates** (as of 2026-06-30) — an assumption pending Finance review. Change
  `data/fx_rates.json` and rebuild to update every figure.
- **Coverage bias.** The corpus reflects the briefing's English-language source skew — Europe-UK,
  North America and APAC dominate; China/India/MENA/Africa/LatAm are under-represented vs reality.
  Absence of evidence is not evidence of absence.
- **Mandate tracker is incidental**, not an exhaustive register of legislated CCS-dependent targets.
- **Not audited financials** — a best-effort read of press summaries.

## Central QA

Extraction is faithful to the prose, but some source figures are market aggregates, cost-savings, or
projected requirements rather than discrete commitments. These are corrected centrally (amount/capacity
nulled or status set to `na`) and the correction is recorded in the record's `extractor_note`. Applied
so far: State-of-CDR US$11.5bn market aggregate; JERA US$4bn project-cost-vs-charter; Morecambe £1.8bn
economic-contribution projection; Europe 320 Mtpa 2050 shipping-requirement study.
