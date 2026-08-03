#!/usr/bin/env python3
"""Board-facing dashboard hierarchy built over the canonical reliability model."""

from __future__ import annotations

import csv
import html
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "dashboard" / "data"

REQUIRED = (
    DATA / "entities" / "projects.csv",
    DATA / "entities" / "capacities.csv",
    DATA / "entities" / "event-crosswalk.csv",
    DATA / "model" / "summary.json",
    DATA / "baselines" / "iea" / "metadata.json",
    DATA / "baselines" / "gccsi" / "metadata.json",
    DATA / "baselines" / "london-register" / "metadata.json",
    DATA / "baselines" / "comparison" / "metadata.json",
)


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def money(value: object) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "not published"
    if abs(amount) >= 1e9:
        return f"A${amount / 1e9:.2f}bn"
    if abs(amount) >= 1e6:
        return f"A${amount / 1e6:.1f}m"
    return f"A${amount:,.0f}"


def number(value: object, places: int = 1) -> str:
    return f"{float(value):,.{places}f}"


def total_by(rows: list[dict], field: str, category: str | None = None) -> float:
    value = 0.0
    for row in rows:
        if category and row.get("category") != category:
            continue
        try:
            value += float(row[field]) if row.get(field) not in (None, "") else 0
        except (TypeError, ValueError):
            pass
    return value


def validate_current_baselines(model: dict) -> None:
    """Fail loudly when a required generated baseline regresses or goes stale."""
    problems = []
    if model.get("iea", {}).get("edition") != "2026" or model.get("iea", {}).get("update_date") != "2026-03-27":
        problems.append("IEA baseline is not the verified 2026-03-27 edition")
    if model.get("gccsi", {}).get("edition") != "2025" or model.get("gccsi", {}).get("data_asof") != "2025-07":
        problems.append("GCCSI global baseline is not GSR 2025 / July 2025")
    london = model.get("london", {})
    if london.get("edition") != "2025" or london.get("summary", {}).get("year_end") != 2024:
        problems.append("London Register is not the 2025 edition with data through 2024")
    if problems:
        raise ValueError("; ".join(problems))


def _extract_map(legacy: str) -> str:
    start = legacy.index('<h2 id="map">')
    end = legacy.index('<h2 id="terms">')
    chunk = legacy[start:end]
    chunk = re.sub(r'<table class="tbl regionroll">.*?</table>', '', chunk, flags=re.S)
    chunk = re.sub(r'<div class="eubadge">.*?</div>', '', chunk, flags=re.S)
    chunk = chunk.replace('<h2 id="map">Where CCS is happening worldwide</h2>',
                          '<h2 id="map">6 · World map</h2>')
    chunk = chunk.replace(
        'Every country is shaded by whichever measure you pick below.',
        'Country shading is a discovery view and is non-additive: multi-country events can appear in more than one country, while reconciled totals below use one canonical physical geography. Every country is shaded by whichever measure you pick below.'
    )
    chunk = chunk.replace('Storage register (Imperial &amp; GCCSI)',
                          'Legacy named-project subset (Imperial &amp; GCCSI)')
    chunk = chunk.replace('CO₂ stored to date</button>', 'Named-subset cumulative</button>')
    chunk = chunk.replace('New public money</button>', 'Public funding events</button>')
    chunk = chunk.replace('New private money</button>', 'Private investment / capex events</button>')
    chunk = chunk.replace('see <a href="#v2c">View 2c</a>',
                          'see <a href="#methodology">Methodology</a>')
    chunk = chunk.replace('see View 2c for the full reconciliation',
                          'see Methodology for the full reconciliation')
    return chunk


def _scripts(legacy: str) -> str:
    start = legacy.index('<nav class="floatnav"')
    suffix = legacy[start:]
    suffix = re.sub(r'^<nav class="floatnav".*?</nav>', '', suffix, count=1, flags=re.S)
    if suffix.endswith('</div>'):
        suffix = suffix[:-6]
    suffix = suffix.replace(
        "Imperial College London, London Register of Subsurface CO₂ Storage — cumulative CO₂ actually measured as injected, in millions of tonnes. This is measured delivery, deliberately kept separate from the capacity and reported figures above.",
        "Legacy named-project subset from storage-baseline.json — incomplete and not a global total. Use the 2025 London Register figures in Deployment reality for the current 46-project all-storage total."
    )
    suffix = suffix.replace("title:'CO₂ stored to date'", "title:'Named-subset cumulative CO₂'")
    suffix = suffix.replace("title:'New public money reported'", "title:'Public funding events reported'")
    suffix = suffix.replace("title:'New private money reported'", "title:'Private investment / capex events reported'")
    suffix = suffix.replace("row('New public money'", "row('Public funding events'")
    suffix = suffix.replace("row('New private money'", "row('Private investment / capex events'")
    return suffix


