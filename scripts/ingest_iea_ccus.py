#!/usr/bin/env python3
"""Reproducible ingestion for the IEA CCUS Projects Database.

Preferred input is the official edition workbook.  The official CCUS Projects
Explorer feed is also supported as a constrained fallback: it is project-level
but deliberately omits project names and rows without a stated capacity and
timeline.  Fallback rows are never guessed into the canonical register; the
review queue makes the limitation explicit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from xlsx_xml import normalise_header, read_sheet, sheet_targets

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "dashboard" / "data" / "baselines" / "iea"
PRODUCT_URL = "https://www.iea.org/data-and-statistics/data-product/ccus-projects-database"
EXPLORER_URL = "https://www.iea.org/data-and-statistics/data-tools/ccus-projects-explorer"
EXPLORER_DATA_URL = (
    "https://iea.blob.core.windows.net/scripts/ccus-projects-database/data/projects.json"
)

STAGE_MAP = {
    "operational": "operating",
    "under construction": "construction",
    "construction": "construction",
    "planned": "concept",
    "advanced development": "FEED",
    "concept and feasibility": "feasibility",
    "suspended/cancelled/decommissioned": "cancelled",
    "suspended": "suspended",
    "cancelled": "cancelled",
    "decommissioned": "closed",
}

BASIS_BY_TYPE = {
    "capture": "capture_capacity",
    "full chain": "capture_capacity",
    "ccu": "capture_capacity",
    "storage": "storage_injection_capacity",
    "t&s": "storage_injection_capacity",
    "transport & storage": "storage_injection_capacity",
    "transport": "transport_capacity",
    "industrial cluster": "cluster_announced_capacity",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def clean(value: object | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: object | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def number(value: object | None) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = clean(value).replace(",", "")
    match = re.search(r"-?[0-9]+(?:\.[0-9]+)?", text)
    return float(match.group()) if match else None


def first_column(headers: dict[str, int], *names: str) -> int | None:
    for name in names:
        if name in headers:
            return headers[name]
    return None


def _workbook_sheet(path: Path) -> tuple[str, list[list[object | None]], dict[str, int]]:
    for sheet in sheet_targets(path):
        rows = read_sheet(path, sheet)
        for header_index, row in enumerate(rows[:30]):
            headers = {normalise_header(value): idx for idx, value in enumerate(row) if value not in (None, "")}
            if any(key in headers for key in ("project_name", "project")) and any(
                key in headers for key in (
                    "country", "country_economy", "country_or_economy", "location_country"
                )
            ):
                return sheet, rows[header_index:], headers
    raise ValueError("could not locate an IEA project table with project and country columns")


def parse_workbook(path: Path) -> tuple[list[dict], dict]:
    sheet, rows, headers = _workbook_sheet(path)
    project_col = first_column(headers, "project_name", "project")
    id_col = first_column(headers, "id", "project_id")
    country_col = first_column(
        headers, "country", "country_economy", "country_or_economy", "location_country"
    )
    status_col = first_column(headers, "status", "project_status")
    type_col = first_column(headers, "project_type", "type")
    capacity_col = first_column(
        headers, "estimated_capacity_by_iea_mt_co2_yr", "estimated_capacity_mt_co2_yr",
        "capacity_mt_co2_yr", "capacity_mtpa", "capacity"
    )
    announcement_col = first_column(headers, "announcement", "announcement_year")
    fid_col = first_column(headers, "fid", "fid_year")
    year_col = first_column(
        headers, "operation", "announced_start_date", "announced_start_year", "operation_year", "year"
    )
    suspension_col = first_column(
        headers, "suspension_decommissioning_cancellation", "suspension_decommissioning"
    )
    phase_col = first_column(headers, "project_phase", "phase")
    announced_capacity_col = first_column(
        headers, "announced_capacity_mt_co2_yr", "announced_capacity_mtpa"
    )
    cdr_capacity_col = first_column(headers, "cdr_capacity_mt_co2_yr", "cdr_capacity_mtpa")
    sector_col = first_column(headers, "sector", "sector_group")
    subsector_col = first_column(headers, "subsector")
    region_col = first_column(headers, "region")
    fate_col = first_column(headers, "fate_of_carbon", "co2_fate")
    partners_col = first_column(headers, "partners", "project_partners")
    hub_col = first_column(headers, "part_of_ccus_hub", "ccus_hub", "hub")
    reference_cols = [headers[key] for key in sorted(headers) if re.fullmatch(r"ref_[1-9][0-9]*", key)]
    required = {"project": project_col, "country": country_col, "status": status_col,
                "project_type": type_col, "capacity": capacity_col}
    missing = [name for name, col in required.items() if col is None]
    if missing:
        raise ValueError(f"IEA workbook schema missing required columns: {missing}; headers={sorted(headers)}")

    out = []
    for index, row in enumerate(rows[1:], start=2):
        name = clean(row[project_col])
        if not name:
            continue
        project_type = clean(row[type_col])
        status = clean(row[status_col])
        cap = number(row[capacity_col])
        if cap is not None and cap < 0:
            raise ValueError(f"negative capacity in {sheet} row {index}")
        source_id = clean(row[id_col]) if id_col is not None else str(index - 1)
        references = [clean(row[col]) for col in reference_cols if col < len(row) and clean(row[col])]
        out.append({
            "source_project_id": f"iea-2026-{int(float(source_id)):04d}" if number(source_id) is not None else f"iea-2026-{source_id}",
            "project_name": name,
            "country": clean(row[country_col]),
            "region": clean(row[region_col]) if region_col is not None else "",
            "project_partners": clean(row[partners_col]) if partners_col is not None else "",
            "project_type": project_type,
            "lifecycle_stage": STAGE_MAP.get(status.lower(), status.lower().replace(" ", "_")),
            "source_status": status,
            "project_phase": clean(row[phase_col]) if phase_col is not None else "",
            "sector": clean(row[sector_col]) if sector_col is not None else "",
            "subsector": clean(row[subsector_col]) if subsector_col is not None else "",
            "capacity_basis": BASIS_BY_TYPE.get(project_type.lower(), "unclassified_capacity"),
            "capacity_mtpa": "" if cap is None else cap,
            "announced_capacity_mtpa": (
                "" if announced_capacity_col is None or number(row[announced_capacity_col]) is None
                else number(row[announced_capacity_col])
            ),
            "cdr_capacity_mtpa": (
                "" if cdr_capacity_col is None or number(row[cdr_capacity_col]) is None
                else number(row[cdr_capacity_col])
            ),
            "announcement_year": clean(row[announcement_col]) if announcement_col is not None else "",
            "fid_year": clean(row[fid_col]) if fid_col is not None else "",
            "announced_start_year": clean(row[year_col]) if year_col is not None else "",
            "suspension_or_cancellation_year": clean(row[suspension_col]) if suspension_col is not None else "",
            "co2_destination": clean(row[fate_col]) if fate_col is not None else "",
            "parent_hub": clean(row[hub_col]) if hub_col is not None else "",
            "reference_urls": "|".join(references),
            "source_vintage": "2026-03-27",
            "source_url": PRODUCT_URL,
            "source_form": "official_workbook",
        })
    if len(out) < 1000:
        raise ValueError(f"IEA 2026 workbook unexpectedly contains only {len(out)} named projects")
    if len({row["source_project_id"] for row in out}) != len(out):
        raise ValueError("IEA 2026 workbook contains duplicate project IDs")
    if any(not row["country"] for row in out):
        raise ValueError("IEA 2026 workbook contains a named project without a country/economy")
    invalid_stages = sorted({row["lifecycle_stage"] for row in out} - set(STAGE_MAP.values()))
    if invalid_stages:
        raise ValueError(f"IEA 2026 workbook contains unmapped lifecycle stages: {invalid_stages}")
    invalid_bases = sorted({row["capacity_basis"] for row in out} - set(BASIS_BY_TYPE.values()))
    if invalid_bases:
        raise ValueError(f"IEA 2026 workbook contains unmapped project/capacity types: {invalid_bases}")
    return out, {
        "source_form": "official_workbook",
        "sheet": sheet,
        "headers": sorted(headers),
        "named_projects": len(out),
        "reference_urls_preserved": sum(bool(row["reference_urls"]) for row in out),
        "workbook_note": "Project announcements are current to February 2026; workbook released 27 March 2026.",
    }


def parse_explorer(path: Path) -> tuple[list[dict], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"country", "projectType", "year", "status", "sector", "region", "capacity"}
    if not isinstance(data, list) or not data or any(set(row) != required for row in data):
        raise ValueError("IEA explorer JSON schema changed")
    out = []
    for index, row in enumerate(data, start=1):
        cap = number(row["capacity"])
        if cap is None or cap < 0:
            raise ValueError(f"invalid IEA explorer capacity in row {index}")
        project_type = clean(row["projectType"])
        status = clean(row["status"])
        out.append({
            "source_project_id": f"iea-2026-explorer-{index:04d}",
            "project_name": "",
            "country": clean(row["country"]),
            "region": clean(row["region"]),
            "project_type": project_type,
            "lifecycle_stage": STAGE_MAP.get(status.lower(), status.lower().replace(" ", "_")),
            "source_status": status,
            "sector": clean(row["sector"]),
            "capacity_basis": BASIS_BY_TYPE.get(project_type.lower(), "unclassified_capacity"),
            "capacity_mtpa": cap,
            "announced_start_year": int(row["year"]) if row["year"] else "",
            "co2_destination": "",
            "source_vintage": "2026-03-26",
            "source_url": EXPLORER_URL,
            "source_form": "official_explorer_fallback",
        })
    if len(out) != 422:
        raise ValueError(f"expected 422 IEA explorer rows for 2026 release, found {len(out)}")
    return out, {
        "source_form": "official_explorer_fallback",
        "limitation": (
            "Official explorer feed omits project names and projects without a disclosed timeline/capacity. "
            "Name-level matching is blocked until the free-account workbook is supplied."
        ),
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summary(rows: list[dict]) -> dict:
    by_status = Counter(row["source_status"] for row in rows)
    by_basis = defaultdict(lambda: {"projects": 0, "capacity_mtpa": 0.0})
    for row in rows:
        group = by_basis[row["capacity_basis"]]
        group["projects"] += 1
        if isinstance(row["capacity_mtpa"], (int, float)):
            group["capacity_mtpa"] += row["capacity_mtpa"]
    return {
        "project_rows": len(rows),
        "named_project_rows": sum(bool(row["project_name"]) for row in rows),
        "canonical_matches": sum(row.get("mapping_status") == "matched-exact" for row in rows),
        "candidate_reviews": sum(row.get("mapping_status") == "candidate-review" for row in rows),
        "by_status": dict(sorted(by_status.items())),
        "by_capacity_basis": {
            key: {"projects": val["projects"], "capacity_mtpa": round(val["capacity_mtpa"], 6)}
            for key, val in sorted(by_basis.items())
        },
    }


def crosswalk(rows: list[dict]) -> list[dict]:
    """Apply only exact curated identity matches; route plausible aliases to review."""
    seed_path = ROOT / "dashboard" / "data" / "curation" / "entity-seed.csv"
    with seed_path.open(newline="", encoding="utf-8-sig") as handle:
        seeds = list(csv.DictReader(handle))
    aliases = []
    for seed in seeds:
        values = [seed["canonical_name"]] + seed.get("aliases", "").split("|")
        for alias in values:
            if norm(alias):
                aliases.append((norm(alias), seed["project_id"], norm(seed["primary_country"])))
    exact_index: dict[str, set[str]] = defaultdict(set)
    for alias, project_id, _country in aliases:
        exact_index[alias].add(project_id)

    review = []
    for row in rows:
        key = norm(row["project_name"])
        country = norm(row["country"])
        exact = sorted(exact_index.get(key, set())) if key else []
        candidates = sorted({
            project_id for alias, project_id, project_country in aliases
            if key and len(alias) >= 5 and project_country and project_country in country
            and (f" {alias} " in f" {key} " or f" {key} " in f" {alias} ")
        })
        if len(exact) == 1:
            row["canonical_project_id"] = exact[0]
            row["mapping_status"] = "matched-exact"
            continue
        row["canonical_project_id"] = ""
        if not key:
            status = "unmatched-no-name"
            note = "Official explorer feed omits project name; do not guess"
        elif exact:
            status = "ambiguous-review"
            note = "Multiple curated aliases match exactly; adjudication required"
        elif candidates:
            status = "candidate-review"
            note = "Unique/candidate alias containment in the same country; review before accepting"
        else:
            status = "unmatched-review"
            note = "No exact curated identity match"
        row["mapping_status"] = status
        review.append({
            "source_project_id": row["source_project_id"],
            "project_name": row["project_name"],
            "country": row["country"],
            "mapping_status": status,
            "canonical_project_id": "",
            "candidate_project_ids": "|".join(sorted(set(exact) | set(candidates))),
            "review_note": note,
        })
    return review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="official 2026 workbook or explorer projects.json")
    parser.add_argument("--output-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--retrieved", default=os.environ.get("RETRIEVED_DATE") or date.today().isoformat())
    args = parser.parse_args()
    if args.source.suffix.lower() == ".json":
        rows, detail = parse_explorer(args.source)
    else:
        rows, detail = parse_workbook(args.source)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    review = crosswalk(rows)
    write_csv(args.output_dir / "projects.csv", rows)
    write_csv(args.output_dir / "crosswalk-review.csv", review)
    meta = {
        "dataset": "IEA CCUS Projects Database",
        "edition": "2026",
        "update_date": "2026-03-27",
        "retrieval_date": args.retrieved,
        "product_url": PRODUCT_URL,
        "explorer_url": EXPLORER_URL,
        "explorer_data_url": EXPLORER_DATA_URL,
        "licence": "CC BY 4.0",
        "citation": f"IEA, CCUS Projects Database, IEA, Paris, {PRODUCT_URL}",
        "coverage_thresholds": {
            "general_tco2_per_year": 100000,
            "direct_air_capture_tco2_per_year": 1000,
        },
        "scope": (
            "Capture, transport, storage and utilisation projects with a clear emissions-reduction scope; "
            "excludes low-climate-benefit utilisation, conventional internal urea use, and naturally "
            "occurring CO2 used for EOR."
        ),
        "not_audited_financial_data": True,
        "source_filename": args.source.name,
        "source_sha256": sha256(args.source),
        "ingestion": detail,
        "summary": summary(rows),
        "crosswalk_review_rows": len(review),
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(rows)} IEA rows to {args.output_dir} ({detail['source_form']})")
    print(f"Named rows: {meta['summary']['named_project_rows']}; review queue: {len(review)}")


if __name__ == "__main__":
    main()
