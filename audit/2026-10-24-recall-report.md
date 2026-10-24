# CCS recall audit — week ending 2026-10-24 — pooled recall 8%

## Headline metrics

- **Pooled recall** (A ∩ U / U): **8%**  (10 of 121)
- **Precision** (adjudicated relevant items / production items): **100%**
- **Decision-relevant recall**: **8%**
- **Adjudicated high-priority floor recall** (A ∩ B★ / B★): **2%**  (1 of 42)
- **Experimental Chapman diagnostic** (median of 2 pair-estimates): **4%** — not an authoritative absolute-recall estimate

## Sampler sizes

| Sampler | Items |
|---|---:|
| A · Production routine | 11 |
| B · RSS floor | 42 |
| C · Google Alerts | 86 |
| D · Shadow LLM | 0 |
| E · Shelly Murrell digest | 0 |
| F · IEAGHG Weekly News | 0 |
| A★ · Production, search-only subset (used for Chapman) | 2 |
| **Union U** | **121** |

_7 junk domains excluded from all samplers (config/junk_domains.txt)._

## Sampler run coverage

| Sampler | Ran (5 weekdays) | Missing |
|---|---|---|
| B · RSS floor | 5/5 | — |
| A · Production routine | 5/5 | — |
| D · Shadow LLM | 5/5 | — |
| C · Google Alerts | 5/5 | — |

_Public holidays are legitimate skips and still show as missing here._

## Experimental Chapman pair-estimates

_Capture side restricted to A★ (search-only, 2 items) — full A ingests the RSS floor and Google Alerts feeds, so it is not independent of samplers B/C._
_Diagnostic only: sampler independence and equal catchability are violated, so this must not be read as authoritative absolute recall._

| Pair | Overlap | Estimated N |
|---|---:|---:|
| A★ × B (RSS floor) | 0 | 128 |
| A★ × C (Google Alerts) | 0 | 260 |

## Top missed items (111 total)

## Recall by geography

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| Unclassified | 121 | 10 | 8% |

## Recall by source class

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| media/newsletter | 120 | 10 | 8% |
| primary/official | 1 | 0 | 0% |

## Recall by content type

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| unclassified | 121 | 10 | 8% |

