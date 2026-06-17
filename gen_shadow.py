#!/usr/bin/env python3
"""Generate audit/2026-06-18-shadow.json for the CCS shadow sampler (sampler D)."""

import json
import re
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

STOPWORDS = {
    'the','a','an','of','to','in','on','at','for','and','or','but','with',
    'by','from','as','is','are','was','were','be','this','that','it','its',
    'their','they','we','you','i','s'
}

def canonicalize(url):
    p = urlparse(url)
    host = p.netloc.lower()
    if host.startswith('www.'):
        host = host[4:]
    # Remove tracking params
    if p.query:
        qs = parse_qs(p.query, keep_blank_values=True)
        qs = {k: v for k, v in qs.items()
              if not k.startswith('utm_') and k not in ('fbclid','gclid','ref')}
        query = urlencode(qs, doseq=True)
    else:
        query = ''
    path = p.path.rstrip('/') or '/'
    return urlunparse((p.scheme, host, path, '', query, ''))

def src_domain(url):
    host = urlparse(url).netloc.lower()
    if host.startswith('www.'):
        host = host[4:]
    parts = host.split('.')
    if len(parts) >= 3 and parts[-2] in ('co','com','org','net','gov','edu'):
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])

def fkey(headline):
    h = re.sub(r'\s[–\-|]\s.*$', '', headline)   # strip trailing source
    toks = re.split(r'[^a-z0-9]+', h.lower())
    toks = [t for t in toks if len(t) > 1 and t not in STOPWORDS]
    return ','.join(sorted(set(toks)))

