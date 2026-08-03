# Reliability operations and refresh handoff

## Normal weekly build

1. Run `scripts/coverage_report.py` for the build date. If status is impaired, show that status and start the backfill workflow; do not label the day quiet.
2. Run `scripts/build_entity_register.py`. Review `dashboard/data/entities/crosswalk-review.csv`; add aliases only when project identity is supported.
3. Run `scripts/build_baseline_comparison.py` and `scripts/build_reliability_model.py`.
4. Run `scripts/build_dashboard.py`, pytest and Bats. Check regional/global reconciliation in `dashboard/data/model/summary.json`.
5. Inspect desktop and narrow layouts, console output and internal anchors before publishing a snapshot.

## Baseline refreshes

### IEA

Download the latest official workbook from the IEA product page using a free authenticated account. Do not scrape around authentication. Save the workbook under `dashboard/data/sources/`, run `scripts/ingest_iea_ccus.py`, inspect required-column/stage/unit validation, then adjudicate the generated name crosswalk. Preserve product URL, edition, update/retrieval dates, CC BY 4.0 attribution, thresholds and exclusions. The explorer JSON is a constrained fallback only.

### GCCSI

Download the official Global Status PDF and run `scripts/ingest_gccsi_2025.py`. The importer deliberately accepts only the verified 47-row construction appendix for GSR 2025. Do not promote it to a full country table. Refresh `curation/gccsi-countries.csv` only when a later report publishes a verifiable all-stage replacement.

### London Register

Download the workbook from Zenodo record 18016847 and run `scripts/ingest_london_register.py`. Verify checksum, 46-project count, final year 2024 and class totals. Keep dedicated, associated and EOR separate. Some annual values are derived averages; retain the source note.

## Human review queues

- `entities/crosswalk-review.csv`: capacity-bearing local events with no certain canonical match.
- `baselines/iea/crosswalk-review.csv`: named workbook projects without an exact curated alias match, including rule-assisted same-country candidates that still require adjudication.
- `baselines/gccsi/crosswalk-review.csv`: construction names not yet mapped to the local canonical subset.
- `coverage/retry-candidates.json`: blocked or unverified collection candidates.
- `monitoring/latest.md`: source changes and retrieval failures from the scheduled authoritative monitor.

Never resolve a queue by fuzzy guessing. Record alias/source/confidence and re-run generation.

## Collection impairment

Use the **Retry and backfill impaired collection days** GitHub workflow with the affected ISO date. The workflow re-runs the deterministic RSS floor and refreshes technical coverage. Candidates whose article verification is blocked must remain tagged for retry. A no-verified-news status is valid only when every scheduled sampler is present and healthy.

## Recall interpretation

The weekly audit denominator is the deduplicated, adjudicated relevant union. Report precision, relevant recall, decision-relevant recall and breakdowns by geography, source class and content type. The 90% plumbing threshold applies only to the adjudicated high-priority RSS floor. Chapman estimates are experimental diagnostics; sampler dependence and unequal catchability prevent authoritative absolute-recall claims.