- **Global carbon capture projects surpass 100 as transport and storage networks reshape ...** — africasustainabilitymatters.com · found via _C_ · [link](https://africasustainabilitymatters.com/global-carbon-capture-projects-surpass-100-as-transport-and-storage-networks-reshape-industrial-decarbonisation/)
- **Inpex-Led Bonaparte CCS Project Gets Australian Offshore Storage Approval** — aogdigital.com · found via _C_ · [link](https://aogdigital.com/amp/news/543732-inpexled-bonaparte-ccs-project-gets-australian-offshore-storage-approval)
- **peptide collision | Exploring the Technical Nuances of Peptide Collision and CCS Analysis** — archaeology.org · found via _C_ · [link](https://archaeology.org/peptide-collision-choice/)
- **EU approves first grants for SMR, direct air carbon capture - Balkan Green Energy News** — balkangreenenergynews.com · found via _C_ · [link](https://balkangreenenergynews.com/eu-approves-first-grants-for-smr-direct-air-carbon-capture/)
- **Smart Control Could Nearly Double the Real Climate Payoff of Direct Air Capture Machines - Bioengineer.org** — bioengineer.org · found via _B_ · [link](https://news.google.com/rss/articles/CBMiswFBVV95cUxQdEhORTd3RzViemlIdjdhV1hBeGdxV2taTDJPRTY0czBlUXo3ZXZzbjhZbmFtNDM1Wm9xbDlCNHdyYXpkRkdzVUNqc1V2d09vY3RIdzJzUnZPLWNiVjhFdE9LdFBBYnAwS2F4RUVpRTktSHpDbkRkUEhKTnRsRFpPZmphZmg1RHM4eDI3UHctRldxVDZFYnNfMkFEMDJZN0I0YjU1bHktNHlZRFFsRmdaWkpMQQ?oc=5)
- **Canadian subsurface engineering firm VZFOX set to enter Indian market | Industry News** — business-standard.com · found via _C_ · [link](https://www.business-standard.com/industry/news/vzfox-india-entry-mature-oilfields-eor-ccus-energy-126101500610_1.html)
- **CCS: More than 100 commercial carbon capture projects now in operation globally** — businessgreen.com · found via _C_ · [link](https://www.businessgreen.com/news/4537529/ccs-100-commercial-carbon-capture-projects-operation-globally)
- **Woodside exits Bonaparte CCS as Inpex presses ahead - Business News** — businessnews.com.au · found via _C_ · [link](https://www.businessnews.com.au/article/Woodside-exits-Bonaparte-CCS-as-Inpex-presses-ahead)
- **UK warns funding constraints could slow next phase of carbon capture rollout** — carbon-pulse.com · found via _C_ · [link](https://carbon-pulse.com/560523/)
- **Carbon Capture Journal - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMivwFBVV95cUxPdkh2LTZwaWpIdmxGX0RSRnhlS3NjbGNaeUd2WC11Rm9fOWxPMEZwbGcza2VtclpuM2ZSYldEOUQxcFZmdGRHRlZDMFowNXA5VHl0RGdmTm1IU203STRpZGp2RTBBMjlvLTJ0ME53S2I5Ukc2ekRWT2QyNnhvaTQ0djBUQkFlc01jbXRCcDlVSnhhaVp1dC13b1NHVlN2TUlzdmlvUFBINmxWcS1fbXIxT2ZmOWhfbkU2SkJNQ2FjNA?oc=5)

## Source-coverage matrix

| Source | Published (B+C+D+E) | Captured by A | Capture rate |
|---|---:|---:|---:|
| carbonherald.com | 22 | 2 | 9% |
| openpr.com | 5 | 0 | 0% |
| carboncapturejournal.com | 4 | 0 | 0% |
| marketscreener.com | 4 | 0 | 0% |
| indianchemicalnews.com | 3 | 1 | 33% |
| oceannews.com | 3 | 0 | 0% |
| offshore-energy.biz | 3 | 0 | 0% |
| upstreamonline.com | 3 | 2 | 67% |
| carboncredits.com | 2 | 1 | 50% |
| com.my | 2 | 0 | 0% |
| economictimes.com | 2 | 0 | 0% |
| energy-pedia.com | 2 | 0 | 0% |
| euro-petrole.com | 2 | 0 | 0% |
| gasworld.com | 2 | 0 | 0% |
| simplywall.st | 2 | 0 | 0% |
| trend.az | 2 | 0 | 0% |
| vermoegenszentrum.ch | 2 | 0 | 0% |
| africasustainabilitymatters.com | 1 | 0 | 0% |
| aogdigital.com | 1 | 0 | 0% |
| archaeology.org | 1 | 0 | 0% |
| balkangreenenergynews.com | 1 | 0 | 0% |
| bioengineer.org | 1 | 0 | 0% |
| business-standard.com | 1 | 0 | 0% |
| businessgreen.com | 1 | 0 | 0% |
| businessnews.com.au | 1 | 0 | 0% |

## Drift — last 12 weeks

| Week ending | Pooled recall | Floor recall |
|---|---:|---:|
| 2026-06-13 | 7% | 2% |
| 2026-06-20 | 14% | 0% |
| 2026-06-27 | 12% | 2% |
| 2026-07-04 | 19% | 11% |
| 2026-07-11 | 6% | 3% |
| 2026-07-18 | 18% | 5% |
| 2026-07-25 | 11% | 10% |
| 2026-08-01 | 13% | 0% |
| 2026-08-22 | 22% | 13% |
| 2026-08-29 | 12% | 0% |
| 2026-09-05 | 14% | 7% |
| 2026-10-24 | 8% | 2% |

_— Auto-audit_