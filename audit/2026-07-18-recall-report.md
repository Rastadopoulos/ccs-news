# CCS recall audit — week ending 2026-07-18 — pooled recall 18%

## Headline metrics

- **Pooled recall** (A ∩ U / U): **18%**  (19 of 107)
- **Floor recall** (A ∩ B / B): **5%**  (2 of 44)
- **Estimated absolute recall** (Chapman, median of 4 pair-estimates): **9%**

## Sampler sizes

| Sampler | Items |
|---|---:|
| A · Production routine | 21 |
| B · RSS floor | 44 |
| C · Google Alerts | 63 |
| D · Shadow LLM | 10 |
| E · Shelly Murrell digest | 0 |
| F · IEAGHG Weekly News | 9 |
| A★ · Production, search-only subset (used for Chapman) | 4 |
| **Union U** | **107** |

_7 junk domains excluded from all samplers (config/junk_domains.txt)._

## Sampler run coverage

| Sampler | Ran (5 weekdays) | Missing |
|---|---|---|
| B · RSS floor | 5/5 | — |
| A · Production routine | 5/5 | — |
| D · Shadow LLM | 4/5 | 2026-07-13 |
| C · Google Alerts | 5/5 | — |

_Public holidays are legitimate skips and still show as missing here._

## Chapman pair-estimates

_Capture side restricted to A★ (search-only, 4 items) — full A ingests the RSS floor and Google Alerts feeds, so it is not independent of samplers B/C._

| Pair | Overlap | Estimated N |
|---|---:|---:|
| A★ × B (RSS floor) | 0 | 224 |
| A★ × C (Google Alerts) | 0 | 319 |
| A★ × D (Shadow LLM) | 0 | 54 |
| A★ × F (IEAGHG Weekly News) | 1 | 24 |

## Top missed items (88 total)

- **Louisiana set to overtake California in renewable diesel, SAF capacity as carbon capture gains momentum** — bioenergytimes.com · found via _C_ · [link](https://bioenergytimes.com/louisiana-set-to-overtake-california-in-renewable-diesel-saf-capacity-as-carbon-capture-gains-momentum)
- **LTi Vessco Secures Major Carbon Capture Vessel Contract For UK Decarbonisation Project** — businesscheshire.co.uk · found via _C_ · [link](https://www.businesscheshire.co.uk/2026/07/17/lti-vessco-secures-major-carbon-capture-vessel-contract-for-uk-decarbonisation-project/)
- **Viking CCS Wins UK Development Funding — A Step Forward, Not a Final Decision** — captaindrawdown.com · found via _C_ · [link](https://captaindrawdown.com/posts/uk-greenlights-development-funding-for-viking-ccs-project/)
- **CATF: how the EU can avoid an international carbon credit deficit** — carbon-pulse.com · found via _F_ · [link](https://carbon-pulse.com/530213)
- **Development funding approved for UK Viking CCS Project - Carbon Capture Journal** — carboncapturejournal.com · found via _C_ · [link](https://www.carboncapturejournal.com/news/development-funding-approved-for-uk-viking-ccs-project/7342.aspx?Category=all)
- **Nuada and Idex partner on CO2 capture project in France - carboncapturejournal.com** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMivAFBVV95cUxOZ011YmJzY01GczFzNkFGMkxxVmRLMDh4LUdUUWI4RUJvczJGbmNLUUFiRzB6emk2QV9Sa2NjX0pBYjQzUW5WWW9nTk1ybWpzR0JNUS1oTTkxbUlFLU14TlA1Yy1MTzd0VmR6QUlBa3Q1cGE1MGF3ZHk0X01WX25uTjFpYXNQa1FZR0g4TG43ckNIdWc4dmd5eTA2RG9QZlZWajBweENaYVlMNGlSUTFvOVpwLXdYWXljbmxELQ?oc=5)
- **Gevo Expands Carbon Credit Business as Low-Carbon Fuel Growth Boosts 2026 Outlook** — carboncredits.com · found via _C_ · [link](https://carboncredits.com/gevo-expands-carbon-credit-business-as-low-carbon-fuel-growth-boosts-2026-outlook/)
- **Saudi Aramco and Spiritus Join Forces to Cut Direct Air Capture Costs and Scale Carbon Removal - CarbonCredits.com** — carboncredits.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiggFBVV95cUxNSEdvZ1A5SDc3b0x6Y09KZFhGbUVoQmZKTnAtME9xRS1QeWRLeU5OODJBVEtoU2UzbVhuV2w3czRzai1mZ3RZR3l6NTJpLW9mSWM3bDhhcGFkUk9CMjhiaktKcy13QXI0NEZKV1I4b29UWXQ4ek5nMXE0SnB2WUMxcGFn?oc=5)
- **Airhive Acquires Carbyon to Forge European Direct Air Capture Powerhouse** — carbonherald.com · found via _B_ · [link](https://carbonherald.com/airhive-acquires-carbyon-to-forge-european-direct-air-capture-powerhouse/?utm_source=rss&utm_medium=rss&utm_campaign=airhive-acquires-carbyon-to-forge-european-direct-air-capture-powerhouse)
- **Arrhenius AG To Scale Microalage-Centered BiCRS With New Seed Funding** — carbonherald.com · found via _B_ · [link](https://carbonherald.com/arrhenius-ag-to-scale-microalage-centered-bicrs-with-new-seed-funding/?utm_source=rss&utm_medium=rss&utm_campaign=arrhenius-ag-to-scale-microalage-centered-bicrs-with-new-seed-funding)

## Source-coverage matrix

| Source | Published (B+C+D+E) | Captured by A | Capture rate |
|---|---:|---:|---:|
| carbonherald.com | 22 | 2 | 9% |
| qcintel.com | 4 | 2 | 50% |
| upstreamonline.com | 4 | 1 | 25% |
| gasworld.com | 3 | 1 | 33% |
| list-manage.com | 3 | 0 | 0% |
| carbon-pulse.com | 2 | 1 | 50% |
| carboncapturejournal.com | 2 | 0 | 0% |
| carboncredits.com | 2 | 0 | 0% |
| ccsassociation.org | 2 | 0 | 0% |
| discoveryalert.com.au | 2 | 0 | 0% |
| einnews.com | 2 | 0 | 0% |
| eurekalert.org | 2 | 0 | 0% |
| globalccsinstitute.com | 2 | 0 | 0% |
| globenewswire.com | 2 | 0 | 0% |
| marketscreener.com | 2 | 0 | 0% |
| theguardian.com | 2 | 0 | 0% |
| tipranks.com | 2 | 0 | 0% |
| bioenergytimes.com | 1 | 0 | 0% |
| bloomberg.com | 1 | 1 | 100% |
| businesscheshire.co.uk | 1 | 0 | 0% |
| captaindrawdown.com | 1 | 0 | 0% |
| cbc.ca | 1 | 0 | 0% |
| climeworks.com | 1 | 0 | 0% |
| contexte.com | 1 | 0 | 0% |
| endswasteandbioenergy.com | 1 | 0 | 0% |

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

_— Auto-audit_