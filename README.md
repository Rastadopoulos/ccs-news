# CCS News

Automated daily briefing on global carbon capture & storage (CCS) news, plus an independent comprehensiveness-audit pipeline that measures how much CCS news the briefing routinely misses, plus a strategic-trend dashboard built from the accumulating briefing archive.

## CCS Intelligence Dashboard

[`dashboard/index.html`](dashboard/index.html) turns the daily briefings into a running, CEO-lens read on global CCS momentum — geography of commitment, where the money goes, who's advancing vs retreating, deployment mandates, an Australia benchmark, capacity (Mtpa), and a segmented CO2CRC/CO2Tech signal feed. It's a single self-contained HTML file, rebuilt every Saturday by `weekly-audit.yml`. Scope and how-it-works: [`dashboard/SCOPE.md`](dashboard/SCOPE.md) and [`dashboard/README.md`](dashboard/README.md). The daily routine emits `audit/YYYY-MM-DD-facts.json` (a structured extraction of each briefing per [`dashboard/data/EXTRACTION_SPEC.md`](dashboard/data/EXTRACTION_SPEC.md)) that feeds it.

## How the briefing reaches you

Delivery pipeline:

1. **Generate + push** — at 07:00 Melbourne weekdays (skipping Vic public holidays) a remote Claude Code routine generates a briefing and pushes three files:
   - `YYYY-MM-DD-ccs-briefing.html` — self-contained styled HTML, used directly as the email body.
   - `YYYY-MM-DD-ccs-briefing.md` — markdown copy (email attachment + searchable archive).
   - `audit/YYYY-MM-DD-candidates.json` — the routine's audit trace (sampler A) for the Saturday recall audit.
2. **Reconcile** — the routine runs as an isolated Claude Code cloud session, so its `git push origin main` actually lands on an auto-created `claude/*` branch, not `main`. `.github/workflows/reconcile-routine-branch.yml` watches those branches, brings the routine's dated files onto `main` (without clobbering anything already there), and dispatches the email step. (The 2026-06/07 "no briefing produced today" alerts were this branch push arriving invisibly — not the scheduler failing to fire.)
3. **Email** — `.github/workflows/email-briefing.yml` reads the HTML/MD and sends to `matthias.raab@co2crc.com.au` via Resend.

The generate/email split exists because the routine sandbox blocks outbound calls to api.resend.com.

A push notification fires when the briefing is pushed. The email follows within ~1 minute. If it doesn't arrive, check https://github.com/Rastadopoulos/ccs-news/actions for the workflow run.

### Manual re-send

Open the **Email CCS briefing** workflow in the Actions tab → **Run workflow** → optionally enter a date (`YYYY-MM-DD`) to re-send an old briefing, or leave blank for the latest.

## Briefing scope

8–12 items per briefing, 2–3-sentence summaries, grouped into five sections:

1. **Projects** — FIDs, milestones, capacity changes, injection updates, permit awards. Geographic coverage is mandatory and roughly proportional to public CCS news flow; the routine actively searches across Australia/APAC, North America, Europe/UK, Middle East, China, India, LatAm, and Africa each run.
2. **Policy & funding** — 45Q, EU ETS, EU CCS Directive, Net-Zero Industry Act, China carbon market, DCCEEW, DESNZ, DOE-FECM, ISO/SPE CCUS updates, plus transboundary frameworks (London Protocol Article 6, IMO MEPC, OSPAR Decision 2007/2, Australian Sea Dumping Act amendments).
3. **Technology & R&D** — capture, transport, storage, MMV/MRV, solid sorbents, membranes, mineralisation, BECCS, marine CDR.
4. **Markets & strategy** — offtakes, CDR credits, M&A, JVs/MoUs, project financing, corporate CCS strategy and roadmap announcements, cross-border / transboundary CCS deals (e.g. Barossa-Bayu-Undan Australia↔Timor-Leste), liquid-CO2 shipping infrastructure. Multinational strategy items are in-scope even without a project announcement (e.g. Mitsui's Asia-Pacific portfolio strategy, BP's hub roadmap).
5. **Media sentiment & social licence** — opinion pieces, sceptic coverage, broadcast segments, NGO/think-tank critiques, reputation-relevant items from mainstream press.

Geographic priority: Australia & APAC → North America → Europe & UK → Middle East → China → India / Latin America / Africa.

The routine includes an explicit anti-anchoring directive: items from unnamed operators (especially NOCs and Asian/MENA/LatAm state companies), unnamed projects, and non-listed publishers are equally in-scope as the named examples.

## Editing the routines

Two Claude scheduled routines drive this pipeline:

- **Production briefing routine** (schedule ID `trig_01TgsPpFGdDogXsqGQsSEeDJ`) — runs 07:00 Melbourne weekdays, writes the briefing + audit trace.
- **Shadow sampler routine** (separate scheduled task) — runs 07:30 Melbourne weekdays, writes only `audit/YYYY-MM-DD-shadow.json` for the recall audit. Uses a deliberately different model from the production routine for methodological independence.

Both prompt bodies are version-controlled in this repo:

- [`docs/routine-prompts/production.md`](docs/routine-prompts/production.md)
- [`docs/routine-prompts/shadow-sampler.md`](docs/routine-prompts/shadow-sampler.md)

When changing a routine, edit it via the `schedule` skill **and** update the corresponding `.md` file in the same commit, so the repo and the live routine stay in sync. `git log -p docs/routine-prompts/` gives you the prompt revision history.

