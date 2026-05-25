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

## Daylight-saving swap

Routine cron runs in UTC. Manual swap twice a year:

- AEST (Apr–Oct, UTC+10): `0 21 * * 0-4`
- AEDT (Oct–Apr, UTC+11): `0 20 * * 0-4`
