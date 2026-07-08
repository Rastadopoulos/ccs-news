# Extraction Spec — briefing prose → structured facts

Contract for turning each `YYYY-MM-DD-ccs-briefing.md` into structured records.
Every extractor (the one-time backfill AND the daily routine going forward) MUST follow this exactly
so records are consistent and mergeable. Output is **JSONL** — one JSON object per line, one line per
briefing *item*.

## Golden rules

1. **One record per news item** (a bullet under a section). Do not invent items; do not merge items.
2. **Never fabricate a figure.** If no money amount is stated, leave `amount` null. Do not guess.
3. **Extract only what the text supports.** Every field is a faithful read of the item's prose.
4. **`item_status`** distinguishes fresh news from recycled context:
   - `fresh` — a normal in-window item under Projects/Policy/Technology/Markets/Media.
   - `radar` — an item under a *"Still on the radar"* / *older-context* heading. Capture it, but it is
     NOT a new commitment on this date (the dashboard excludes `radar` from time-series counts and
     only uses it to backfill context if the item never appears fresh elsewhere).
5. **Quiet/stub days** (e.g. "Quiet day", "No CCS items confirmed") produce zero `fresh` records —
   only whatever sits under *Still on the radar* as `radar`. That's expected and correct.
6. When unsure of a controlled-vocab value, pick the closest listed value and add a note in
   `extractor_note`; never invent new vocab tokens.

## Record schema (fields)

| Field | Type | Notes |
|---|---|---|
| `id` | string | `YYYY-MM-DD#NN` — briefing date + item index within that briefing (01-based). |
| `briefing_date` | string | ISO date of the briefing file. |
| `item_status` | enum | `fresh` \| `radar` (see rule 4). |
| `section` | enum | `projects` \| `policy` \| `technology` \| `markets` \| `media`. Map the briefing's headings to these five. |
| `headline` | string | The item's bolded title / first clause. Plain text, no markdown. |
| `summary` | string | The item's 1–2 sentence gist (trimmed). |
| `source` | string | Publisher(s) as stated, e.g. "Carbon Herald". |
| `pub_date` | string\|null | Item publication date if stated (ISO); else null. |
| `url` | string\|null | The item's link. |
| `region` | enum\|null | See REGIONS. Primary region of the item. |
| `countries` | string[] | ISO-ish country names involved (e.g. ["Australia","South Korea"]). Normalise per COUNTRY NOTES. |
| `organisations` | string[] | Named orgs (companies, govts, bodies). Normalise obvious variants (see ORG NOTES). |
| `org_types` | enum[] | One per org where clear, from ORG_TYPES. Order-aligned with `organisations` when possible. |
| `instrument_type` | enum | Primary instrument, from INSTRUMENT_TYPES. |
| `value_chain` | enum[] | One or more from VALUE_CHAIN. |
| `amount` | number\|null | Numeric value as stated (no currency symbol, no "million"/"bn" — expand to full units). |
| `currency` | enum\|null | ISO code from FX_RATES keys (e.g. "EUR"). null if no amount. |
| `amount_aud` | number\|null | Filled centrally at normalisation time — extractors may leave null. |
| `commitment_status` | enum | From COMMITMENT_STATUS. |
| `target_year` | number\|null | Deadline/target year for mandate/deployment items (e.g. 2030 for NZIA 50 Mtpa). |
| `capacity_mtpa` | number\|null | CO₂ capacity in Mtpa if stated (convert kt/yr → Mtpa: kt÷1000). |
| `co2crc_relevance` | enum | `high` \| `medium` \| `low` — strategic relevance to CO2CRC/CO2Tech/Australia. |
| `co2crc_note` | string\|null | One line: *why it matters* for CO2CRC/Australia. Use the briefing's own "for CO2CRC" cues when present. |
| `sentiment` | enum\|null | `positive` \| `neutral` \| `negative` — for media/social-licence items; null otherwise. |
| `tags` | string[] | Inline briefing tags: `opinion`, `paywall`, `NGO`, etc. |
| `extractor_note` | string\|null | Any ambiguity flag for later human review. |

## Controlled vocabularies

### REGIONS
`APAC` · `North America` · `Europe-UK` · `Middle East` · `China` · `India` · `Latin America` · `Africa` · `Global`
(China and India are called out separately from APAC to match the briefing's own geographic priority list.
Use `Global` for multilateral/UN/cross-region items.)

