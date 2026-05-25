# CCS Daily Briefing — Setup notes

Architecture (re-revised 2026-05-25): routine pushes to GitHub → GitHub Action emails via Resend. The direct Resend-from-routine path was blocked by the routine sandbox's host allowlist (HTTP 403 for `api.resend.com`).

## Current state

- Routine `trig_01TgsPpFGdDogXsqGQsSEeDJ` — generates briefing and pushes to `main`. Resend code removed from the prompt.
- Workflow `.github/workflows/email-briefing.yml` — triggers on push when `*-ccs-briefing.{html,md}` change. Also has `workflow_dispatch` for manual re-runs.
- Sender: `onboarding@resend.dev` (Resend shared sender). Recipient: `matthias.raab@co2crc.com.au`.

## One-time setup steps

### 1. Add the Resend API key as a repo secret

https://github.com/Rastadopoulos/ccs-news/settings/secrets/actions → **New repository secret**

- Name: `RESEND_API_KEY`
- Value: your `re_…` key from https://resend.com/api-keys

The workflow won't run without it (it errors loudly).

### 2. Email today's already-pushed briefing

The 2026-05-25 briefing pushed this morning before the workflow existed. To email it after step 1:

https://github.com/Rastadopoulos/ccs-news/actions → **Email CCS briefing** → **Run workflow** → leave date blank → run.

From tomorrow on, the workflow fires automatically on every routine push.

### 3. (Optional) Rotate the key

The original `re_…` key was pasted in a Claude Code chat transcript. Once delivery is confirmed working:

1. https://resend.com/api-keys → revoke the current key, generate a new one with **Sending access** scope only.
2. Update the `RESEND_API_KEY` secret value in the repo settings.

## If a briefing email doesn't arrive

1. Was there a push? Check `git log origin/main --oneline -5` or the repo commit list.
2. Did the workflow fire? https://github.com/Rastadopoulos/ccs-news/actions
3. If the workflow errored: open the run, expand the failing step. Common causes:
   - `RESEND_API_KEY` not set → set the secret.
   - Resend HTTP 403 → key revoked or wrong scope. Regenerate.
   - Resend HTTP 422 → sender or recipient rejected. If you ever change your Resend signup email, the shared `onboarding@resend.dev` sender will stop delivering until you change it back or verify a domain.
4. Junk folder. First send from a new sender to a corporate tenant often lands there.

## Decommissioned

- **`~/Library/LaunchAgents/com.mraab.ccs-news-pull.plist`** (07:15 local auto-pull) — no longer load-bearing now that delivery is by email. Unload + remove:
  ```sh
  launchctl unload ~/Library/LaunchAgents/com.mraab.ccs-news-pull.plist
  rm ~/Library/LaunchAgents/com.mraab.ccs-news-pull.plist
  ```
- **`YYYY-MM-DD-email.md`** — old Outlook-paste artifact. Replaced by `YYYY-MM-DD-ccs-briefing.md`. Old files remain in git history.

## Daylight-saving swap

Routine cron is UTC-only. Manual swap twice a year:

- AEST (Apr–Oct, UTC+10): `0 21 * * 0-4` — currently set
- AEDT (Oct–Apr, UTC+11): `0 20 * * 0-4`

Calendar reminders: early October 2026 to switch to AEDT, early April 2027 to switch back.

## Annual maintenance

- Refresh the Victorian public-holiday list in the routine prompt each January.
