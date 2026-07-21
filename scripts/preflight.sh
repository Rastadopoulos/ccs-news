#!/bin/bash
#
# preflight.sh — environment check for the CCS-Brief pipeline.
#
# Run before patching any script in this repo. Verifies that the environment
# you are about to test against matches what actually runs in production:
#   * interpreter versions (local python vs the venv, and vs the CI pin)
#   * required third-party modules importable from the venv
#   * tools the email workflows assume (jq, git)
#   * the network-allowlist rule: nothing outside .github/ may call Resend
#     (the local sandbox cannot reach api.resend.com — outbound email goes
#     through GitHub Actions only)
#
# Written for stock macOS bash 3.2. Exit 0 = safe to patch; exit 1 = the
# environment diverges from what production runs.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FAIL=0
WARN=0

pass() { printf 'PASS  %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; WARN=$((WARN + 1)); }
fail() { printf 'FAIL  %s\n' "$*"; FAIL=$((FAIL + 1)); }

echo "== CCS-Brief preflight ($REPO_ROOT) =="

# --- 1. Shell -----------------------------------------------------------------
BASH_MAJOR="${BASH_VERSINFO[0]}"
if [ "$BASH_MAJOR" -ge 3 ]; then
  pass "bash $BASH_VERSION"
else
  fail "bash too old: $BASH_VERSION"
fi

# --- 2. Python: system, venv, and CI pin --------------------------------------
if command -v python3 >/dev/null 2>&1; then
  SYS_PY="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  pass "system python3 $SYS_PY"
else
  fail "python3 not found on PATH"
  SYS_PY=""
fi

VENV_PY_BIN="$REPO_ROOT/.venv/bin/python"
if [ -x "$VENV_PY_BIN" ]; then
  VENV_PY="$("$VENV_PY_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  if [ -n "$SYS_PY" ] && [ "$VENV_PY" != "$SYS_PY" ]; then
    warn "venv python ($VENV_PY) != system python ($SYS_PY) — tests may not see venv deps"
  else
    pass "venv python $VENV_PY matches system python"
  fi
  if "$VENV_PY_BIN" -c 'import feedparser, yaml, zoneinfo' >/dev/null 2>&1; then
    pass "venv imports feedparser, yaml, zoneinfo"
  else
    fail "venv missing feedparser/yaml/zoneinfo — collectors will not run locally"
  fi
else
  fail "venv python not found at .venv/bin/python"
fi

# CI pins its own Python; a local/CI major.minor gap means "works here, breaks
# there" (or vice versa). Informational only.
CI_PY="$(grep -h "python-version:" "$REPO_ROOT"/.github/workflows/*.yml 2>/dev/null \
          | sed "s/.*python-version:[^0-9]*\([0-9][0-9.]*\).*/\1/" | sort -u | tr '\n' ' ')"
if [ -n "$CI_PY" ] && [ -n "${SYS_PY:-}" ]; then
  case " $CI_PY" in
    *" $SYS_PY "*) pass "local python matches a CI pin ($CI_PY)" ;;
    *) warn "CI pins python $CI_PY but local is $SYS_PY — verify version-sensitive changes in CI" ;;
  esac
fi

# --- 3. Tools the workflows assume ---------------------------------------------
for tool in jq git sqlite3; do
  if command -v "$tool" >/dev/null 2>&1; then
    pass "$tool present"
  else
    fail "$tool not found (email payload validation / audit DB work needs it)"
  fi
done

# --- 4. Git state ---------------------------------------------------------------
BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
if [ "$BRANCH" = "main" ]; then
  pass "on branch main"
else
  warn "on branch '$BRANCH' — the pipeline reads from main; pushes elsewhere won't email"
fi

# --- 5. Network-allowlist rule ---------------------------------------------------
# api.resend.com is NOT reachable from the local sandbox. Outbound email must
# live only in .github/workflows/. docs/ may mention it descriptively.
OFFENDERS="$(grep -rl "api\.resend\.com" "$REPO_ROOT/scripts" 2>/dev/null | grep -v "preflight\.sh" || true)"
for f in "$REPO_ROOT"/*.py "$REPO_ROOT"/*.sh; do
  [ -f "$f" ] || continue
  if grep -q "api\.resend\.com" "$f" 2>/dev/null; then
    OFFENDERS="$OFFENDERS $f"
  fi
done
if [ -z "$(echo "$OFFENDERS" | tr -d '[:space:]')" ]; then
  pass "no direct Resend calls outside .github/workflows (allowlist rule holds)"
else
  fail "direct Resend usage found outside Actions:$OFFENDERS"
fi

# --- 6. Audit store sanity --------------------------------------------------------
DB="$REPO_ROOT/audit/candidates.db"
if [ -f "$DB" ]; then
  TABLES="$(sqlite3 "$DB" ".tables" 2>/dev/null || true)"
  case "$TABLES" in
    *items*samples*|*samples*items*) pass "candidates.db has items + samples tables" ;;
    *) fail "candidates.db missing expected tables (found: $TABLES)" ;;
  esac
else
  warn "audit/candidates.db not present locally (CI owns it; fine unless testing DB paths)"
fi

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "preflight: $FAIL failure(s), $WARN warning(s) — environment does NOT match production; fix before patching."
  exit 1
fi
echo "preflight: OK ($WARN warning(s))."
exit 0