## Audit & comprehensiveness pipeline

The briefing's recall — what fraction of CCS news in the world it actually catches each day — is measured by an independent pipeline running alongside the routine. The Saturday-morning audit email reports three numbers: pooled recall, floor recall, and an estimated absolute recall via Chapman capture-recapture.

Samplers feeding the audit:

| ID | Sampler | How |
|---|---|---|
| A | Production routine | The briefing itself, via the `audit/${TODAY}-candidates.json` trace |
| B | RSS floor | `scripts/rss_collector.py` polls ~30 RSS/Atom feeds (`config/feeds.yml`), filters on CCS keywords, applies the 24h/72h window |
| C | Google Alerts | `scripts/alerts_ingest.py` polls a dedicated Gmail mailbox via IMAP every 30 min, parses Google Alerts emails — see [`docs/google-alerts.md`](docs/google-alerts.md) for the 30 configured alerts |
| D | Shadow LLM | Separate scheduled Claude routine, concept-based queries, different model from production. Writes `audit/${TODAY}-shadow.json` only |
| E | Shelly Murrell digest | Already pulled by the production routine's Step 2b; trace entries tagged `found_via=shelly_digest` |
| F | IEAGHG Weekly News | Already pulled by the production routine's Step 2b-2 (Outlook folder "IEAGHG news"); trace entries tagged `found_via=ieaghg_newsletter` |

Workflows (all in `.github/workflows/`):

- `email-briefing.yml` — fires on push of `*-ccs-briefing.{html,md}` to `main`, or via dispatch from `reconcile-routine-branch.yml`; emails the briefing via Resend.
- `reconcile-routine-branch.yml` — fires on push to `claude/**`. Brings routine-authored dated briefing/audit files (incl. `*-shadow.json`) onto `main` without clobbering existing files, then dispatches `email-briefing.yml` per reconciled date. Bridges the routines' isolated-branch pushes to `main`.
- `late-file-check.yml` — cron 07:50 Melbourne weekdays. Soft "not in yet" nudge if the day's files haven't reached `main`; 40 min before the dead-man's switch.
- `rss-floor.yml` — cron 07:00 Melbourne weekdays. Writes `audit/${TODAY}-rss.json` and updates `audit/candidates.db`.
- `alerts-ingest.yml` — cron every 30 min during business hours. Requires `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` secrets + `ALERTS_INGEST_ENABLED=true` repo variable.
- `weekly-audit.yml` — cron 08:00 Sat Melbourne. Renders `audit/${SAT}-recall-report.{html,md}`. Manual: Actions tab → Weekly recall audit → Run workflow.
- `email-audit.yml` — fires on push of a new audit report; emails it via Resend.
- `deadman-check.yml` — cron 08:30 Melbourne weekdays. Alerts by email if today's briefing (`${TODAY}-ccs-briefing.md`) or shadow trace (`audit/${TODAY}-shadow.json`) is missing from `main`. Since `reconcile-routine-branch.yml` now delivers the routines' branch pushes, a genuine alert here means the routine truly did not run (check its run history in Claude Code) — not a branch mis-push. Skips weekends and Vic public holidays; the holiday list must be kept in sync with the production prompt.

Dedup contract shared by all samplers: `scripts/_canon.py` — canonical URL (strip safelinks/tracking, lowercase host) plus fuzzy headline match (Jaccard ≥ 0.7 on tokenised, stopword-stripped headline).

If floor recall (`|A ∩ B| / |B|`) drops below 90% in any week, treat it as a plumbing alert — the routine is missing items the RSS sampler proves were published.

For the Chapman estimator's theory and per-week metric definitions, see the comments in [`scripts/weekly_audit.py`](scripts/weekly_audit.py).

## Setup & operations references

- [`docs/secrets.md`](docs/secrets.md) — repo secrets and variables inventory, rotation guidance.
- [`docs/google-alerts.md`](docs/google-alerts.md) — the 30 currently-configured Google Alerts with category groupings and maintenance notes.
- [`docs/routine-prompts/`](docs/routine-prompts/) — version-controlled copies of both Claude scheduled-task prompts.
- [`SETUP.md`](SETUP.md) — Resend wiring, decommissioned LaunchAgent, daylight-saving swap reminders.

## Daylight-saving swap

Cron expressions run in UTC. Manual swap twice a year:

| | AEST (Apr–Oct, UTC+10) | AEDT (Oct–Apr, UTC+11) |
|---|---|---|
| Production briefing routine | `0 21 * * 0-4` | `0 20 * * 0-4` |
| Shadow sampler routine | `30 21 * * 0-4` | `30 20 * * 0-4` |
| `rss-floor.yml` | `0 21 * * 0-4` | `0 20 * * 0-4` |
| `weekly-audit.yml` | `0 22 * * 5` | `0 21 * * 5` |
| `alerts-ingest.yml` | `*/30 20-23 * * *` + `*/30 0-12 * * *` | no swap needed (runs in UTC business-hours band) |
| `deadman-check.yml` | no swap needed (both crons registered; job self-gates on Melbourne local hour) | — |

Calendar reminders: early October to switch to AEDT, early April to switch back.

## Annual maintenance

- Refresh the Victorian public-holiday list in both routine prompts each January.
- Quarterly: scan the most recent Saturday audit's source-coverage matrix; verify `config/feeds.yml` doesn't have stale URLs; review `docs/google-alerts.md` for low-yield alerts to drop.
