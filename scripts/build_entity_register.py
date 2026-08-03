#!/usr/bin/env python3
"""Build the canonical CCS entity register and event crosswalk.

Curated entity identity lives in ``entity-seed.csv``.  The generated files are
review artifacts: news can change status history or attach evidence, but it can
never create additive capacity merely because another article mentions the
same project.  Ambiguous and capacity-carrying unmatched records are routed to
``crosswalk-review.csv`` instead of being guessed.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dashboard" / "data"
SEED = DATA / "curation" / "entity-seed.csv"
OUT = DATA / "entities"
QUARTERLY_REPORT_URL = (
    "https://www.globalccsinstitute.com/resources/publications-reports-research/"
)

STAGES = {
    "concept", "feasibility", "pre-FEED", "FEED", "permit application",
    "permitted", "FID/financial close", "construction", "commissioning",
    "operating", "suspended", "cancelled", "closed",
}
CAPACITY_BASES = {
    "capture_capacity", "transport_capacity", "storage_injection_capacity",
    "removal_purchase_volume", "cumulative_storage_resource",
    "utilisation_capacity", "policy_target_capacity",
}


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, fieldnames: list[str], data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(data)


def load_facts() -> list[dict]:
    sources = [(DATA / "facts-backfill.jsonl", "daily_news")]
    sources += [(Path(path), "periodic_report")
                for path in sorted(glob.glob(str(DATA / "quarterly" / "*.jsonl")))]
    sources += [(Path(path), "daily_news")
                for path in sorted(glob.glob(str(DATA / "raw" / "*.jsonl")))]
    facts = []
    for path, source_type in sources:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                record["_source_type"] = source_type
                record["_source_file"] = str(path.relative_to(ROOT))
                facts.append(record)
    for path in sorted((ROOT / "audit").glob("*-facts.json")):
        for record in json.loads(path.read_text(encoding="utf-8")):
            record["_source_type"] = "daily_news"
            record["_source_file"] = str(path.relative_to(ROOT))
            facts.append(record)
    # Stable event id is the only permissible collision: prefer the daily item
    # with an item-level URL, then the earliest occurrence.
    by_id = {}
    for record in facts:
        key = record.get("id") or hashlib.sha1(
            (record.get("headline", "") + record.get("briefing_date", "")).encode()
        ).hexdigest()[:12]
        current = by_id.get(key)
        if current is None or (not current.get("url") and record.get("url")):
            by_id[key] = record
    return sorted(by_id.values(), key=lambda r: (r.get("briefing_date", ""), r.get("id", "")))


def validate_seed(seed: list[dict]) -> None:
    ids = [row["project_id"] for row in seed]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate project_id in entity-seed.csv")
    aliases = {}
    for row in seed:
        if row["lifecycle_stage"] not in STAGES:
            raise ValueError(f"{row['project_id']}: invalid lifecycle stage {row['lifecycle_stage']!r}")
        basis = row.get("capacity_basis")
        if basis and basis not in CAPACITY_BASES:
            raise ValueError(f"{row['project_id']}: invalid capacity basis {basis!r}")
        for alias in row["aliases"].split("|"):
            key = norm(alias)
            if key in aliases and aliases[key] != row["project_id"]:
                raise ValueError(f"ambiguous curated alias {alias!r}: {aliases[key]} and {row['project_id']}")
            aliases[key] = row["project_id"]


def event_direction(record: dict) -> str:
    text = norm(" ".join((record.get("headline", ""), record.get("summary", ""),
                          record.get("instrument_type", ""))))
    negative = ("cancel", "scrap", "withdraw", "redirect", "delay", "slip",
                "suspend", "risk", "does not renew", "reject", "lawsuit")
    positive = ("fid", "financial close", "construction", "commission", "operate",
                "opens", "starts", "permit", "award", "approv", "first injection")
    if any(word in text for word in negative):
        return "negative"
    if any(word in text for word in positive):
        return "positive"
    return "neutral"


def stage_from_event(record: dict) -> str:
    text = norm(" ".join((record.get("headline", ""), record.get("summary", ""),
                          record.get("instrument_type", ""))))
    ordered = [
        (("cancel", "scrap"), "cancelled"),
        (("suspend",), "suspended"),
        (("commenc operation", "begins operation", "becomes operational", "opens"), "operating"),
        (("commission", "first injection"), "commissioning"),
        (("start construction", "begins construction", "enters construction", "construction phase"), "construction"),
        (("financial close", " final investment decision", " fid "), "FID/financial close"),
        (("final permit", "permit to construct", "wins permit"), "permitted"),
        (("permit application", "submits environmental impact"), "permit application"),
        (("feed study", " front end engineering"), "FEED"),
        (("pre feed",), "pre-FEED"),
        (("feasibility", "assess phase"), "feasibility"),
    ]
    padded = f" {text} "
    for needles, stage in ordered:
        if any(needle in padded for needle in needles):
            return stage
    return ""


def mandate_class(record: dict) -> str:
    if not record.get("target_year"):
        return "not-dated"
    text = norm(" ".join((record.get("headline", ""), record.get("summary", ""),
                          record.get("instrument_type", ""))))
    if any(x in text for x in ("law", "act ", "regulation", "regulatory", "mandatory", "article 23", "mandate")):
        return "legislated/regulatory mandate"
    if record.get("instrument_type") in ("policy", "incentive") or any(
            x in text for x in ("government target", "national target", "ministry", "plan on energy")):
        return "government target"
    if any(x in text for x in ("contract", "tender", "offtake", "deadline")):
        return "commercial deadline"
    return "corporate/project milestone"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    seed = rows(SEED)
    validate_seed(seed)

    alias_index = []
    for project in seed:
        for alias in project["aliases"].split("|"):
            alias_index.append((norm(alias), project["project_id"]))
    alias_index.sort(key=lambda item: len(item[0]), reverse=True)

    facts = load_facts()
    crosswalk, review, histories, policies = [], [], [], []
    matched_ids = set()
    for record in facts:
        haystack = norm(record.get("headline", "") + " " + record.get("summary", ""))
        matches = []
        for alias, project_id in alias_index:
            if alias and re.search(r"(?:^| )" + re.escape(alias) + r"(?: |$)", haystack):
                matches.append(project_id)
        matches = sorted(set(matches))
        mapping_status = "matched" if len(matches) == 1 else ("ambiguous" if matches else "unmatched")
        project_id = matches[0] if len(matches) == 1 else ""
        if project_id:
            matched_ids.add(project_id)
        countries = record.get("countries") or []
        if project_id:
            primary = next(p["primary_country"] for p in seed if p["project_id"] == project_id)
            geography_basis = "canonical physical project location"
        elif len(countries) == 1:
            primary = countries[0]
            geography_basis = "single event geography; entity not mapped"
        else:
            primary = ""
            geography_basis = "multi-country or global event; non-additive until adjudicated"
        item_url = record.get("url") or ""
        report_url = QUARTERLY_REPORT_URL if record["_source_type"] == "periodic_report" else ""
        direction = event_direction(record)
        media_tone = record.get("sentiment") if record.get("section") == "media" else ""
        stage = stage_from_event(record) if project_id else ""
        crosswalk.append({
            "event_id": record.get("id", ""), "project_id": project_id,
            "mapping_status": mapping_status, "mapping_method": "curated alias" if project_id else "",
            "source_type": record["_source_type"], "source_file": record["_source_file"],
            "briefing_date": record.get("briefing_date", ""), "publication_date": record.get("pub_date") or "",
            "headline": record.get("headline", ""), "primary_geography": primary,
            "geography_basis": geography_basis, "event_direction": direction,
            "media_tone": media_tone, "mandate_class": mandate_class(record),
            "capacity_reported_mtpa": record.get("capacity_mtpa") if record.get("capacity_mtpa") is not None else "",
            "capacity_additive": "no — evidence only; canonical capacity register controls totals",
            "item_url": item_url, "report_url": report_url,
            "verification_status": "item-link" if item_url else ("report-level provenance" if report_url else "missing provenance"),
        })
        if stage:
            histories.append({
                "project_id": project_id, "event_id": record.get("id", ""),
                "effective_date": record.get("pub_date") or record.get("briefing_date", ""),
                "lifecycle_stage": stage, "event_direction": direction,
                "source_url": item_url or report_url, "confidence": "medium",
                "note": "Stage signal extracted from event; current register remains curator-controlled.",
            })
        if record.get("target_year"):
            policy_id = "policy-" + hashlib.sha1(norm(record.get("headline", "")).encode()).hexdigest()[:12]
            policies.append({
                "policy_id": policy_id, "event_id": record.get("id", ""),
                "name": record.get("headline", ""), "classification": mandate_class(record),
                "target_year": record.get("target_year"), "primary_geography": primary,
                "event_direction": direction, "source_url": item_url or report_url,
                "verification_status": "verified" if (item_url or report_url) else "review",
            })
        if mapping_status != "matched" and (record.get("capacity_mtpa") is not None or matches):
            review.append({
                "event_id": record.get("id", ""), "headline": record.get("headline", ""),
                "candidate_project_ids": "|".join(matches), "review_reason": (
                    "multiple curated aliases matched" if matches else
                    "capacity-carrying event has no canonical entity match"
                ), "capacity_reported_mtpa": record.get("capacity_mtpa"),
                "countries": "|".join(countries), "resolution": "",
            })

    project_fields = list(seed[0])
    write(args.output_dir / "projects.csv", project_fields, seed)
    components = []
    capacities = []
    for project in seed:
        basis = project.get("capacity_basis")
        component_type = {
            "capture_capacity": "capture facility", "transport_capacity": "transport network",
            "storage_injection_capacity": "storage site", "utilisation_capacity": "utilisation facility",
            "policy_target_capacity": "policy target",
        }.get(basis, project["entity_type"])
        component_id = project["project_id"] + "-" + component_type.replace(" ", "-")
        components.append({
            "component_id": component_id, "project_id": project["project_id"],
            "component_type": component_type, "name": project["canonical_name"],
            "parent_hub_id": project.get("parent_hub_id", ""),
            "primary_country": project["primary_country"],
            "co2_destination": project["co2_destination"],
            "lifecycle_stage": project["lifecycle_stage"],
        })
        if basis and project.get("capacity_mtpa"):
            capacities.append({
                "project_id": project["project_id"], "component_id": component_id,
                "capacity_basis": basis, "nameplate_mtpa": project["capacity_mtpa"],
                "actual_annual_mt": project.get("actual_annual_mt", ""),
                "capacity_status": project["capacity_status"],
                "source_date": project["capacity_source_date"],
                "lifecycle_stage": project["lifecycle_stage"],
                "source_url": project["source_url"], "confidence": project["confidence"],
                "additive_key": f"{component_id}|{basis}|{project['capacity_source_date']}",
            })
    if len({row["additive_key"] for row in capacities}) != len(capacities):
        raise ValueError("duplicate canonical capacity key")
    histories += [{
        "project_id": project["project_id"], "event_id": "canonical-snapshot",
        "effective_date": project["last_verified"], "lifecycle_stage": project["lifecycle_stage"],
        "event_direction": "neutral", "source_url": project["source_url"],
        "confidence": project["confidence"], "note": "Current curator-verified snapshot.",
    } for project in seed]

    write(args.output_dir / "components.csv", list(components[0]), components)
    write(args.output_dir / "capacities.csv", list(capacities[0]), capacities)
    write(args.output_dir / "event-crosswalk.csv", list(crosswalk[0]), crosswalk)
    write(args.output_dir / "crosswalk-review.csv", list(review[0]), review)
    write(args.output_dir / "status-history.csv", list(histories[0]), histories)
    write(args.output_dir / "policy-instruments.csv", list(policies[0]), policies)
    summary = {
        "canonical_entities": len(seed), "canonical_projects_referenced_by_events": len(matched_ids),
        "events": len(crosswalk), "matched_events": sum(r["mapping_status"] == "matched" for r in crosswalk),
        "unmatched_events": sum(r["mapping_status"] == "unmatched" for r in crosswalk),
        "ambiguous_events": sum(r["mapping_status"] == "ambiguous" for r in crosswalk),
        "capacity_review_queue": len(review), "canonical_capacity_rows": len(capacities),
        "source_type_counts": dict(Counter(r["source_type"] for r in crosswalk)),
        "rules": {
            "capacity": "Only capacities.csv is additive; event capacities are evidence only.",
            "geography": "Canonical physical location, else one event country; multi-country records are non-additive.",
            "mapping": "Curated exact aliases only; ambiguity is never guessed.",
        },
    }
    (args.output_dir / "metadata.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(seed)} canonical entities, {len(crosswalk)} event links, {len(review)} review items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
