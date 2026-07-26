"""Regression tests for scripts/build_dashboard.py.

Two layers:
  1. Unit tests over synthetic fact records (FX normalisation, status-weighted
     money, dedup, fresh/radar split, signal buckets).
  2. A real-environment build: rebuild the dashboard from the repo's actual
     data into a temp dir and check the output contract (self-contained HTML,
     snapshot naming, BUILD_DATE stamping) without touching dashboard/index.html.
"""

import inspect
import json
import math
import os
import re

import pytest

import build_dashboard as bd
import _countries


# ---------------------------------------------------------------- unit layer

def test_status_weight_contract():
    """Announced money must stay discounted and cancelled money must never be
    summed into positive totals."""
    assert bd.STATUS_WEIGHT["announced"] < bd.STATUS_WEIGHT["allocated"] \
        <= bd.STATUS_WEIGHT["committed"] == bd.STATUS_WEIGHT["spent"] == 1.0
    assert bd.STATUS_WEIGHT["cancelled"] == 0.0
    assert bd.STATUS_WEIGHT["na"] == 0.0


def test_committed_aud_weights_by_status():
    rec = {"amount_aud": 1000, "commitment_status": "announced"}
    assert bd.committed_aud(rec) == 250.0
    assert bd.committed_aud({"amount_aud": 1000, "commitment_status": "committed"}) == 1000.0
    assert bd.committed_aud({"amount_aud": None, "commitment_status": "committed"}) == 0.0
    assert bd.committed_aud({"amount_aud": 1000}) == 0.0  # missing status = na


def test_capacity_ignores_junk():
    assert bd.capacity({"capacity_mtpa": 1.5}) == 1.5
    assert bd.capacity({"capacity_mtpa": -2}) == 0.0
    assert bd.capacity({"capacity_mtpa": "big"}) == 0.0
    assert bd.capacity({}) == 0.0


def _rec(headline, url, status="fresh", briefing_date="2026-07-01", **extra):
    return {"headline": headline, "url": url, "item_status": status,
            "briefing_date": briefing_date, "source": "Test", **extra}


def test_load_records_fx_normalisation_and_dedup(monkeypatch):
    records = [
        _rec("US grant for carbon capture", "https://ex.com/usd",
             amount=100, currency="USD"),
        _rec("Mystery-currency item", "https://ex.com/xxx",
             amount=100, currency="XXX"),
        # Same canonical URL (tracking param) — must dedup to one record.
        _rec("US grant for carbon capture", "https://ex.com/usd?utm_source=x",
             briefing_date="2026-07-02"),
        # Radar copy of a fresh item, same URL, later date — fresh must win.
        _rec("US grant for carbon capture", "https://ex.com/usd",
             status="radar", briefing_date="2026-07-03"),
        _rec("Completely different radar story", "https://ex.com/radar", status="radar"),
    ]
    monkeypatch.setattr(bd, "_iter_records", lambda: iter(records))
    fresh, radar, stats = bd.load_records({"USD": 1.5})

    assert stats["dropped_dupes"] == 2
    urls = {r["url"] for r in fresh}
    assert urls == {"https://ex.com/usd", "https://ex.com/xxx"}
    assert [r["url"] for r in radar] == ["https://ex.com/radar"]

    by_url = {r["url"]: r for r in fresh}
    assert by_url["https://ex.com/usd"]["amount_aud"] == 150
    assert by_url["https://ex.com/xxx"]["amount_aud"] is None
    assert by_url["https://ex.com/xxx"]["_fx_missing"] == "XXX"


def test_load_records_fuzzy_dedup_respects_org(monkeypatch):
    """Near-identical headlines only merge when the primary organisation
    matches (or one side has none)."""
    records = [
        _rec("Chevron commits to Gorgon CCS expansion plan", "https://a.com/1",
             organisations=["Chevron"]),
        _rec("Chevron commits to Gorgon CCS expansion plans", "https://b.com/2",
             organisations=["Chevron"]),   # same story, different outlet -> dupe
        _rec("Chevron commits to Gorgon CCS expansion plan", "https://c.com/3",
             organisations=["Santos"]),    # different org -> not a dupe
    ]
    monkeypatch.setattr(bd, "_iter_records", lambda: iter(records))
    fresh, _, stats = bd.load_records({})
    assert stats["dropped_dupes"] == 1
    assert {r["url"] for r in fresh} == {"https://a.com/1", "https://c.com/3"}


def test_signal_bucket_priority_order():
    assert bd.signal_bucket({"instrument_type": "policy"}) == "Policy & advocacy hooks"
    assert bd.signal_bucket({"instrument_type": "offtake"}) \
        == "Storage customers & cross-border demand"
    assert bd.signal_bucket({"instrument_type": "project-FID",
                             "org_types": ["NOC"]}) \
        == "Competitor & peer project moves"
    assert bd.signal_bucket({"section": "technology"}) \
        == "Technology threats & substitutes"
    assert bd.signal_bucket({"instrument_type": "M&A"}) \
        == "Partnership & investment targets"
    assert bd.signal_bucket({}) == "Other high-relevance"
    # Policy outranks storage-customer for a policy offtake with target year.
    assert bd.signal_bucket({"instrument_type": "offtake", "target_year": 2030}) \
        == "Policy & advocacy hooks"


