#!/usr/bin/env python3
"""Ingest the verifiable structured portion of GCCSI Global Status 2025.

The 2025 report publishes a complete global headline and a 47-row facilities
table for the *in-construction* stage.  It does not publish the all-stage
country table used in GSR 2024, so this importer never pretends the construction
appendix is a full country baseline.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gen_gccsi_countries as parser  # noqa: E402

OUT = ROOT / "dashboard" / "data" / "baselines" / "gccsi"
SOURCE_URL = "https://www.globalccsinstitute.com/resources/global-status-report/"
PDF_URL = "https://www.globalccsinstitute.com/wp-content/uploads/2025/10/Global-Status-of-CCS-2025-report-9-October.pdf"


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def aliases() -> list[tuple[str, str]]:
    path = ROOT / "dashboard" / "data" / "curation" / "entity-seed.csv"
    out = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            for alias in row["aliases"].split("|"):
                out.append((norm(alias), row["project_id"]))
    return sorted(out, key=lambda item: len(item[0]), reverse=True)


def write(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--output-dir", type=Path, default=OUT)
    ap.add_argument("--retrieved", default=date.today().isoformat())
    args = ap.parse_args()
    if not args.pdf.exists():
        raise SystemExit(f"missing source PDF: {args.pdf}")

    raw = parser.parse_facilities(parser.extract_text(str(args.pdf)))
    if len(raw) != 47 or set(row[0] for row in raw) != {"construction"}:
        raise ValueError(f"expected GCCSI 2025's 47 construction rows; got {len(raw)}")
    alias_index = aliases()
    output, review = [], []
    for index, (stage, name, countries, year, industry, capacity) in enumerate(raw, start=1):
        country = parser.COUNTRY_FIX.get(countries[0], countries[0]) if countries else ""
        cap = parser.parse_capacity(capacity)
        matches = sorted({pid for alias, pid in alias_index if alias and alias in norm(name)})
        project_id = matches[0] if len(matches) == 1 else ""
        status = "matched" if project_id else ("ambiguous" if matches else "unmatched")
        output.append({
            "source_project_id": f"gccsi-2025-construction-{index:03d}",
            "project_name": name, "canonical_project_id": project_id,
            "mapping_status": status, "country": country,
            "lifecycle_stage": "construction", "expected_operational_year": year,
            "industry": industry, "capacity_basis": "capture_capacity" if cap is not None else "not_reported_for_transport_storage",
            "capture_capacity_mtpa": "" if cap is None else cap,
            "source_vintage": "2025-07", "source_url": SOURCE_URL,
        })
        if status != "matched":
            review.append({
                "source_project_id": f"gccsi-2025-construction-{index:03d}",
                "project_name": name, "country": country,
                "candidate_project_ids": "|".join(matches),
                "mapping_status": status, "review_note": "Name review required; do not guess",
            })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write(args.output_dir / "construction-projects.csv", list(output[0]), output)
    write(args.output_dir / "crosswalk-review.csv", list(review[0]), review)
    summary = {
        "dataset": "Global Status of CCS 2025",
        "edition": "2025", "data_asof": "2025-07", "retrieval_date": args.retrieved,
        "source_url": SOURCE_URL, "pdf_url": PDF_URL,
        "source_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "structured_scope": "The report's complete 47-facility in-construction appendix only.",
        "country_scope_limitation": (
            "GSR 2025 does not reproduce GSR 2024's all-stage country facilities table. "
            "The dashboard therefore labels its all-stage country layer GSR 2024 and its global/"
            "construction baseline GSR 2025; the vintages are never blended into one total."
        ),
        "global": {
            "operating_facilities": 77, "operating_capacity_mtpa": 64,
            "construction_facilities": 47, "construction_capacity_mtpa": 44,
            "development_facilities": 610, "pipeline_facilities": 734,
            "pipeline_capacity_mtpa": 513,
        },
        "construction_rows": len(output),
        "construction_rows_with_capture_capacity": sum(r["capture_capacity_mtpa"] != "" for r in output),
        "canonical_matches": sum(r["mapping_status"] == "matched" for r in output),
        "crosswalk_review": len(review),
        "not_audited_financial_data": True,
        "methodology": "PDF table located by repeated column headings; capture capacities preserved as Mtpa; T&S rows remain blank.",
    }
    (args.output_dir / "metadata.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(output)} GCCSI construction rows; {summary['canonical_matches']} canonical matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
