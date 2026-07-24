# CCS recall audit — week ending 2026-07-25 — pooled recall 11%

## Headline metrics

- **Pooled recall** (A ∩ U / U): **11%**  (14 of 128)
- **Floor recall** (A ∩ B / B): **10%**  (5 of 49)
- **Estimated absolute recall** (Chapman, median of 4 pair-estimates): **6%**

## Sampler sizes

| Sampler | Items |
|---|---:|
| A · Production routine | 14 |
| B · RSS floor | 49 |
| C · Google Alerts | 59 |
| D · Shadow LLM | 16 |
| E · Shelly Murrell digest | 18 |
| F · IEAGHG Weekly News | 0 |
| A★ · Production, search-only subset (used for Chapman) | 12 |
| **Union U** | **128** |

_7 junk domains excluded from all samplers (config/junk_domains.txt)._

## Sampler run coverage

| Sampler | Ran (5 weekdays) | Missing |
|---|---|---|
| B · RSS floor | 5/5 | — |
| A · Production routine | 5/5 | — |
| D · Shadow LLM | 5/5 | — |
| C · Google Alerts | 5/5 | — |

_Public holidays are legitimate skips and still show as missing here._

## Chapman pair-estimates

_Capture side restricted to A★ (search-only, 12 items) — full A ingests the RSS floor and Google Alerts feeds, so it is not independent of samplers B/C._

| Pair | Overlap | Estimated N |
|---|---:|---:|
| A★ × B (RSS floor) | 4 | 129 |
| A★ × C (Google Alerts) | 2 | 259 |
| A★ × D (Shadow LLM) | 4 | 43 |
| A★ × E (Shelly Murrell digest) | 0 | 246 |

## Top missed items (114 total)

