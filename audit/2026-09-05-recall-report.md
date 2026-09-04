# CCS recall audit — week ending 2026-09-05 — pooled recall 14%

## Headline metrics

- **Pooled recall** (A ∩ U / U): **14%**  (10 of 74)
- **Precision** (adjudicated relevant items / production items): **100%**
- **Decision-relevant recall**: **14%**
- **Adjudicated high-priority floor recall** (A ∩ B★ / B★): **7%**  (2 of 30)
- **Experimental Chapman diagnostic** (median of 2 pair-estimates): **13%** — not an authoritative absolute-recall estimate

## Sampler sizes

| Sampler | Items |
|---|---:|
| A · Production routine | 13 |
| B · RSS floor | 30 |
| C · Google Alerts | 49 |
| D · Shadow LLM | 0 |
| E · Shelly Murrell digest | 0 |
| F · IEAGHG Weekly News | 0 |
| A★ · Production, search-only subset (used for Chapman) | 5 |
| **Union U** | **74** |

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

_Capture side restricted to A★ (search-only, 5 items) — full A ingests the RSS floor and Google Alerts feeds, so it is not independent of samplers B/C._
_Diagnostic only: sampler independence and equal catchability are violated, so this must not be read as authoritative absolute recall._

| Pair | Overlap | Estimated N |
|---|---:|---:|
| A★ × B (RSS floor) | 2 | 61 |
| A★ × C (Google Alerts) | 2 | 99 |

## Top missed items (64 total)

## Recall by geography

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| Unclassified | 74 | 10 | 14% |

## Recall by source class

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| media/newsletter | 72 | 10 | 14% |
| primary/official | 2 | 0 | 0% |

## Recall by content type

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| unclassified | 74 | 10 | 14% |

