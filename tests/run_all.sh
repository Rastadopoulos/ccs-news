#!/bin/bash
#
# run_all.sh — one command for the full automation regression suite across all
# three projects (CCS-Brief, website review loop, MC4 launchd jobs).
#
#   bash tests/run_all.sh            # tests only
#   bash tests/run_all.sh --preflight  # also run the three preflight checks
#
# Preflights are opt-in here because their job is to fail on real environment
# drift (e.g. prod hotfixes not yet in git) — that is a finding, not a broken
# test suite. Written for stock macOS bash 3.2.

set -u

CCS_BRIEF="$(cd "$(dirname "$0")/.." && pwd)"
WEBREVIEW="$HOME/Documents/CO2CRC/Website review loop CO2CRC CO2Tech"
MC4_DEV="$HOME/MC4/mc4-dev"
BATS="${BATS:-/opt/homebrew/bin/bats}"
PY="${PY:-/usr/bin/python3}"
RC=0

section() { printf '\n=== %s ===\n' "$*"; }

section "CCS-Brief: pytest"
"$PY" -m pytest "$CCS_BRIEF/tests" -q || RC=1

section "CCS-Brief: bats"
"$BATS" "$CCS_BRIEF/tests/shell" || RC=1

section "Website review loop: bats"
"$BATS" "$WEBREVIEW/tests" || RC=1

section "Website review loop: pytest"
"$PY" -m pytest "$WEBREVIEW/tests" -q || RC=1

section "MC4: bats"
"$BATS" "$MC4_DEV/tests/shell" || RC=1

if [ "${1:-}" = "--preflight" ]; then
  section "Preflight: CCS-Brief"
  /bin/bash "$CCS_BRIEF/scripts/preflight.sh" || RC=1
  section "Preflight: website review loop"
  /bin/bash "$WEBREVIEW/scripts/preflight.sh" || RC=1
  section "Preflight: MC4"
  /bin/bash "$MC4_DEV/scripts/preflight.sh" || RC=1
fi

echo ""
if [ "$RC" -eq 0 ]; then
  echo "ALL GREEN"
else
  echo "FAILURES — see above"
fi
exit "$RC"
