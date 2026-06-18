#!/usr/bin/env python3
"""Generate audit/2026-06-19-shadow.json for CCS Shadow Sampler D."""

import json
import re
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

STOPWORDS = {
    'the','a','an','of','to','in','on','at','for','and','or','but',
    'with','by','from','as','is','are','was','were','be','this','that',
    'it','its','their','they','we','you','i','s'
}

def make_fuzzy_key(headline):
    # Strip source suffix like "– Source" or "| Source"
    h = re.sub(r'\s*[–—|]\s*[^–—|]+$', '', headline)
    h = h.lower()
    # Normalise subscript digits
    h = h.replace('₂','2').replace('₁','1').replace('₀','0').replace('₃','3')
    h = h.replace('₂','2')
    tokens = re.findall(r"[a-z0-9']+", h)
    # Strip apostrophes from tokens like "canada's" → "canadas"
    tokens = [t.replace("'","") for t in tokens]
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    tokens = sorted(set(tokens))
    return ','.join(tokens)

def canonical_url(url):
    p = urlparse(url)
    host = p.netloc.lower()
    if host.startswith('www.'):
        host = host[4:]
    # Strip tracking params
    qp = parse_qs(p.query, keep_blank_values=False)
    filtered = {k: v for k, v in qp.items()
                if not k.lower().startswith('utm_')
                and k.lower() not in ('fbclid','gclid','ref','source','safelink')}
    new_query = urlencode({k: v[0] for k, v in filtered.items()}) if filtered else ''
    path = p.path.rstrip('/') or '/'
    result = urlunparse((p.scheme, host, path, p.params, new_query, ''))
    return result

def source_domain(url):
    p = urlparse(url)
    host = p.netloc.lower()
    if host.startswith('www.'):
        host = host[4:]
    labels = host.split('.')
    three_label_tlds = {'co.uk','com.au','org.uk','net.au','org.au','co.nz',
                        'com.nz','co.za','com.sg','co.in'}
    if len(labels) >= 3:
        suffix2 = '.'.join(labels[-2:])
        if suffix2 in three_label_tlds:
            return '.'.join(labels[-3:])
    return '.'.join(labels[-2:]) if len(labels) >= 2 else host

# Window: Friday 2026-06-19  →  last 24 h Melbourne (AEST=UTC+10)
# Window start: 2026-06-18T07:33 AEST = 2026-06-17T21:33Z
# Anything published 2026-06-18 (calendar day, any tz) is safely inside window.

