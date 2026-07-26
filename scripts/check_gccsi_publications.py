#!/usr/bin/env python3
"""Detect new GCCSI publications and say what each one needs.

The GCCSI library at 03-GCCSI-publications/ is a local folder the user drops
reports into. Nothing in CI can see it — GitHub Actions and the daily briefing
routine both run in the cloud — so a local scheduled task
(`gccsi-publications-watch`, Mondays) calls this script.

Detection alone is not much use: different publications need completely
different follow-up. A quarterly update needs a judgement-heavy extraction with
a manual duplicate cross-check; a new Global Status Report needs two generator
scripts re-run and their edition-specific constants updated. So this script
classifies each new file and prints the actual next step.

It deliberately does NOT extract anything. Extraction needs a human in the loop
(see EXTRACTION_SPEC.md) and must never happen unattended.

Usage:
  python3 scripts/check_gccsi_publications.py            # report only
  python3 scripts/check_gccsi_publications.py --update   # also update the manifest
  python3 scripts/check_gccsi_publications.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY = os.path.join(os.path.dirname(ROOT), "03-GCCSI-publications")
MANIFEST = os.path.join(ROOT, "dashboard", "data", ".gccsi-publications-seen.txt")

# Office lock/temp files, not publications.
IGNORE_PREFIXES = (".~lock", "~$", ".")


def classify(filename):
    """Work out what a new file is and what it needs. Returns (kind, action)."""
    n = filename.lower()

    if re.search(r"q[1-4][-_ ]?20\d\d|20\d\d[-_ ]?q[1-4]", n):
        return ("quarterly-update", [
            "Extract into dashboard/data/quarterly/YYYY-QN.jsonl, same schema as the daily facts.",
            "CRITICAL: cross-check every item against the daily corpus by organisation + event "
            "before merging. GCCSI words the same events differently from the press, so the "
            "automatic headline dedup catches none of them — the Q2-2026 batch had 23 real "
            "duplicates and the pipeline caught 0.",
            "Skip GCCSI's own institutional activity (its events, its own reports, roll-call lists).",
            "Do this interactively with the user, never unattended.",
        ])

    if "global-status" in n or "global status" in n or re.search(r"\bgsr\b", n):
        return ("global-status-report", [
            "Re-run: python3 scripts/gen_gccsi_countries.py '<path to the new PDF>'",
            "  The facilities list is now located by content, so pagination changes are handled — "
            "but check the reported page range looks sane.",
            "Update NARRATIVE_CROSSCHECK and CROSSCHECK_SOURCE in that script to the new edition's "
            "stated per-country totals (GSR2024 used Figure 3.1-4, p.15). The parse is UNVERIFIED "
            "until you do.",
            "Re-read the national-strategy figure (GSR2024: Figure 4.4-1, p.47) and update "
            "POLICY_STATUS — it is hand-read from a colour-coded map, not parsed.",
            "Review CARBON_PRICE and dashboard/data/funding-programmes.json for changed figures.",
            "Update dashboard/data/reference-baseline.json (global + regional headline numbers).",
        ])

    if "safety" in n and "permanence" in n:
        return ("storage-permanence", [
            "This is the source behind the GCCSI side of dashboard/data/storage-baseline.json "
            "(dedicated-storage project count and cumulative Mt).",
            "Check whether the project count or cumulative figure has moved, and update the "
            "gccsi_dedicated series if so.",
        ])

    if "policy" in n or "legal" in n or "regulatory" in n:
        return ("policy-review", [
            "Possible source for national CCS policy status. Currently the dashboard reads policy "
            "status from the GSR's Europe-only figure, so a global policy review could extend "
            "coverage beyond Europe — worth reviewing against POLICY_STATUS in "
            "scripts/gen_gccsi_countries.py.",
        ])

    return ("other", [
        "No automated consumer for this publication type. Review whether it contains per-country "
        "or per-project data worth adding; otherwise no action.",
    ])


def scan():
    if not os.path.isdir(LIBRARY):
        sys.exit(f"GCCSI library not found: {LIBRARY}")
    current = sorted(
        f for f in os.listdir(LIBRARY)
        if not f.startswith(IGNORE_PREFIXES) and os.path.isfile(os.path.join(LIBRARY, f))
    )
    seen = set()
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            seen = {line.strip() for line in f if line.strip()}
    new = [f for f in current if f not in seen]
    return current, sorted(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true",
                    help="add the new filenames to the manifest")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    current, new = scan()

    if args.json:
        print(json.dumps({
            "library": LIBRARY,
            "tracked": len(current),
            "new": [{"file": f, "kind": classify(f)[0], "actions": classify(f)[1]} for f in new],
        }, indent=2))
    elif not new:
        print(f"No new GCCSI publications ({len(current)} tracked).")
    else:
        print(f"{len(new)} new GCCSI publication(s) in {LIBRARY}\n")
        for f in new:
            kind, actions = classify(f)
            print(f"  {f}")
            print(f"    type: {kind}")
            for a in actions:
                print(f"      - {a}")
            print()

    if args.update and new:
        with open(MANIFEST, "w", encoding="utf-8") as fh:
            fh.write("\n".join(sorted(set(current))) + "\n")
        print(f"Manifest updated: {len(current)} files tracked.")

    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
