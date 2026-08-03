# CCS Intelligence Dashboard

[`index.html`](index.html) is a self-contained, offline CCS intelligence product for board and senior-stakeholder use. It leads with data health and official deployment baselines, then uses the daily briefing as an evidence stream. A news article is never treated as a project-sized commitment.

## Architecture

```text
daily facts + periodic reports ──► event archive ──► canonical entity crosswalk
                                                     │
official IEA / GCCSI / London baselines ─────────────┼──► reliability model ──► dashboard
funding programme + event curation ──────────────────┘
```

Key generated datasets:

- `data/entities/projects.csv` — stable project/entity IDs, aliases, physical geography, lifecycle and verification fields.
- `data/entities/components.csv` — capture facilities, transport networks, storage sites and other linked components.
- `data/entities/capacities.csv` — the only additive local capacity table; basis-specific and deduplicated.
- `data/entities/event-crosswalk.csv` — daily/periodic evidence mapped to canonical entities; uncertain mappings remain blank.
- `data/entities/crosswalk-review.csv` — human mapping queue.
- `data/model/funding-programmes.csv` and `funding-commitments.csv` — programme stock and unique event categories, kept separate.
- `data/model/regional-reconciliation.csv` — one primary physical geography per event, including an explicit EU-bloc bucket.
- `data/coverage/latest.json` — technical collection health; an impaired day can never become a quiet-day claim.

The generated model is intentionally reviewable CSV/JSON. Source workbooks/feeds and checksums live under `data/sources/` and baseline metadata.

## Reproducible rebuild

The checked-in baseline outputs are current as of 3 August 2026. Refresh them in this order when their sources change:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ingest_iea_ccus.py \
  dashboard/data/sources/iea-ccus-projects-database-2026.xlsx --retrieved 2026-08-03

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ingest_gccsi_2025.py \
  "/path/to/Global-Status-of-CCS-2025.pdf" --retrieved 2026-08-03

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/ingest_london_register.py \
  dashboard/data/sources/london-register-2025.xlsx --retrieved 2026-08-03

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/build_entity_register.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/build_baseline_comparison.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/coverage_report.py --date 2026-08-03 --window 14
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/build_reliability_model.py
BUILD_DATE=2026-08-03 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/build_dashboard.py
```

The dashboard build fails if required generated layers are missing or if the verified IEA 2026, GCCSI 2025 or London Register 2025 metadata regresses. Use `--snapshot YYYY-MM-DD` on the final command for a board snapshot.

## Companion baselines

### IEA CCUS Projects Database 2026

Source: <https://www.iea.org/data-and-statistics/data-product/ccus-projects-database>. Update 27 March 2026; retrieved 3 August 2026; CC BY 4.0.

IEA coverage includes projects above 100,000 tCO₂/year and DAC above 1,000 tCO₂/year. It excludes low-climate-benefit utilisation, conventional internal urea use and naturally occurring CO₂ used for EOR. The authenticated official workbook contains 1,110 named projects, preserves partner, phase, hub, sector, capacity, milestone and reference fields, and states that project announcements are current through February 2026. Exact curated entity matches are accepted; plausible alias/component matches remain in the review queue. The 422-row public explorer feed is retained only as a reproducible fallback.

### GCCSI Global Status of CCS 2025

The global headline is 77 operating facilities / 64 Mtpa, 47 in construction / 44 Mtpa, 610 in development and 734 in the total pipeline / 513 Mtpa, with data as of July 2025. The reproducible importer extracts the report's full 47-row in-construction appendix. GSR 2025 does not reproduce the all-stage country facility table, so the country map is visibly labelled GSR 2024 rather than silently mixed with the 2025 global totals.

### London Register 2025

Source: DOI `10.5281/zenodo.18016847`, CC BY 4.0. The current downloadable workbook contains 46 projects and annual series through 2024. The independent sum is 384.597621 Mt cumulative all-storage and 33.218509 Mt in 2024. Dedicated, associated reinjection and EOR remain separate. Some annual figures are averages derived from cumulative disclosures, as documented in the source.

The older `storage-baseline.json` remains only for the legacy named-project map subset and is visibly labelled incomplete. It is not a headline source.

## Capacity, funding and geography rules

- Capture, transport, storage injection, utilisation, removal-purchase/offtake, policy-target and cumulative resource values are distinct bases.
- An event capacity is evidence only. Latest curator-verified project/component values control totals.
- Project updates replace prior values; Pathways, Morecambe, Carbon TerraVault and Padeswood article repeats cannot add capacity.
- Programme stock, CCS-eligible pots, published awards, actual spend, private investment, capex, supplier contracts, cancelled capex and withdrawn public funding are separate.
- Missing drawdown is “not published”, never zero. “Published awards: at least A$8.02bn across four reporting programmes” is a lower bound.
- “Status-weighted reported value” is an analytical scenario using disclosed weights; it is not committed money.
- Multi-country tags are useful for discovery but non-additive. Reconciliation uses canonical physical location, not company headquarters. BP Tangguh is Indonesia; EU-wide measures sit in an EU-bloc bucket.

## Collection, recall and monitoring

`scripts/coverage_report.py` records attempted/reachable feeds, retrieved articles, verified publication dates, failures and missing sampler files. Status is one of `normal coverage`, `partial coverage`, `collection impaired` or `no verified news`. The last status is legal only when all scheduled samplers are healthy.

The weekly audit adjudicates relevance before constructing the denominator, reports precision, overall and decision-relevant recall by geography/source/content, and applies the 90% floor only to adjudicated high-priority RSS items. Chapman capture–recapture is an experimental diagnostic because independence and equal-catchability assumptions are violated.

`config/authoritative-sources.yml` and `scripts/monitor_authoritative_sources.py` fingerprint official baselines, regulators, operators/NOCs and technology providers. `.github/workflows/authoritative-source-monitor.yml` runs this with network access; changes that cannot be safely structured generate human-review alerts. `.github/workflows/collection-backfill.yml` re-runs the deterministic floor for an impaired date.

See [`../docs/reliability-operations.md`](../docs/reliability-operations.md) and [`data/SOURCE_INVENTORY.md`](data/SOURCE_INVENTORY.md) for refresh and operational handoff.