RAW_ITEMS = [
    # ─── CONCEPT QUERY a – Sinopec / CNPC / CNOOC ───────────────────────────
    {
        "url": "https://www.globalconstructionreview.com/sinopec-plans-million-tonne-carbon-capture-project/",
        "headline": "Sinopec plans million-tonne carbon capture project to meet China's 2030 target",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "Sinopec OR CNPC OR CNOOC carbon capture project",
    },
    {
        "url": "https://www.sciencedirect.com/science/article/pii/S2666759226000442",
        "headline": "Carbon capture, utilization, and storage: Advances made by Sinopec and future prospects",
        "publication_date": "2026",
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "Sinopec OR CNPC OR CNOOC carbon capture project",
    },
    # ─── CONCEPT QUERY b – ADNOC / Aramco / QatarEnergy ─────────────────────
    {
        "url": "https://agbi.com/analysis/adipec-gulf-decarbonisation",
        "headline": "Aramco, Adnoc and the long road to decarbonisation",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "ADNOC OR Aramco OR QatarEnergy carbon storage",
    },
    {
        "url": "https://dii-desertenergy.org/dii-editorial-q1-2025-mena-carbon-capture-storage-a-growth-sector/",
        "headline": "Dii Editorial Q1 2025: MENA Carbon Capture & Storage: A Growth Sector",
        "publication_date": "2025",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "ADNOC OR Aramco OR QatarEnergy carbon storage",
    },
    # ─── CONCEPT QUERY c – Petrobras / Pertamina / Petronas ─────────────────
    {
        "url": "https://oilprice.com/Company-News/Petronas-Maps-Heavy-Upstream-LNG-and-CCS-Push-Through-2028.html",
        "headline": "Petronas Maps Heavy Upstream, LNG, and CCS Push Through 2028",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "Petrobras OR Pertamina OR Petronas CCS FID",
    },
    # ─── CONCEPT QUERY d – Indonesia / Malaysia / Vietnam ────────────────────
    {
        "url": "https://seads.adb.org/articles/indonesia-malaysia-seek-become-regional-carbon-storage-hubs",
        "headline": "Indonesia, Malaysia Seek to Become Regional Carbon Storage Hubs",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "Indonesia OR Malaysia OR Vietnam carbon capture hub",
    },
    {
        "url": "https://www.hatch.com/About-Us/News-And-Media/2026/04/CCUS-Hub-Study-identifies-five-Asia-Pacific-hub-sites",
        "headline": "CCUS Hub Study identifies five Asia-Pacific hub sites and welcomes new consortium partners",
        "publication_date": "2026-04",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Indonesia OR Malaysia OR Vietnam carbon capture hub",
    },
    # ─── CONCEPT QUERY e – India / ONGC / Reliance ───────────────────────────
    {
        "url": "https://www.constructionworld.in/energy-infrastructure/oil-and-gas/ongc-launches-first-ccs-pilot-at-gandhar-oilfield/84138",
        "headline": "ONGC Launches First CCS Pilot At Gandhar Oilfield",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "India OR ONGC OR Reliance CCS pilot",
    },
    # ─── CONCEPT QUERY f – Japan / Tomakomai / Suiso ─────────────────────────
    {
        "url": "https://www.mhi.com/news/25070701.html",
        "headline": "MHI Awarded Contract for Basic Design of Japan's Largest CO2 Capture Plant at Hokkaido Electric Power's Tomato-Atsuma Power Station",
        "publication_date": "2025-07-07",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Japan OR Tomakomai OR Suiso carbon storage milestone",
    },
    {
        "url": "https://drillingcontractor.org/inpex-jv-wins-approval-to-drill-two-ccs-exploration-wells-offshore-japan-77867",
        "headline": "INPEX JV wins approval to drill two CCS exploration wells offshore Japan",
        "publication_date": "2026-04-15",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Japan OR Tomakomai OR Suiso carbon storage milestone",
    },
    # ─── CONCEPT QUERY i – Mitsui / Mitsubishi Corp / Itochu ────────────────
    {
        "url": "https://www.sumitomocorp.com/en/jp/news/topics/2024/group/20240314",
        "headline": "Joint Feasibility Study on Direct Air Capture with Carbon Storage",
        "publication_date": "2024-03-14",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Mitsui OR Mitsubishi Corp OR Itochu CCS investment OR MoU",
    },
    # ─── CONCEPT QUERY j – Sumitomo / Marubeni / JERA ───────────────────────
    {
        "url": "https://carboncapturemagazine.com/articles/deep-sky-smbc-partner-to-advance-direct-air-capture-and-carbon-removal-in-japan",
        "headline": "Deep Sky, SMBC Partner to Advance Direct Air Capture and Carbon Removal in Japan",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "Sumitomo OR Marubeni OR JERA carbon capture",
    },
    {
        "url": "https://www.marubeni.com/en/news/2024/info/00042.html",
        "headline": "Joint Development of a Commercial Carbon Dioxide Storage Project in South Texas, United States",
        "publication_date": "2024",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Sumitomo OR Marubeni OR JERA carbon capture",
    },
    {
        "url": "https://www.pipeline-journal.net/news/japans-sumitomo-backs-major-uk-carbon-capture-pipeline-project",
        "headline": "Japan's Sumitomo Backs Major UK Carbon Capture Pipeline Project",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "Sumitomo OR Marubeni OR JERA carbon capture",
    },
    # ─── CONCEPT QUERY k – BP / Shell / TotalEnergies ────────────────────────
    {
        "url": "https://corporate.totalenergies.us/news/totalenergies-publishes-its-sustainability-climate-2025-progress-report-and-further",
        "headline": "TotalEnergies publishes its Sustainability & Climate 2025 Progress Report and further strengthens its emissions reduction targets",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "BP OR Shell OR TotalEnergies CCS strategy OR roadmap",
    },
    # ─── CONCEPT QUERY l – Eni / Equinor / INPEX ────────────────────────────
    {
        "url": "https://www.eni.com/en-IT/media/press-release/2026/05/eni-ccus-holding-expands-financing-sources-for-platform-ccs-projects.html",
        "headline": "Eni CCUS Holding expands the financing sources for its platform of CCS projects",
        "publication_date": "2026-05-21",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Eni OR Equinor OR INPEX CCS partnership OR JV",
    },
    {
        "url": "https://www.rigzone.com/news/eni_blackrock_ccus_jv_raises_582mm-26-may-2026-183780-article/",
        "headline": "Eni, BlackRock CCUS JV Raises $582MM",
        "publication_date": "2026-05-26",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Eni OR Equinor OR INPEX CCS partnership OR JV",
    },
    {
        "url": "https://www.energynewsbulletin.net/operations/news-analysis/4531657/inpex-takes-step-approval-pathway-bonaparte-ccs-project",
        "headline": "INPEX takes first step down approval pathway for Bonaparte CCS project",
        "publication_date": "2026-05",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Eni OR Equinor OR INPEX CCS partnership OR JV",
    },
    {
        "url": "https://pgjonline.com/news/2026/january/inpex-to-resubmit-environmental-plan-for-bonaparte-ccs-project-offshore-australia",
        "headline": "Inpex to Resubmit Environmental Plan for Bonaparte CCS Project Offshore Australia",
        "publication_date": "2026-01",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Eni OR Equinor OR INPEX CCS partnership OR JV",
    },
    # ─── CONCEPT QUERY s – London Protocol ───────────────────────────────────
    {
        "url": "https://www.sciencedirect.com/science/article/pii/S2772655X26000534",
        "headline": "Toward a transboundary legal framework: The Indonesia–Singapore carbon capture and storage agreement",
        "publication_date": "2026",
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "London Protocol CO2 OR carbon storage OR sub-seabed",
    },
    {
        "url": "https://www.ieaghg.org/publications/exporting-co2-for-offshore-storage-the-london-protocols-export-amendment-and-associated-guidelines-and-guidance/",
        "headline": "Exporting CO2 for Offshore Storage – The London Protocol's Export Amendment and Associated Guidelines and Guidance",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "London Protocol CO2 OR carbon storage OR sub-seabed",
    },
    # ─── CONCEPT QUERY t – Transboundary CCS / cross-border CO2 ─────────────
    {
        "url": "https://angeassociation.com/policy-areas/cross-border-ccs-for-asia-pacific/",
        "headline": "Cross-Border CCS for Asia Pacific",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "transboundary CCS OR cross-border CO2 OR CO2 export licence",
    },
    # ─── CONCEPT QUERY m – CCS storage permit / Class VI well ────────────────
    {
        "url": "https://worldoil.com/news/2026/6/3/class-vi-well-approvals-accelerate-as-ccs-permit-applications-slow/",
        "headline": "Class VI well approvals accelerate as CCS permit applications slow",
        "publication_date": "2026-06-03",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CCS storage permit OR Class VI well issued",
    },
    {
        "url": "https://www.epa.gov/system/files/documents/2026-03/public-notice-announcement-front-range-storage-complex_newpaper.pdf",
        "headline": "Public Notice: Front Range 1-1 Class VI UIC Permit – Front Range Storage Complex",
        "publication_date": "2026-03",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CCS storage permit OR Class VI well issued",
    },
    # ─── CONCEPT QUERY n – CCUS hub / FID ────────────────────────────────────
    {
        "url": "https://www.offline-energy.biz/norwegian-co2-transport-and-storage-project-gathers-three-industry-majors/",
        "headline": "Norwegian CO2 transport and storage project gathers three industry majors",
        "publication_date": "2026-05-04",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CCUS hub announcement OR financial investment decision",
    },
    {
        "url": "https://www.offshore-energy.biz/norwegian-co2-transport-and-storage-project-gathers-three-industry-majors/",
        "headline": "Norwegian CO2 transport and storage project gathers three industry majors",
        "publication_date": "2026-05-04",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CCUS hub announcement OR financial investment decision",
    },
    {
        "url": "https://pgjonline.com/news/2026/march/woodside-to-resubmit-browse-ccs-plan-under-new-australia-rules",
        "headline": "Woodside to Resubmit Browse CCS Plan Under New Australia Rules",
        "publication_date": "2026-03",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CCUS hub announcement OR financial investment decision",
    },
    # ─── CONCEPT QUERY o – Direct air capture offtake ────────────────────────
    {
        "url": "https://www.newswire.ca/news-releases/deep-sky-announces-direct-air-capture-carbon-removal-agreement-with-td-bank-group-advancing-canada-s-leadership-in-carbon-removal-899228119.html",
        "headline": "Deep Sky Announces Direct Air Capture Carbon Removal Agreement with TD Bank Group, Advancing Canada's Leadership in Carbon Removal",
        "publication_date": "2026-06-04",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "direct air capture offtake agreement",
    },
    {
        "url": "https://www.bnnbloomberg.ca/business/company-news/2026/06/04/deep-sky-signs-10-year-carbon-credit-deal-with-td-bank-group/",
        "headline": "Deep Sky signs 10-year carbon credit deal with TD Bank Group",
        "publication_date": "2026-06-04",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "direct air capture offtake agreement",
    },
    {
        "url": "https://enkiai.com/carbon-capture/climeworks-dac-corporate-offtake/",
        "headline": "Climeworks Carbon Capture 2026, $10M Swiss Re Deal",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "direct air capture offtake agreement",
    },
    {
        "url": "https://enkiai.com/carbon-capture/climeworks-dac-aviation-offtake/",
        "headline": "Climeworks Carbon Capture 2026, 31,000 Ton Schneider Deal",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "direct air capture offtake agreement",
    },
    # ─── CONCEPT QUERY q – Cement / steel carbon capture ─────────────────────
    {
        "url": "https://www.airliquide.com/group/press-releases-news/2026-06-10/air-liquide-starting-co2-capture-pilot-unit-dedicated-decarbonization-cement-industry",
        "headline": "Air Liquide starting a CO2 capture pilot unit dedicated to the decarbonization of cement industry",
        "publication_date": "2026-06-10",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "cement OR steel plant carbon capture pilot",
    },
    {
        "url": "https://www.airliquide.com/group/press-releases-news/2026-02-27/air-liquide-and-holcim-sign-agreement-decarbonize-cement-production-carbon-capture-project-belgium",
        "headline": "Air Liquide and Holcim sign an agreement to decarbonize cement production with a carbon capture project in Belgium",
        "publication_date": "2026-02-27",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "cement OR steel plant carbon capture pilot",
    },
    {
        "url": "https://herema.gr/storage-permit-issued-for-prinos-co2/",
        "headline": "Storage permit issued for Prinos CO2",
        "publication_date": "2026-02-26",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "cement OR steel plant carbon capture pilot",
    },
    # ─── CONCEPT QUERY r – CO2 pipeline / CO2 shipping milestone ─────────────
    {
        "url": "http://www.hydrocarbonprocessing.com/news/2026/06/burckhardt-compression-secures-milestone-order-for-first-industrial-scale-liquefied-co2-carrier-supporting-northern-lights-ccs-project/",
        "headline": "Burckhardt Compression secures milestone order for first industrial scale liquefied CO₂ carrier supporting Northern Lights CCS project",
        "publication_date": "2026-06-18",
        "in_window": True,
        "kept": True,
        "reject_reason": None,
        "concept_query": "CO2 pipeline OR CO2 shipping milestone",
    },
    {
        "url": "https://uk.advfn.com/stock-market/london/burckhardt-compression-0QNN/share-news/Burckhardt-Compression-secures-milestone-order-for/98767327",
        "headline": "Burckhardt Compression secures milestone order for first industrial scale Liquefied CO₂ carrier supporting Northern Lights CCS project",
        "publication_date": "2026-06-18",
        "in_window": True,
        "kept": True,
        "reject_reason": None,
        "concept_query": "CO2 pipeline OR CO2 shipping milestone",
    },
    {
        "url": "https://tradearabia.com/News/463855/Burckhardt-secures-compression-solutions-for-industrial-LCO%E2%82%82-carrier/OGN",
        "headline": "Burckhardt secures compression solutions for industrial LCO₂ carrier",
        "publication_date": "2026-06-18",
        "in_window": True,
        "kept": True,
        "reject_reason": None,
        "concept_query": "CO2 pipeline OR CO2 shipping milestone",
    },
    {
        "url": "https://lifestyle.middletownlifemagazine.com/story/538441/burckhardt-compression-secures-milestone-order-for-first-industrial-scale-liquefied-co%E2%82%82-carrier/",
        "headline": "Burckhardt Compression secures milestone order for first industrial scale Liquefied CO₂ carrier",
        "publication_date": "2026-06-18",
        "in_window": True,
        "kept": True,
        "reject_reason": None,
        "concept_query": "CO2 pipeline OR CO2 shipping milestone",
    },
    {
        "url": "https://www.ukpandi.com/news-and-resources/news/article/co2time-2026-a-standard-form-for-an-emerging-co2-shipping-market",
        "headline": "CO2TIME 2026: A Standard Form for an Emerging CO₂ Shipping Market",
        "publication_date": "2026-04",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CO2 pipeline OR CO2 shipping milestone",
    },
    {
        "url": "https://swzmaritime.nl/news/2026/04/21/porthos-co2-storage-project-suffers-delays/",
        "headline": "Porthos CO2 storage project suffers delays",
        "publication_date": "2026-04-21",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CO2 pipeline OR CO2 shipping milestone",
    },
    {
        "url": "https://www.rivieramm.com/news-content-hub/2026-in-co2-shipping-co2-shipping-outlook-in-2026-and-beyond-87070",
        "headline": "How storage hubs, terminals and contracts will drive CO2 shipping growth in 2026",
        "publication_date": None,
        "in_window": False,
        "kept": False,
        "reject_reason": "no_pub_date",
        "concept_query": "CO2 pipeline OR CO2 shipping milestone",
    },
    # ─── Additional items found in follow-up searches ─────────────────────────
    {
        "url": "https://www.businesswire.com/news/home/20260616410381/en/GE-Vernovas-New-Sustainability-Report-Highlights-Progress-Adding-New-Power-to-the-Grid-Enabling-People-to-Thrive-Reducing-Carbon-Intensity-and-Advancing-Breakthrough-Energy-Technologies",
        "headline": "GE Vernova's New Sustainability Report Highlights Progress Adding New Power to the Grid, Enabling People to Thrive, Reducing Carbon Intensity, and Advancing Breakthrough Energy Technologies",
        "publication_date": "2026-06-16",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "BP OR Shell OR TotalEnergies CCS strategy OR roadmap",
    },
    {
        "url": "https://www.socialnews.xyz/2026/06/09/carbon-markets-africa-summit-cmas-2026-programme-launched-as-africas-carbon-markets-move-from-readiness-to-delivery/amp/",
        "headline": "Carbon Markets Africa Summit (CMAS) 2026 programme launched as Africa's carbon markets move from readiness to delivery",
        "publication_date": "2026-06-09",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "Africa OR South Africa OR Egypt carbon capture",
    },
    {
        "url": "https://carbonherald.com/carbon-circle-and-energnist-advance-carbon-capture-plans-in-denmark/",
        "headline": "Carbon Circle And Energnist Advance Carbon Capture Plans In Denmark",
        "publication_date": "2026-04-26",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CCUS hub announcement OR financial investment decision",
    },
    {
        "url": "https://www.globalccsinstitute.com/2026-americas-forum-recap/",
        "headline": "2026 Americas Forum on Carbon Capture and Storage: Recap",
        "publication_date": "2026-06-03",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "CCUS hub announcement OR financial investment decision",
    },
    {
        "url": "https://ammoniaenergy.org/articles/yara-sluiskil-start-up-this-summer/",
        "headline": "Yara: Sluiskil start-up \"this summer\"",
        "publication_date": "2026-03",
        "in_window": False,
        "kept": False,
        "reject_reason": "out_of_window",
        "concept_query": "transboundary CCS OR cross-border CO2 OR CO2 export licence",
    },
]