# ── Candidate data ────────────────────────────────────────────────────────────
# Fields: url, headline, pub_date (ISO str or None), in_window, kept, reject
RAW = [
    # ── GROUP A: URL-embedded dates ──────────────────────────────────────────
    {
        "url": "https://www.worldpipelines.com/project-news/17062026/europe-needs-65-strong-co2-shipping-fleet-and-33-ports-to-store-carbon-at-scale-xodus-report-finds/",
        "headline": "Europe needs 65-strong CO2 shipping fleet and 33 ports to store carbon at scale, Xodus report finds",
        "pub_date": "2026-06-17T00:00:00+10:00",
        "in_window": True,
        "kept": True,
        "reject": None,
        # note: WebFetch returned HTTP 403; date inferred from URL path "17062026"
    },
    {
        "url": "https://worldoil.com/news/2026/6/9/major-uk-ccs-project-clears-milestone-toward-offshore-co2-storage/",
        "headline": "Major UK CCS project clears milestone toward offshore CO2 storage",
        "pub_date": "2026-06-09T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://worldoil.com/news/2026/6/3/class-vi-well-approvals-accelerate-as-ccs-permit-applications-slow/",
        "headline": "Class VI well approvals accelerate as CCS permit applications slow",
        "pub_date": "2026-06-03T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.airliquide.com/group/press-releases-news/2026-06-10/air-liquide-starting-co2-capture-pilot-unit-dedicated-decarbonization-cement-industry",
        "headline": "Air Liquide starting a CO2 capture pilot unit dedicated to the decarbonization of cement industry",
        "pub_date": "2026-06-10T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://insideclimatenews.org/news/28032026/summit-midwest-co2-pipeline/",
        "headline": "Summit Sold Its Midwest Pipeline as a Carbon Solution. Now, It'll Be Used for Fossil Fuels.",
        "pub_date": "2026-03-28T00:00:00+11:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.spglobal.com/energy/en/news-research/blog/energy-transition/041426-2026-ccus-navigating-the-tides-of-the-great-realignment",
        "headline": "2026 CCUS: Navigating the tides of the great realignment",
        "pub_date": "2026-04-14T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.spglobal.com/energy/en/news-research/blog/energy-transition/022526-et-highlights-ammonia-blue-hydrogen-kawasaki-green-ai",
        "headline": "ET Highlights: Ammonia producers lead blue hydrogen, US states sue over hydrogen hubs, Japan's NEDO backs Kawasaki's liquid hydrogen projects",
        "pub_date": "2026-02-25T00:00:00+11:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.globenewswire.com/news-release/2026/04/20/3276685/0/en/ccus-hub-study-identifies-five-asia-pacific-hub-sites-and-welcomes-new-consortium-partners.html",
        "headline": "CCUS Hub Study identifies five Asia-Pacific hub sites and welcomes new consortium partners",
        "pub_date": "2026-04-20T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.hatch.com/About-Us/News-And-Media/2026/04/CCUS-Hub-Study-identifies-five-Asia-Pacific-hub-sites",
        "headline": "CCUS Hub Study identifies five Asia-Pacific hub sites and welcomes new consortium partners",
        "pub_date": "2026-04-20T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window_duplicate_globenewswire",
    },
    {
        "url": "https://www.climatesolutionslaw.com/2026/03/texas-takes-the-wheel-the-railroad-commissions-class-vi-well-primacy-and-what-it-means-for-carbon-capture-in-the-lone-star-state/",
        "headline": "Texas Takes the Wheel: The Railroad Commission's Class VI Well Primacy and What It Means for Carbon Capture in the Lone Star State",
        "pub_date": "2026-03-01T00:00:00+11:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://solarquarter.com/2026/01/10/middle-east-energy-outlook-2026-investment-innovation-and-decarbonization-drive-global-stability/",
        "headline": "Middle East Energy Outlook 2026: Investment, Innovation, And Decarbonization Drive Global Stability",
        "pub_date": "2026-01-10T00:00:00+11:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.climatechangenews.com/2025/03/20/carbon-colonialism-malaysia-and-indonesia-plan-storage-hubs-for-asian-emissions/",
        "headline": "Carbon colonialism: Malaysia and Indonesia plan storage hubs for Asian emissions",
        "pub_date": "2025-03-20T00:00:00+11:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.globalcement.com/news/analysis/20811-update-on-carbon-capture-in-cement-may-2026",
        "headline": "Update on carbon capture in cement, May 2026",
        "pub_date": "2026-05-01T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.mhi.com/news/25070701.html",
        "headline": "MHI Awarded Contract for Basic Design of Japan's Largest CO2 Capture Plant at Hokkaido Electric Power's Tomato-Atsuma Power Station",
        "pub_date": "2025-07-07T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://thediplomat.com/2024/02/japan-bets-on-carbon-capture-and-storage-technology/",
        "headline": "Japan Bets on Carbon Capture and Storage Technology",
        "pub_date": "2024-02-01T00:00:00+11:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://dii-desertenergy.org/dii-editorial-q1-2025-mena-carbon-capture-storage-a-growth-sector/",
        "headline": "Dii Editorial Q1 2025: MENA Carbon Capture & Storage: A Growth Sector",
        "pub_date": "2025-03-01T00:00:00+11:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    # ── GROUP B: Dates from search snippets (WebFetch 403; snippet-sourced date) ─
    {
        "url": "https://www.newswire.ca/news-releases/deep-sky-announces-direct-air-capture-carbon-removal-agreement-with-td-bank-group-advancing-canada-s-leadership-in-carbon-removal-899228119.html",
        "headline": "Deep Sky Announces Direct Air Capture Carbon Removal Agreement with TD Bank Group, Advancing Canada's Leadership in Carbon Removal",
        "pub_date": "2026-06-04T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://drillingcontractor.org/inpex-jv-wins-approval-to-drill-two-ccs-exploration-wells-offshore-japan-77867",
        "headline": "INPEX JV wins approval to drill two CCS exploration wells offshore Japan",
        "pub_date": "2026-04-17T00:00:00+10:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    # ── GROUP C: No confirmable date (WebFetch HTTP 403, no URL date clue) ───
    {
        "url": "https://carbonherald.com/air-liquide-and-holcim-launch-industrial-scale-carbon-capture-pilot-for-cement/",
        "headline": "Air Liquide And Holcim Launch Industrial-Scale Carbon Capture Pilot For Cement",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://esgnews.com/air-liquide-launches-industrial-scale-co2-capture-pilot-to-decarbonize-cement-production/",
        "headline": "Air Liquide Launches Industrial Scale CO2 Capture Pilot to Decarbonize Cement Production",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://carbonherald.com/iea-ccus-investment-surges-to-5b-but-financing-gaps-remain/",
        "headline": "IEA: CCUS Investment Surges To $5B, But Financing Gaps Remain",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.businessgreen.com/news/4525876/ccus-report-warns-carbon-capture-projects-challenging-financing-gap",
        "headline": "CCUS: Report warns carbon capture projects still face challenging 'financing gap'",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.gasworld.com/story/first-mover-ccus-projects-must-reach-financial-close-to-meet-targets-urges-ccsa/2173655.article/",
        "headline": "First-mover CCUS projects must reach financial close to meet targets urges CCSA",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.energynewsbulletin.net/operations/news-analysis/4525880/inpex-pulls-bonaparte-ccs-project-govt-assessment-process",
        "headline": "INPEX pulls Bonaparte CCS project from govt assessment process",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.bp.com/en_gb/united-kingdom/home/news/press-releases/bp-selects-basfs-carbon-capture-technology-for-blue-hydrogen.html",
        "headline": "bp selects BASF's carbon capture technology for blue hydrogen project in Teesside",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.h2-view.com/story/woodside-delays-blue-ammonia-beyond-2026-after-beaumont-takeover/2138748.article/",
        "headline": "Woodside delays blue ammonia beyond 2026 after Beaumont takeover",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://ieaghg.org/news/occidentals-blue-point-ammonia-project/",
        "headline": "Occidental's Blue Point Ammonia Project",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.constructionbriefing.com/news/construction-of-japans-largest-co2-capture-plant-moves-closer/8073294.article",
        "headline": "Construction of Japan's largest CO2 capture plant moves closer",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.pipeline-journal.net/news/japans-sumitomo-backs-major-uk-carbon-capture-pipeline-project",
        "headline": "Japan's Sumitomo backs major UK carbon capture pipeline project",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://carbonherald.com/japans-marubeni-buys-50-of-ozona-ccs-project-in-south-texas/",
        "headline": "Japan's Marubeni Buys 50% Of Ozona CCS Project In South Texas",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://asia.nikkei.com/spotlight/environment/climate-change/japan-s-sumitomo-joins-massive-canadian-carbon-capture-project",
        "headline": "Japan's Sumitomo joins massive Canadian carbon capture project",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://asia.nikkei.com/spotlight/environment/climate-change/japan-s-marubeni-to-capture-10m-tonnes-of-carbon-in-north-america",
        "headline": "Japan's Marubeni to capture 10m tonnes of carbon in North America",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://en.clickpetroleoegas.com.br/european-ship-will-transport-captured-co-to-be-stored-under-the-north-sea-as-the-greensand-project-prepares-the-first-industrial-offshore-st-ctl01/",
        "headline": "European ship will transport captured CO2 to be stored under the North Sea as the Greensand project prepares the first industrial offshore storage in the EU",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://enkiai.com/carbon-capture/climeworks-dac-corporate-offtake/",
        "headline": "Climeworks Carbon Capture 2026, $10M Swiss Re Deal",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://enkiai.com/carbon-capture/climeworks-dac-aviation-offtake/",
        "headline": "Climeworks Carbon Capture 2026, 31,000 Ton Schneider Deal",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://enkiai.com/carbon-capture/deep-sky-direct-air-capture/",
        "headline": "Deep Sky Carbon Capture 2026, 18,000 Credit TD Bank Deal",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://enkiai.com/carbon-capture/microalgae-dac-frontier-deal/",
        "headline": "Carbon Capture 2026, $41M Frontier Deal, DOE Risk",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://ghanaupstream.com/class-vi-well-approvals-accelerate-as-ccs-permit-applications-slow/",
        "headline": "Class VI well approvals accelerate as CCS permit applications slow",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.tge-marine.com/news-events/detail/co2-shipping-and-terminals-june-2026",
        "headline": "CO2 Shipping and Terminals June 2026",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "event_page_not_news_article",
    },
    {
        "url": "https://carboncapturemagazine.com/articles/deep-sky-smbc-partner-to-advance-direct-air-capture-and-carbon-removal-in-japan",
        "headline": "Deep Sky, SMBC Partner to Advance Direct Air Capture and Carbon Removal in Japan",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.constructionworld.in/energy-infrastructure/oil-and-gas/ongc-launches-first-ccs-pilot-at-gandhar-oilfield/84138",
        "headline": "ONGC Launches First CCS Pilot At Gandhar Oilfield",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://carbonherald.com/ongc-launches-first-ccs-pilot-at-gujarats-gandhar-oilfield/",
        "headline": "ONGC Launches First CCS Pilot At Gujarat's Gandhar Oilfield",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://bimp-eaga.asia/articles/indonesia-malaysia-seek-become-regional-carbon-storage-hubs",
        "headline": "Indonesia, Malaysia Seek to Become Regional Carbon Storage Hubs",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://seads.adb.org/articles/indonesia-malaysia-seek-become-regional-carbon-storage-hubs",
        "headline": "Indonesia, Malaysia Seek to Become Regional Carbon Storage Hubs",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.reccessary.com/en/news/2026-Sustainability-Trends",
        "headline": "2026 Sustainability Trends: Top 10 new energy and carbon issues in ASEAN",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://africacarbonremovalsummit.com/",
        "headline": "Africa Carbon Removal Summit 2026",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "event_page_not_news_article",
    },
    {
        "url": "https://www.rystadenergy.com/insights/fueling-a-nation-china-s-big-three-nocs-drive-energy-security-and-innovation",
        "headline": "Fueling a nation: China's 'Big Three' NOCs drive energy security and innovation",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.sciencedirect.com/science/article/pii/S2666759226000442",
        "headline": "Carbon capture, utilization, and storage: Advances made by Sinopec and future prospects",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://ieaghg.org/publications/exporting-co2-for-offshore-storage-the-london-protocols-export-amendment-and-associated-guidelines-and-guidance/",
        "headline": "Exporting CO2 for Offshore Storage – The London Protocol's Export Amendment and Associated Guidelines and Guidance",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
    {
        "url": "https://www.tandfonline.com/doi/full/10.1080/00908320.2025.2566714",
        "headline": "Cross-Border CO2 Transport and Storage Networks in Europe through 'Arrangements' under the London Protocol",
        "pub_date": "2025-01-01T00:00:00+11:00",
        "in_window": False,
        "kept": False,
        "reject": "out_of_window",
    },
    {
        "url": "https://www.globalccsinstitute.com/2026-americas-forum-recap/",
        "headline": "2026 Americas Forum on Carbon Capture and Storage: Recap",
        "pub_date": None,
        "in_window": False,
        "kept": False,
        "reject": "pub_date_not_confirmed_http403",
    },
]

# ── Build audit_trace ─────────────────────────────────────────────────────────
audit_trace = []
for r in RAW:
    audit_trace.append({
        "url": r["url"],
        "canonical_url": canonicalize(r["url"]),
        "fuzzy_key": fkey(r["headline"]),
        "source_domain": src_domain(r["url"]),
        "headline": r["headline"],
        "publication_date": r["pub_date"],
        "in_window": r["in_window"],
        "kept": r["kept"],
        "reject_reason": r["reject"],
        "found_via": "concept_query",
    })

import os
os.makedirs("audit", exist_ok=True)
with open("audit/2026-06-18-shadow.json", "w", encoding="utf-8") as f:
    json.dump(audit_trace, f, indent=2, ensure_ascii=False)

n_considered = len(audit_trace)
n_in_window  = sum(1 for x in audit_trace if x["in_window"])
n_kept       = sum(1 for x in audit_trace if x["kept"])
domains      = sorted({x["source_domain"] for x in audit_trace})
print(f"Wrote {n_considered} candidates, {n_in_window} in-window, {n_kept} kept, {len(domains)} domains")
print("Domains:", ", ".join(domains))
