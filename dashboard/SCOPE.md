# CCS Intelligence Dashboard — Scope & Goals

> Status: **v1 built and populated from backfill (24 May – 8 Jul 2026); decisions below are signed off.**
> Owner: Matthias Raab (CEO, CO2CRC). This doc is the agreed intent; the build artefacts are
> `scripts/build_dashboard.py`, `dashboard/index.html`, and `dashboard/data/`.
> Items marked **[planned]** are agreed in principle but not yet built — they need a go-ahead
> because they change the dashboard or add a data source.

## 1. Why this exists (the CEO lens)

The daily CCS briefing tells us *what happened yesterday*. It does not tell us *where the world is
moving over months*. This dashboard turns ~daily briefings into a running, evidence-based read on
global CCS momentum, in service of two decisions only the CEO makes:

1. **Strategic alignment** — continuously test whether the CO2CRC and CO2Tech strategies are pointed
   at where local, regional and global CCS capital, policy and demand are actually heading.
2. **Authoritative stakeholder reporting** — give the board and senior external stakeholders
   (DCCEEW, Victorian Government, research partners, potential CO2Tech customers/investors) a
   defensible, *sourced* trend picture rather than anecdote.

## 2. Core questions the dashboard must answer

**Global trend questions**
- **Geography of commitment** — which countries/regions are committing the most CCS spending
  (A$) and capture/storage capacity (Mtpa), and how is that concentrating over time?
- **What the money funds** — split across policy, direct funding/grants, tax credits (e.g. 45Q),
  carbon-credit/removal markets (e.g. CRCF), project FIDs, infrastructure (transport, hubs, shipping),
  incentives, and R&D.
- **Who is committing** — which companies (esp. global O&G majors + NOCs), countries and regions are
  most strongly backing, incentivising, or deploying CCUS — and who is *retreating* (lease surrenders,
  cancelled FIDs, capex cuts).
- **Deployment mandates** — legislated targets/deadlines requiring CCS, and by when. See the
  completeness caveat in §5 — the news corpus surfaces these *incidentally*, not exhaustively.
- **Momentum & social licence** — direction of media sentiment and public-acceptance signals.

**Australia / CO2CRC "so what" layer (derived)**
- Benchmark Australia's commitment pace against peer jurisdictions (US 45Q, EU, UK, Norway, Japan,
  South Korea, Malaysia, MENA, China).
- Flag policy instruments maturing overseas that Australia lacks (strategic gaps / advocacy hooks).
- Track APAC neighbours (Malaysia, Japan, South Korea, Indonesia, Timor-Leste) as both competitors and
  potential cross-border storage customers relevant to Australian storage capacity.
- Surface O&G-major capital rotation into/out of CCS as an early strategic signal.
- Flag CO2Tech-relevant commercial signals: technology gaps, MMV/MRV demand, offtake/CDR demand.

## 3. What we measure

The record schema and its controlled vocabularies are defined once, authoritatively, in
[`dashboard/data/EXTRACTION_SPEC.md`](data/EXTRACTION_SPEC.md) — that file is the single source of
truth and both the one-time backfill and the daily routine follow it. Rather than restate (and drift
from) it here, the headline dimensions are:

- **Provenance** — every record links back to a dated source item; no unsourced number reaches a view.
- **Geography** — `region` (APAC / China / India / North America / Europe-UK / Middle East /
  Latin America / Africa / Global) and normalised `countries[]`.
- **Actors** — `organisations[]` with `org_types[]` (O&G-major, NOC, developer, government,
  financier, registry, industry-body, research, startup, …).
- **What it is** — `instrument_type` (incl. `project-cancellation`, `investment`, `litigation`) and
  `value_chain[]` (capture / transport / storage / MMV-MRV / DAC / BECCS / utilisation / …).
- **Money** — `amount` + `currency`, normalised to `amount_aud`; `commitment_status`
  (announced / allocated / committed / spent / cancelled / na) drives status-weighting.
- **Capacity** — `capacity_mtpa`: for CCS, tonnes matter as much as dollars. Captured for every
  item and surfaced as headline KPIs + a dedicated view (firm vs pipeline Mtpa) — see §4.7.
- **Deadlines** — `target_year` for mandate/deployment items.
- **CO2CRC lens** — `co2crc_relevance` (high/medium/low) + a one-line `co2crc_note` (*why it matters*).
- **Sentiment** — positive / neutral / negative for media & social-licence items.

## 4. Dashboard views

Built in v1 unless marked **[planned]**. Every chart is backed by the underlying sourced records.

1. **Geography league table** — committed A$ and item-count by region and top countries.
   *(Renamed from "heatmap": v1 shows ranked bars, not a choropleth. A real map is **[planned]**.)*
2. **Where the money goes** — instrument-type and value-chain breakdown (committed A$ + counts).
3. **Actors** — most-mentioned organisations; O&G-major/NOC posture tracker (advancing vs retreating).
4. **Deployment-mandate tracker** — dated legislated targets/deadlines surfaced from policy items
   (see §5 completeness caveat). A curated authoritative reference layer (IEA/GCCSI/NDC) is **[planned]**.
5. **Australia benchmark panel** — Australia vs peers; Australia item feed; APAC cross-border watch.
6. **Momentum & social licence** — weekly newsflow and committed-A$ trend; media-sentiment mix.
7. **Capacity committed (Mtpa)** — firm (committed/operating) vs pipeline (announced/allocated)
   capacity by region and value chain; firm/pipeline Mtpa also shown as headline KPIs. Tonnes as a
   first-class metric alongside A$.
