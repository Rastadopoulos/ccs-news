# CCS recall audit — week ending 2026-07-11 — pooled recall 6%

## Headline metrics

- **Pooled recall** (A ∩ U / U): **6%**  (6 of 105)
- **Floor recall** (A ∩ B / B): **3%**  (1 of 30)
- **Estimated absolute recall** (Chapman, median of 4 pair-estimates): **3%**

## Sampler sizes

| Sampler | Items |
|---|---:|
| A · Production routine | 10 |
| B · RSS floor | 30 |
| C · Google Alerts | 51 |
| D · Shadow LLM | 4 |
| E · Shelly Murrell digest | 36 |
| A★ · Production, search-only subset (used for Chapman) | 8 |
| **Union U** | **105** |

_7 junk domains excluded from all samplers (config/junk_domains.txt)._

## Sampler run coverage

| Sampler | Ran (5 weekdays) | Missing |
|---|---|---|
| B · RSS floor | 5/5 | — |
| A · Production routine | 5/5 | — |
| D · Shadow LLM | 2/5 | 2026-07-06, 2026-07-07, 2026-07-10 |
| C · Google Alerts | 5/5 | — |

_Public holidays are legitimate skips and still show as missing here._

## Chapman pair-estimates

_Capture side restricted to A★ (search-only, 8 items) — full A ingests the RSS floor and Google Alerts feeds, so it is not independent of samplers B/C._

| Pair | Overlap | Estimated N |
|---|---:|---:|
| A★ × B (RSS floor) | 1 | 138 |
| A★ × C (Google Alerts) | 0 | 467 |
| A★ × D (Shadow LLM) | 0 | 44 |
| A★ × E (Shelly Murrell digest) | 0 | 332 |

## Top missed items (99 total)

- **UQ tech turns captured CO2 into valuable chemicals** — advancedbiofuelsusa.info · found via _E_ · [link](us.list-manage.com/eVnmgbJ66OH)
- **Benefits agreement tied to carbon capture hub proposed** — americanpress.com · found via _D_ · [link](americanpress.com/2026/07/08/benefits-agreement-tied-to-carbon-capture-hub-proposed)
- **Deep Sky Announces Direct Air Capture Carbon Removal Agreement with TD Bank Group ...** — aol.com · found via _C_ · [link](https://www.aol.com/articles/deep-sky-announces-direct-air-100000000.html)
- **Deep Sky and Lufthansa Group Enter Carbon Removal Credit Agreement - AOL.com** — aol.com · found via _C_ · [link](https://www.aol.com/articles/deep-sky-lufthansa-group-enter-154900000.html)
- **Louisiana House rejects bills on local control over carbon-capture** — aol.com · found via _C_ · [link](https://www.aol.com/articles/louisiana-house-rejects-bills-local-171147000.html)
- **Flanders unveils EUR2bn industrial decarbonisation plan with focus on carbon capture** — belganewsagency.eu · found via _E_ · [link](us.list-manage.com/1BRsIfZKumY)
- **CP Daily News Ticker: 7 July 2026** — carbon-pulse.com · found via _D_ · [link](carbon-pulse.com/529177)
- **New mechanism to mitigate very long-term project risk launching this year** — carbon-pulse.com · found via _E_ · [link](us.list-manage.com/B5lBAw3CuQ3)
- **Q&A: The current state of 'carbon dioxide removal' around the world** — carbonbrief.org · found via _E_ · [link](us.list-manage.com/GctAFgMnnos)
- **Ambuja Cements and Leilac partner on commercial scale low carbon cement** — carboncapturejournal.com · found via _E_ · [link](us.list-manage.com/en9eBb2MdLd)

## Source-coverage matrix

| Source | Published (B+C+D+E) | Captured by A | Capture rate |
|---|---:|---:|---:|
| carbonherald.com | 15 | 0 | 0% |
| list-manage.com | 9 | 0 | 0% |
| gasworld.com | 6 | 0 | 0% |
| carboncapturejournal.com | 4 | 0 | 0% |
| ccsassociation.org | 4 | 0 | 0% |
| aol.com | 3 | 0 | 0% |
| carbon-pulse.com | 3 | 1 | 33% |
| inspenet.com | 2 | 0 | 0% |
| megaproject.com | 2 | 0 | 0% |
| morningstar.com | 2 | 0 | 0% |
| offshore-energy.biz | 2 | 0 | 0% |
| tipranks.com | 2 | 0 | 0% |
| advancedbiofuelsusa.info | 1 | 0 | 0% |
| americanpress.com | 1 | 0 | 0% |
| belganewsagency.eu | 1 | 0 | 0% |
| bloomberg.com | 1 | 1 | 100% |
| carbonbrief.org | 1 | 0 | 0% |
| carboncredits.com | 1 | 0 | 0% |
| chemengonline.com | 1 | 0 | 0% |
| cleanenergywire.org | 1 | 0 | 0% |
| climeworks.com | 1 | 0 | 0% |
| com.my | 1 | 0 | 0% |
| contexte.com | 1 | 0 | 0% |
| dcceew.gov.au | 1 | 0 | 0% |
| decarbonfuse.com | 1 | 0 | 0% |

## Drift — last 12 weeks

| Week ending | Pooled recall | Floor recall |
|---|---:|---:|
| 2026-05-26 | 0% | 0% |
| 2026-05-27 | 0% | 0% |
| 2026-05-30 | 20% | 0% |
| 2026-06-06 | 13% | 0% |
| 2026-06-13 | 7% | 2% |
| 2026-06-20 | 14% | 0% |
| 2026-06-27 | 12% | 2% |
| 2026-07-04 | 19% | 11% |
| 2026-07-11 | 6% | 3% |

_— Auto-audit_