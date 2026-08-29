# CCS recall audit — week ending 2026-08-29 — pooled recall 12%

## Headline metrics

- **Pooled recall** (A ∩ U / U): **12%**  (14 of 118)
- **Precision** (adjudicated relevant items / production items): **100%**
- **Decision-relevant recall**: **12%**
- **Adjudicated high-priority floor recall** (A ∩ B★ / B★): **0%**  (0 of 47)
- **Experimental Chapman diagnostic** (median of 2 pair-estimates): **3%** — not an authoritative absolute-recall estimate

## Sampler sizes

| Sampler | Items |
|---|---:|
| A · Production routine | 16 |
| B · RSS floor | 47 |
| C · Google Alerts | 69 |
| D · Shadow LLM | 0 |
| E · Shelly Murrell digest | 0 |
| F · IEAGHG Weekly News | 0 |
| A★ · Production, search-only subset (used for Chapman) | 6 |
| **Union U** | **118** |

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

_Capture side restricted to A★ (search-only, 6 items) — full A ingests the RSS floor and Google Alerts feeds, so it is not independent of samplers B/C._
_Diagnostic only: sampler independence and equal catchability are violated, so this must not be read as authoritative absolute recall._

| Pair | Overlap | Estimated N |
|---|---:|---:|
| A★ × B (RSS floor) | 0 | 335 |
| A★ × C (Google Alerts) | 0 | 489 |

## Top missed items (104 total)

## Recall by geography

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| Unclassified | 118 | 14 | 12% |

## Recall by source class

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| media/newsletter | 117 | 14 | 12% |
| primary/official | 1 | 0 | 0% |

## Recall by content type

| Group | Adjudicated relevant | Captured | Recall |
|---|---:|---:|---:|
| unclassified | 118 | 14 | 12% |

