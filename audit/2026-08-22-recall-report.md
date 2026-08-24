# CCS recall audit — week ending 2026-08-22 — pooled recall 22%

## Headline metrics

- **Pooled recall** (A ∩ U / U): **22%**  (18 of 82)
- **Precision** (adjudicated relevant items / production items): **100%**
- **Decision-relevant recall**: **22%**
- **Adjudicated high-priority floor recall** (A ∩ B★ / B★): **13%**  (4 of 31)
- **Experimental Chapman diagnostic** (median of 2 pair-estimates): **4%** — not an authoritative absolute-recall estimate

## Sampler sizes

| Sampler | Items |
|---|---:|
| A · Production routine | 19 |
| B · RSS floor | 31 |
| C · Google Alerts | 50 |
| D · Shadow LLM | 0 |
| E · Shelly Murrell digest | 0 |
| F · IEAGHG Weekly News | 0 |
| A★ · Production, search-only subset (used for Chapman) | 9 |
| **Union U** | **82** |

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

_Capture side restricted to A★ (search-only, 9 items) — full A ingests the RSS floor and Google Alerts feeds, so it is not independent of samplers B/C._
_Diagnostic only: sampler independence and equal catchability are violated, so this must not be read as authoritative absolute recall._

| Pair | Overlap | Estimated N |
|---|---:|---:|
| A★ × B (RSS floor) | 4 | 63 |
| A★ × C (Google Alerts) | 0 | 509 |

## Top missed items (64 total)

## Recall by geography

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| Unclassified | 82 | 18 | 22% |

## Recall by source class

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| media/newsletter | 79 | 18 | 23% |
| primary/official | 3 | 0 | 0% |

## Recall by content type

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| unclassified | 82 | 18 | 22% |

