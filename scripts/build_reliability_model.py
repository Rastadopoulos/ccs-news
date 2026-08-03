#!/usr/bin/env python3
"""Build board-facing reconciliations from canonical entities and commitments."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_dashboard as legacy  # noqa: E402
from _countries import CONTINENT_GROUPS  # noqa: E402

DATA = ROOT / "dashboard" / "data"
OUT = DATA / "model"
POSITIVE_STATUSES = {"announced", "allocated", "committed", "spent"}


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def region_for(country: str) -> str:
    if country == "European Union":
        return "EU bloc"
    return CONTINENT_GROUPS.get(country, "Global / unallocated")


def funding_category(record: dict) -> str:
    basis = record.get("_basis") or "unclassified"
    funder = record.get("_funder_type") or "unknown"
    status = record.get("commitment_status") or "na"
    if status == "cancelled" and funder in ("government", "mixed"):
        return "withdrawn_or_redirected_public_funding"
    if status == "cancelled" and funder == "private":
        return "cancelled_project_capex"
    return {
        "government-funding": "ccs_public_funding_event",
        "private-investment": "private_investment",
        "project-capex": "project_capex",
        "supplier-contract": "supplier_contract",
        "cancelled": "cancelled_project_capex" if funder == "private" else "withdrawn_or_redirected_public_funding",
        "market-aggregate": "market_aggregate_not_commitment",
        "not-ccs-funding": "not_ccs_funding",
    }.get(basis, "unclassified")


def as_float(value: object) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    fx, fx_asof = legacy.load_fx()
    fresh, radar, stats = legacy.load_records(fx)
    crosswalk = {r["event_id"]: r for r in read_csv(DATA / "entities" / "event-crosswalk.csv")}
    capacities = read_csv(DATA / "entities" / "capacities.csv")
    projects = {r["project_id"]: r for r in read_csv(DATA / "entities" / "projects.csv")}
    programmes = legacy.load_funding_programmes()["programmes"]

    commitments = []
    for record in fresh:
        amount = record.get("amount_aud")
        if amount is None and not record.get("_amount_aud_excluded"):
            continue
        link = crosswalk.get(record.get("id"), {})
        category = funding_category(record)
        commitments.append({
            "commitment_id": record.get("id", ""), "project_id": link.get("project_id", ""),
            "headline": record.get("headline", ""), "primary_geography": link.get("primary_geography", ""),
            "region": region_for(link.get("primary_geography", "")), "category": category,
            "funder_type": record.get("_funder_type") or "unknown",
            "commitment_status": record.get("commitment_status") or "na",
            "reported_value_aud": "" if amount is None else round(amount),
            "status_weight": legacy.STATUS_WEIGHT.get(record.get("commitment_status", "na"), 0),
            "status_weighted_reported_value_aud": (
                "" if amount is None else round(amount * legacy.STATUS_WEIGHT.get(record.get("commitment_status", "na"), 0))
            ),
            "duplicate_of": record.get("_dup_of", ""),
            "additive": "no" if (record.get("_dup_of") or category in (
                "supplier_contract", "market_aggregate_not_commitment", "not_ccs_funding", "unclassified"
            )) else "yes",
            "ccs_specific_share_known": "no — whole gas development plus CCUS" if record.get("id") == "2026-07-27#02" else "not applicable/unspecified",
            "source_url": record.get("url") or link.get("report_url", ""),
        })
    write_csv(OUT / "funding-commitments.csv", commitments, list(commitments[0]))

    programme_rows = []
    for index, programme in enumerate(programmes, start=1):
        rate = fx[programme["currency"]]
        amount = as_float(programme.get("amount")) * rate
        award_known = programme.get("awarded_to_date") is not None
        award = as_float(programme.get("awarded_to_date")) * rate if award_known else None
        programme_rows.append({
            "programme_id": f"funding-programme-{index:03d}", "geography": programme["country"],
            "region": region_for(programme["country"]), "programme": programme["programme"],
            "scope": programme["scope"], "reported_total_aud": round(amount),
            "published_awards_aud": "" if award is None else round(award),
            "drawdown_status": "published" if award_known else "not published — not zero",
            "period_years": programme.get("period_years") or "", "status": programme["status"],
            "source": programme["source"], "source_page": programme.get("page") or "",
        })
    write_csv(OUT / "funding-programmes.csv", programme_rows, list(programme_rows[0]))

    programme_summary = {
        "ccs_specific_reported_programme_total_aud": round(sum(
            r["reported_total_aud"] for r in programme_rows if r["scope"] == "ccs-specific")),
        "ccs_eligible_reported_programme_total_aud": round(sum(
            r["reported_total_aud"] for r in programme_rows if r["scope"] == "ccs-eligible")),
        "published_awards_lower_bound_aud": round(sum(
            as_float(r["published_awards_aud"]) for r in programme_rows)),
        "published_awards_reporting_programmes": sum(r["published_awards_aud"] != "" for r in programme_rows),
        "missing_drawdown_programmes": sum(r["published_awards_aud"] == "" for r in programme_rows),
        "eu_bloc_included": any(r["region"] == "EU bloc" for r in programme_rows),
    }

    # One unique commitment is allocated to exactly one region.  Multi-country
    # display tags therefore cannot inflate either counts or money.
    regional = defaultdict(lambda: {"events": 0, "reported_value_aud": 0, "additive_commitments": 0})
    for record in fresh:
        link = crosswalk.get(record.get("id"), {})
        region = region_for(link.get("primary_geography", ""))
        regional[region]["events"] += 1
    for row in commitments:
        if row["additive"] == "yes" and row["reported_value_aud"] != "":
            regional[row["region"]]["reported_value_aud"] += as_float(row["reported_value_aud"])
            regional[row["region"]]["additive_commitments"] += 1
    regional_rows = [{"region": region, **values} for region, values in sorted(regional.items())]
    global_events = len(fresh)
    global_value = round(sum(r["reported_value_aud"] for r in regional_rows))
    if sum(r["events"] for r in regional_rows) != global_events:
        raise ValueError("regional event counts do not reconcile to global")
    if global_value != round(sum(as_float(r["reported_value_aud"]) for r in commitments if r["additive"] == "yes")):
        raise ValueError("regional funding does not reconcile to global")
    write_csv(OUT / "regional-reconciliation.csv", regional_rows,
              ["region", "events", "reported_value_aud", "additive_commitments"])

    capacity_by_basis_stage = defaultdict(float)
    actual_by_basis = defaultdict(float)
    for row in capacities:
        capacity_by_basis_stage[(row["capacity_basis"], row["lifecycle_stage"])] += as_float(row["nameplate_mtpa"])
        actual_by_basis[row["capacity_basis"]] += as_float(row["actual_annual_mt"])
    capacity_summary = [{
        "capacity_basis": basis, "lifecycle_stage": stage,
        "nameplate_mtpa": round(value, 6),
    } for (basis, stage), value in sorted(capacity_by_basis_stage.items())]

    histories = read_csv(DATA / "entities" / "status-history.csv")
    stage_signals = {}
    for row in histories:
        if row["event_id"] == "canonical-snapshot":
            continue
        key = (row["project_id"], row["lifecycle_stage"])
        if key not in stage_signals or row["effective_date"] > stage_signals[key]["effective_date"]:
            stage_signals[key] = row
    momentum = Counter()
    for row in stage_signals.values():
        if row["lifecycle_stage"] in ("FID/financial close", "construction", "commissioning", "operating"):
            momentum["advancing"] += 1
            momentum[row["lifecycle_stage"]] += 1
        elif row["lifecycle_stage"] in ("suspended", "cancelled"):
            momentum["slipping_suspended_cancelled"] += 1

    au_caps = [r for r in capacities if projects[r["project_id"]]["primary_country"] == "Australia"]
    australia = {
        "operating_storage_injection_nameplate_mtpa": round(sum(
            as_float(r["nameplate_mtpa"]) for r in au_caps
            if r["capacity_basis"] == "storage_injection_capacity" and r["lifecycle_stage"] == "operating"), 6),
        "construction_or_fid_capacity_mtpa_by_basis": {
            basis: round(sum(as_float(r["nameplate_mtpa"]) for r in au_caps
                             if r["capacity_basis"] == basis and r["lifecycle_stage"] in ("construction", "FID/financial close")), 6)
            for basis in sorted({r["capacity_basis"] for r in au_caps})
        },
        "actual_annual_storage_mt_known_subset": round(sum(
            as_float(r["actual_annual_mt"]) for r in au_caps
            if r["capacity_basis"] == "storage_injection_capacity"), 6),
        "actual_coverage_note": "Moomba disclosed annualised value only; missing Gorgon actual is not treated as zero.",
        "projects_advancing_stage_in_observed_event_history": len({
            r["project_id"] for r in stage_signals.values()
            if projects[r["project_id"]]["primary_country"] == "Australia"
            and r["lifecycle_stage"] in ("FID/financial close", "construction", "commissioning", "operating")}),
        "public_support_awarded": "not published in the four programme drawdown fields; not zero",
        "policy_support": "Safeguard Mechanism crediting and federal/state storage title, environment and sea-dumping frameworks",
        "emissions_scale_comparison": "omitted — no defensible like-for-like industrial-emissions denominator in the local baselines",
    }

    source_counts = Counter(
        crosswalk.get(r.get("id"), {}).get("source_type", "daily_news") for r in fresh
    )
    source_counts["external_iea_rows"] = len(read_csv(DATA / "baselines" / "iea" / "projects.csv"))
    source_counts["external_gccsi_construction_rows"] = len(read_csv(DATA / "baselines" / "gccsi" / "construction-projects.csv"))
    source_counts["external_london_storage_projects"] = len(read_csv(DATA / "baselines" / "london-register" / "projects.csv"))
    coverage = json.loads((DATA / "coverage" / "latest.json").read_text(encoding="utf-8"))
    london = json.loads((DATA / "baselines" / "london-register" / "metadata.json").read_text(encoding="utf-8"))
    iea = json.loads((DATA / "baselines" / "iea" / "metadata.json").read_text(encoding="utf-8"))
    gccsi = json.loads((DATA / "baselines" / "gccsi" / "metadata.json").read_text(encoding="utf-8"))
    comparison = json.loads((DATA / "baselines" / "comparison" / "metadata.json").read_text(encoding="utf-8"))
    summary = {
        "source_counts": dict(source_counts), "legacy_load_stats": stats,
        "funding": programme_summary,
        "funding_event_unweighted_by_stage_aud": {
            status: round(sum(as_float(r["reported_value_aud"]) for r in commitments
                              if r["additive"] == "yes" and r["commitment_status"] == status))
            for status in sorted(POSITIVE_STATUSES)
        },
        "status_weighted_reported_value_aud": round(sum(
            as_float(r["status_weighted_reported_value_aud"]) for r in commitments if r["additive"] == "yes")),
        "status_weight_assumptions": legacy.STATUS_WEIGHT,
        "capacity_by_basis_and_stage": capacity_summary,
        "actual_annual_by_basis": {key: round(value, 6) for key, value in actual_by_basis.items()},
        "deployment_stage_signals": dict(momentum), "australia": australia,
        "reconciliation": {
            "global_events": global_events, "regional_events_sum": sum(r["events"] for r in regional_rows),
            "global_additive_reported_value_aud": global_value,
            "regional_additive_reported_value_aud": global_value,
            "multi_country_rule": "one primary physical geography or Global/unallocated; display tags are non-additive",
        },
        "coverage": coverage, "london": london, "iea": iea, "gccsi": gccsi,
        "baseline_comparison": comparison, "fx_asof": fx_asof,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Model: {global_events} unique events; regional reconciliation exact; A${global_value:,.0f} additive reported value")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