- **Avnos’ Largest Hybrid Direct Air Capture Deployment Enters Operations - 01net** — 01net.it · found via _B_ · [link](https://news.google.com/rss/articles/CBMilAFBVV95cUxQRzdGUTBnZFpVTjVrUUZ4eEprdHp0VUp3T1ZyaXB2a1NUdlE1NzZwRHB2dV84ZnhaSmhEUFFqNGNfbTRsTWVNVDJGZTEtYl9PUVp0Wno1Uk1keGtwQzhaUnpncG1KMUVheFpJdUNGSDR1OS0xdExPcUFFNTloZ1ZNNkZ5blhOZ0c1N3JUbVlBMW9hclNB?oc=5)
- **Climate authority questions viability of short-term carbon credits - AFR** — afr.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiuwFBVV95cUxPNmM4RGM4TjlYR2lKempjZUhfWVpmLTNVQTR6WnN3b0UwQ0lFcTNBbnhiUjAxRjBOLUJFb2J5d2dMOS00RHpMQU5nZHpub1hiOVR1OENBUWdjOHVZNlktM3FtXzBVMG04NGk2T081MjBGbXk5a0lKbHM3NUl4OHBCZnVJUjZCbnI1WGZFWlhpQ2NfUzNaeWVCUGFVU3FvTGRyUkhvUVNkemNpcUtTRjRDVnByc0lEMktBZ25Z?oc=5)
- **Pertamina Eyes Regional CCS Hub Role - AsiaToday.id** — asiatoday.id · found via _C_ · [link](https://asiatoday.id/read/pertamina-eyes-regional-ccs-hub-role)
- **EU should start securing international carbon credits well before 2036, researchers say** — carbon-pulse.com · found via _C_ · [link](https://carbon-pulse.com/545908/?site=cpp)
- **Carbon Capture Journal - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMi1gFBVV95cUxNNHp3b09uWEt0S2NlRGdydVkxWHpDYjFLWUV1WklLM2wtajlXRFFEMVNuR3pualIxZ1ktZ21aR3NMQUVfOThObGlweC0wZlJXNkdJV3FtNXFNVkV4R3hGU3czaXpqLVVJZ1BhRi1OaDh3dm1lV2EzakVuVF9Bb2ZON2lkeU1iVUxEQ0RoSGhFMEJXTFZsRU84WXlOQk5CdXZza1BacDZmRE5qXzRDZ0dEV19VSmFoSkJESmgzaGc3TTQtWkxPem1XOURuZ3ZrbFBzRUtYRnVR?oc=5)
- **INPEX begins CO2 injection at Kashiwazaki Hydrogen Park - Carbon Capture Journal** — carboncapturejournal.com · found via _C_ · [link](https://www.carboncapturejournal.com/news/inpex-begins-co2-injection-at-kashiwazaki-hydrogen-park/7399.aspx?Category=all)
- **LR: Applying Onboard Carbon Capture and Storage to Ships - carboncapturejournal.com** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMivAFBVV95cUxNa0I4QTVYOEQtTjVSQkF0VDZRQm5wWHo2R09FQjNLbnRvMExJNlhKNE5VNzRyUVR6d3ZBRS00YldCNUxpZ3cteXMweHpSYjFjbl9NWVZLNDdDRE1JcEdxVC13V3JacG02T1pwR2VtMjhMeFpkYmNWYWkxZ0xsRVJzQnpsYmVEaTdHSFBuNmFZZFQxRVVGMEVaQ3VoaDhtcm5aYzJmS0EtakVicGpCN0pNSWNvUVdlSlZYOHlmTA?oc=5)
- **CF Industries, JERA and Mitsui Break Ground on $3.7 Billion Low-Carbon Ammonia Plant in ...** — carboncredits.com · found via _C_ · [link](https://carboncredits.com/cf-industries-jera-and-mitsui-break-ground-on-3-7-billion-low-carbon-ammonia-plant-in-louisiana/)
- **Japan Advances Maritime CCS Hub to Ship 3.43M Tons of CO2 a Year - CarbonCredits.com** — carboncredits.com · found via _C_ · [link](https://carboncredits.com/japan-3-43m-ton-co2-shipping-hub-ccs/)
- **Alberta Allocates $20M To Scale Hydrogen And Carbon Capture** — carbonherald.com · found via _B_ · [link](https://carbonherald.com/alberta-allocates-20m-to-scale-hydrogen-and-carbon-capture/?utm_source=rss&utm_medium=rss&utm_campaign=alberta-allocates-20m-to-scale-hydrogen-and-carbon-capture)

## Source-coverage matrix

| Source | Published (B+C+D+E) | Captured by A | Capture rate |
|---|---:|---:|---:|
| carbonherald.com | 17 | 2 | 12% |
| gasworld.com | 5 | 1 | 20% |
| petromindo.com | 4 | 1 | 25% |
| carboncapturejournal.com | 3 | 0 | 0% |
| carboncredits.com | 2 | 0 | 0% |
| ecobiz.asia | 2 | 2 | 100% |
| offshore-energy.biz | 2 | 0 | 0% |
| upstreamonline.com | 2 | 0 | 0% |
| 01net.it | 1 | 0 | 0% |
| afr.com | 1 | 0 | 0% |
| asiatoday.id | 1 | 0 | 0% |
| carbon-pulse.com | 1 | 0 | 0% |
| ccsassociation.org | 1 | 0 | 0% |
| crikey.com.au | 1 | 1 | 100% |
| cyprusshippingnews.com | 1 | 0 | 0% |
| endswasteandbioenergy.com | 1 | 0 | 0% |
| energynewsbulletin.net | 1 | 1 | 100% |
| energyvoice.com | 1 | 0 | 0% |
| esgnews.earth | 1 | 0 | 0% |
| europa.eu | 1 | 0 | 0% |
| fuelcellsworks.com | 1 | 0 | 0% |
| fxempire.com | 1 | 0 | 0% |
| globo.com | 1 | 0 | 0% |
| hellenicshippingnews.com | 1 | 0 | 0% |
| hklaw.com | 1 | 0 | 0% |

## Drift — last 12 weeks

| Week ending | Pooled recall | Floor recall |
|---|---:|---:|
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
| 2026-08-29 | 12% | 0% |
| 2026-09-05 | 14% | 7% |

_— Auto-audit_