# Deduplicate by canonical URL
seen_canonical = set()
audit_trace = []

for item in RAW_ITEMS:
    url = item["url"]
    can = canonical_url(url)
    # Remove duplicate canonical URLs (keep first occurrence)
    if can in seen_canonical:
        continue
    seen_canonical.add(can)

    headline = item["headline"]
    fk = make_fuzzy_key(headline)
    sd = source_domain(url)

    entry = {
        "url": url,
        "canonical_url": can,
        "fuzzy_key": fk,
        "source_domain": sd,
        "headline": headline,
        "publication_date": item["publication_date"],
        "in_window": item["in_window"],
        "kept": item["kept"],
        "reject_reason": item["reject_reason"],
        "found_via": "concept_query",
        "_concept_query": item["concept_query"],
    }
    audit_trace.append(entry)

# Remove internal _concept_query field (not in schema) – keep it for traceability
# Actually per spec the schema doesn't include it, so strip it
for e in audit_trace:
    e.pop("_concept_query", None)

out_path = "/home/user/ccs-news/audit/2026-06-19-shadow.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(audit_trace, f, indent=2, ensure_ascii=False)

kept = sum(1 for e in audit_trace if e["kept"])
considered = len(audit_trace)
domains = len({e["source_domain"] for e in audit_trace})
print(f"Wrote {out_path}")
print(f"Considered: {considered}, In-window/kept: {kept}, Distinct source domains: {domains}")
in_window_items = [e for e in audit_trace if e["kept"]]
for e in in_window_items:
    print(f"  KEPT: {e['headline']} ({e['source_domain']}, {e['publication_date']})")