def test_iter_records_skips_bad_lines(monkeypatch, tmp_path, capsys):
    data_dir = tmp_path / "data"
    raw_dir = data_dir / "raw"
    quarterly_dir = data_dir / "quarterly"
    audit_dir = tmp_path / "audit"
    raw_dir.mkdir(parents=True)
    quarterly_dir.mkdir()
    audit_dir.mkdir()
    (data_dir / "facts-backfill.jsonl").write_text(
        '{"headline": "ok1"}\n\nnot json at all\n{"headline": "ok2"}\n')
    (audit_dir / "2026-07-20-facts.json").write_text('{bad json')
    monkeypatch.setattr(bd, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(bd, "RAW_DIR", str(raw_dir))
    monkeypatch.setattr(bd, "QUARTERLY_DIR", str(quarterly_dir))
    monkeypatch.setattr(bd, "AUDIT_DIR", str(audit_dir))
    recs = list(bd._iter_records())
    assert [r["headline"] for r in recs] == ["ok1", "ok2"]
    err = capsys.readouterr().err
    assert "skipping bad JSONL line" in err
    assert "skipping bad facts file" in err


# ---------------------------------------------------------------- real build

@pytest.fixture()
def real_build(monkeypatch, tmp_path):
    """Point the writers at a temp dir but read the repo's real data."""
    out_html = tmp_path / "index.html"
    snap_dir = tmp_path / "snapshots"
    monkeypatch.setattr(bd, "OUT_HTML", str(out_html))
    monkeypatch.setattr(bd, "SNAP_DIR", str(snap_dir))
    return out_html, snap_dir


def test_real_data_build_produces_selfcontained_html(real_build, monkeypatch):
    out_html, snap_dir = real_build
    monkeypatch.setattr("sys.argv", ["build_dashboard.py", "--snapshot", "2099-01-01"])
    monkeypatch.setenv("BUILD_DATE", "2099-01-01")
    bd.main()

    assert out_html.exists()
    page = out_html.read_text()
    assert page.startswith("<!doctype html>")
    assert page.endswith("</body></html>")
    assert page.count("<body") == 1 and "</head><body>" in page
    assert "2099-01-01" in page  # BUILD_DATE stamped

    # Self-contained contract: no external fetches (CSP/email/offline safety).
    for marker in ("<script src=", "<link rel=\"stylesheet\"", "<link rel='stylesheet'",
                   "src=\"http", "src='http"):
        assert marker not in page, f"external resource reference found: {marker}"

    snap = snap_dir / "2099-01-01.html"
    assert snap.exists()
    assert snap.read_text() == page


def test_real_data_has_no_unknown_currencies(real_build, monkeypatch):
    """Every currency appearing in the live fact records must have an FX rate,
    otherwise its money silently drops out of the dashboard totals."""
    fx, _ = bd.load_fx()
    fresh, radar, _ = bd.load_records(fx)
    missing = sorted({r["_fx_missing"] for r in fresh + radar if r.get("_fx_missing")})
    assert not missing, f"currencies missing from fx_rates.json: {missing}"


# ---------------------------------------------------------------- world map

def test_real_data_has_no_unmapped_countries(real_build, monkeypatch):
    """Every country string appearing in the live corpus, storage-baseline.json,
    and reference-baseline-countries.json must resolve via _countries.COUNTRY_ISO
    or be an explicit NON_COUNTRY_TOKEN — otherwise it silently vanishes from the
    map with no shape and no warning a human would see. Mirrors the
    FX-completeness test above, for the country axis."""
    fx, _ = bd.load_fx()
    fresh, radar, _ = bd.load_records(fx)
    seen = set()
    for r in fresh + radar:
        seen.update(r.get("countries") or [])
    sref = bd.load_storage_baseline()
    for p in (sref or {}).get("projects", []):
        seen.update(_countries.split_compound(p.get("country", "")))
    ref_countries = bd.load_reference_countries()
    for row in (ref_countries or {}).get("countries", []):
        seen.add(row["country"])
    unmapped = seen - set(_countries.COUNTRY_ISO) - _countries.NON_COUNTRY_TOKENS
    assert not unmapped, f"countries missing from _countries.COUNTRY_ISO: {sorted(unmapped)}"


def test_every_tracked_country_is_drawable():
    """Each country we can resolve to an ISO code must be renderable on the map —
    either it has an outline, or it is a known microstate with a marker point.
    Without this a country can hold data and still be invisible."""
    import _worldmap as wm
    undrawable = [
        name for name, iso in _countries.COUNTRY_ISO.items()
        if iso not in wm.COUNTRY_PATH and iso not in wm.LABEL_POINT
    ]
    assert not undrawable, f"tracked countries with no shape and no marker: {undrawable}"


def test_worldmap_projection_matches_vendored_geometry():
    """project_lonlat() places the project pins; COUNTRY_PATH draws the land.
    If the two ever drift apart, pins float into the sea. Check a few known
    points land inside their country's bounding box."""
    import re
    import _worldmap as wm

    def bbox(iso):
        nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", wm.COUNTRY_PATH[iso])]
        xs, ys = nums[0::2], nums[1::2]
        return min(xs), min(ys), max(xs), max(ys)

    # lon/lat well inside each country
    for iso, lon, lat in [("US", -98.5, 39.5), ("AU", 134.0, -25.0),
                          ("BR", -51.0, -12.0), ("CN", 103.0, 35.0)]:
        x, y = wm.project_lonlat(lon, lat)
        x0, y0, x1, y1 = bbox(iso)
        assert x0 <= x <= x1 and y0 <= y <= y1, f"{iso}: projected point fell outside its own outline"


def test_split_compound_handles_plain_and_compound_names():
    assert _countries.split_compound("Norway") == ["Norway"]
    assert _countries.split_compound("United States/Canada") == ["United States", "Canada"]
    assert _countries.split_compound("") == []


def test_map_storage_register_splits_compound_country_to_both():
    """'United States/Canada' (Great Plains Synfuel -> Weyburn-Midale) must credit
    BOTH countries, not be dropped or arbitrarily assigned to just one."""
    sref = bd.load_storage_baseline()
    plocs = bd.load_project_locations()
    storage = bd.map_storage_register(sref, plocs)
    assert storage["United States"]["eor"] >= 1
    assert storage["Canada"]["eor"] >= 1
    for country in ("United States", "Canada"):
        names = {p["name"] for p in storage[country]["projects"]}
        assert "Great Plains Synfuel -> Weyburn-Midale" in names


def test_map_storage_register_keeps_the_two_tonnage_bases_apart():
    """measured_total_mt (Imperial, actual) and reported_total_mt (GCCSI,
    reported) must be accumulated separately and never summed into one figure."""
    sref = bd.load_storage_baseline()
    storage = bd.map_storage_register(sref, bd.load_project_locations())
    no = storage["Norway"]
    assert no["measured_total_mt"] == pytest.approx(25.0)   # Sleipner 18.5 + Snohvit 6.5
    assert no["reported_total_mt"] == pytest.approx(20.0)   # Sleipner 20 + Northern Lights 0
    assert no["measured_total_mt"] != no["reported_total_mt"]


def test_every_storage_project_has_map_coordinates():
    """A project on the register with no coordinates silently disappears from the
    map, which would misrepresent where storage is actually happening."""
    sref = bd.load_storage_baseline()
    plocs = bd.load_project_locations() or {"locations": {}}
    missing = [p["name"] for p in sref["projects"] if p["name"] not in plocs["locations"]]
    assert not missing, f"storage projects with no map coordinates: {missing}"


def test_project_coordinates_are_plausible():
    """Guard against transposed or sign-flipped lat/lon, the classic mapping bug."""
    plocs = bd.load_project_locations()
    for name, loc in plocs["locations"].items():
        assert -90 <= loc["lat"] <= 90, f"{name}: latitude out of range"
        assert -180 <= loc["lon"] <= 180, f"{name}: longitude out of range"
    # spot-check hemispheres that a sign flip would break
    assert plocs["locations"]["Gorgon"]["lat"] < 0, "Gorgon is in Australia (southern hemisphere)"
    assert plocs["locations"]["Sleipner"]["lat"] > 50, "Sleipner is in the North Sea"


def test_map_gccsi_country_degrades_gracefully_without_file():
    """The GCCSI map layers must not crash the build if the country-level
    extraction file is absent — they should simply render as 'no data'."""
    assert bd.map_gccsi_country(None) == {}


def test_map_news_activity_splits_public_from_private_money():
    """Government money and company money are not the same event and must never
    be added together — a state pledging billions and a developer closing a
    venture round mean entirely different things."""
    recs = {"Testland": [
        {"amount_aud": 1000, "commitment_status": "committed",
         "_funder_type": "government", "_basis": "government-funding"},
        {"amount_aud": 500, "commitment_status": "committed",
         "_funder_type": "private", "_basis": "private-investment"},
    ]}
    out = bd.map_news_activity({"Testland": 2}, {"Testland": 1500.0}, recs)
    assert out["Testland"]["public_aud"] == 1000
    assert out["Testland"]["private_aud"] == 500
    assert out["Testland"]["developments"] == 2


def test_non_funding_figures_never_reach_a_funding_total():
    """A whole-economy investment figure, a lawsuit, a merger synergy target and
    a supplier sub-contract are all real numbers that are not CCS funding.
    Every one of these was found in the live corpus."""
    for basis in ("market-aggregate", "not-ccs-funding", "supplier-contract"):
        rec = {"amount_aud": 1_000_000, "commitment_status": "committed", "_basis": basis}
        assert bd.funding_flow(rec) == 0.0, f"{basis} leaked into a funding total"
        assert bd.committed_aud(rec) == 0.0, f"{basis} leaked into the weighted KPI"
    real = {"amount_aud": 1_000_000, "commitment_status": "committed",
            "_basis": "government-funding"}
    assert bd.funding_flow(real) == 1_000_000


def test_duplicate_commitments_are_stripped_of_their_amount(monkeypatch):
    """The same commitment reported twice must contribute money once. The record
    stays (the news did happen); only the amount is removed."""
    fx, _ = bd.load_fx()
    fresh, radar, _ = bd.load_records(fx)
    dups = [r for r in fresh + radar if r.get("_dup_of")]
    assert dups, "expected the known duplicate commitments to be flagged"
    for r in dups:
        assert r.get("amount_aud") is None, f"{r['id']} still carries money"
        assert r.get("_amount_aud_excluded"), f"{r['id']} lost its audit trail"


def test_woodside_synergy_figure_is_not_counted_as_ccs_funding():
    """US$60m of 'annual operating synergies' from an operatorship transfer was
    carried as committed money and landed in Australia's funding total."""
    fx, _ = bd.load_fx()
    fresh, _, _ = bd.load_records(fx)
    rec = next((r for r in fresh if r.get("id") == "2026-07-03#03"), None)
    assert rec, "the Woodside record has gone missing"
    assert rec["commitment_status"] == "na"
    assert bd.committed_aud(rec) == 0.0


def test_funding_programmes_carry_period_and_scope():
    """A programme total with no period is unreadable, and a broad
    decarbonisation pot must not be presented as CCS-specific money."""
    fprog = bd.load_funding_programmes()
    assert fprog, "funding-programmes.json missing"
    uk = [p for p in fprog["programmes"]
          if p["country"] == "United Kingdom" and "Track-1" in p["programme"]]
    assert uk, "the UK cluster programme is missing"
    assert uk[0]["amount"] == 21_700_000_000 and uk[0]["currency"] == "GBP"
    assert uk[0]["period_years"] == 25
    for p in fprog["programmes"]:
        assert p.get("scope") in ("ccs-specific", "ccs-eligible"), p["programme"]
        assert p.get("source"), p["programme"]


def test_programme_drawdown_is_computed_as_a_ratio():
    """'£21.7bn committed' only becomes useful next to how much has been awarded."""
    fx, _ = bd.load_fx()
    layer = bd.map_funding_programmes(bd.load_funding_programmes(), fx)
    us = layer["United States"]
    bil = next(p for p in us["programmes"] if "Bipartisan" in p["programme"])
    assert bil["awarded_pct"] == 18          # $2.2bn of $12.5bn
    assert bil["awarded_aud"] < bil["amount_aud"]
    # Where no drawdown is published, the ratio must be absent, not zero.
    uk = layer["United Kingdom"]
    cluster = next(p for p in uk["programmes"] if "Track-1" in p["programme"])
    assert cluster["awarded_pct"] is None


def test_uk_funding_position_is_not_the_news_window():
    """The bug that started this: the UK's funding position read as A$8.8m
    because its £21.7bn predates the corpus. Programmes must dominate."""
    fx, _ = bd.load_fx()
    merged, _, _ = bd.build_country_map_data(
        {}, {}, {}, None, None, None, bd.load_funding_programmes(), fx)
    uk = merged["United Kingdom"]["funding"]
    assert uk["total_aud"] > 40_000_000_000, "UK programme total looks wrong"


def test_programme_annualisation_is_offered_where_a_period_exists():
    fx, _ = bd.load_fx()
    layer = bd.map_funding_programmes(bd.load_funding_programmes(), fx)
    cluster = next(p for p in layer["United Kingdom"]["programmes"]
                   if "Track-1" in p["programme"])
    assert cluster["annual_aud"] == round(cluster["amount_aud"] / 25)


def test_build_country_map_data_keeps_a_country_present_in_only_one_layer():
    country_cnt = {"Iceland": 1}
    country_val = {"Iceland": 50.0}
    country_recs = {"Iceland": [{"amount_aud": 50, "commitment_status": "announced"}]}
    merged, eu, regions = bd.build_country_map_data(
        country_cnt, country_val, country_recs, None, None, None)
    assert "Iceland" in merged
    assert merged["Iceland"]["storage"] == {}
    assert merged["Iceland"]["gccsi"] == {}
    assert eu is None


def test_build_country_map_data_splits_out_eu_as_its_own_aggregate():
    """EU-wide money must not be smeared across member states — the source never
    attributed it to one, and inventing that split would fabricate detail."""
    country_cnt = {"European Union": 3, "Germany": 1}
    country_val = {"European Union": 300.0, "Germany": 100.0}
    country_recs = {
        "European Union": [{"amount_aud": 300, "commitment_status": "committed"}],
        "Germany": [{"amount_aud": 100, "commitment_status": "committed"}],
    }
    merged, eu, regions = bd.build_country_map_data(
        country_cnt, country_val, country_recs, None, None, None)
    assert "European Union" not in merged
    assert "Germany" in merged
    assert eu["developments"] == 3


def test_region_totals_roll_up_countries():
    country_cnt = {"Germany": 2, "Australia": 3}
    country_val = {"Germany": 100.0, "Australia": 200.0}
    country_recs = {
        "Germany": [{"amount_aud": 100, "commitment_status": "committed"}],
        "Australia": [{"amount_aud": 200, "commitment_status": "committed"}],
    }
    _, _, regions = bd.build_country_map_data(
        country_cnt, country_val, country_recs, None, None, None)
    assert regions["Europe"]["developments"] == 2
    assert regions["Asia-Pacific"]["developments"] == 3


def test_country_contour_map_renders_shapes_pins_and_payload():
    sref = bd.load_storage_baseline()
    plocs = bd.load_project_locations()
    merged, _, _ = bd.build_country_map_data(
        {"Norway": 4}, {"Norway": 10.0},
        {"Norway": [{"amount_aud": 10, "commitment_status": "committed"}]},
        sref, None, plocs)
    svg, payload = bd.country_contour_map(merged)
    assert 'id="ccs-map"' in svg
    assert 'data-country="Norway"' in svg
    assert 'class="pin pin-dedicated"' in svg
    data = json.loads(payload.replace("\\u003c", "<"))
    assert "Norway" in data["countries"]
    assert data["countries"]["Norway"]["storage"]["dedicated"] == 3


def test_contour_map_draws_each_project_pin_once():
    """The one cross-border project is credited to two countries in the data but
    is a single physical site — it must not be drawn, or counted by eye, twice."""
    sref = bd.load_storage_baseline()
    plocs = bd.load_project_locations()
    fresh_counts = {c: 1 for c in ("United States", "Canada")}
    merged, _, _ = bd.build_country_map_data(
        fresh_counts, {c: 0.0 for c in fresh_counts},
        {c: [] for c in fresh_counts}, sref, None, plocs)
    svg, _ = bd.country_contour_map(merged)
    assert svg.count('data-project="Great Plains Synfuel -&gt; Weyburn-Midale"') == 1


def test_map_payload_is_safely_escaped_for_inline_script():
    """The JSON island sits inside a <script> tag; an unescaped '<' could close
    it early and break the page."""
    merged, _, _ = bd.build_country_map_data(
        {"Norway": 1}, {"Norway": 0.0}, {"Norway": []}, None, None, None)
    _, payload = bd.country_contour_map(merged)
    assert "<" not in payload


def test_real_build_map_and_glossary_render(real_build, monkeypatch):
    """The map, its source-grouped controls, the country card, the region
    roll-up and the glossary must all appear in the real build, and the page
    must stay self-contained."""
    out_html, snap_dir = real_build
    monkeypatch.setattr("sys.argv", ["build_dashboard.py"])
    bd.main()
    page = out_html.read_text()

    for marker in ('id="ccs-map"', 'class="pillgroups"', 'id="ccs-country-card"',
                   'id="ccs-map-data"', 'regionroll', 'class="glossary"',
                   'data-mode="developments"', 'data-mode="storageclass"',
                   'class="srcchip'):
        assert marker in page, f"missing from build output: {marker}"
    for bad in ("<script src=", '<link rel="stylesheet"', 'src="http', "src='http"):
        assert bad not in page, f"external resource reference found: {bad}"


def test_every_section_declares_its_data_source(real_build, monkeypatch):
    """Three organisations feed this dashboard and they measure different
    things. Every numbered section must say which one it rests on."""
    out_html, snap_dir = real_build
    monkeypatch.setattr("sys.argv", ["build_dashboard.py"])
    bd.main()
    page = out_html.read_text()
    # one provenance line per numbered section (10 numbered + view 2c)
    assert page.count('class="srcline"') >= 11


def test_dashboard_avoids_conflating_news_items_with_projects(real_build, monkeypatch):
    """'items' is meaningless to a reader and 'projects' would be wrong — the
    corpus counts news developments. Guard the wording against regressions."""
    out_html, snap_dir = real_build
    monkeypatch.setattr("sys.argv", ["build_dashboard.py"])
    bd.main()
    page = out_html.read_text()
    for banned in ("item count", "tracked items", "No items in", "Items / week"):
        assert banned not in page, f"imprecise wording resurfaced: {banned!r}"


def test_region_rollup_does_not_double_count_cross_border_projects():
    """A project shared by two countries is credited to both in the per-country
    layer, by design. Any roll-up must therefore deduplicate by project name —
    otherwise Great Plains -> Weyburn-Midale adds its 32.2 Mt to the Americas
    twice, and the regions stop summing to the world total."""
    sref = bd.load_storage_baseline()
    plocs = bd.load_project_locations()
    merged, _, regions = bd.build_country_map_data({}, {}, {}, sref, None, plocs)

    # The shared project really is credited to both countries.
    us_names = {p["name"] for p in merged["United States"]["storage"]["projects"]}
    ca_names = {p["name"] for p in merged["Canada"]["storage"]["projects"]}
    assert us_names & ca_names, "expected a cross-border project in the fixture data"

    # Every region counts each project once, and the regions sum to the truth.
    truth_names, truth_mt = set(), {}
    for p in sref["projects"]:
        truth_names.add(p["name"])
        truth_mt[p["name"]] = p.get("measured_actual_cumulative_mt")

    assert sum(r["storage_projects"] for r in regions.values()) == len(truth_names)
    expected_total = sum(v for v in truth_mt.values() if isinstance(v, (int, float)))
    assert sum(r["measured_mt"] for r in regions.values()) == pytest.approx(
        round(expected_total, 2), abs=0.05)

    # And specifically: the Americas must not carry the shared project twice.
    americas_names = set()
    for d in merged.values():
        if d["region"] == "Americas":
            americas_names.update(p["name"] for p in d["storage"].get("projects", []))
    assert regions["Americas"]["storage_projects"] == len(americas_names)


# ------------------------------------------------- GCCSI country-level layer

def test_gccsi_country_data_matches_the_reports_own_totals():
    """gen_gccsi_countries.py parses ~629 facility rows out of the GSR2024
    facilities list. Guard the headline reconciliations so a future re-parse
    can't silently drift: the report states these totals itself (Figure 3.1-4,
    p.15, and the narrative on p.32)."""
    ref = bd.load_reference_countries()
    assert ref, "reference-baseline-countries.json missing"
    by_country = {r["country"]: r for r in ref["countries"]}
    for country, expected in [("United States", 276), ("United Kingdom", 65),
                              ("Canada", 58), ("China", 25)]:
        assert by_country[country]["total_facilities"] == expected, (
            f"{country} total drifted from the figure stated in the source")
    # p.32: "The US remains the global facility leader with 19 projects in operation"
    assert by_country["United States"]["operating"] == 19


def test_curation_notes_document_every_dataset_and_its_caveats():
    """The CSVs hold rows; NOTES.md holds the part a row cannot — what a column
    means, where it came from, what is knowingly missing. A figure without its
    caveat is worse than no figure, so the notes are not optional."""
    import _curation
    notes_path = os.path.join(_curation.CSV_DIR, "NOTES.md")
    assert os.path.exists(notes_path), "curation/NOTES.md is missing"
    notes = open(notes_path, encoding="utf-8").read().lower()
    for dataset in ("funding-programmes.csv", "funding-enrichment.csv",
                    "project-locations.csv", "gccsi-countries.csv"):
        assert dataset in notes, f"NOTES.md does not cover {dataset}"
    # The caveats that stop numbers being misread must survive the migration.
    for topic in ("nameplate", "norway", "europe only", "drawdown",
                  "blank", "indicative"):
        assert topic in notes, f"NOTES.md no longer mentions {topic!r}"


def test_map_gccsi_country_exposes_all_four_metric_layers():
    layer = bd.map_gccsi_country(bd.load_reference_countries())
    us = layer["United States"]
    assert us["operating"] == 19
    assert us["capacity_mtpa"] and us["capacity_mtpa"] > 0
    assert us["carbon_price"]
    # Policy status is Europe-only in the source; the US must not be given one.
    assert us.get("policy_status") is None
    assert layer["Norway"]["policy_status"] == "published"


def test_policy_status_is_not_invented_outside_europe():
    """Figure 4.4-1 covers Europe only. Assigning its published/in-preparation/
    none taxonomy to Japan or Brazil would be our judgement, not the source's."""
    ref = bd.load_reference_countries()
    non_european_with_policy = [
        r["country"] for r in ref["countries"]
        if r.get("policy_status") and _countries.CONTINENT_GROUPS.get(r["country"]) != "Europe"
    ]
    assert not non_european_with_policy, (
        f"policy status invented for non-European countries: {non_european_with_policy}")


def test_every_country_has_a_continent_group():
    """A country missing from CONTINENT_GROUPS silently vanishes from the
    per-region roll-up while still appearing on the map."""
    missing = [c for c in _countries.COUNTRY_ISO if c not in _countries.CONTINENT_GROUPS]
    assert not missing, f"countries with no continent group: {missing}"


# ------------------------------------------------------- map marker legibility

def test_displace_markers_separates_overlapping_points():
    """Two markers on top of each other are one clickable target, not two."""
    markers = [{"x": 100.0, "y": 100.0}, {"x": 101.0, "y": 100.5},
               {"x": 300.0, "y": 300.0}]
    bd._displace_markers(markers, min_gap=11.0)
    a, b = markers[0], markers[1]
    assert a.get("moved") and b.get("moved")
    sep = math.hypot(a["dx"] - b["dx"], a["dy"] - b["dy"])
    assert sep >= 10.0, f"overlapping markers still {sep:.1f}px apart"
    # An isolated marker must not be nudged off its real location.
    assert not markers[2].get("moved")


def test_displaced_markers_keep_a_leader_back_to_the_true_location():
    """Displacement moves the symbol, never the stated position — so a moved
    marker has to retain its original coordinates for the leader line."""
    markers = [{"x": 50.0, "y": 50.0}, {"x": 51.0, "y": 50.0}]
    bd._displace_markers(markers, min_gap=11.0)
    for m in markers:
        assert m["x"] in (50.0, 51.0) and m["y"] == 50.0   # truth preserved
        assert "dx" in m and "dy" in m                      # drawn position added


def test_real_map_markers_are_all_individually_clickable():
    """End-to-end: no two rendered markers on the real map may sit closer than
    the minimum gap, or the Gulf cluster becomes unpickable again."""
    merged, _, _ = bd.build_country_map_data(
        {}, {}, {}, bd.load_storage_baseline(),
        bd.load_reference_countries(), bd.load_project_locations())
    svg, _ = bd.country_contour_map(merged)
    centres = [(float(x), float(y)) for x, y in
               re.findall(r'cx="([-\d.]+)" cy="([-\d.]+)" r="3\.4"', svg)]
    assert len(centres) >= 20
    worst = min(math.hypot(a[0] - b[0], a[1] - b[1])
                for i, a in enumerate(centres) for b in centres[i + 1:])
    assert worst >= 10.0, f"closest rendered markers are {worst:.1f}px apart"


def test_microdot_suppressed_where_the_country_already_has_pins():
    """Qatar carries a project pin; drawing its microstate ring underneath adds
    a collision and tells the reader nothing new. Bahrain has no project, so it
    keeps its ring."""
    merged, _, _ = bd.build_country_map_data(
        {}, {}, {}, bd.load_storage_baseline(),
        bd.load_reference_countries(), bd.load_project_locations())
    svg, _ = bd.country_contour_map(merged)
    qatar = re.findall(r'<g class="marker" data-country="Qatar"[^>]*>(.*?)</g>', svg, re.S)
    assert qatar and not any("microdot" in g for g in qatar)
    assert 'data-country="Bahrain"' in svg and "microdot" in svg


def test_markers_carry_an_enlarged_hit_target():
    """The visible dot stays small so the map reads cleanly; a transparent
    larger circle does the clicking."""
    merged, _, _ = bd.build_country_map_data(
        {}, {}, {}, bd.load_storage_baseline(), None, bd.load_project_locations())
    svg, _ = bd.country_contour_map(merged)
    assert 'class="hit"' in svg
    assert svg.count('class="hit"') == svg.count('<g class="marker"')


def test_country_card_can_be_pinned(real_build, monkeypatch):
    """Clicking a country must lock the card open — otherwise its scrollbar is
    unreachable, because moving the pointer off the country wipes the content."""
    out_html, _ = real_build
    monkeypatch.setattr("sys.argv", ["build_dashboard.py"])
    bd.main()
    page = out_html.read_text()
    for marker in ("pinnedCountry", "function pin(", "function unpin(",
                   "cc-unpin", "Escape", "if(!pinnedCountry) showCountry"):
        assert marker in page, f"pinning logic missing: {marker}"


# ---------------------------------------------------- maintenance safeguards

def test_unreviewed_money_is_surfaced_not_silently_counted():
    """funding-enrichment.json is keyed by record id, so it only covers records
    that existed when it was last reviewed. Money arriving later is counted in
    full by default — safe for a total, but the audit decays invisibly unless
    the backlog is reported."""
    fx, _ = bd.load_fx()
    bd.load_records(fx)
    assert bd.UNREVIEWED == [], (
        "unclassified money in the corpus: "
        + ", ".join(r.get("id", "?") for r in bd.UNREVIEWED))


def test_unreviewed_detection_actually_fires(monkeypatch):
    """Guard the guard: if the coverage check silently stopped working, the
    test above would pass for the wrong reason."""
    real = bd.load_funding_enrichment()
    victim = "2026-07-16#01"
    assert victim in real, "fixture record has gone; pick another"
    monkeypatch.setattr(bd, "load_funding_enrichment",
                        lambda: {k: v for k, v in real.items() if k != victim})
    fx, _ = bd.load_fx()
    bd.load_records(fx)
    assert any(r.get("id") == victim for r in bd.UNREVIEWED)


def test_unreviewed_check_ignores_radar_items():
    """Radar items carry money but are excluded from every total. Flagging them
    would be noise that trains people to ignore the warning."""
    fx, _ = bd.load_fx()
    fresh, radar, _ = bd.load_records(fx)
    radar_money = {r["id"] for r in radar if r.get("amount_aud")}
    assert radar_money, "expected some radar records to carry money"
    assert not (radar_money & {r.get("id") for r in bd.UNREVIEWED})


def test_gccsi_parser_locates_its_section_by_content():
    """Page numbers move between report editions. A pinned range applied to a
    new edition would parse the wrong pages and produce a silently wrong
    dataset, so the section must be found by its own column header."""
    import gen_gccsi_countries as gen
    src = inspect.getsource(gen)
    assert "def find_facilities_pages" in src
    assert "Facility" in src and "Country" in src
    # The old hardcoded constants must be gone.
    assert "FIRST_PAGE, LAST_PAGE = 56, 79" not in src
    assert gen.PAGE_HINT_END - gen.PAGE_HINT_START >= 40, \
        "the search window is too narrow to survive a repaginated edition"


def test_gccsi_publication_classifier_routes_each_type():
    """A new file is only useful if the alert says what it needs — a quarterly
    update and a Global Status Report require completely different follow-up."""
    import check_gccsi_publications as chk
    cases = {
        "Q3-2026-Report.pdf": "quarterly-update",
        "Global-Status-of-CCS-2025.pdf": "global-status-report",
        "The-Safety-and-Permanence-of-CO2-Geological-Storage.pdf": "storage-permanence",
        "Economics-of-DAC_FINAL.pdf": "other",
    }
    for filename, expected in cases.items():
        kind, actions = chk.classify(filename)
        assert kind == expected, f"{filename} classified as {kind}"
        assert actions, f"{filename} has no follow-up actions"
    # The quarterly path must keep warning about the dedup trap.
    _, quarterly_actions = chk.classify("Q3-2026-Report.pdf")
    assert any("dedup" in a.lower() or "duplicate" in a.lower() for a in quarterly_actions)


# ------------------------------------------------ curated CSV source of truth

CURATED_CSVS = ("funding-programmes.csv", "funding-enrichment.csv",
                "project-locations.csv", "gccsi-countries.csv")


def test_curated_csvs_are_the_source_of_truth():
    """All four exist, and no JSON copy survives to drift out of step with them."""
    import _curation
    for name in CURATED_CSVS:
        path = os.path.join(_curation.CSV_DIR, name)
        assert os.path.exists(path), f"{name} is missing"
        assert _curation.read_rows(name), f"{name} is empty"
    for orphan in ("funding-programmes.json", "funding-enrichment.json",
                   "project-locations.json", "reference-baseline-countries.json"):
        assert not os.path.exists(os.path.join(_curation.DATA_DIR, orphan)), (
            f"{orphan} still exists — two representations of the same data is "
            f"exactly the drift risk the migration removed")


def test_blank_cells_load_as_none_never_zero():
    """The dashboard distinguishes 'not reported' from 'zero' everywhere. A blank
    drawdown rendering as A$0 would say a government has spent nothing when the
    truth is that nobody publishes the figure."""
    import _curation
    assert _curation._coerce("awarded_to_date", "") is None
    assert _curation._coerce("awarded_to_date", "   ") is None
    assert _curation._coerce("capacity_mtpa", "") is None
    assert _curation._coerce("awarded_to_date", "0") == 0     # a real zero survives


def test_csv_number_typing_survives_the_spreadsheet():
    """period_years is 25 for the UK clusters but 2.5 for the Viking grant, so
    whole numbers must stay int and fractions stay float. Coordinates and
    capacities stay float even when whole — -103 instead of -103.0 reads as
    dropped precision."""
    import _curation
    assert _curation._coerce("period_years", "25") == 25
    assert isinstance(_curation._coerce("period_years", "25"), int)
    assert _curation._coerce("period_years", "2.5") == 2.5
    assert isinstance(_curation._coerce("lon", "-103"), float)
    assert isinstance(_curation._coerce("capacity_mtpa", "4"), float)
    assert _curation._coerce("amount", "21700000000") == 21_700_000_000
    assert isinstance(_curation._coerce("amount", "21700000000"), int)


def test_curated_data_passes_integrity_checks():
    """The validation the importer used to run at edit time. These files are now
    maintained programmatically, so the guard belongs in the suite: bad data
    should fail the build, not reach the dashboard."""
    import _curation
    fx, _ = bd.load_fx()
    problems = []

    progs = _curation.load_funding_programmes()["programmes"]
    for p in progs:
        where = f"funding-programmes: {p.get('programme')}"
        if p["country"] not in _countries.COUNTRY_ISO and \
                p["country"] not in _countries.NON_COUNTRY_TOKENS:
            problems.append(f"{where}: unknown country {p['country']!r}")
        if p.get("currency") and p["currency"] not in fx:
            problems.append(f"{where}: currency {p['currency']!r} has no FX rate")
        if p.get("scope") not in ("ccs-specific", "ccs-eligible"):
            problems.append(f"{where}: bad scope {p.get('scope')!r}")
        if p.get("status") not in ("announced", "committed", "operating"):
            problems.append(f"{where}: bad status {p.get('status')!r}")
        if not p.get("source"):
            problems.append(f"{where}: no source")
        if p.get("amount") and p.get("awarded_to_date") and \
                p["awarded_to_date"] > p["amount"]:
            problems.append(f"{where}: awarded exceeds the programme total")

    enrich = _curation.load_funding_enrichment()
    VALID_BASIS = {"government-funding", "private-investment", "project-capex",
                   "supplier-contract", "market-aggregate", "not-ccs-funding",
                   "cancelled"}
    for rid, e in enrich.items():
        if e.get("funder_type") not in ("government", "private", "mixed", "none"):
            problems.append(f"funding-enrichment {rid}: bad funder_type")
        if e.get("basis") not in VALID_BASIS:
            problems.append(f"funding-enrichment {rid}: bad basis {e.get('basis')!r}")
        if e.get("duplicate_of") and e["duplicate_of"] not in enrich:
            problems.append(f"funding-enrichment {rid}: duplicate_of points nowhere")
        if not e.get("note"):
            problems.append(f"funding-enrichment {rid}: no note — the audit trail")

    locs = _curation.load_project_locations()["locations"]
    known = {p["name"] for p in bd.load_storage_baseline()["projects"]}
    for name, loc in locs.items():
        if name not in known:
            problems.append(f"project-locations: {name!r} is not in storage-baseline "
                            f"— its pin would never be drawn")
        if not (-90 <= loc["lat"] <= 90) or not (-180 <= loc["lon"] <= 180):
            problems.append(f"project-locations: {name} has out-of-range coordinates")

    for row in _curation.load_reference_countries()["countries"]:
        if row["country"] not in _countries.COUNTRY_ISO:
            problems.append(f"gccsi-countries: unknown country {row['country']!r}")

    assert not problems, "curated data failed validation:\n  " + "\n  ".join(problems)


def test_every_storage_project_still_has_a_pin_after_migration():
    locs = _curation_locations()
    missing = [p["name"] for p in bd.load_storage_baseline()["projects"]
               if p["name"] not in locs]
    assert not missing, f"storage projects with no coordinates: {missing}"


def _curation_locations():
    import _curation
    return _curation.load_project_locations()["locations"]


def test_generated_dataset_is_not_hand_edited(real_build, monkeypatch):
    """gccsi-countries.csv is produced by gen_gccsi_countries.py. If someone
    hand-edits it the next regeneration silently discards the edit, so the
    header must keep exactly the columns the generator writes."""
    import _curation
    rows = _curation.read_rows("gccsi-countries.csv")
    expected = {"country", "operating", "construction", "advanced_development",
                "early_development", "pipeline", "total_facilities",
                "cross_border_participation", "capacity_mtpa",
                "capacity_all_stages_mtpa", "page", "policy_status",
                "policy_page", "policy_note", "carbon_price", "carbon_price_page"}
    assert set(rows[0]) == expected