- **ITB Petroleum Engineering Students Present Economical and Forward-Looking CCS Well ...** — ac.id · found via _C_ · [link](https://itb.ac.id/news/itb-petroleum-engineering-students-present-economical-and-forward-looking-ccs-well-development-strategy-at-international-conference/63748)
- **Direct air capture supports sustainable methanol production in water-limited regions - Bioengineer.org** — bioengineer.org · found via _B_ · [link](https://news.google.com/rss/articles/CBMirgFBVV95cUxQYTd3LVJOdkctb3g5SFJaaDZKbnRDSWNSWGctLXZLd2lfNTZIT05XRkRNUFBWWkNXWmhaM2E5RjAydGRHVndWbkx0X0hGUlVral9MMFZkQ1hwQWRtUzFxR0hhVTRCelRNT0w4Q3BXb3U4Rnc0QkFmRHlWVzBQQ0VRalNJdVJkR0dVWHlEaGtmOHpiT18wWldKZU9vM2lSUHpGYmZ6UG5EU1lhTXgyRVE?oc=5)
- **What has changed for carbon capture and storage in Brazil? - BNamericas** — bnamericas.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMijwFBVV95cUxPN2hmNFlYc0tObF9DZG40YXdmbmtEYjFuXzdSQ0FSdEx0YV9wdWtmN2l1N3hDZndGdUJZaUUzU01hNmc4OFRWeDZPX2xSa1E3dG5BeHNHNzRscWs5aUQyalh5R05fclkyQ295MG1EcWxBSVRpbVpETUs2enoxZjFzd1pxN045TkJseVY1U2dNTQ?oc=5)
- **Jan De Nul enters CCS market with North Sea pipeline protection contract** — breakbulk.news · found via _C_ · [link](https://breakbulk.news/jan-de-nul-enters-ccs-market-with-north-sea-pipeline-protection-contract)
- **Aramco Chases Cheaper Air-to-Carbon Capture** — carbon-capture-conference.com · found via _C_ · [link](https://www.middleeast.carbon-capture-conference.com/news/aramco-chases-cheaper-air-to-carbon-capture)
- **Carbon Capture Journal - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiwwFBVV95cUxNMDdLOFNHMWd4UWdwV3NYY2kyaHRpYzlzZjdRRklJSkJGcDh5c0JSdnpwdmFWUTF3RmwwNDVZZFc0c3NHWTNtYUVMblNHSnpCMkp4UU1nVFRGY28xbzBoYVkxVEt1LTdmQWxCMzhFckxjUEJCRHJpOVZ5ZU5IWlNUTno0alQ2QWFHMENJTVFzUUtqZXlESXpHRzZXRjRYdlNWeTVGbHNmWlpCbmJ3UTUyNFNHTW9iY2psRGpoWm9uazR1aFk?oc=5)
- **Cosmo Oil and KEPCO to design CO2 capture and marine transport - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMixgFBVV95cUxPTGowMlhxME1HbDF3aFlQelhsOVFOVGJLa0gtdzktTFhUeGpmV1Njc21kemZmcVNBZDRXc050R0VpU3IwVU5lbVRyaC1UVkhoMUp1RWN3Ulh3RkJOZUJTWi1PYm0yTk5FVlNYT01ZZkRjWW5TWXBBZU5jTHhON290WWR1Z0luTjB0dUFVMHJodWkwWE9mVlZ6UEpVRklMX2R5UGJyNEpVejlRc0lZd1I4T05zd3hTVjFIRmxzR2dvVFB0eW9hM3c?oc=5)
- **Höganäs AB and Öresundskraft sign agreement on carbon removals - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiwgFBVV95cUxORFM4cm4tTmRIUFNZWkUyMl9WN1MtZWY5VEFuc3o0UjNVVmJXQkppNVczcm9mSHBiTE5WbF80NXJQUkNLVjRXODNqdTJiNGlhaXhsYTQ3aXJKbmpNbkpkNDRnVlBjUTZNX05QZnhzUXpEeUc3OW8tazJxS3RoVVQ4bVdiU0l6SWFtUUtDS3ZTc2VlXzdHVkYxcUNzMzV6Skh0NjF5cXVmS0pXSnh4eFhCYV9pY2pFZnBBbTZaS2pSbUs3QQ?oc=5)
- **MHI extends compact CO2 capture system to larger size - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiugFBVV95cUxQRjRGclpxUXJ6VzZHSUlaNUhzYkUxa2oxWWEwYXo1OWM3ZWRjYlFHV2l5LXFuNloxYkRIOF9tSjU4YjNpRzZSWjIwLUZjazYwd2pyQjRqZXF6c2Z5N2lGb3plRzU5dDhzMnlzYUY1RVJsTm14aEZxT283a05HQm5kbFAtWUpmWGs4Zmx4OFhGTWE1dENONDRjUk1lWEZhd1RzRVVFVDJYU1VPTkM4LU81LXhMTHR5OEw5Umc?oc=5)
- **Mantel raises cash to scale commercial carbon capture deployment - Carbon Capture Journal** — carboncapturejournal.com · found via _B_ · [link](https://news.google.com/rss/articles/CBMiyAFBVV95cUxOcTJacHJfbzBDcUhmV3BwcFU0WnVEQUItdnFCNVFFOGs5ZjZ5b3h4bkZsc3B6VFdJbkkwREc1TEhIMk8xeGNEU0tBSlZScE1ublo5Mk5jVU5TZ3BYX29WTTVBaE5GdEVPTkZZRHZQTVZvUWFYVEJOU2MtOTF1aGVaaWJYTGhqUzdBWTBFMnY0ZGswV1pvMnNNTEtiSGMwcUxnY3JpRGhCX19BYzkyZHFJSlZRd2FZRHBJbDdFcFJUTUVyZExQdDF0Mw?oc=5)

## Source-coverage matrix

| Source | Published (B+C+D+E) | Captured by A | Capture rate |
|---|---:|---:|---:|
| carbonherald.com | 23 | 0 | 0% |
| carboncapturejournal.com | 7 | 0 | 0% |
| climeworks.com | 4 | 0 | 0% |
| petromindo.com | 4 | 0 | 0% |
| energynewsbulletin.net | 3 | 2 | 67% |
| carboncredits.com | 2 | 0 | 0% |
| ecobiz.asia | 2 | 0 | 0% |
| energiesmedia.com | 2 | 0 | 0% |
| fuelcellsworks.com | 2 | 0 | 0% |
| gasworld.com | 2 | 0 | 0% |
| globalccsinstitute.com | 2 | 0 | 0% |
| oceannews.com | 2 | 1 | 50% |
| offshore-energy.biz | 2 | 0 | 0% |
| pipeline-journal.net | 2 | 1 | 50% |
| tipranks.com | 2 | 0 | 0% |
| ac.id | 1 | 0 | 0% |
| bioengineer.org | 1 | 0 | 0% |
| bnamericas.com | 1 | 0 | 0% |
| breakbulk.news | 1 | 0 | 0% |
| carbon-capture-conference.com | 1 | 0 | 0% |
| carbon-pulse.com | 1 | 1 | 100% |
| ccsassociation.org | 1 | 0 | 0% |
| chemengonline.com | 1 | 0 | 0% |
| chemxplore.com | 1 | 0 | 0% |
| dayakdaily.com | 1 | 1 | 100% |

## Drift — last 12 weeks

| Week ending | Pooled recall | Floor recall |
|---|---:|---:|
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
| 2026-08-29 | 12% | 0% |

_— Auto-audit_