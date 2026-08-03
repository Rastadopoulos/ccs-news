# Source and refresh inventory

| Dataset | Current edition / as-of | Local source | Generated output | Refresh / licence |
|---|---|---|---|---|
| IEA CCUS Projects Database | 2026, updated 27 Mar 2026; announcements through Feb 2026 | `sources/iea-ccus-projects-database-2026.xlsx` (primary); `sources/iea-ccus-projects-explorer-2026.json` (fallback) | `baselines/iea/` | Re-run `ingest_iea_ccus.py`; CC BY 4.0. Workbook SHA-256 and schema are recorded in metadata. |
| GCCSI Global Status of CCS | GSR 2025, data Jul 2025 | official PDF supplied to importer | `baselines/gccsi/` | Re-run `ingest_gccsi_2025.py`; review publication terms. Global and construction outputs only. |
| GCCSI country layer | GSR 2024, data 24 Jul 2024 | `03-GCCSI-publications/Global-Status-Report-6-November.pdf` | `curation/gccsi-countries.csv` | Retained because GSR 2025 has no full replacement table; UI must show vintage. |
| London Register | 2025 edition, data through 2024 | `sources/london-register-2025.xlsx` | `baselines/london-register/` | Re-run `ingest_london_register.py`; DOI 10.5281/zenodo.18016847, CC BY 4.0. |
| Daily briefing facts | 24 May–31 Jul 2026 files | `facts-backfill.jsonl`, `audit/*-facts.json` | canonical event crosswalk/model | Daily; technical coverage report must be healthy before calling a day quiet. |
| GCCSI quarterly | Q2 2026 | `quarterly/2026-Q2.jsonl` | event crosswalk/model | Periodic report; report-level URL where item URL is absent; excluded from weekly newsflow. |
| Funding programmes | curated through Jul 2026 | `curation/funding-programmes.csv` | `model/funding-programmes.csv` | Human review; original currencies retained; fixed A$ FX basis disclosed. |
| Authoritative monitor | registry v1 | `config/authoritative-sources.yml` | `data/monitoring/` in GitHub Actions | Weekly fingerprints; human review when structured extraction is unsafe. |

Checksums, retrieval dates, methodology and limitations live in each baseline's `metadata.json`.
