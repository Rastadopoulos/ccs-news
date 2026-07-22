# Repo secrets and variables — inventory

All secrets and variables live in the GitHub repo at
https://github.com/Rastadopoulos/ccs-news/settings/secrets/actions
and
https://github.com/Rastadopoulos/ccs-news/settings/variables/actions.

Treat this file as the source of truth for *what* exists and *what each one does* — never paste actual secret values here.

## Secrets

| Name | Used by | What it is | Rotation guidance |
|---|---|---|---|
| `RESEND_API_KEY` | `email-briefing.yml`, `email-audit.yml`, `email-shadow.yml` (future) | Resend API key with **Sending access** scope only. Authorises the GitHub Action to send emails via api.resend.com. | Rotate at https://resend.com/api-keys whenever the laptop's secret-store may have been compromised, when a Claude Code transcript containing the key has been shared externally, or on a yearly cadence as default hygiene. Generate the new key first, update the repo secret, then revoke the old key. |
| `GMAIL_ADDRESS` | `alerts-ingest.yml` | The full email address of the dedicated Gmail mailbox that receives Google Alerts. Currently `co2crc.ccs.alerts@gmail.com`. Not strictly a secret (it's discoverable from the alerts subscription metadata), but stored as a secret so any code reading it can't be inspected via workflow log echo. | Only changes if the dedicated mailbox is migrated. Update the secret + the Gmail account itself + every Google Alert's "Deliver to" field in lockstep. |
| `GMAIL_APP_PASSWORD` | `alerts-ingest.yml` | 16-character Google app password generated at https://myaccount.google.com/apppasswords on the dedicated Gmail account. Grants IMAP read access to that mailbox. | Rotate annually as default hygiene, or immediately if the secret store is compromised. Procedure: sign into the dedicated Gmail account, generate a new app password labelled `ccs-news-audit-vN`, update the repo secret, delete the old app password in the Google account. |

### Routine push token (not a repo secret)

The two Claude scheduled routines (production briefing + shadow sampler) push commits to this repo, so they need a GitHub credential. The token is embedded directly in the live routine prompts via `git remote set-url origin https://rastadopoulos:<GITHUB_PAT>@github.com/rastadopoulos/ccs-news.git`. It is NOT a GitHub Actions secret because the routines run on Anthropic infrastructure outside this repo's CI environment.

The repo-tracked copies of the prompts in `docs/routine-prompts/` redact this token to `<GITHUB_PAT_REDACTED>` because GitHub's secret-scanning push protection blocks any commit containing a literal `github_pat_…` value (this is by design and is the right behaviour).

**Where the live token lives**: in the prompt bodies of routine `trig_01TgsPpFGdDogXsqGQsSEeDJ` (production) and the shadow sampler routine, accessible only via the `schedule` skill in your Claude Code CLI.

**Rotation procedure**:
1. Generate a new fine-grained PAT at https://github.com/settings/personal-access-tokens/new with **Contents: Read and write** scope on `Rastadopoulos/ccs-news` only. Expiry: 1 year.
2. Open both routine prompts via the `schedule` skill. Find the `git remote set-url` line in each and replace the old token with the new one. Save each routine.
3. Revoke the old PAT at https://github.com/settings/personal-access-tokens (Active tokens list).
4. The repo-tracked copies in `docs/routine-prompts/` don't need to change — they remain redacted.

**When to rotate**: annually as default hygiene; immediately if the PAT may have leaked (pasted into a chat transcript, committed by mistake to a public repo, included in a screenshot).

**Rotation status**: the PAT exposed in earlier chat transcripts was **rotated on 2026-07-22**; the old token is revoked. Next routine hygiene rotation due ~2026-07 (annual). Note: as of 2026-07-22 both routines run with the `Rastadopoulos/ccs-news` repository bound and push via isolated cloud-session `claude/*` branches (reconciled to main by `reconcile-routine-branch.yml`). If the bound-repo GitHub integration now authorises those pushes, the PAT embedded in the `git remote set-url` line may be legacy — verify at the next rotation whether the routines still depend on it before regenerating.

## Variables

| Name | Used by | What it is | Default |
|---|---|---|---|
| `ALERTS_INGEST_ENABLED` | `alerts-ingest.yml` (the `if:` gate on the `ingest` job) | Feature flag that keeps the alerts-ingest workflow dormant until the Gmail setup is complete. The workflow's `if:` clause skips the job unless this is the literal string `true`. Manual `workflow_dispatch` runs bypass the flag (so you can always trigger it from the Actions tab for testing). | `true` (set during Phase 2b activation) |

## Where each is set

All four live at the same repo settings page. Secrets and variables are different tabs in the GitHub UI:

- **Secrets tab** — https://github.com/Rastadopoulos/ccs-news/settings/secrets/actions
- **Variables tab** — https://github.com/Rastadopoulos/ccs-news/settings/variables/actions

There are no organization-level or environment-scoped secrets in use; everything is repo-level.

## Verifying that secrets are wired correctly

The cleanest tests, in order of usefulness:

1. **Resend** — manually trigger `email-briefing.yml` via the Actions tab → Run workflow. Expected: the most recent briefing is re-sent to your inbox within ~1 minute. Failure modes documented in `SETUP.md`.
2. **Gmail IMAP** — manually trigger `alerts-ingest.yml`. Expand the "Run Alerts ingester" log step. Expected lines:
   - `[INFO] fetched N Google Alerts emails`
   - `[INFO] M in-window CCS items extracted`
   - `[INFO] wrote audit/YYYY-MM-DD-alerts.json (P total)`
   Any `[WARN] IMAP login failed` or `[WARN] GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set` indicates a secret problem — see `docs/google-alerts.md` for setup recovery steps.
3. **Feature flag** — trigger `alerts-ingest.yml` once with `ALERTS_INGEST_ENABLED` unset or set to anything other than `true`. The job should be skipped with `if: ${{ vars.ALERTS_INGEST_ENABLED == 'true' || github.event_name == 'workflow_dispatch' }}` — but `workflow_dispatch` overrides the gate, so this verification is only meaningful by triggering via cron (which you'd need to wait for) or by inspecting the workflow definition directly.

## What NOT to do

- Do not paste secret values into commit messages, code comments, README files, or this file.
- Do not store secrets in `audit/`, `config/`, or anywhere else in the working tree. The scripts read them from environment variables provided by the GitHub Actions secret-injection system.
- Do not log secret values from within workflows. Use `::add-mask::` if you must echo something derived from a secret.
- Do not commit `.env` files. `.gitignore` blocks `.venv*/` but not `.env` — if you ever add one locally, add it to `.gitignore` first.