- **Puro.earth Certifies Inherit Carbon Solutions for First Biogas BECCS Carbon Removal in Norway** — biochartoday.com · found via _C_ · [link](https://biochartoday.com/news/puro-earth-certifies-inherit-carbon-solutions-for-first-biogas-beccs-carbon-removal-in-norway/)
- **Metropolitan CCS did not respond - Business and Human Rights Centre** — business-humanrights.org · found via _C_ · [link](https://business-humanrights.org/en/latest-news/metropolitan-ccs-did-not-respond)
- **Viking CCS Wins UK Development Funding — A Step Forward, Not a Final Decision** — captaindrawdown.com · found via _C_ · [link](https://captaindrawdown.com/posts/uk-greenlights-development-funding-for-viking-ccs-project/)
- **CP Daily News Ticker: 21 July 2026** — carbon-pulse.com · found via _D_ · [link](https://carbon-pulse.com/533429)
- **Adani partners with Dioxycle for low carbon chemicals production - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiyAFBVV95cUxNdmVRdXZCTGQ2TVNXaUpwR3dPQjQyMm9yc3ota3puOGxjVDRyMUxybHBiNHA2VkVfYkQ4d1pUQWdDNnpzWkNiUWxMSTBnN1JzbUZyZFFWd3JfZFA2ZncxSkhsOV93WmdHWVE4aW52bmlFUXN3cXZwR2xvcEdtTWM2c2xUVVJWUmxvWEhGQ2ZOVkktcDhhU3BVc05DeDNTN2g0WUFncHhGcGJBVkdZd1RoUTZ4V1RKZWVhMVNlTGQ0eE01TEdNWEkzNg?oc=5)
- **Carbon Capture Journal - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMirAFBVV95cUxPVl9GbEYwV1pwZl90MlhCTV9MM1J4ckVfNWxZSzB5V29GdmhWWEdGNzdCR2tkRXQzVmhBcjg3WVNodEdYUDNIS1R5RWdRb2szbEZsU0I4dU1pc1dsdHhxTnNmNVdDeWNLNi1vTV9LMURyWmNBNkVocWlaT05ZWGlXRW1nVF94ZWlBbEdmT2diSWRsbC1kZ3FzT21lRGt4cEJZN3BTdHV2YlV4OExp?oc=5)
- **Contribution of Carbon Capture and Utilisation towards climate neutrality in the EU - carboncapturejournal.com** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMi4gFBVV95cUxPa2FGYV9RSlZPWHNsTTBsdEVZYTVFMTVOaXJEano2cElkN1psMi00Yjg1TXBiX3F3RHFuaWJuNlQtYTVPQ3I2SUFOSTJWQnJraHVMQWpkZ0tsNkIxYW5SVUtCeWkwZXVmUmsyMjU2eGFjeV9WdERJd1pieHRCWXpXV3NrWVp2cDVvRUR3UWIxRG9INm9tRTF6SjhqeWJ4aEtsUU9rblJhNHpzMkxwdXFSamluMmV3aUxQVS1CdEIxaThOX0p0cXJ1b2tJX3Rtb1lrd3ZqcFdtajdBSXJEMEs5MmtB?oc=5)
- **Development funding approved for UK Viking CCS Project - Carbon Capture Journal** — carboncapturejournal.com · found via _C_ · [link](https://www.carboncapturejournal.com/news/development-funding-approved-for-uk-viking-ccs-project/7342.aspx?Category=all)
- **EU ETS recognises onboard mineralisation capture method - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMivAFBVV95cUxQLUplMXo4YVA5T0xNNU0wV2kxWXpfdkFPa1hQLThrZDgyRXJqTHhfdFhrRXlmMjJLbWJqUndwaEhIYVBNRDZxcE15cExpYlRsLTRraklweVVIMElGcDRrN0JzcldwRW5JbkNaSGNQM2VvYXNhb2lNdjdhQVRfRmhYMnBQbGJ4TVUxMVU1NUtkUFpkTnF0Z1kydlE2X2tGVF9LYVBuazZXbm9JWHo4UGxVUy1hR0RrU1p4bVZQdw?oc=5)
- **NSTA operational guidance for carbon storage projects - carboncapturejournal.com** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiugFBVV95cUxQZkJQZHFjY0Vob0ppYjNRWWlKQU9fS0xVd3ZhWjRIYVhrNlgwNUFPU2RQLXdQZjVHXy03Rk9odjV0VUdwbEJPNHNlQXNEcHRQY0VsdzJZb1NZMWVYNXdNbXM0TVAtd2lCMGpRSnNPdmJWbmpfVW1kaXVPdHplME1PMzlFUEE0RkVra3ZEZ1FvZU00VXJPamduUDN2VlhoRGRMbmZxRVR4NjZPTDZpWWw5LWNuS3h4STlZMFE?oc=5)

## Source-coverage matrix

| Source | Published (B+C+D+E) | Captured by A | Capture rate |
|---|---:|---:|---:|
| carbonherald.com | 30 | 5 | 17% |
| list-manage.com | 11 | 0 | 0% |
| carboncapturejournal.com | 7 | 0 | 0% |
| ccsassociation.org | 6 | 0 | 0% |
| simplywall.st | 4 | 0 | 0% |
| upstreamonline.com | 4 | 1 | 25% |
| carbon-pulse.com | 2 | 1 | 50% |
| carboncredits.com | 2 | 0 | 0% |
| climeworks.com | 2 | 0 | 0% |
| decarbonfuse.com | 2 | 0 | 0% |
| esgnews.com | 2 | 0 | 0% |
| latrobevalleyexpress.com.au | 2 | 1 | 50% |
| oedigital.com | 2 | 0 | 0% |
| offshore-energy.biz | 2 | 0 | 0% |
| tipranks.com | 2 | 0 | 0% |
| biochartoday.com | 1 | 0 | 0% |
| business-humanrights.org | 1 | 0 | 0% |
| businesscheshire.co.uk | 1 | 1 | 100% |
| captaindrawdown.com | 1 | 0 | 0% |
| chinadaily.com.cn | 1 | 1 | 100% |
| co2crc.com.au | 1 | 0 | 0% |
| commodityinside.com | 1 | 0 | 0% |
| corrs.com.au | 1 | 0 | 0% |
| defence.in | 1 | 0 | 0% |
| discoveryalert.com.au | 1 | 0 | 0% |

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
| 2026-07-18 | 18% | 5% |
| 2026-07-25 | 11% | 10% |

_— Auto-audit_