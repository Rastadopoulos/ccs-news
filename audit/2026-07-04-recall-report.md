# CCS recall audit — week ending 2026-07-04 — pooled recall 19%

## Headline metrics

- **Pooled recall** (A ∩ U / U): **19%**  (23 of 123)
- **Floor recall** (A ∩ B / B): **11%**  (4 of 35)
- **Estimated absolute recall** (Chapman, median of 4 pair-estimates): **5%**

## Sampler sizes

| Sampler | Items |
|---|---:|
| A · Production routine | 29 |
| B · RSS floor | 35 |
| C · Google Alerts | 59 |
| D · Shadow LLM | 1 |
| E · Shelly Murrell digest | 37 |
| A★ · Production, search-only subset (used for Chapman) | 27 |
| **Union U** | **123** |

_7 junk domains excluded from all samplers (config/junk_domains.txt)._

## Sampler run coverage

| Sampler | Ran (5 weekdays) | Missing |
|---|---|---|
| B · RSS floor | 5/5 | — |
| A · Production routine | 5/5 | — |
| D · Shadow LLM | 1/5 | 2026-06-29, 2026-07-01, 2026-07-02, 2026-07-03 |
| C · Google Alerts | 5/5 | — |

_Public holidays are legitimate skips and still show as missing here._

## Chapman pair-estimates

_Capture side restricted to A★ (search-only, 27 items) — full A ingests the RSS floor and Google Alerts feeds, so it is not independent of samplers B/C._

| Pair | Overlap | Estimated N |
|---|---:|---:|
| A★ × B (RSS floor) | 4 | 201 |
| A★ × C (Google Alerts) | 2 | 559 |
| A★ × D (Shadow LLM) | 0 | 55 |
| A★ × E (Shelly Murrell digest) | 0 | 1063 |

## Top missed items (100 total)

- **UQ tech turns captured CO₂ into valuable chemicals** — advancedbiofuelsusa.info · found via _E_ · [link](advancedbiofuelsusa.info/uq-tech-turns-captured-co2-into-valuable-chemicals)
- **Giant gas project earns $90m in 'free' carbon offsets** — afr.com · found via _E_ · [link](afr.com/companies/energy/giant-gas-project-earns-90m-in-free-carbon-offsets-20260622)
- **The Class VI Permit That Sounds Like a Milestone But Isn't One You Can Trade - AInvest** — ainvest.com · found via _C_ · [link](https://www.ainvest.com/news/class-vi-permit-sounds-milestone-isn-trade-2606/)
- **Carbon capture, utilization, and storage needs to move faster. Why? - Baker Hughes** — bakerhughes.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMipwFBVV95cUxOdlRSSnJOeWRkWEpDcUctYlJsanBjQzlfU3NZdlVyTDI5b2w3YTkxamxYclBBLVo3MTFJTHJhVkhQcWNXcmZUaWM3dHFLMTgtM1JQVm1xYkNSeDJmOS1hNi1iWnRPQXhhclJaMWo2QlVlUE56ZEhrX2pqUXJ4WUlMWkxYU3NPYXM1OTZJNnkyQXNleVVXVXZ3SGZ1RWFTTTgzcTZzR0VUOA?oc=5)
- **Flanders unveils €2bn industrial decarbonisation plan with focus on carbon capture** — belganewsagency.eu · found via _E_ · [link](belganewsagency.eu/flanders-unveils-2bn-industrial-decarbonisation-plan-with-focus-on-carbon-capture)
- **Climeworks Solutions Secures 450,000 Tons of Diversified Carbon Removal Agreements ...** — biochartoday.com · found via _C_ · [link](https://biochartoday.com/news/climeworks-solutions-secures-450000-tons-of-diversified-carbon-removal-agreements-with-major-global-corporations/)
- **Amazon to Buy Half the Carbon Credits From Bacon Tree Project** — bloomberg.com · found via _B_ · [link](https://www.bloomberg.com/news/articles/2026-06-30/amazon-to-buy-half-the-carbon-credits-from-bacon-tree-project)
- **BKV Announces Two New Carbon Capture and Sequestration Facilities Now Operational** — businesswire.com · found via _C_ · [link](https://www.businesswire.com/news/home/20260630926298/en/BKV-Announces-Two-New-Carbon-Capture-and-Sequestration-Facilities-Now-Operational)
- **Strategic Biofuels Secures Pivotal Class VI Permit, Advancing Louisiana's Next Major Clean ...** — businesswire.com · found via _C_ · [link](https://www.businesswire.com/news/home/20260630121450/en/Strategic-Biofuels-Secures-Pivotal-Class-VI-Permit-Advancing-Louisianas-Next-Major-Clean-Energy-Project)
- **Canadian developer issued North America's first certified DAC credits under long-term offtake deals** — carbon-pulse.com · found via _C_ · [link](https://carbon-pulse.com/526722/)

## Source-coverage matrix

| Source | Published (B+C+D+E) | Captured by A | Capture rate |
|---|---:|---:|---:|
| carbonherald.com | 16 | 4 | 25% |
| gasworld.com | 7 | 1 | 14% |
| carbon-pulse.com | 6 | 4 | 67% |
| com.my | 5 | 0 | 0% |
| ccsassociation.org | 4 | 0 | 0% |
| climeworks.com | 3 | 0 | 0% |
| offshore-energy.biz | 3 | 2 | 67% |
| businesswire.com | 2 | 0 | 0% |
| carboncapturejournal.com | 2 | 0 | 0% |
| cbc.ca | 2 | 2 | 100% |
| esgtoday.com | 2 | 0 | 0% |
| qcintel.com | 2 | 0 | 0% |
| reuters.com | 2 | 0 | 0% |
| simplywall.st | 2 | 0 | 0% |
| tradingview.com | 2 | 0 | 0% |
| upstreamonline.com | 2 | 0 | 0% |
| advancedbiofuelsusa.info | 1 | 0 | 0% |
| afr.com | 1 | 0 | 0% |
| ainvest.com | 1 | 0 | 0% |
| bakerhughes.com | 1 | 0 | 0% |
| belganewsagency.eu | 1 | 0 | 0% |
| biochartoday.com | 1 | 0 | 0% |
| bloomberg.com | 1 | 0 | 0% |
| carbonbrief.org | 1 | 0 | 0% |
| carboncredits.com | 1 | 0 | 0% |

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

_— Auto-audit_