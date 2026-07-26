# Curated datasets — what they are and how to read them

The four CSVs in this folder are the **source of truth** for everything on the dashboard that is
curated rather than extracted from the news corpus. The dashboard build reads them directly; there
is no JSON copy to keep in sync.

They are maintained programmatically. This file holds the part that cannot fit in a spreadsheet
row — what each column means, where the numbers came from, and what is knowingly missing. **When a
dataset changes in a way that changes what its numbers mean, update the relevant section here in the
same commit.** A figure without its caveat is worse than no figure.

Two datasets deliberately stay as JSON in the parent folder: `storage-baseline.json` (a
reconciliation waterfall and two labelled series — not a table) and `reference-baseline.json`
(nested global and regional blocks). Their caveats are rendered into the dashboard itself rather
than being maintainer notes.

**A blank cell means "not stated by the source", never zero.** The dashboard depends on this
distinction throughout: a country with no published drawdown figure must not render as having drawn
down nothing.

---

## funding-programmes.csv

Standing government CCS funding programmes — the total each government has committed, the period it
runs over, and how much has actually been awarded where a source publishes it.

This exists because the news corpus cannot answer "how much public money is behind CCS in this
country". The corpus is a rolling window of recent reporting, so a commitment made before the window
is invisible to it. Before this dataset existed the dashboard showed the UK's committed funding as
**A$8.8m** — its £21.7bn cluster programme was announced in October 2024, outside the window.

| Column | Meaning |
|---|---|
| `amount` | Headline size of the pot, in its own currency. **Not annual** unless `period_years` is 1. |
| `period_years` | Years the pot is stated to run over. The field whose absence made a 25-year programme look like this year's budget. |
| `awarded_to_date` | What has actually been awarded, contracted or paid out. Blank = no source states it. |
| `scope` | `ccs-specific` — the pot exists for CCS, its full value is CCS money. `ccs-eligible` — a broader decarbonisation pot where CCS is one eligible use; **its headline value overstates CCS funding**. |
| `status` | `announced` (stated intention) / `committed` (legislated or contracted) / `operating` (actively awarding). |

### Known gaps

- **Drawdown is published for only four programmes** (US BIL, US DAC hubs, Norway Longship,
  Flanders). Everywhere else `awarded_to_date` is blank because no source states it — including the
  UK's £21.7bn, the largest commitment here.
- **Government programmes only.** Private and corporate CCS investment is substantial and is tracked
  separately through the news corpus, labelled by funder type.
- **Coverage follows available sources, not a systematic global survey.** A country absent here may
  still have public CCS funding. Most entries come from the GCCSI 2024 country chapters, which are
  selective, plus programmes that surfaced in the news window.
- **Currency conversion uses fixed reference rates.** For multi-decade programmes the real exchange
  path will differ substantially; the A$ figures order countries against each other, they are not
  budgeting figures.
- **Japan's US$26bn is derived, not stated** — 20% of a US$130bn ten-year bond, the share the report
  says is *expected* to be earmarked for CCS. The only derived amount in the dataset.
- **The US 45Q entry has no `amount`** — it is an uncapped per-tonne credit, so it has no headline
  total. The dashboard renders this as "uncapped per-tonne credit", not as zero.

---

## funding-enrichment.csv

One row per money-carrying record in the news corpus, answering three questions the extraction
schema never asked: **who is paying**, **what the figure actually measures**, and **over what
period**. Keyed by `record_id`.

Without this, figures that are not CCS funding reach the funding totals. All of the following were
found in the live corpus.

| `basis` | Meaning |
|---|---|
| `government-funding` | A public grant, subsidy, contract-for-difference or tax-credit pot. The default meaning of "funding". |
| `private-investment` | Corporate capex, venture rounds, bank facilities, corporate programmes. |
| `project-capex` | Total build cost of a named project. Real CCS money, but a cost, not an award. |
| `supplier-contract` | Payment for goods or services *inside* a project. Already in that project's capex — counting it separately double-counts. |
| `market-aggregate` | An economy-wide or sector-wide total. Not a CCS commitment. |
| `not-ccs-funding` | A lawsuit value, an emissions budget, a merger synergy target. |
| `cancelled` | Money withdrawn or redirected. A negative signal, never summed into positive totals. |

`funder_type` is `government` / `private` / `mixed` / `none`. **Do not infer it from `org_types`** —
a government can announce money a company will spend.

`duplicate_of` links a record to the commitment it re-reports. Its amount is removed from all totals
while the record itself stays, because the news did happen.

### Known gaps

- **The overlay only covers records reviewed to date.** Money arriving afterwards is counted in full
  until classified. Every build prints the backlog, the dashboard shows a banner while any exists,
  and a test fails if the queue is non-empty.
