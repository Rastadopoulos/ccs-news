"""Regression tests for scripts/build_dashboard.py.

Two layers:
  1. Unit tests over synthetic fact records (FX normalisation, status-weighted
     money, dedup, fresh/radar split, signal buckets).
  2. A real-environment build: rebuild the dashboard from the repo's actual
     data into a temp dir and check the output contract (self-contained HTML,
     snapshot naming, BUILD_DATE stamping) without touching dashboard/index.html.
"""

import json
import os

import pytest

import build_dashboard as bd


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
    audit_dir = tmp_path / "audit"
    raw_dir.mkdir(parents=True)
    audit_dir.mkdir()
    (data_dir / "facts-backfill.jsonl").write_text(
        '{"headline": "ok1"}\n\nnot json at all\n{"headline": "ok2"}\n')
    (audit_dir / "2026-07-20-facts.json").write_text('{bad json')
    monkeypatch.setattr(bd, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(bd, "RAW_DIR", str(raw_dir))
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
