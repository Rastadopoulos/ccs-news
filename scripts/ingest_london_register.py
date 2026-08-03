#!/usr/bin/env python3
"""Ingest the official London Register workbook into reviewable CSV outputs.

The workbook's ``Pivot-*`` sheet is the publisher-selected one-row-per-project
view used for its website and annual report.  Values are annual million tonnes
of CO2 stored.  The source notes that some annual cells are averages derived
from cumulative disclosures; they therefore remain labelled as Imperial's
standardised measured-actual series rather than being described as audited.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import date
from pathlib import Path

from xlsx_xml import read_sheet, sheet_targets

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "dashboard" / "data" / "baselines" / "london-register"
SOURCE_URL = "https://zenodo.org/records/18016847"
DOWNLOAD_URL = (
    "https://zenodo.org/api/records/18016847/files/"
    "2-2025Nov12_LondonRegisterofSubsurfaceCO2Storage.xlsx/content"
)

COUNTRY_NORMALISE = {"USA": "United States"}
ASSOCIATED_PROJECTS = {"Qatar LNG"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def storage_class(project: str, source_type: str) -> tuple[str, str, str]:
    if "oil recovery" in source_type.lower():
        return "eor", "reported-class", "high"
    if project in ASSOCIATED_PROJECTS:
        return "associated", "derived-destination-class", "medium"
    return "dedicated", "derived-destination-class", "medium"


def parse_workbook(path: Path) -> tuple[list[dict], list[dict], dict]:
    pivot_names = [name for name in sheet_targets(path) if name.startswith("Pivot-")]
    if len(pivot_names) != 1:
        raise ValueError(f"expected exactly one Pivot-* sheet, found {pivot_names}")
    sheet = pivot_names[0]
    rows = read_sheet(path, sheet)
    if not rows or [str(v or "").strip() for v in rows[0][:3]] != [
        "Country", "CO2 Storage Project", "Storage type"
    ]:
        raise ValueError("London Register Pivot sheet header changed")

    years = []
    for value in rows[0][3:]:
        if isinstance(value, (int, float)) and 1990 <= int(value) <= 2100:
            years.append(int(value))
        else:
            break
    if not years or years[-1] != 2024:
        raise ValueError(f"unexpected London Register year range: {years[:1]}..{years[-1:]}")

    projects = []
    annual = []
    for source_row, row in enumerate(rows[1:], start=2):
        country = str(row[0] or "").strip()
        project = str(row[1] or "").strip()
        source_type = str(row[2] or "").strip()
        if not country and not project:
            continue
        if not country or not project or not source_type:
            raise ValueError(f"incomplete project identity in {sheet} row {source_row}")
        country = COUNTRY_NORMALISE.get(country, country)
        cls, class_basis, class_confidence = storage_class(project, source_type)
        values = []
        for year, value in zip(years, row[3:3 + len(years)]):
            if value in (None, ""):
                mt = None
            elif isinstance(value, (int, float)) and value >= 0:
                mt = float(value)
                values.append(mt)
            else:
                raise ValueError(f"invalid storage value {value!r} in row {source_row}, {year}")
            annual.append({
                "source_project_id": f"london-2025-{source_row - 1:03d}",
                "project_name": project,
                "country": country,
                "storage_class": cls,
                "year": year,
                "actual_stored_mt": "" if mt is None else round(mt, 9),
                "value_status": "measured-actual-standardised",
                "source_vintage": "2025-11-12",
                "source_url": SOURCE_URL,
            })
        projects.append({
            "source_project_id": f"london-2025-{source_row - 1:03d}",
            "project_name": project,
            "country": country,
            "storage_type_reported": source_type,
            "storage_class": cls,
            "storage_class_basis": class_basis,
            "classification_confidence": class_confidence,
            "first_reported_year": min((r["year"] for r in annual[-len(years):]
                                        if r["actual_stored_mt"] != ""), default=""),
            "latest_reported_year": max((r["year"] for r in annual[-len(years):]
                                         if r["actual_stored_mt"] != ""), default=""),
            "latest_annual_stored_mt": round(float(row[3 + len(years) - 1] or 0), 9),
            "cumulative_stored_mt": round(sum(values), 9),
            "population_coverage": "46 operational storage projects in London Register 2025",
            "value_status": "measured-actual-standardised",
            "source_vintage": "2025-11-12",
            "source_url": SOURCE_URL,
        })

    if len(projects) != 46:
        raise ValueError(f"expected 46 London Register projects, found {len(projects)}")
    summary = {
        "project_count": len(projects),
        "year_start": years[0],
        "year_end": years[-1],
        "cumulative_all_storage_mt": round(sum(p["cumulative_stored_mt"] for p in projects), 6),
        "latest_annual_all_storage_mt": round(sum(p["latest_annual_stored_mt"] for p in projects), 6),
        "by_storage_class": {
            cls: {
                "projects": sum(p["storage_class"] == cls for p in projects),
                "cumulative_mt": round(sum(p["cumulative_stored_mt"] for p in projects
                                           if p["storage_class"] == cls), 6),
                "latest_annual_mt": round(sum(p["latest_annual_stored_mt"] for p in projects
                                               if p["storage_class"] == cls), 6),
            }
            for cls in ("dedicated", "associated", "eor")
        },
    }
    return projects, annual, summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path, help="official London Register .xlsx")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--retrieved", default=os.environ.get("RETRIEVED_DATE") or date.today().isoformat())
    args = parser.parse_args()
    projects, annual, summary = parse_workbook(args.workbook)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "projects.csv", projects)
    write_csv(args.output_dir / "annual-storage.csv", annual)
    metadata = {
        "dataset": "The London Register of Subsurface CO2 Storage",
        "edition": "2025",
        "update_date": "2025-11-12",
        "zenodo_metadata_updated": "2025-12-22",
        "retrieval_date": args.retrieved,
        "source_url": SOURCE_URL,
        "download_url": DOWNLOAD_URL,
        "licence": "CC BY 4.0",
        "doi": "10.5281/zenodo.18016847",
        "source_filename": args.workbook.name,
        "source_sha256": sha256(args.workbook),
        "methodology": (
            "Pivot sheet selected by Imperial for the public register; annual MtCO2 values. "
            "Some years are averages derived from cumulative disclosures. Not audited financial data."
        ),
        "summary": summary,
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(projects)} projects and {len(annual)} annual rows to {args.output_dir}")
    print(f"Cumulative all-storage scope: {summary['cumulative_all_storage_mt']:.1f} Mt")


if __name__ == "__main__":
    main()