- **Duplicate detection is manual.** The daily corpus and the GCCSI quarterlies describe the same
  events in different words, so automatic headline dedup catches none of them. Confirmed live cases:
  the Pathways Alliance network (C$16.5bn / C$16bn), India's CCUS scheme (₹20,000cr / ₹19,700cr), and
  Spain's PERTE round where a €119m award is a *subset* of a €319m total.
- **Periods are only recorded where the source states one**, which is the minority of records.
- **`project-capex` sometimes covers more than the CCS.** BP's Tangguh Ubadari is carried at its
  US$7bn whole-scheme cost, but that pairs a gas development with enhanced gas recovery and CO₂
  storage — the CCS-specific share is not broken out and the figure therefore overstates it. Where a
  capex figure bundles CCS into a larger development, say so in the row's note.

---

## project-locations.csv

Map coordinates for the CO₂ storage projects in `storage-baseline.json`. The `project` column must
match a project name in that file **exactly** — a mismatch means the pin is silently never drawn.

**Coordinates are indicative, not surveyed.** They locate the storage site (or, where noted, the
capture plant) to roughly the nearest field or town. The map renders about 40 km per pixel at the
equator, so errors of a few tens of kilometres are sub-pixel and do not affect what the map shows.
**Do not reuse these for anything needing real positional accuracy.**

---

## gccsi-countries.csv

Per-country CCS facility counts, capture capacity, national strategy status and headline carbon
price. **Generated** — rerun `scripts/gen_gccsi_countries.py` against the report PDF rather than
editing by hand.

Counts and capacity are parsed from the Global Status of CCS 2024 Section 5.0 Facilities List
(pp.57-79), the report's only full-coverage country-level dataset. The parser locates that table by
its column header rather than by page number, so a repaginated edition still works.

`capacity_mtpa` is **nameplate capture capacity as designed**, not tonnes captured or stored. For
measured injection see the Imperial College series in `storage-baseline.json`. The two must never be
added together or used interchangeably.

### Validation

Parsed totals are checked against Figure 3.1-4 (p.15), where the report states its own top-five
country counts: United States 276, United Kingdom 65, Canada 58, China 25 all reconcile exactly.
A facility is counted for its first-listed country.

### Known gaps

- **Norway parses to 27 against a stated 26.** The difference is in the source: Norway carries both
  a "Havstjerne Storage" entry and a "Wintershall Dea Havstjerne" entry at different stages, which
  the summary figure appears to treat as one project. Left visible rather than adjusted to match.
- **The source spells the United Kingdom two ways** — "United Kingdom" and, on p.70, "United
  kingdom". They are folded together; without that the UK total comes out one short.
- **Values in the Country column that are regions** ("Northern Europe") are excluded rather than
  rendered as a country.
- **Capacity is missing for facilities listed as "Under Evaluation" or as transport-and-storage
  only** (which have no capture capacity by definition). A country's capacity therefore understates
  its facility count; do not divide one into the other to infer an average project size.
- **Nameplate vs actual.** The report lists Chevron Gorgon at 4 Mtpa capture capacity (p.57) while
  its own regional chapter says ~1.6 Mtpa is actually stored (p.42). Both are the source's figures.
- **Internal inconsistency in the source.** Qatar's Ras Laffan is 2.1 Mtpa in the regional chapter
  (p.54) and 2.2 Mtpa in the facilities list (p.57). The facilities-list figure is used throughout.
- **Petrobras Santos Basin** is listed at 10.6 Mtpa capture capacity but the regional chapter reports
  13 Mt injected in 2023 — injection includes reinjected produced CO₂, so it can exceed capture
  capacity.
- **National strategy status covers Europe only** (Figure 4.4-1, p.47, read from the figure's vector
  fills rather than by eye). Asia-Pacific, the Americas and the Middle East have substantial CCS
  legislation described in prose — Japan's CCS Business Act, South Korea's CCUS Act, Indonesia's
  Presidential Regulation 14/2024, Brazil's Fuels of the Future law — but the report applies no
  comparable classification to them, so none is invented. A blank `policy_status` means **not
  assessed**, not "no policy".
- **Two readings worth a human sense-check.** Figure 4.4-1 fills the **Netherlands** as "no strategy"
  despite Porthos being under construction with an ~€86/t contract-for-difference; the figure tracks
  whether a single national strategy document exists, not how much CCS is happening. And **Iceland**
  is filled "no strategy" while p.46 lists it among countries that "adopted strategies and roadmaps"
  — a genuine source contradiction, shown as the figure has it.
- **`carbon_price` is strictly a price or per-tonne rate.** Funding pots live in
  `funding-programmes.csv`; mixing them in here once made the UK's card read "Carbon price: £21.7bn
  over 25 years", which is a category error.
