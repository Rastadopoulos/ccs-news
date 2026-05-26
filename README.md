# CCS News

Automated daily briefing on global carbon capture & storage (CCS) news.

## How it gets to your inbox

Two-stage pipeline:

1. **Generate + push** — at 07:00 Melbourne weekdays (skipping Vic public holidays) a remote Claude Code routine generates a briefing and pushes two files to this repo:
   - `YYYY-MM-DD-ccs-briefing.html` — self-contained styled HTML, used directly as the email body
   - `YYYY-MM-DD-ccs-briefing.md` — markdown copy (email attachment + searchable archive)
2. **Email** — `.github/workflows/email-briefing.yml` fires on push, reads the new files, and sends to `matthias.raab@co2crc.com.au` via Resend.

Reason for the two-stage split: the routine's sandbox blocks outbound calls to arbitrary hosts (Resend included), so the email send must run from a GitHub Actions runner where outbound is unrestricted.

A push notification fires when the briefing is pushed. The email follows within ~1 minute. If it doesn't arrive, check https://github.com/Rastadopoulos/ccs-news/actions for the workflow run.

## Manual re-send

Open the **Email CCS briefing** workflow in the Actions tab → **Run workflow** → optionally enter a date (`YYYY-MM-DD`) to re-send an old briefing, or leave blank for the latest.

## Briefing scope

~8–12 items, 2–3-sentence summaries, grouped into:

1. **Projects** — FIDs, milestones, capacity changes (Otway, Northern Lights, Quest, Stratos, Bayou Bend, Porthos, Aramis, etc.)
2. **Policy & funding** — 45Q, EU ETS, CCS Directive, DCCEEW, DESNZ, DOE-FECM, ISO/SPE CCUS updates
3. **Technology & R&D** — capture, transport, storage, MMV
4. **Markets & corporate** — offtakes, CDR credits, M&A, hubs, supply chain

Geographic priority: Australia/APAC → North America → Europe & UK → MENA/RoW.

## Editing the routine

The routine prompt lives server-side via the `schedule` skill. Routine ID: `trig_01TgsPpFGdDogXsqGQsSEeDJ`. To adjust scope, sources, format, or schedule, ask Claude Code in this folder.

## Audit & comprehensiveness (Phase 1)

The briefing's recall — what fraction of CCS news in the world it actually catches each day — is measured by an independent pipeline running alongside the routine. The Saturday-morning audit email gives you three numbers: pooled recall, floor recall, and (once Phase 2 ships) an estimated absolute recall via Chapman capture-recapture.

Samplers feeding the audit:

| ID | Sampler | How | Phase |
|---|---|---|---|
| A | Production routine | The briefing itself, via the `audit/${TODAY}-candidates.json` trace | 1 |
| B | RSS floor | `scripts/rss_collector.py` polls ~30 RSS/Atom feeds (`config/feeds.yml`), filters on CCS keywords, applies the 24h/72h window | 1 |
| C | Google Alerts | Dedicated Gmail → IMAP poll (Phase 2) | 2 |
| D | Shadow LLM | Second briefing agent with different prompt/model (Phase 2) | 2 |
| E | Shelly Murrell digest | Already pulled by the routine's Step 2b; trace tags items `found_via=shelly_digest` | 1 |

Workflows (all in `.github/workflows/`):

- `rss-floor.yml` — cron 07:00 Melbourne weekdays. Writes `audit/${TODAY}-rss.json` and updates `audit/candidates.db`.
- `weekly-audit.yml` — cron 08:00 Sat Melbourne. Renders `audit/${SAT}-recall-report.{html,md}`. Manual: Actions tab → Weekly recall audit → Run workflow.
- `email-audit.yml` — fires on push of a new audit report; emails it via Resend, same pattern as the briefing.

Dedup contract (shared by all samplers): `scripts/_canon.py` — canonical URL (strip safelinks/tracking, lowercase host) plus fuzzy headline match (Jaccard ≥ 0.7 on tokenised, stopword-stripped headline).

If floor recall (`|A ∩ B| / |B|`) drops below 90% in any week, treat it as a plumbing alert — the routine is missing items the RSS sampler proves were published.

### Routine prompt extension required

For sampler A to feed the audit, the routine must also write a trace file. Append to the OUTPUTS section of the routine prompt:

> **D) Audit trace** → `audit/${TODAY}-candidates.json` in the repo root.
> One JSON array, one entry per URL the routine considered, schema:
> `{url, canonical_url, fuzzy_key, source_domain, headline, publication_date, in_window: bool, kept: bool, reject_reason, found_via: "search_query"|"shelly_digest"}`.
> Include rejected items too (with `kept: false` and a reason string) so the audit can distinguish "never found" from "found-and-dropped".
> Commit it alongside the briefing files (`git add audit/${TODAY}-candidates.json`).

Until that prompt change is applied, the audit can still run (B and E populate the union) but the source-coverage matrix will not show the routine's rejection reasons.

## Daylight-saving swap

Routine cron runs in UTC. Manual swap twice a year:

| | AEST (Apr–Oct, UTC+10) | AEDT (Oct–Apr, UTC+11) |
|---|---|---|
| `email-briefing.yml` (briefing) | `0 21 * * 0-4` | `0 20 * * 0-4` |
| `rss-floor.yml` | `0 21 * * 0-4` | `0 20 * * 0-4` |
| `weekly-audit.yml` | `0 22 * * 5` | `0 21 * * 5` |