def upgrade_body(legacy: str, fresh: list[dict], build_date: str) -> str:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.exists()]
    if missing:
        raise FileNotFoundError("required current dashboard inputs missing: " + ", ".join(missing))
    model = json.loads((DATA / "model" / "summary.json").read_text(encoding="utf-8"))
    validate_current_baselines(model)
    projects = {row["project_id"]: row for row in read_csv(DATA / "entities" / "projects.csv")}
    capacities = read_csv(DATA / "entities" / "capacities.csv")
    crosswalk = {row["event_id"]: row for row in read_csv(DATA / "entities" / "event-crosswalk.csv")}
    policies = read_csv(DATA / "entities" / "policy-instruments.csv")
    commitments = read_csv(DATA / "model" / "funding-commitments.csv")
    programme_rows = read_csv(DATA / "model" / "funding-programmes.csv")
    regional = read_csv(DATA / "model" / "regional-reconciliation.csv")
    iea_rows = read_csv(DATA / "baselines" / "iea" / "projects.csv")
    gccsi_rows = read_csv(DATA / "baselines" / "gccsi" / "construction-projects.csv")
    prefix = legacy[:legacy.index('<div class="wrap">')]
    map_chunk = _extract_map(legacy)
    scripts = _scripts(legacy)

    coverage = model["coverage"]
    london = model["london"]
    gccsi = model["gccsi"]
    comparison = model["baseline_comparison"]
    iea_meta = model["iea"]
    funding = model["funding"]
    source_counts = model["source_counts"]
    storage_summary = london["summary"]

    iea_stage_basis = defaultdict(lambda: [0, 0.0])
    for row in iea_rows:
        key = (row["source_status"], row["capacity_basis"])
        iea_stage_basis[key][0] += 1
        if row.get("capacity_mtpa") not in (None, ""):
            iea_stage_basis[key][1] += float(row["capacity_mtpa"])
    latest_event_date = max((r.get("briefing_date", "") for r in fresh), default="")
    stage = model["deployment_stage_signals"]
    advancing = stage.get("advancing", 0)
    slipping = stage.get("slipping_suspended_cancelled", 0)

    def kpi(value: str, label: str, basis: str, href: str) -> str:
        return (f'<a class="rkpi" href="{href}"><span class="rkv">{esc(value)}</span>'
                f'<span class="rkl">{esc(label)}</span><span class="rkb">{esc(basis)}</span></a>')

    css = """<style>
body{background:#f3f6f5;color:#17302d}.wrap{max-width:1240px}.rheader{padding:8px 0 22px;border-bottom:3px solid #0b6b5b}.rheader h1{max-width:850px;font-size:clamp(30px,5vw,52px);line-height:1.02;letter-spacing:-.035em}.rdeck{font-size:17px;max-width:850px;color:#4c6661}.statusline{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.status{display:inline-flex;align-items:center;gap:7px;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:700;background:#fff;border:1px solid #cfdad7}.status.bad{color:#8b2e2b;border-color:#e5b6b0;background:#fff6f4}.status.good{color:#17624f}.sectionnav{position:sticky;top:0;z-index:60;margin:0 -20px 20px;padding:9px 20px;display:flex;gap:8px;overflow-x:auto;background:rgba(243,246,245,.96);border-bottom:1px solid #cfdad7;backdrop-filter:blur(8px)}.sectionnav a{white-space:nowrap;text-decoration:none;color:#305d55;font-size:12px;font-weight:700;padding:5px 8px;border-radius:6px}.sectionnav a:hover,.sectionnav a:focus{background:#dfece8}.rkpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0 8px}.rkpi{display:flex;flex-direction:column;min-height:148px;padding:16px;background:#fff;border:1px solid #d7e1de;border-radius:12px;text-decoration:none;color:inherit}.rkpi:hover{border-color:#0b6b5b}.rkv{font-size:27px;font-weight:760;color:#0b6b5b}.rkl{font-size:14px;font-weight:700;margin-top:4px}.rkb{font-size:11px;color:#60736f;margin-top:auto;padding-top:10px}.sectionlead{max-width:850px;color:#5b706b}.callout{background:#e7f2ef;border-left:4px solid #0b6b5b;border-radius:0 9px 9px 0;padding:13px 16px}.callout.bad{background:#fff1ee;border-color:#b23b35}.conclusions{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}.conclusion{padding:14px;background:#fff;border:1px solid #d7e1de;border-radius:10px}.conclusion b{display:block;margin-bottom:5px}.metricgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric{background:#fff;border:1px solid #d7e1de;border-radius:10px;padding:14px}.metric strong{font-size:23px;color:#0b6b5b;display:block}.metric small{display:block;color:#60736f;margin-top:7px}.basis-tag{display:inline-block;border-radius:5px;padding:2px 6px;font-size:10px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;background:#e2eeeb;color:#275c52}.basis-tag.derived{background:#fff2d9;color:#7b5716}.baselinegrid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.baseline{background:#fff;border:1px solid #d7e1de;border-radius:10px;padding:16px}.baseline h3{text-transform:none;letter-spacing:0;color:#17302d;font-size:16px}.compare-note{font-size:12px;color:#60736f;border-top:1px solid #e1e8e6;margin-top:12px;padding-top:10px}.rtbl{width:100%;border-collapse:collapse;font-size:13px}.rtbl th,.rtbl td{text-align:left;padding:8px 9px;border-bottom:1px solid #e1e8e6;vertical-align:top}.rtbl th{color:#4e6661;font-size:11px;text-transform:uppercase;letter-spacing:.04em}.rtbl .num{text-align:right;font-variant-numeric:tabular-nums}.lowconf{background:#fff8ea}.filters{display:flex;gap:9px;flex-wrap:wrap;align-items:end;padding:12px;background:#e7efed;border-radius:9px;margin:12px 0}.filters label{font-size:11px;font-weight:700;color:#4e6661}.filters select{display:block;margin-top:3px;padding:7px 8px;border:1px solid #bfcfcb;background:white;border-radius:6px;max-width:170px}.archive-status{margin-left:auto;font-size:12px;color:#4e6661}.archive-wrap{max-height:620px;overflow:auto;border:1px solid #d7e1de;background:#fff;border-radius:9px}.evidence-row[hidden]{display:none}.signal-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.signal{background:#fff;border:1px solid #d7e1de;border-radius:9px;padding:13px}.signal a{font-weight:700;color:#155f52}.signal p{font-size:12px;color:#586d68}.method details,.method>details{background:#fff;border:1px solid #d7e1de;border-radius:9px;padding:11px 14px;margin:8px 0}.method summary{font-weight:750;cursor:pointer}.source-note{font-size:11px;color:#60736f}.correction{border-left:3px solid #c79024}.mapcard{border-color:#cbdad6}.pill.active{background:#0b6b5b}.derived-note{color:#7b5716;background:#fff8ea;padding:8px;border-radius:6px}.footer-note{margin-top:30px;font-size:12px;color:#60736f}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(max-width:950px){.conclusions{grid-template-columns:repeat(2,1fr)}.metricgrid{grid-template-columns:repeat(2,1fr)}.signal-grid{grid-template-columns:1fr 1fr}}
@media(max-width:720px){.rkpis{grid-template-columns:1fr 1fr}.baselinegrid{grid-template-columns:1fr}.sectionnav{top:0}.rtbl{font-size:12px}.rtbl th,.rtbl td{padding:7px 6px}}
@media(max-width:500px){.wrap{padding-left:14px;padding-right:14px}.rkpis,.conclusions,.metricgrid,.signal-grid{grid-template-columns:1fr}.rkpi{min-height:120px}.rheader h1{font-size:34px}.sectionnav{margin-left:-14px;margin-right:-14px;padding-left:14px}.archive-wrap{max-height:520px}}
@media print{.sectionnav,.filters{display:none}.archive-wrap{max-height:none;overflow:visible}.rkpi,.metric,.baseline{break-inside:avoid}}
</style>"""

    parts = [prefix, css, '<div class="wrap">']
    A = parts.append
    A('<header class="rheader" id="top"><div class="eyebrow">CO2CRC · Decision-grade CCS intelligence</div>')
    A('<h1>CCS deployment: what is real, what moved, and how reliable is the evidence?</h1>')
    A(f'<p class="rdeck">A project- and component-level view of deployment, finance and policy. News is retained as evidence, but never summed as if every article were a new project.</p>')
    A('<div class="statusline">')
    A(f'<span class="status bad">● {esc(coverage["status"].title())}</span>')
    A(f'<span class="status">Build {esc(build_date)}</span><span class="status">Latest facts file {esc(coverage["latest_fact_date"])}</span>')
    A(f'<span class="status">Latest tracked event {esc(latest_event_date)}</span><span class="status">{len(projects)} canonical entities</span>')
    A('</div></header>')
    A('<nav class="sectionnav" aria-label="Dashboard sections">'
      '<a href="#freshness">1 Freshness</a><a href="#changed">2 What changed</a>'
      '<a href="#deployment">3 Deployment</a><a href="#australia">4 Australia</a>'
      '<a href="#funding">5 Funding</a><a href="#map">6 World map</a>'
      '<a href="#policy">7 Policy</a><a href="#technology">8 Technology</a>'
      '<a href="#social">9 Social licence</a><a href="#evidence">10 Evidence</a>'
      '<a href="#methodology">11 Methodology</a></nav>')

    A('<div class="rkpis" aria-label="Headline measures">')
    A(kpi(f'{storage_summary["cumulative_all_storage_mt"]:.1f} Mt', 'Actual CO₂ stored',
          'London Register · cumulative all-storage · 46 projects · through 2024', '#deployment'))
    A(kpi('64 Mtpa', 'Operating capture capacity',
          'GCCSI GSR 2025 · 77 operating facilities · data July 2025 · nameplate', '#deployment'))
    A(kpi('44 Mtpa', 'Under-construction capture capacity',
          'GCCSI GSR 2025 · 47 facilities · FID not separately published · July 2025', '#deployment'))
    A(kpi(f'{advancing} / {slipping}', 'Advancing / slipping, suspended or cancelled',
          f'Unique canonical stage signals · {len(projects)}-entity curated population · May–Jul 2026', '#deployment'))
    A(kpi(f'{money(funding["ccs_specific_reported_programme_total_aud"])} / {money(funding["published_awards_lower_bound_aud"])}',
          'CCS-specific programmes / published awards',
          f'Programme totals vs lower-bound awards across {funding["published_awards_reporting_programmes"]} reporting programmes · A$ FX basis', '#funding'))
    A(kpi(f'{coverage["calendar_days_since_latest_facts"]} days behind', 'Data freshness / coverage confidence',
          f'{coverage["status"]} · latest facts {coverage["latest_fact_date"]} · no quiet-day claim', '#freshness'))
    A('</div>')

    A('<h2 id="freshness">1 · Data freshness and coverage status</h2>')
    A(f'<div class="callout bad"><b>Collection is impaired, not quiet.</b> The local fact stream last produced a file on {esc(coverage["latest_fact_date"])} and is {coverage["calendar_days_since_latest_facts"]} calendar days behind this {esc(build_date)} build. Missing scheduled sampler files prevent any “no news” conclusion. Retry candidates are retained in <code>dashboard/data/coverage/retry-candidates.json</code>.</div>')
    A('<div class="metricgrid">')
    A(f'<div class="metric"><strong>{source_counts.get("daily_news", 0)}</strong>Daily-news events<small>Fresh, deduplicated events; coverage May–July 2026.</small></div>')
    A(f'<div class="metric"><strong>{source_counts.get("periodic_report", 0)}</strong>Periodic-report records<small>GCCSI Q2 2026 batch; excluded from weekly newsflow trends.</small></div>')
    A(f'<div class="metric"><strong>{source_counts.get("external_iea_rows", 0):,}</strong>IEA baseline projects<small>Authenticated official 2026 workbook · {iea_meta["summary"]["named_project_rows"]:,} named rows · separate from news and GCCSI.</small></div>')
    A(f'<div class="metric"><strong>{source_counts.get("external_london_storage_projects", 0)}</strong>London storage projects<small>2025 register edition; annual series through 2024.</small></div></div>')
    A('<p class="source-note">Quarterly items without item-level URLs carry report-level GCCSI provenance. External baseline rows are never described as daily developments.</p>')

    A('<h2 id="changed">2 · What changed since the previous dashboard</h2>')
    A('<div class="conclusions">')
    changes = [
        ('Collection gap surfaced', f'No quiet-day inference: the repository is {coverage["calendar_days_since_latest_facts"]} calendar days behind after {coverage["latest_fact_date"]}.'),
        ('Storage baseline corrected', f'The downloadable London Register now sums to {storage_summary["cumulative_all_storage_mt"]:.1f} Mt all-storage through 2024, replacing the stale ~383 Mt local headline.'),
        ('Capacity made basis-specific', 'Capture, transport, storage injection, utilisation, policy targets and cumulative resources no longer share one additive field.'),
        ('Two current global baselines', 'IEA 2026 and GCCSI 2025 are displayed side by side with their own stages, scope and methodology; they are never blended.'),
        ('Latest execution evidence', 'Northern Endurance and Tangguh moved into physical construction; Tangguh’s US$7bn covers gas development plus CCUS, so its CCS share remains unknown.'),
    ]
    for title, text in changes:
        A(f'<div class="conclusion"><b>{esc(title)}</b><span>{esc(text)}</span></div>')
    A('</div>')

    A('<h2 id="deployment">3 · Deployment reality</h2><p class="sectionlead">Stock measures come from official baselines; flow measures come from unique canonical stage changes. Capture and storage-injection capacities are never added together.</p>')
    A('<div class="baselinegrid">')
    A(f'<div class="baseline"><h3>IEA CCUS Projects Database 2026</h3><span class="basis-tag">Official companion baseline</span>'
      f'<table class="rtbl"><tr><th>Stage / basis</th><th class="num">Rows</th><th class="num">Mtpa</th></tr>'
      f'<tr><td>Operational · capture</td><td class="num">{iea_stage_basis[("Operational", "capture_capacity")][0]}</td><td class="num">{iea_stage_basis[("Operational", "capture_capacity")][1]:.3f}</td></tr>'
      f'<tr><td>Operational · storage injection</td><td class="num">{iea_stage_basis[("Operational", "storage_injection_capacity")][0]}</td><td class="num">{iea_stage_basis[("Operational", "storage_injection_capacity")][1]:.3f}</td></tr>'
      f'<tr><td>Under construction · capture</td><td class="num">{iea_stage_basis[("Under construction", "capture_capacity")][0]}</td><td class="num">{iea_stage_basis[("Under construction", "capture_capacity")][1]:.3f}</td></tr>'
      f'<tr><td>Under construction · storage injection</td><td class="num">{iea_stage_basis[("Under construction", "storage_injection_capacity")][0]}</td><td class="num">{iea_stage_basis[("Under construction", "storage_injection_capacity")][1]:.3f}</td></tr></table>'
      '<p class="compare-note">Edition/update: 27 Mar 2026; authenticated official workbook, with project announcements through February 2026. Coverage: projects above 100,000 tCO₂/yr; DAC above 1,000 tCO₂/yr; commercial projects may be included when capacity is unknown. Excludes low-climate-benefit utilisation, conventional internal urea use and naturally occurring CO₂ used for EOR.</p></div>')
    A(f'<div class="baseline"><h3>GCCSI Global Status of CCS 2025</h3><span class="basis-tag">Official companion baseline</span>'
      f'<table class="rtbl"><tr><th>Stage</th><th class="num">Facilities</th><th class="num">Capture Mtpa</th></tr>'
      f'<tr><td>Operating</td><td class="num">{gccsi["global"]["operating_facilities"]}</td><td class="num">{gccsi["global"]["operating_capacity_mtpa"]}</td></tr>'
      f'<tr><td>In construction</td><td class="num">{gccsi["global"]["construction_facilities"]}</td><td class="num">{gccsi["global"]["construction_capacity_mtpa"]}</td></tr>'
      f'<tr><td>In development</td><td class="num">{gccsi["global"]["development_facilities"]}</td><td class="num">—</td></tr>'
      f'<tr><td>Pipeline total</td><td class="num">{gccsi["global"]["pipeline_facilities"]}</td><td class="num">{gccsi["global"]["pipeline_capacity_mtpa"]}</td></tr></table>'
      '<p class="compare-note">Edition/data: GSR 2025, July 2025. The current structured appendix covers all 47 in-construction facilities. The all-stage country map remains explicitly GSR 2024 because GSR 2025 does not reproduce that full country table.</p></div></div>')
    A(f'<div class="callout"><b>Cross-baseline comparison is reviewable, not guessed.</b> Exact normalised IEA↔GCCSI names: {comparison["matched_projects"]}; rule-assisted same-country naming candidates awaiting human review: {comparison["likely_naming_candidates_for_review"]}; authenticated IEA named projects: {iea_meta["summary"]["named_project_rows"]}; GCCSI construction names without an exact IEA name match: {comparison["gccsi_only_named_projects"]}. Candidate matches are never silently accepted.</div>')

    A('<h3>Canonical capacity by basis and lifecycle</h3><div class="card"><table class="rtbl"><thead><tr><th>Basis</th><th>Lifecycle</th><th class="num">Nameplate Mtpa</th><th>Population / vintage</th></tr></thead><tbody>')
    for row in model["capacity_by_basis_and_stage"]:
        A(f'<tr><td>{esc(row["capacity_basis"].replace("_", " "))}</td><td>{esc(row["lifecycle_stage"])}</td><td class="num">{float(row["nameplate_mtpa"]):.3f}</td><td>{len(projects)}-entity curated register · latest source dates 2025–2026</td></tr>')
    A('</tbody></table><p class="source-note">Policy-target capacity is non-project and non-additive. Removal purchases, cumulative storage resources and transport values are excluded unless their own basis is populated.</p></div>')

    A('<h3>Actual storage delivery — current London Register</h3><div class="metricgrid">')
    A(f'<div class="metric"><strong>{storage_summary["cumulative_all_storage_mt"]:.1f} Mt</strong>All-storage cumulative<small><span class="basis-tag">reported / measured</span> 46 projects · 1996–2024 · annual register series; some years are derived averages · high confidence in sum.</small></div>')
    A(f'<div class="metric"><strong>{storage_summary["latest_annual_all_storage_mt"]:.2f} Mt</strong>2024 annual injection<small><span class="basis-tag">annual actual</span> All classes · 46-project register population · 2024 · high confidence in sum.</small></div>')
    for cls in ('dedicated', 'associated', 'eor'):
        s = storage_summary['by_storage_class'][cls]
        label = 'EOR' if cls == 'eor' else cls.title()
        project_label = 'project' if s['projects'] == 1 else 'projects'
        A(f'<div class="metric"><strong>{s["cumulative_mt"]:.2f} Mt</strong>{esc(label)} cumulative<small><span class="basis-tag">register total</span> {s["projects"]} {project_label} · through 2024 · 2024 annual {s["latest_annual_mt"]:.2f} Mt · classification confidence recorded per project.</small></div>')
    A('</div>')
    A('<div class="callout correction"><b>Storage correction ledger.</b> The old 56–65 Mt dedicated figure was an analytical derivation, not an independent measurement; the ~123 Mt EOR figure was roughly 2020-vintage and is no longer labelled “to date”; the 111.6 Mt map figure was an incomplete named-project subset. The historical ~383 Mt figure was all-storage cumulative since 1996 in the older local baseline; the current downloadable register gives 384.6 Mt through 2024.</div>')

    au = model["australia"]
    A('<h2 id="australia">4 · Australia benchmark</h2><p class="sectionlead">Authoritative stock measures lead; recent Australian news is an overlay only.</p><div class="metricgrid">')
    A('<div class="metric"><strong>4.0 Mtpa</strong>Operating capture capacity<small>GCCSI GSR 2024 country table · one operating facility · nameplate · data 24 Jul 2024. Kept visibly older because no equivalent 2025 all-stage country table is published.</small></div>')
    A(f'<div class="metric"><strong>{au["operating_storage_injection_nameplate_mtpa"]:.1f} Mtpa</strong>Operating storage-injection nameplate<small>Canonical Moomba + Gorgon subset · different basis from capture · source dates to Jul 2026.</small></div>')
    A(f'<div class="metric"><strong>{au["actual_annual_storage_mt_known_subset"]:.1f} Mt</strong>Known annual actual storage<small>Moomba disclosed subset only; Gorgon actual is missing and not treated as zero.</small></div>')
    A(f'<div class="metric"><strong>{au["projects_advancing_stage_in_observed_event_history"]}</strong>Observed recent stage advance<small>Canonical event history; recent news overlay, not the benchmark denominator.</small></div></div>')
    A(f'<div class="callout"><b>Support mechanism:</b> {esc(au["policy_support"])}. <b>Published awards:</b> {esc(au["public_support_awarded"])}. Industrial-emissions scaling is {esc(au["emissions_scale_comparison"])}.</div>')

    A('<h2 id="funding">5 · Funding and commercial support</h2><p class="sectionlead">Programme stock, awards, spend, private investment, capex, contracts and cancellations are separate measures. Nothing here is called “new money”.</p>')
    A('<div class="metricgrid">')
    A(f'<div class="metric"><strong>{money(funding["ccs_specific_reported_programme_total_aud"])}</strong>CCS-specific programme stock<small>Whole-of-life reported ceilings; includes the EU bloc where applicable; not annual spend.</small></div>')
    A(f'<div class="metric"><strong>{money(funding["ccs_eligible_reported_programme_total_aud"])}</strong>CCS-eligible broader programmes<small>CCS share unknown; never added to CCS-specific stock.</small></div>')
    A(f'<div class="metric"><strong>{money(funding["published_awards_lower_bound_aud"])}</strong>Published awards: at least<small>Across {funding["published_awards_reporting_programmes"]} reporting programmes. The other {funding["missing_drawdown_programmes"]} missing drawdown fields mean “not published”, not zero.</small></div>')
    A('<div class="metric"><strong>Not consistently published</strong>Actual spend<small>Kept separate from awards/contracts. No zero is inferred from missing drawdown data.</small></div></div>')
    cat_labels = [
        ('ccs_public_funding_event', 'CCS public-funding events'), ('private_investment', 'Private investment'),
        ('project_capex', 'Project capex'), ('supplier_contract', 'Supplier contracts'),
        ('cancelled_project_capex', 'Cancelled whole-project capex'),
        ('withdrawn_or_redirected_public_funding', 'Withdrawn/redirected public funding'),
    ]
    A('<div class="card"><table class="rtbl"><thead><tr><th>Distinct event category</th><th class="num">Reported A$</th><th>Interpretation</th></tr></thead><tbody>')
    for key, label in cat_labels:
        rows = [r for r in commitments if r['category'] == key and not r.get('duplicate_of')]
        amount = total_by(rows, 'reported_value_aud')
        note = 'Non-additive supplier spend inside project capex.' if key == 'supplier_contract' else 'Unique event commitments; never combined with programme stock.'
        if key in ('cancelled_project_capex', 'withdrawn_or_redirected_public_funding'):
            note = 'Negative category shown separately; not subtracted from or combined with the other cancellation class.'
        A(f'<tr><td>{esc(label)}</td><td class="num">{money(amount)}</td><td>{esc(note)}</td></tr>')
    A('</tbody></table>')
    A(f'<p class="derived-note"><b>Status-weighted reported value:</b> {money(model["status_weighted_reported_value_aud"])}. This is an analytical scenario, not committed money. Weights: announced 25%, allocated 75%, committed/spent 100%, cancelled/NA 0%. Unweighted stage values: ' + ', '.join(f'{esc(k)} {money(v)}' for k, v in model['funding_event_unweighted_by_stage_aud'].items()) + '.</p>')
    A('<p class="source-note">Tangguh UCC’s ~US$7bn is whole gas-development-plus-CCUS capex; the CCS-specific share is unknown. Supplier contracts such as Padeswood are not additional project capital.</p></div>')

    A(map_chunk)
    A('<div class="card"><h3>Exact regional/global reconciliation</h3><table class="rtbl"><thead><tr><th>Canonical region</th><th class="num">Unique events</th><th class="num">Additive reported event value</th></tr></thead><tbody>')
    for row in regional:
        A(f'<tr><td>{esc(row["region"])}</td><td class="num">{esc(row["events"])}</td><td class="num">{money(row["reported_value_aud"])}</td></tr>')
    A(f'</tbody><tfoot><tr><th>Global</th><th class="num">{model["reconciliation"]["global_events"]}</th><th class="num">{money(model["reconciliation"]["global_additive_reported_value_aud"])}</th></tr></tfoot></table><p class="source-note">Every event is assigned once to canonical physical geography, an explicit EU-bloc bucket, or Global/unallocated. Organisation headquarters never changes project location; BP Tangguh is assigned to Indonesia, not the UK.</p></div>')

    counts = Counter(row['classification'] for row in policies)
    A('<h2 id="policy">7 · Policy, mandate and milestone tracker</h2><p class="sectionlead">A date is not automatically a mandate. Legislated requirements, government targets, project milestones and commercial deadlines are classified separately.</p><div class="metricgrid">')
    for label in ('legislated/regulatory mandate', 'government target', 'corporate/project milestone', 'commercial deadline'):
        A(f'<div class="metric"><strong>{counts.get(label, 0)}</strong>{esc(label.title())}<small>Dated events in the evidence archive; event direction is separate from media tone.</small></div>')
    A('</div><div class="card"><table class="rtbl"><thead><tr><th>Year</th><th>Classification</th><th>Instrument / milestone</th><th>Direction</th></tr></thead><tbody>')
    for row in sorted(policies, key=lambda r: (r['target_year'], r['name']))[:18]:
        A(f'<tr><td>{esc(row["target_year"])}</td><td>{esc(row["classification"])}</td><td>{esc(row["name"])}</td><td>{esc(row["event_direction"])}</td></tr>')
    A('</tbody></table></div>')

    tech = [r for r in fresh if r.get('section') == 'technology' or 'MMV-MRV' in (r.get('value_chain') or [])]
    tech.sort(key=lambda r: (r.get('co2crc_relevance') != 'high', r.get('briefing_date', '')), reverse=False)
    A('<h2 id="technology">8 · Technology, MMV/MRV and CO2Tech signals</h2><div class="callout"><b>So what for CO2CRC / CO2Tech:</b> offshore monitoring is moving toward continuous fibre-enabled seismic; capture developers are testing lower-heat sorbents and modular regeneration; and transport design is scaling toward cross-border shipping and shared networks. The evidence below is technology signal flow, not deployment capacity.</div><div class="signal-grid">')
    for record in tech[:9]:
        url = record.get('url') or ''
        title = f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(record.get("headline"))}</a>' if url else esc(record.get('headline'))
        A(f'<article class="signal">{title}<p>{esc(record.get("co2crc_note") or record.get("summary"))}</p><span class="basis-tag">{esc(record.get("briefing_date"))} · {esc(record.get("co2crc_relevance"))}</span></article>')
    A('</div>')

    social = [r for r in fresh if r.get('section') == 'media' or any(term in (r.get('headline') or '').lower() for term in ('opinion', 'letters:', 'community'))]
    social_tones = Counter((r.get('sentiment') or 'not coded') for r in social)
    A('<h2 id="social">9 · Social licence</h2><p class="sectionlead">Only media, opinion and community records are included. A project cancellation is a negative project event, not automatically negative editorial tone.</p>')
    A('<div class="metricgrid">' + ''.join(f'<div class="metric"><strong>{count}</strong>{esc(tone.title())} media tone<small>Within {len(social)} qualifying social-licence records only.</small></div>' for tone, count in sorted(social_tones.items())) + '</div>')
    A('<div class="card"><ul class="items">')
    for r in social[:12]:
        url = r.get('url') or ''
        title = f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(r.get("headline"))}</a>' if url else esc(r.get('headline'))
        A(f'<li><div class="ih">{title}</div><div class="im">media tone: {esc(r.get("sentiment") or "not coded")} · event direction: {esc(crosswalk.get(r.get("id"), {}).get("event_direction", "neutral"))}</div></li>')
    A('</ul></div>')

    A('<h2 id="evidence">10 · Detailed evidence and event archive</h2><p class="sectionlead">Use the filters to inspect the evidence. Results are event records, not unique projects. Quarterly rows use report-level provenance where item-level links were unavailable.</p>')
    regions = sorted({crosswalk.get(r.get('id'), {}).get('primary_geography', '') or 'Global / unallocated' for r in fresh})
    lifecycles = sorted({projects.get(crosswalk.get(r.get('id'), {}).get('project_id', ''), {}).get('lifecycle_stage', '') or 'unmapped' for r in fresh})
    sectors = sorted({projects.get(crosswalk.get(r.get('id'), {}).get('project_id', ''), {}).get('sector', '') or r.get('section', '') or 'unclassified' for r in fresh})
    value_chains = sorted({value for r in fresh for value in (r.get('value_chain') or ['unclassified'])})
    A('<div class="filters" id="evidence-filters">')
    def select(name: str, label: str, values: list[str]) -> str:
        return f'<label>{esc(label)}<select name="{esc(name)}"><option value="all">All</option>' + ''.join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in values) + '</select></label>'
    A(select('time', 'Time period', ['7 days', '30 days', 'full corpus']))
    A(select('region', 'Region / geography', regions))
    A(select('lifecycle', 'Lifecycle', lifecycles))
    A(select('sector', 'Sector', sectors))
    A(select('component', 'Value-chain component', value_chains))
    A(select('source', 'Source type', ['daily_news', 'periodic_report']))
    A(f'<span class="archive-status" aria-live="polite"><b id="visible-count">{len(fresh)}</b> of {len(fresh)} events</span></div>')
    A('<div class="archive-wrap"><table class="rtbl" id="evidence-table"><thead><tr><th>Date</th><th>Evidence</th><th>Canonical project</th><th>Geography</th><th>Source</th></tr></thead><tbody>')
    for record in sorted(fresh, key=lambda r: (r.get('briefing_date', ''), r.get('id', '')), reverse=True):
        link = crosswalk.get(record.get('id'), {})
        project = projects.get(link.get('project_id', ''), {})
        geo = link.get('primary_geography') or 'Global / unallocated'
        lifecycle = project.get('lifecycle_stage') or 'unmapped'
        sector = project.get('sector') or record.get('section') or 'unclassified'
        components = '|'.join(record.get('value_chain') or ['unclassified'])
        source_type = link.get('source_type') or 'daily_news'
        source_url = record.get('url') or link.get('report_url') or ''
        title = f'<a href="{esc(source_url)}" target="_blank" rel="noopener">{esc(record.get("headline"))}</a>' if source_url else esc(record.get('headline'))
        A(f'<tr class="evidence-row" data-date="{esc(record.get("briefing_date"))}" data-region="{esc(geo)}" data-lifecycle="{esc(lifecycle)}" data-sector="{esc(sector)}" data-component="{esc(components)}" data-source="{esc(source_type)}"><td>{esc(record.get("briefing_date"))}</td><td>{title}<div class="source-note">direction {esc(link.get("event_direction"))} · tone {esc(link.get("media_tone") or "not applicable")}</div></td><td>{esc(project.get("canonical_name") or "unmatched / review")}</td><td>{esc(geo)}</td><td>{esc(source_type)}<br><span class="source-note">{esc(link.get("verification_status"))}</span></td></tr>')
    A('</tbody></table></div>')

    A('<section class="method" id="methodology"><h2>11 · Glossary and methodology</h2>')
    A('<details><summary>Entity model and deduplication</summary><p>Stable project IDs link aliases, components, physical geography and status history. Only <code>entities/capacities.csv</code> is additive. Every news capacity is evidence only. Pathways, Morecambe, Carbon TerraVault and Padeswood repeat articles therefore cannot increase totals. Uncertain aliases remain in <code>crosswalk-review.csv</code>.</p></details>')
    A('<details><summary>Capacity bases</summary><p><b>Capture capacity</b> is CO₂ separated at a source. <b>Transport capacity</b> is network throughput. <b>Storage-injection capacity</b> is injection rate. <b>Removal purchase/offtake</b> is a procurement volume. <b>Cumulative storage resource</b> is a stock. These measures are never silently added.</p></details>')
    A('<details><summary>Funding categories and status weights</summary><p>CCS-specific and CCS-eligible programmes, published awards, actual spend, private investment, project capex, supplier contracts, cancelled capex and withdrawn public funding remain separate. Status weights are scenario assumptions only and produce “status-weighted reported value”, never “committed money”.</p></details>')
    A('<details><summary>IEA, GCCSI and London Register scope</summary><p>IEA 2026 and GCCSI 2025 are companion project baselines and are not blended. Neither is audited financial data. The London Register 2025 is an annual actual-injection register through 2024; its all-storage total includes dedicated, associated and EOR projects, and some annual figures are averages derived from cumulative disclosures.</p></details>')
    A('<details><summary>Monitoring/newsflow versus deployment momentum</summary><p>Article counts are labelled monitoring/newsflow volume and exclude periodic-report batches from weekly trends. Deployment momentum uses unique canonical stage-change evidence: FID, construction, commissioning, operation, schedule slip, suspension and cancellation.</p></details>')
    A('<details><summary>Collection and recall</summary><p>No verified news is only permitted when scheduled samplers are healthy. Impaired candidates are retained for retry. Recall uses adjudicated relevant candidates, reports precision and decision-relevant recall by geography/source/content, and treats Chapman capture–recapture as experimental because independence and equal-catchability assumptions are violated.</p></details>')
    A('</section>')
    A('<p class="footer-note">Self-contained offline build. Source editions and as-of dates are shown beside each baseline. This dashboard is decision support, not audited financial reporting.</p>')
    A('</div>')
    A(scripts)
    A("""<script>
(function(){
  var filters=document.getElementById('evidence-filters'); if(!filters) return;
  var rows=[].slice.call(document.querySelectorAll('.evidence-row'));
  var count=document.getElementById('visible-count');
  var latest=rows.reduce(function(m,r){var d=r.dataset.date||'';return d>m?d:m;},'');
  function daysBetween(a,b){return Math.round((new Date(a+'T00:00:00Z')-new Date(b+'T00:00:00Z'))/86400000);}
  function apply(){
    var values={}; [].slice.call(filters.querySelectorAll('select')).forEach(function(s){values[s.name]=s.value;});
    var shown=0;
    rows.forEach(function(r){
      var ok=true;
      if(values.time==='7 days') ok=daysBetween(latest,r.dataset.date)<=6;
      if(values.time==='30 days') ok=daysBetween(latest,r.dataset.date)<=29;
      ['region','lifecycle','sector','source'].forEach(function(k){if(values[k]&&values[k]!=='all'&&r.dataset[k]!==values[k]) ok=false;});
      if(values.component&&values.component!=='all'&&!(r.dataset.component||'').split('|').includes(values.component)) ok=false;
      r.hidden=!ok; if(ok) shown++;
    });
    if(count) count.textContent=shown;
  }
  filters.addEventListener('change',apply); apply();
})();
</script>""")
    return ''.join(parts)
