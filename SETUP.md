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

## Local auto-pull (recreated 2026-10-24)

Not load-bearing — delivery is by email — but keeps the local clone at `~/Documents/Claude-Code/01-CCS-Brief` current for working on the code. It was removed in May and the clone silently fell two months behind.

- **Agent:** `~/Library/LaunchAgents/com.mraab.ccs-news-pull.plist`, daily at 08:30 local and at login (a run missed while asleep fires on wake).
- **Command:** `/Library/Developer/CommandLineTools/usr/bin/git -C <clone> -c credential.helper= pull --ff-only origin main`. Fast-forward only, so it never merges or overwrites local work; a diverged clone just logs an error. The repo is public, so no credentials — the helper is disabled so a hidden keychain prompt can't hang the job.
- **Log:** `~/Library/Logs/ccs-news-pull.log`. `launchctl print gui/$(id -u)/com.mraab.ccs-news-pull | grep "last exit code"` shows the last result.

### Full Disk Access (required)

The clone is under `~/Documents`, which macOS privacy protection (TCC) blocks for background jobs. Without a grant every run fails with `fatal: Unable to read current working directory: Operation not permitted`.

Grant Full Disk Access to **`/Library/Developer/CommandLineTools/usr/bin/git`** — the real binary, not `/usr/bin/git`. `/usr/bin/git` is the xcode-select shim, signed separately (`com.apple.dt.xcode_select.tool-shim-public` vs `com.apple.git`); TCC checks the real git it hands off to, so a grant on the shim does nothing. The agent runs git directly rather than via a shell script so that only git needs the grant, not `bash`.

1. System Settings → Privacy & Security → Full Disk Access.
2. In Finder, Go → Go to Folder → `/Library/Developer/CommandLineTools/usr/bin`, and **drag `git` into the list**. Adding it with **+** and Cmd+Shift+G silently added nothing.
3. Check the **git** entry (black "exec" icon) is switched on.

Re-test: `launchctl kickstart -k gui/$(id -u)/com.mraab.ccs-news-pull`, then `tail ~/Library/Logs/ccs-news-pull.log`. Redo the grant after reinstalling Command Line Tools or moving to a new Mac.

To diagnose a denial: `/usr/bin/log show --last 5m --predicate 'process == "tccd"' --info --debug | grep AUTHREQ_RESULT` (`authValue=0` = denied; use `/usr/bin/log`, as `log` is a zsh builtin).

To remove: `launchctl bootout gui/$(id -u)/com.mraab.ccs-news-pull && rm ~/Library/LaunchAgents/com.mraab.ccs-news-pull.plist`.

## Decommissioned

- **`YYYY-MM-DD-email.md`** — old Outlook-paste artifact. Replaced by `YYYY-MM-DD-ccs-briefing.md`. Old files remain in git history.

## Daylight-saving (automatic since 2026-10-24)

Routine cron is UTC-only, so it cannot follow Melbourne daylight saving by itself. Instead the routine fires at **both** possible times and checks the clock:

- Cron: `0 20,21 * * 0-4` — 20:00 and 21:00 UTC, Sun–Thu (= Mon–Fri morning in Melbourne).
- The first block of the routine prompt is a **SCHEDULE GUARD**: the run checks `TZ=Australia/Melbourne date +%H` and stops immediately unless it prints `07`.
- AEDT (Oct–Apr, UTC+11): the 20:00 UTC run is 07:xx Melbourne and produces the briefing; the 21:00 run is 08:xx and exits.
- AEST (Apr–Oct, UTC+10): the 21:00 UTC run is 07:xx and produces it; the 20:00 run is 06:xx and exits.
- DST changes happen early Sunday morning in Melbourne, when the routine doesn't run, so there is no changeover day with two briefings or none.

No manual swap is needed any more. Cost: one extra run per weekday that exits within seconds; it shows in the routine's run history with the reply "Off-hour run … exiting".

**What to watch for**

- **Two briefings in one day** → the guard was skipped or removed. Check it is still the first block of the prompt (claude.ai/code → routine "CCS Daily News Briefing", or `/schedule` in a `claude` terminal). The copy in `docs/routine-prompts/production.md` has the exact wording.
- **No briefing on a weekday that isn't a public holiday** → the right run started so late it was already 08:xx (guard exited) — rare. Re-run the routine manually.
- **Editing the prompt** → keep the guard first. Removing it while the cron is `0 20,21` gives two briefings a day.

History: until 2026-10-24 this was a manual twice-yearly cron swap (`0 21 * * 0-4` AEST / `0 20 * * 0-4` AEDT). The October 2026 swap was missed, so briefings from 5 to 23 Oct landed at ~08:15 instead of ~07:15.

## Annual maintenance

- Refresh the Victorian public-holiday list in the routine prompt each January.
