# CCS News — project notes for Claude Code

## Local sync step (add to routine PROCEDURE after successful push)

After a successful `git push`, run:

```bash
git -C "/Users/matthias/Documents/Claude Code/CCS-news" pull origin main 2>/dev/null \
  || git clone https://github.com/Rastadopoulos/ccs-news.git \
       "/Users/matthias/Documents/Claude Code/CCS-news"
```

- If the directory already exists and is a repo: pull the latest from main.
- If it doesn't exist yet: clone the repo there.
- Ignore failure silently — this step is best-effort and only works when the routine runs locally on Matthias's Mac. It will fail (silently) in remote/cloud sessions; that's fine.
- Do NOT count a failure here as a push failure and do NOT retry or notify about it.
