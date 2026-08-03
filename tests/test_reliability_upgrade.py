"""Acceptance guardrails for the reliability/usability upgrade."""

import csv
import json
import re
from datetime import date
from pathlib import Path

import pytest

import coverage_report
import reliability_dashboard


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dashboard" / "data"


def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_canonical_ids_aliases_and_cross_source_links_are_stable():
    projects = rows(DATA / "entities" / "projects.csv")
    assert len({row["project_id"] for row in projects}) == len(projects)
    assert all(row["aliases"] and row["primary_country"] for row in projects)
    links = rows(DATA / "entities" / "event-crosswalk.csv")
    by_id = {row["event_id"]: row for row in links}
    assert by_id["2026-05-26#01"]["project_id"] == "ca-pathways"
    assert by_id["2026-07-02#04"]["project_id"] == "ca-pathways"
    assert by_id["2026-07-27#02"]["primary_geography"] == "Indonesia"


def test_capacity_is_basis_specific_and_article_duplicates_cannot_add():
    capacities = rows(DATA / "entities" / "capacities.csv")
    allowed = {"capture_capacity", "transport_capacity", "storage_injection_capacity",
               "utilisation_capacity", "policy_target_capacity"}
    assert {row["capacity_basis"] for row in capacities} <= allowed
    assert len({row["additive_key"] for row in capacities}) == len(capacities)
    for project_id in ("ca-pathways", "uk-morecambe", "us-carbon-terravault-i",
                       "uk-hynet-padeswood"):
        assert sum(row["project_id"] == project_id for row in capacities) == 1
    links = rows(DATA / "entities" / "event-crosswalk.csv")
    assert all(row["capacity_additive"].startswith("no") for row in links
               if row["capacity_reported_mtpa"])


def test_funding_categories_and_cancellations_are_separate():
    commitments = rows(DATA / "model" / "funding-commitments.csv")
    by_id = {row["commitment_id"]: row for row in commitments}
    assert by_id["2026-06-05#02"]["category"] == "withdrawn_or_redirected_public_funding"
    assert by_id["2026-07-03#04"]["category"] == "cancelled_project_capex"
    assert by_id["2026-07-27#02"]["ccs_specific_share_known"].startswith("no")
    assert by_id["2026-07-02#04"]["additive"] == "no"


def test_regional_global_reconciliation_and_eu_bloc():
    model = json.loads((DATA / "model" / "summary.json").read_text())
    regional = rows(DATA / "model" / "regional-reconciliation.csv")
    assert sum(int(row["events"]) for row in regional) == model["reconciliation"]["global_events"]
    assert sum(float(row["reported_value_aud"]) for row in regional) == pytest.approx(
        model["reconciliation"]["global_additive_reported_value_aud"])
    assert any(row["region"] == "EU bloc" for row in regional)
    assert model["funding"]["eu_bloc_included"] is True


def test_stock_flow_provenance_and_report_level_urls():
    model = json.loads((DATA / "model" / "summary.json").read_text())
    assert model["source_counts"]["daily_news"] == 153
    assert model["source_counts"]["periodic_report"] == 115
    links = rows(DATA / "entities" / "event-crosswalk.csv")
    periodic = [row for row in links if row["source_type"] == "periodic_report"]
    assert len(periodic) == 115
    assert all(row["report_url"] for row in periodic if not row["item_url"])
    assert all(row["verification_status"] == "report-level provenance"
               for row in periodic if not row["item_url"])


def test_mandate_class_and_event_direction_are_not_media_tone():
    links = rows(DATA / "entities" / "event-crosswalk.csv")
    assert {row["mandate_class"] for row in links if row["mandate_class"] != "not-dated"} <= {
        "legislated/regulatory mandate", "government target",
        "corporate/project milestone", "commercial deadline",
    }
    cancellation = next(row for row in links if row["event_id"] == "2026-07-03#04")
    assert cancellation["event_direction"] == "negative"
    assert cancellation["media_tone"] == ""


def test_coverage_status_never_calls_impaired_day_quiet(tmp_path):
    report = coverage_report.build(date(2026, 8, 3), 3, tmp_path)
    assert report["status"] == "collection impaired"
    assert all(day["status"] != "no verified news" for day in report["days"])
    assert "healthy" in report["quiet_day_rule"]