- **Europe's largest biomass burial carbon removal deal signed – Bioenergy Insight Magazine** — bioenergy-news.com · found via _C_ · [link](https://bioenergy-news.com/news/europes-largest-biomass-burial-carbon-removal-deal-signed)
- **Eni expands partnership with Algerian oil company on emission reductions, CO2 removal** — carbon-pulse.com · found via _C_ · [link](https://carbon-pulse.com/542523/?site=cpp)
- **Petrobras signs drilling deal for Rio CCS pilot targeting 100k tCO2 annually - Carbon Pulse** — carbon-pulse.com · found via _C_ · [link](https://carbon-pulse.com/543020/)
- **Carbon Capture Journal - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiuAFBVV95cUxPZUVKV2ZrQWdwQS1kUzVONEJSNXA0SmcxSzc2cUNvTy0teDV6aU5YMUxmYlJKUVdMbzNmV0xESHRmLU53UmxkMDg5RTNTTDJ5ZHA4YUx0TTVZYnNFOGlnU3VlYkxKdzRoSjBaZ0ZvNU9UQlIxdmNtWTZ5bllmMHczUENFVi1oOGM5cmpxNGphNmtVeU1PVUlKYjNqQ1Jab18wQkhSTnE1a08ycFJ1Mzl2aTEtUTh4cnN2?oc=5)
- **Government of Quebec approves carbon storage pilot application - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMixgFBVV95cUxNZEpZX1pISWR0UTMwQWk3SFpzMEZJS1B0ODVBNUc3ZVdjMThSR1ZSYkMwQlU0eGZJYzZnU3U4MmFNcHlFUGNIdGtOT2EyOTVCczBYUXpCQVM3RTdWTlZzM3pFMGcxS2s1dHVEbFRKdEhZZ0cxUkR1MnJUdjB0dERicDg2OVA4V0Fmai1RdnZERkhwZERWWlJDRWV0OWRQaDZOTV9HN3k5RnpWcnF6cW5oZ3lGMVJYOWE4Vk1yZjJOZVluMlZLX3c?oc=5)
- **JAPEX drilling second well for Tomakomai CCS Project - Carbon Capture Journal** — carboncapturejournal.com · found via _C_ · [link](https://www.carboncapturejournal.com/news/japex-drilling-second-well-for-tomakomai-ccs-project/7378.aspx?Category=all)
- **Scientists use AI to find new more efficient carbon capture materials - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMizwFBVV95cUxPQzZoYlhNX01qc1VhaUdLSDk5b29zSW81cTRJZVBfUnZUMUM4YVR5VHgxSF9KV0V1OG5qQkVZaF9fLVRyQXZFQm9iV0t6dGNGbHEzSk9RcFhlTmdRaHBTajF0WVNiZmNoczlrYWtpdEd5a29IRjdRSGJqM1hPd3R5WmljaFZVYnRYOGZaMXJGRTl2N18wUUdybktHT1FKRFRDQWRfcXk0Ui03SHAwOG84cUdlbm5wMDdEQnY1Xy1BRVRxamtsal9lREF1ZUZlU0k?oc=5)
- **Canadian Oil Sands Producers Target Late 2027 Decision On Pathways CCS Project** — carbonherald.com · found via _C_ · [link](https://carbonherald.com/canadian-oil-sands-producers-target-late-2027-decision-on-pathways-ccs-project/)
- **CapChar Celebrates First Commercial Biochar Tech Deployment** — carbonherald.com · found via _B_ · [link](https://carbonherald.com/capchar-celebrates-first-commercial-biochar-tech-deployment/?utm_source=rss&utm_medium=rss&utm_campaign=capchar-celebrates-first-commercial-biochar-tech-deployment)
- **CapMan And FSC I&P Partner To Improve Measurement Of Forest Biodiversity Outcomes** — carbonherald.com · found via _B_ · [link](https://carbonherald.com/capman-and-fsc-ip-partner-to-improve-measurement-of-forest-biodiversity-outcomes/?utm_source=rss&utm_medium=rss&utm_campaign=capman-and-fsc-ip-partner-to-improve-measurement-of-forest-biodiversity-outcomes)

## Source-coverage matrix

| Source | Published (B+C+D+E) | Captured by A | Capture rate |
|---|---:|---:|---:|
| carbonherald.com | 18 | 5 | 28% |
| carbon-pulse.com | 4 | 2 | 50% |
| carboncapturejournal.com | 4 | 0 | 0% |
| ccsassociation.org | 2 | 0 | 0% |
| drillingcontractor.org | 2 | 0 | 0% |
| energy.gov | 2 | 0 | 0% |
| energynewsbulletin.net | 2 | 0 | 0% |
| energynow.ca | 2 | 1 | 50% |
| eurekalert.org | 2 | 0 | 0% |
| gasworld.com | 2 | 1 | 50% |
| upstreamonline.com | 2 | 1 | 50% |
| bioenergy-news.com | 1 | 0 | 0% |
| caixinglobal.com | 1 | 1 | 100% |
| chemxplore.com | 1 | 0 | 0% |
| climeworks.com | 1 | 0 | 0% |
| co2crc.com.au | 1 | 0 | 0% |
| deeside.com | 1 | 1 | 100% |
| energate-messenger.com | 1 | 0 | 0% |
| energy-pedia.com | 1 | 0 | 0% |
| energyindepth.org | 1 | 0 | 0% |
| energyintel.com | 1 | 0 | 0% |
| energyvoice.com | 1 | 0 | 0% |
| esgnews.earth | 1 | 0 | 0% |
| esgtoday.com | 1 | 0 | 0% |
| gastopowerjournal.com | 1 | 1 | 100% |

## Drift — last 12 weeks

| Week ending | Pooled recall | Floor recall |
|---|---:|---:|
| 2026-05-27 | 0% | 0% |
| 2026-05-30 | 20% | 0% |
| 2026-06-06 | 13% | 0% |
| 2026-06-13 | 7% | 2% |
| 2026-06-20 | 14% | 0% |
| 2026-06-27 | 12% | 2% |
| 2026-07-04 | 19% | 11% |
| 2026-07-11 | 6% | 3% |
| 2026-07-18 | 18% | 5% |
| 2026-07-25 | 11% | 10% |
| 2026-08-01 | 13% | 0% |
| 2026-08-22 | 22% | 13% |

_— Auto-audit_