### ORG_TYPES
`OG-major` (ExxonMobil, TotalEnergies, BP, Shell, Chevron, Woodside, Air Products, Equinor, Eni…) ·
`NOC` (Petronas, Aramco, KNOC, ADNOC, INPEX…) ·
`developer` (project/tech developer: Summit, Deep Sky, Pilot Energy, Captura, Heirloom…) ·
`utility` · `government` (incl. agencies: EU Commission, DCCEEW, DOE, RVO…) ·
`multilateral` (UN, IMO, OSPAR, ASEAN…) ·
`financier` (banks, VC/CVC, funds: SMBC, Equinor Ventures, OMERS…) ·
`registry` (Verra, Gold Standard, Isometric, ICVCM, Rainbow…) ·
`industry-body` (CCSA, Global CCS Institute…) ·
`research` (universities, CO2CRC, MARIN…) ·
`startup` · `other`

### INSTRUMENT_TYPES
`policy` (regulation, law, mandate, standard, ETS/CBAM changes) ·
`grant-funding` (government grants/auctions: Innovation Fund, PERTE, RVO) ·
`tax-credit` (45Q, ITCs) ·
`carbon-credit-removal` (CDR/BECCS/DAC credit issuance, retirements, methodologies, CRCF) ·
`project-FID` (final investment decision / financial close) ·
`project-milestone` (permit, injection start, contract award, operatorship, first credits) ·
`project-cancellation` (cancelled/withdrawn/surrendered — a NEGATIVE signal) ·
`infrastructure` (T&S networks, pipelines, hubs, shipping, ports) ·
`incentive` (non-tax subsidies/support schemes) ·
`R&D` (technology development, pilots, MoUs to develop tech) ·
`M&A` (acquisitions, ownership changes) ·
`offtake` (offtake/purchase agreements) ·
`MoU-JV` (partnerships, consortia, JVs, forums) ·
`investment` (equity/VC funding rounds) ·
`litigation` (court rulings, lawsuits) ·
`other`

### VALUE_CHAIN
`capture` · `transport` · `storage` · `MMV-MRV` · `DAC` · `BECCS` · `utilisation` · `marine-CDR` · `mineralisation` · `whole-chain` · `not-applicable`

### COMMITMENT_STATUS  (drives financial-rigour weighting)
`announced` (intention/target, no money committed yet — e.g. "FID targeted 2028") ·
`allocated` (public money earmarked/awarded but not yet spent — e.g. Spain PERTE award, Flanders earmark) ·
`committed` (binding: FID reached, financial close, funding round closed, contract signed) ·
`spent` (money deployed / credits delivered / facility operating) ·
`cancelled` (cancelled/withdrawn/surrendered/at-risk — NEGATIVE signal) ·
`na` (no financial dimension — e.g. a court ruling, an opinion piece)

### FX_RATES — fixed reference rates to A$ (as of 2026-06-30; ASSUMPTION, editable)
> These are **fixed** so trendlines reflect real commitment shifts, not FX noise. Values are approximate
> reference rates and should be reviewed/corrected by Finance. The dashboard states this assumption.

```
AUD 1.000
USD 1.530
EUR 1.660
GBP 1.950
CAD 1.120
NOK 0.148
JPY 0.01040
CNY 0.2120
SGD 1.140
BRL 0.2800
INR 0.01790
AED 0.4170
SAR 0.4080
DKK 0.2230
```
`amount_aud = amount × FX_RATES[currency]`, rounded to whole A$.

## COUNTRY / ORG NOTES
- Normalise country names: "UK" → "United Kingdom"; "US"/"USA" → "United States"; "Korea" → "South Korea";
  "UAE"/"Abu Dhabi" → "United Arab Emirates" (keep emirate in `organisations` if named).
- EU-wide items: `countries: ["European Union"]`, `region: Europe-UK`.
- Multilateral items (UN, IMO): `countries: []` unless specific states are the story; `region: Global`.
- Normalise obvious org variants: "thyssenkrupp"/"thyssenkrupp Calvion" kept as stated; "Global CCS Institute"
  consistent spelling; "CCSA" (Carbon Capture & Storage Association) consistent.

## Dedup (applied centrally after extraction, NOT by extractors)
Two records are the same item if: canonical URL matches (strip tracking/safelinks, lowercase host) OR
fuzzy headline match (Jaccard ≥ 0.7 on tokenised, stopword-stripped headline) AND same primary org.
Keep the **earliest** `fresh` occurrence; drop later duplicates and `radar` copies of an item that also
appears `fresh`. Reuses the repo's existing `scripts/_canon.py` logic.

## Output location
- Backfill (one-time, all history): `dashboard/data/facts-backfill.jsonl`
- Ongoing (per daily routine): `audit/YYYY-MM-DD-facts.json` (a JSON array of that day's records)
- The dashboard builder reads BOTH, dedups, and renders.