def test_coverage_can_report_healthy_no_verified_news(tmp_path):
    day = "2026-08-03"
    for suffix in coverage_report.SAMPLERS.values():
        (tmp_path / f"{day}-{suffix}").write_text("[]")
    (tmp_path / f"{day}-facts.json").write_text("[]")
    report = coverage_report.build(date(2026, 8, 3), 1, tmp_path)
    assert report["status"] == "no verified news"


def test_iea_schema_licence_and_comparison_are_explicit():
    meta = json.loads((DATA / "baselines" / "iea" / "metadata.json").read_text())
    comparison = json.loads((DATA / "baselines" / "comparison" / "metadata.json").read_text())
    assert meta["edition"] == "2026" and meta["licence"] == "CC BY 4.0"
    assert meta["ingestion"]["source_form"] == "official_workbook"
    assert meta["source_sha256"] == "9afde5c0ba8f8b3f314ebc44eed7bdaa0a54d479be70c242369e696857272bd8"
    assert meta["summary"]["project_rows"] == 1110
    assert meta["summary"]["named_project_rows"] == 1110
    assert meta["ingestion"]["reference_urls_preserved"] == 1058
    assert meta["coverage_thresholds"] == {
        "general_tco2_per_year": 100000, "direct_air_capture_tco2_per_year": 1000}
    assert comparison["never_blended"] is True
    assert comparison["matched_projects"] == 1
    assert comparison["likely_naming_candidates_for_review"] == 21
    assert comparison["iea_unnamed_rows"] == 0


def test_iea_workbook_output_preserves_identity_component_and_reference_fields():
    iea_rows = rows(DATA / "baselines" / "iea" / "projects.csv")
    required = {"source_project_id", "project_name", "country", "project_partners",
                "project_type", "source_status", "project_phase", "sector", "subsector",
                "capacity_basis", "capacity_mtpa", "announced_capacity_mtpa",
                "cdr_capacity_mtpa", "announcement_year", "fid_year",
                "announced_start_year", "suspension_or_cancellation_year",
                "co2_destination", "parent_hub", "reference_urls",
                "canonical_project_id", "mapping_status"}
    assert required <= set(iea_rows[0])
    assert len(iea_rows) == 1110
    assert sum(bool(row["reference_urls"]) for row in iea_rows) == 1058
    assert sum(row["mapping_status"] == "matched-exact" for row in iea_rows) == 29
    assert sum(row["mapping_status"] == "candidate-review" for row in iea_rows) == 1


def test_current_baseline_validation_rejects_stale_metadata():
    model = json.loads((DATA / "model" / "summary.json").read_text())
    reliability_dashboard.validate_current_baselines(model)
    model["iea"]["edition"] = "2025"
    with pytest.raises(ValueError, match="IEA baseline"):
        reliability_dashboard.validate_current_baselines(model)


def test_storage_labels_distinguish_scope_measure_and_vintage():
    page = (ROOT / "dashboard" / "index.html").read_text()
    for marker in ("384.6 Mt", "All-storage cumulative", "46 projects", "1996–2024",
                   "reported / measured", "annual actual", "Dedicated cumulative",
                   "Associated cumulative", "EOR cumulative"):
        assert marker in page
    assert "111.6 Mt map figure was an incomplete named-project subset" in page
    assert "~123 Mt EOR figure was roughly 2020-vintage" in page


def test_dashboard_links_resolve_and_file_is_self_contained():
    page = (ROOT / "dashboard" / "index.html").read_text()
    ids = set(re.findall(r'\bid="([^"]+)"', page))
    anchors = set(re.findall(r'href="#([^"]+)"', page))
    assert anchors <= ids
    for marker in ('<script src=', '<link rel="stylesheet"', 'src="http', "src='http"):
        assert marker not in page
    assert "data-mode=\"operating\"" in page
    assert "host.querySelector('[data-mode=\"operating\"]')" in page


def test_authoritative_registry_covers_required_regulators_and_broader_operators():
    registry = json.loads((ROOT / "config" / "authoritative-sources.yml").read_text())
    ids = {row["id"] for row in registry["sources"]}
    assert {"iea-ccus-product", "gccsi-publications", "london-register-zenodo",
            "us-epa-class-vi", "uk-nsta-carbon-storage", "uk-ofgem-ccus",
            "au-nopta-ghg", "au-neats", "au-nopsema-environment-plans",
            "au-sea-dumping", "eu-nzia"} <= ids
    assert {"aramco-ccs", "adnoc-ccs", "petronas-ccs", "petrobras-news",
            "sinopec-news", "mhi-carbon-capture"} <= ids
