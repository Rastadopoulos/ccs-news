# CCS News

Automated daily briefing on global carbon capture & storage (CCS) news.

## What lands here

Each weekday morning at ~07:00 Australia/Melbourne (skipping Victorian public holidays), a scheduled remote Claude Code agent commits two files to this repo:

- `YYYY-MM-DD-ccs-briefing.html` — standalone styled briefing (open in any browser)
- `YYYY-MM-DD-email.md` — subject line + email body, ready to paste into Outlook

A local launchd agent (`~/Library/LaunchAgents/com.mraab.ccs-news-pull.plist`) pulls this repo at 07:15 so the files appear on disk shortly after generation. A push notification fires when the briefing is ready.

## Briefing scope

~8–12 items, 2–3 sentence summaries, grouped into:

1. **Projects** — FIDs, milestones, capacity changes (Otway, Northern Lights, Quest, Stratos, Bayou Bend, Porthos, Aramis, etc.)
2. **Policy & funding** — 45Q, EU ETS, CCS Directive, DCCEEW, DESNZ, DOE-FECM, ISO/SPE updates
3. **Technology & R&D** — capture, transport, storage, MMV
4. **Markets & corporate** — offtakes, CDR credits, M&A, hubs, supply chain

Geographic priority: Australia/APAC → North America → Europe & UK → MENA/RoW.

## Editing the routine

The full routine prompt is stored server-side via the `schedule` skill. To adjust scope, sources, format, or scheduling, ask Claude Code in this folder — it has the project context in memory.
