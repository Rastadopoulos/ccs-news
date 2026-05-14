# CCS Daily Briefing — Final Setup Steps

The routine is **created but disabled** until you complete the steps below. Once done, you'll get a daily briefing at 7am Melbourne, Mon–Fri (skipping Vic public holidays).

## What's already done locally

- `CCS-news/` initialised as a git repo on `main` with `.gitignore` + this `README.md` committed.
- SSH deploy key generated at `~/.ssh/ccs-news-deploy` (private) and `~/.ssh/ccs-news-deploy.pub` (public).
- Launchd plist for the local 07:15 auto-pull written to `~/Library/LaunchAgents/com.mraab.ccs-news-pull.plist` (not yet loaded).
- Scheduled remote routine **created (disabled)** with ID `trig_01TgsPpFGdDogXsqGQsSEeDJ` — view at <https://claude.ai/code/routines/trig_01TgsPpFGdDogXsqGQsSEeDJ>.
- Project context saved to Claude Code memory.

## Steps for you (Matthias)

### 1. Create the GitHub repo

Go to <https://github.com/new>. Name it `ccs-news`. Choose **Public** or **Private**:

- **Public** is simpler — the remote routine can clone and push without credentials. Briefings are curated public news, no proprietary content, so this is the path of least resistance.
- **Private** — requires you to add a GitHub Personal Access Token (or app credentials) for the routine to be able to push. See note in step 4.

Don't initialise it with a README — we already have local commits to push.

### 2. Connect the local repo to GitHub

In Terminal:

```sh
cd "/Users/matthias/Documents/Claude Code/CCS-news"
git remote add origin https://github.com/<your-username>/ccs-news.git
git push -u origin main
```

(Use HTTPS so macOS Keychain stores credentials and the launchd auto-pull works without SSH-key faff. If you prefer SSH, configure as you normally would.)

### 3. Update the routine to point at your real repo URL

Tell Claude Code in this folder:

> Update routine `trig_01TgsPpFGdDogXsqGQsSEeDJ` — set the git_repository URL to `https://github.com/<your-username>/ccs-news`.

(Or edit it via the web UI at the link above.)

### 4. Sort write-auth so the routine can `git push`

- **If repo is public**: the routine can clone but not push without write credentials. The routine prompt has a fallback: if push fails, it emits the briefing content in its final response so you can still read it from the push notification → Claude Code app. To enable proper push, you'll need to embed an auth mechanism (GitHub PAT in the prompt, or wait for the schedule skill to support workspace secrets). Ask Claude Code for help when ready.
- **If repo is private**: same situation, push needs auth. PAT in the prompt is the pragmatic option for now (fine-grained PAT scoped to this single repo, write access only — minimal blast radius).

If you'd rather skip git-sync entirely and just read the briefing inline each morning, the routine fallback already covers that — no further auth setup needed.

### 5. Load the local 07:15 auto-pull job

```sh
launchctl load ~/Library/LaunchAgents/com.mraab.ccs-news-pull.plist
launchctl list | grep ccs-news
```

(Log file: `~/Library/Logs/ccs-news-pull.log`.)

Skip this step if you decided not to do git-sync.

### 6. Confirm push notifications work

In Claude Code, ensure Remote Control is connected (so notifications reach your phone, not just the desktop terminal). If you're unsure, look up Claude Code's "Remote Control" feature in the docs.

### 7. Enable the routine and trigger a test run

Once the URL is updated and auth is sorted:

> Enable routine `trig_01TgsPpFGdDogXsqGQsSEeDJ` and run it once now.

That fires a one-off run so you can see what tomorrow morning's briefing will look like. Watch for the push notification. Then check:

- Files committed to the GitHub repo (if push works)
- Local files appear after `git pull` (or wait for tomorrow's 07:15 auto-pull)
- HTML opens cleanly in a browser
- The email draft pastes nicely into Outlook

## Daylight saving reminder

The cron is **UTC-only** so the seasonal swap is manual:

- **AEST (Apr–Oct, UTC+10)**: cron `0 21 * * 0-4` — currently set
- **AEDT (Oct–Apr, UTC+11)**: change to cron `0 20 * * 0-4`

Set a calendar reminder for early October 2026 to switch, and early April 2027 to switch back.

## Deploy key (only if you want SSH push)

If you decide to use SSH instead of HTTPS for the routine, the public key is at `~/.ssh/ccs-news-deploy.pub`:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMP7ZuHK1WpENCVx+JcPrmx8ldjRjWQIFF1E52yzW9A1 ccs-news-routine@co2crc.com.au
```

Add it as a **deploy key with write access** under your repo's Settings → Deploy keys. But: getting the *private* key into the remote routine workspace is the hard part — the schedule skill doesn't expose a secrets mechanism. Until that's resolved, stick with HTTPS + PAT.

## Open questions / known limitations

- **Write-auth for the remote routine to push to GitHub** — the schedule skill clones repos into the routine workspace but doesn't document a write-credentials mechanism. The current routine prompt falls back to emitting briefing content inline if push fails.
- **Recurring routine lifetime** — if the routine auto-expires, you may need to re-arm. Watch the first week for any gaps.
- **DST swap** — manual, twice a year (see above).
