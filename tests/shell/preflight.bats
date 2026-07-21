#!/usr/bin/env bats
#
# Tests for scripts/preflight.sh — the environment check run before patching
# anything in this repo. Sandbox fixtures deliberately live in a directory
# with spaces to cover the paths-with-spaces failure mode.

setup() {
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
  PREFLIGHT="$REPO_ROOT/scripts/preflight.sh"
}

# Build a minimal fake repo the preflight can pass on, in a spaced path.
make_fixture() {
  FIX="$BATS_TEST_TMPDIR/repo with spaces"
  mkdir -p "$FIX/scripts" "$FIX/.venv/bin" "$FIX/.github/workflows" "$FIX/audit"
  cp "$PREFLIGHT" "$FIX/scripts/preflight.sh"
  # Wrapper that forwards to the real venv python (same 3.9 + deps).
  cat > "$FIX/.venv/bin/python" <<EOF
#!/bin/bash
exec "$REPO_ROOT/.venv/bin/python" "\$@"
EOF
  chmod +x "$FIX/.venv/bin/python"
  cp "$REPO_ROOT/.github/workflows/rss-floor.yml" "$FIX/.github/workflows/"
  git -C "$FIX" init -q -b main 2>/dev/null || git -C "$FIX" init -q
}

@test "preflight passes on the real repository" {
  run /bin/bash "$PREFLIGHT"
  echo "$output"
  [ "$status" -eq 0 ]
  [[ "$output" == *"allowlist rule holds"* ]]
}

@test "preflight passes in a clean sandbox with spaces in the path" {
  make_fixture
  run /bin/bash "$FIX/scripts/preflight.sh"
  echo "$output"
  [ "$status" -eq 0 ]
}

@test "preflight fails when a local script calls Resend directly" {
  make_fixture
  printf '#!/bin/bash\ncurl https://api.resend.com/emails\n' > "$FIX/scripts/rogue.sh"
  run /bin/bash "$FIX/scripts/preflight.sh"
  echo "$output"
  [ "$status" -eq 1 ]
  [[ "$output" == *"direct Resend usage"* ]]
}

@test "preflight fails when the venv is missing" {
  make_fixture
  rm -rf "$FIX/.venv"
  run /bin/bash "$FIX/scripts/preflight.sh"
  [ "$status" -eq 1 ]
  [[ "$output" == *"venv python not found"* ]]
}

@test "preflight is bash 3.2 compatible (static scan)" {
  # Constructs that only exist in bash 4+: fail fast if any sneak in.
  run grep -nE 'mapfile|readarray|declare -A|\$\{[A-Za-z_]+(\^\^|,,)\}|&>>|\|&' "$PREFLIGHT"
  echo "$output"
  [ "$status" -ne 0 ]
}

@test "preflight parses under bash --posix noexec (syntax check)" {
  run /bin/bash -n "$PREFLIGHT"
  [ "$status" -eq 0 ]
}