8. **CO2CRC / CO2Tech signal feed** — high & medium-relevance items segmented into *actionable*,
   priority-ordered buckets (rule-based): policy & advocacy hooks · storage customers & cross-border
   demand · competitor & peer project moves · technology threats & substitutes · partnership &
   investment targets. Each with the "why it matters" read.
2b. **Global reality check — GCCSI baseline** — an external, authoritative benchmark from the Global
   CCS Institute *Global Status of CCS 2025* report (global pipeline facilities & Mtpa, regional
   spotlight, sector projections) placed directly under the geography view, with a region-by-region
   "reality vs corpus coverage" table. Corrects for the corpus's news-flow/source bias (see §5) — e.g.
   shows the US and Middle East at their true operating scale even in windows where the news is quiet.
   Data: `dashboard/data/reference-baseline.json` (refresh annually when GCCSI publishes).
2c. **Cumulative storage delivered — pipeline vs actual tonnes** — reconciles two authoritative
   cumulative-storage sources that measure *different things* and are therefore **never blended**:
   GCCSI's dedicated (non-EOR) **project count** (capacity-leaning, >80 Mt / 18 projects) and Imperial
   College's **London Register of Subsurface CO₂ Storage** (measured *actual* tonnes, all storage types,
   383 Mt to 2024). Shown as two labelled series joined by a documented reconciliation **bridge
   (waterfall)** + a per-project table under a **destination-based 3-way taxonomy** (dedicated /
   associated reinjection / EOR — signed off 2026-07-13). Corrects the common error of reading the
   "383 Mt" all-storage figure as dedicated-only or as a GCCSI number, and surfaces Imperial's
   measured ~19–30% capacity-vs-actual gap. Data: `dashboard/data/storage-baseline.json`. Second
   external source refreshed **monthly** by `.github/workflows/imperial-register-check.yml`, which
   emails when the Imperial register changes.
9. **[planned] Otway / MMV lens** — map monitoring-verification and research-collaboration signals to
   CO2CRC's flagship Otway International Test Centre capabilities and CO2Tech's commercial offer.
10. **[planned] Geographic choropleth** and a **[planned] curated deployment-mandate reference layer**
    (IEA/GCCSI/NDC) to make §4 authoritative rather than incidental (see §5).

## 5. Data-integrity guardrails

- **Everything is sourced.** Every figure traces to a dated, linked source item.
- **Announced ≠ committed ≠ spent.** Commitment status is tracked and status-weighted so trendlines
  don't overstate reality; cancellations are tracked separately as a negative signal.
- **Currency.** Normalised to A$ at *fixed* reference rates (`dashboard/data/fx_rates.json`, as of
  2026-06-30) so trends reflect real commitment shifts, not FX noise. Rates are an assumption pending
  Finance review; original currency is retained on drill-down.
- **Coverage bias — read every geography chart with this in mind.** The corpus reflects the briefing's
  English-language source skew: Europe-UK, North America and APAC dominate; China, India, MENA, Africa
  and LatAm are thin relative to their real-world CCS activity (China especially is under-represented).
  **Absence of evidence here is not evidence of absence.** The dashboard's completeness is bounded by
  the briefing's recall, which the Saturday audit pipeline measures independently. The **GCCSI baseline
  (view 2b)** is the built-in corrective — it shows the true global/regional pipeline so a quiet news
  window for a region is not mistaken for real-world inactivity.
- **Mandate tracker is incidental, not exhaustive.** It lists deadlines that *appeared in the news*,
  not a complete register of every jurisdiction's CCS-dependent legislated target. Treat it as
  "deadlines we've seen," not "the answer to which countries must deploy CCS and by when" — that
  authoritative answer needs the **[planned]** curated reference layer.
- **Mega-project double-count.** The same large project can recur across dates under different
  headlines (e.g. Alberta/Pathways appeared twice); such items are `announced` (heavily discounted),
  but announced totals can still overstate. Named as a known limitation.
- **Not audited financials.** Extraction is a best-effort read of press summaries. The board-facing
  view states this explicitly.

## 6. Decisions (signed off)

1. **Extraction & automation** — one-time local backfill of the historical briefings (no API cost);
   ongoing, the daily production routine emits `audit/YYYY-MM-DD-facts.json` per the spec.
2. **Output format** — self-contained HTML committed to the repo (`dashboard/index.html`); dated board
   snapshots in `dashboard/snapshots/`. The snapshot is emailed weekly as an attachment by
   `email-dashboard.yml` (short intro body + the interactive HTML attached — email clients can't render
   the fixed nav / inline JS inline).
3. **Refresh cadence** — rebuilt weekly on Saturdays alongside the recall audit (`weekly-audit.yml`);
   committing the new snapshot triggers `email-dashboard.yml`, so the board email rides the same cadence.
4. **Financial rigour & currency** — commitment-status tracked; normalised to **A$** at fixed
   reference rates; original currency shown on drill-down.

## 7. Out of scope (for now)

- Primary-source financial verification / independent valuation of announced figures.
- Non-CCS decarbonisation (renewables, EVs, hydrogen except where CCS-coupled).
- Predictive/forecast modelling — v1 is descriptive trend intelligence, not forecasting.
