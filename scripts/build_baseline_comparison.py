#!/usr/bin/env python3
"""Compare the IEA and GCCSI companion baselines without blending them."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "dashboard" / "data" / "baselines"
OUT = BASE / "comparison"


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


NAME_STOP = {
    "ccs", "ccus", "co2", "carbon", "capture", "project", "facility",
    "plant", "phase", "the", "and", "of", "at",
}


def country_key(value: object) -> str:
    key = norm(value)
    return {
        "people s republic of china": "china",
        "pr china": "china",
    }.get(key, key)


def name_tokens(value: object) -> set[str]:
    return {token for token in norm(value).split() if token not in NAME_STOP and len(token) > 1}


def similarity(left: object, right: object) -> float:
    a, b = name_tokens(left), name_tokens(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def f(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    iea = read_csv(BASE / "iea" / "projects.csv")
    gccsi = read_csv(BASE / "gccsi" / "construction-projects.csv")
    iea_meta = json.loads((BASE / "iea" / "metadata.json").read_text(encoding="utf-8"))
    named_iea = [r for r in iea if r["project_name"].strip()]
    iea_by_name = {norm(r["project_name"]): r for r in named_iea}
    gccsi_by_name = {norm(r["project_name"]): r for r in gccsi}
    matched_names = sorted(set(iea_by_name) & set(gccsi_by_name))
    diffs = []
    for name in matched_names:
        left, right = iea_by_name[name], gccsi_by_name[name]
        left_cap, right_cap = f(left.get("capacity_mtpa")), f(right.get("capture_capacity_mtpa"))
        diffs.append({
            "normalised_name": name, "iea_project": left["project_name"],
            "gccsi_project": right["project_name"], "iea_stage": left["lifecycle_stage"],
            "gccsi_stage": right["lifecycle_stage"],
            "stage_difference": "yes" if left["lifecycle_stage"] != right["lifecycle_stage"] else "no",
            "iea_capacity_basis": left["capacity_basis"],
            "gccsi_capacity_basis": right["capacity_basis"],
            "iea_capacity_mtpa": "" if left_cap is None else left_cap,
            "gccsi_capacity_mtpa": "" if right_cap is None else right_cap,
            "capacity_difference_mtpa": "" if left_cap is None or right_cap is None else round(left_cap - right_cap, 6),
            "review_note": "Exact normalised name match; adjudicate scope/components before accepting differences.",
        })
    likely = []
    matched_gccsi_names = set(matched_names)
    for right in gccsi:
        right_key = norm(right["project_name"])
        if right_key in matched_gccsi_names:
            continue
        candidates = [left for left in named_iea if country_key(left["country"]) == country_key(right["country"])]
        ranked = sorted(
            ((similarity(right["project_name"], left["project_name"]), left) for left in candidates),
            key=lambda item: (item[0], item[1]["project_name"]), reverse=True,
        )
        if not ranked:
            continue
        best_score, left = ranked[0]
        next_score = ranked[1][0] if len(ranked) > 1 else 0.0
        if best_score < 0.25 or (best_score < 0.5 and best_score - next_score < 0.05):
            continue
        left_cap, right_cap = f(left.get("capacity_mtpa")), f(right.get("capture_capacity_mtpa"))
        likely.append({
            "gccsi_project": right["project_name"],
            "iea_candidate": left["project_name"],
            "country": right["country"],
            "name_similarity": round(best_score, 3),
            "next_best_similarity": round(next_score, 3),
            "iea_stage": left["lifecycle_stage"],
            "gccsi_stage": right["lifecycle_stage"],
            "iea_capacity_basis": left["capacity_basis"],
            "gccsi_capacity_basis": right["capacity_basis"],
            "iea_capacity_mtpa": "" if left_cap is None else left_cap,
            "gccsi_capacity_mtpa": "" if right_cap is None else right_cap,
            "review_note": "Rule-assisted naming candidate only; not counted as matched until human adjudication.",
        })
    source_form = iea_meta.get("ingestion", {}).get("source_form", "unknown")
    workbook = source_form == "official_workbook"
    iea_label = (
        "IEA CCUS Projects Database 2026 — official workbook"
        if workbook else "IEA CCUS Projects Database 2026 — explorer fallback"
    )
    iea_scope = (
        f"{len(iea)} named workbook projects; announcements current to February 2026"
        if workbook else f"{len(iea)} capacity-and-timeline rows; project names omitted by public feed"
    )
    aggregate = [
        {
            "baseline": iea_label,
            "scope": iea_scope,
            "stage": stage,
            "projects": sum(r["source_status"] == status for r in iea),
            "capacity_mtpa": round(sum(f(r["capacity_mtpa"]) or 0 for r in iea if r["source_status"] == status), 6),
            "capacity_basis": "mixed capture and storage injection; see basis column, never additive together",
        }
        for stage, status in (("operating", "Operational"), ("construction", "Under construction"), ("planned", "Planned"))
    ]
    aggregate.append({
        "baseline": "GCCSI Global Status of CCS 2025",
        "scope": "Global in-construction headline; 47 named construction facilities",
        "stage": "construction", "projects": 47, "capacity_mtpa": 44,
        "capacity_basis": "capture capacity headline; T&S facilities have no capture value",
    })
    write_csv(OUT / "project-differences.csv", diffs,
              ["normalised_name", "iea_project", "gccsi_project", "iea_stage", "gccsi_stage",
               "stage_difference", "iea_capacity_basis", "gccsi_capacity_basis",
               "iea_capacity_mtpa", "gccsi_capacity_mtpa", "capacity_difference_mtpa", "review_note"])
    write_csv(OUT / "likely-naming-candidates.csv", likely,
              ["gccsi_project", "iea_candidate", "country", "name_similarity",
               "next_best_similarity", "iea_stage", "gccsi_stage", "iea_capacity_basis",
               "gccsi_capacity_basis", "iea_capacity_mtpa", "gccsi_capacity_mtpa", "review_note"])
    write_csv(OUT / "aggregate-stage-comparison.csv", aggregate,
              ["baseline", "scope", "stage", "projects", "capacity_mtpa", "capacity_basis"])
    metadata = {
        "comparison_status": (
            "official workbook ingested; exact matches separated from rule-assisted review candidates"
            if workbook else "constrained by IEA public-feed name suppression"
        ),
        "iea_source_form": source_form,
        "matched_projects": len(matched_names),
        "match_method": "exact normalised project name only",
        "likely_naming_candidates_for_review": len(likely),
        "iea_only_named_projects": len(set(iea_by_name) - set(gccsi_by_name)),
        "gccsi_only_named_projects": len(set(gccsi_by_name) - set(iea_by_name)),
        "iea_unnamed_rows": len(iea) - len(named_iea),
        "lifecycle_differences": sum(r["stage_difference"] == "yes" for r in diffs),
        "capacity_differences": sum(r["capacity_difference_mtpa"] not in ("", 0, 0.0) for r in diffs),
        "likely_naming_or_scope_differences": (
            f"The authenticated workbook enables name-level review. {len(likely)} additional same-country "
            "rule-assisted naming candidates are listed separately and are not counted as matches until "
            "human adjudication; component/phase naming and differing source cut-off dates remain material."
            if workbook else
            "All IEA explorer rows lack project names. GCCSI construction names are therefore provisionally "
            "GCCSI-only, not evidence of true source exclusivity."
        ),
        "never_blended": True,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(
        f"Baseline comparison: {len(matched_names)} exact matches; {len(likely)} naming candidates; "
        f"{metadata['iea_unnamed_rows']} unnamed IEA rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
