#!/usr/bin/env python3
"""
CCS Shadow Sampler D — 2026-06-30
Builds audit/2026-06-30-shadow.json from concept-based searches.
Recency window: Tuesday => last 24 hours Melbourne (AEST UTC+10),
i.e. items published on 2026-06-29 or 2026-06-30.
"""

import json, re, os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

TODAY = "2026-06-30"
WINDOW_START = "2026-06-29"  # inclusive
WINDOW_END   = "2026-06-30"  # inclusive

STOPWORDS = {
    "the","a","an","of","to","in","on","at","for","and","or","but","with","by",
    "from","as","is","are","was","were","be","this","that","it","its","their",
    "they","we","you","i","s"
}

STRIP_PARAMS = {"utm_source","utm_medium","utm_campaign","utm_content","utm_term",
                "fbclid","gclid","ref","share","msclkid","_hsenc","_hsmi"}

SPECIAL_TLDS = {".co.uk", ".com.au", ".co.nz", ".co.jp", ".org.uk", ".net.au"}


def canonicalize(url: str) -> str:
    try:
        p = urlparse(url)
        host = p.netloc.lower().replace(":80", "").replace(":443", "")
        if host.startswith("www."):
            host = host[4:]
        # strip utm/fbclid params
        qs = parse_qs(p.query, keep_blank_values=False)
        qs_clean = {k: v for k, v in qs.items() if k not in STRIP_PARAMS}
        new_query = urlencode(qs_clean, doseq=True) if qs_clean else ""
        path = p.path.rstrip("/") if p.path != "/" else p.path
        return urlunparse(("https", host, path, "", new_query, ""))
    except Exception:
        return url


def source_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        parts = host.split(".")
        # check for special 3-label TLDs
        if len(parts) >= 3:
            tail = "." + ".".join(parts[-2:])
            if tail in SPECIAL_TLDS:
                return ".".join(parts[-3:])
        return ".".join(parts[-2:]) if len(parts) >= 2 else host
    except Exception:
        return url


def fuzzy_key(headline: str) -> str:
    # strip trailing " – Source" or " | Source"
    h = re.sub(r"\s*[–|]\s*.{1,40}$", "", headline)
    h = h.lower()
    tokens = re.findall(r"[a-z0-9$€£]+", h)
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    return ",".join(sorted(set(tokens)))


def in_window(pub_date: str) -> bool:
    if not pub_date:
        return False
    d = pub_date[:10]
    return WINDOW_START <= d <= WINDOW_END


# ── RAW CANDIDATE LIST ─────────────────────────────────────────────────────────
# Each entry: url, headline, publication_date (ISO-8601 or None), reject_reason hint
# reject_reason is auto-computed but can be pre-set for clarity.
# "no_pub_date"  = couldn't confirm date (WebFetch 403 / not in snippet)
# "out_of_window" = confirmed date outside window
# ──────────────────────────────────────────────────────────────────────────────

RAW = [

    # ── QUERY a: Sinopec / CNPC / CNOOC ───────────────────────────────────────
    {
        "url": "https://www.sciencedirect.com/science/article/pii/S2666759226000442",
        "headline": "Carbon capture, utilization, and storage: Advances made by Sinopec and future prospects",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://www.prnewswire.com/news-releases/sinopec-announces-the-launch-of-carbon-footprint-alliance-to-drive-green-development-in-energy-and-chemicals-302212283.html",
        "headline": "Sinopec Announces the Launch of Carbon Footprint Alliance to Drive Green Development in Energy and Chemicals",
        "publication_date": "2024-08-01T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.sinopecgroup.com/group/en/000/000/067/67312.shtml",
        "headline": "Carbon Future with CCUS – Sinopec Group",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY b: ADNOC / Aramco / QatarEnergy ────────────────────────────────
    {
        "url": "https://agbi.com/analysis/adipec-gulf-decarbonisation",
        "headline": "Aramco, Adnoc and the long road to decarbonisation",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://themiddleeastinsider.com/2026/04/28/adnoc-strategy-post-opec-2026-2030/",
        "headline": "ADNOC Strategy Post-OPEC: 2026-2030 Production Path",
        "publication_date": "2026-04-28T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://dii-desertenergy.org/dii-editorial-q1-2025-mena-carbon-capture-storage-a-growth-sector/",
        "headline": "MENA Carbon Capture & Storage: A Growth Sector – Dii Desert Energy",
        "publication_date": "2025-04-01T00:00:00+00:00",
        "hint": "out_of_window",
    },

    # ── QUERY c: Petrobras / Pertamina / Petronas ─────────────────────────────
    {
        "url": "https://oilprice.com/Company-News/Petronas-Maps-Heavy-Upstream-LNG-and-CCS-Push-Through-2028.html",
        "headline": "Petronas Maps Heavy Upstream, LNG, and CCS Push Through 2028",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://worldoil.com/news/2026/4/14/petrobras-takes-fid-on-seap-fpso-development-in-brazil-basin/",
        "headline": "Petrobras takes FID on SEAP FPSO development in Brazil basin",
        "publication_date": "2026-04-14T00:00:00+00:00",
        "hint": "out_of_window",
    },

    # ── QUERY d: Indonesia / Malaysia / Vietnam ───────────────────────────────
    {
        "url": "https://www.hatch.com/About-Us/News-And-Media/2026/04/CCUS-Hub-Study-identifies-five-Asia-Pacific-hub-sites",
        "headline": "CCUS Hub Study identifies five Asia-Pacific hub sites and welcomes new consortium partners",
        "publication_date": "2026-04-01T00:00:00+10:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.bhp.com/news/articles/2026/04/ccus-hub-study-identifies-five-asia-pacific-hub-sites-and-welcomes-new-consortium-partners",
        "headline": "CCUS Hub Study identifies five Asia-Pacific hub sites and welcomes new consortium partners – BHP",
        "publication_date": "2026-04-01T00:00:00+10:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.climatechangenews.com/2025/03/20/carbon-colonialism-malaysia-and-indonesia-plan-storage-hubs-for-asian-emissions/",
        "headline": "Malaysia and Indonesia plan to store East Asia's emissions",
        "publication_date": "2025-03-20T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.reccessary.com/en/news/malaysia-carbon-storage-challenges",
        "headline": "Carbon storage unlocked: Malaysia bets on CCS, but challenges loom behind the boom",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY e: India / ONGC / Reliance ──────────────────────────────────────
    {
        "url": "https://carbonherald.com/ongc-launches-first-ccs-pilot-at-gujarats-gandhar-oilfield/",
        "headline": "ONGC Launches First CCS Pilot At Gujarat's Gandhar Oilfield",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://discoveryalert.com.au/india-ccus-scheme-approval-carbon-capture-investment-2026/",
        "headline": "India's CCUS Scheme Approval: A $2.2 Billion Milestone for 2026",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY g: Latin America / Brazil / Argentina ────────────────────────────
    # No relevant CCS results found; no entries.

    # ── QUERY i: Mitsui / Mitsubishi / Itochu ────────────────────────────────
    {
        "url": "https://www.sumitomocorp.com/en/jp/news/release/2026/group/21320",
        "headline": "Sumitomo Corporation to Participate in CDR Project Through Joint Venture with Graphyte",
        "publication_date": "2026-06-04T00:00:00+09:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.chemanalyst.com/NewsAndDeals/NewsDetails/sumitomo-and-graphyte-launch-joint-venture-to-expand-42620",
        "headline": "Sumitomo and Graphyte Launch Joint Venture to Expand Biomass-Based Carbon Removal Credits",
        "publication_date": "2026-06-04T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.bioenergy-news.com/news/sumitomo-and-graphyte-form-joint-venture-to-scale-biomass-carbon-removal-credits/",
        "headline": "Sumitomo and Graphyte form joint venture to scale biomass carbon removal credits",
        "publication_date": "2026-06-04T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://carbonherald.com/graphyte-secures-backing-from-sumitomo-and-expands-partnerships/",
        "headline": "Graphyte Secures Backing From Sumitomo And Expands Partnerships",
        "publication_date": "2026-06-04T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://marubeni.com/en/news/2024/info/00042.html",
        "headline": "Joint Development of a Commercial Carbon Dioxide Storage Project in South Texas, United States – Marubeni",
        "publication_date": "2024-06-01T00:00:00+09:00",
        "hint": "out_of_window",
    },

    # ── QUERY j: Sumitomo / Marubeni / JERA ───────────────────────────────────
    {
        "url": "https://www.pipeline-journal.net/news/japans-sumitomo-backs-major-uk-carbon-capture-pipeline-project",
        "headline": "Japan's Sumitomo Backs Major UK Carbon Capture Pipeline Project",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY k: BP / Shell / TotalEnergies ──────────────────────────────────
    {
        "url": "https://fortune.com/europe/2025/02/26/bp-energy-giant-unveils-strategy-shakeup-amid-global-energy-transition-murray-auchincloss/",
        "headline": "'A new direction for BP' as energy giant unveils strategy shakeup amid global energy transition",
        "publication_date": "2025-02-26T00:00:00+00:00",
        "hint": "out_of_window",
    },

    # ── QUERY l: Eni / Equinor / INPEX ────────────────────────────────────────
    {
        "url": "https://www.eni.com/en-IT/media/press-release/2026/05/eni-ccus-holding-expands-financing-sources-for-platform-ccs-projects.html",
        "headline": "Eni CCUS Holding expands the financing sources for its platform of CCS projects",
        "publication_date": "2026-05-01T00:00:00+02:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://drillingcontractor.org/inpex-jv-wins-approval-to-drill-two-ccs-exploration-wells-offshore-japan-77867",
        "headline": "INPEX JV wins approval to drill two CCS exploration wells offshore Japan",
        "publication_date": "2026-04-27T00:00:00+09:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.offshore-energy.biz/ccs-exploration-drilling-ops-cleared-for-launch-offshore-japan/",
        "headline": "CCS exploration drilling ops cleared for launch offshore Japan",
        "publication_date": "2026-04-27T00:00:00+09:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.offshore-mag.com/energy-transition/news/55374748/inpex-venture-cleared-for-carbon-capture-drilling-investigations-offshore-japan",
        "headline": "INPEX venture cleared for carbon capture drilling investigations offshore Japan",
        "publication_date": "2026-04-27T00:00:00+09:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://carbonherald.com/japan-approves-offshore-carbon-storage-exploration-near-chiba/",
        "headline": "Japan Approves Offshore Carbon Storage Exploration Near Chiba",
        "publication_date": "2026-04-27T00:00:00+09:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.ccarbon.info/news/metropolitan-ccs-joint-venture-granted-approval-for-ccs-exploration-drilling-off-pacific-coast-of-chiba-prefecture-japan/",
        "headline": "Metropolitan CCS Joint Venture Granted Approval For CCS Exploration Drilling Off Pacific Coast Of Chiba Prefecture, Japan",
        "publication_date": "2026-04-27T00:00:00+09:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.equinor.com/news/20260625-wisting-proposal-environmental-impact-assessment-programme",
        "headline": "Proposal for environmental impact assessment programme for Wisting submitted for public consultation",
        "publication_date": "2026-06-25T00:00:00+02:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://carboncredits.com/blackrock-and-enis-1-2-billion-deal-to-push-carbon-capture/",
        "headline": "BlackRock and Eni's $1.2 Billion Deal to Push Carbon Capture",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY s: London Protocol ──────────────────────────────────────────────
    # Only background/policy pages found; no breaking news in window.

    # ── QUERY t: Transboundary CCS ────────────────────────────────────────────
    {
        "url": "https://www.gov.uk/government/consultations/uk-emissions-trading-scheme-regulating-cross-boundary-ccs-pipelines/uk-emissions-trading-scheme-regulating-cross-boundary-ccs-pipelines-accessible-webpage",
        "headline": "UK Emissions Trading Scheme: Regulating cross-boundary CCS pipelines",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY u: Bayu-Undan / Barossa / Sea Dumping Act ──────────────────────
    {
        "url": "https://ieefa.org/resources/bayu-undan-test-bed-carbon-trading-or-distraction",
        "headline": "Bayu-Undan: A test bed for carbon trading or a distraction?",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://australiainstitute.org.au/post/governments-dirty-favour-for-santos-bill-passes-with-opposition-support/",
        "headline": "Government's 'dirty favour for Santos' bill passes with opposition support",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY m: Class VI / storage permit ───────────────────────────────────
    {
        "url": "https://worldoil.com/news/2026/6/3/class-vi-well-approvals-accelerate-as-ccs-permit-applications-slow/",
        "headline": "Class VI well approvals accelerate as CCS permit applications slow",
        "publication_date": "2026-06-03T00:00:00-05:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://ghanaupstream.com/class-vi-well-approvals-accelerate-as-ccs-permit-applications-slow/",
        "headline": "Class VI well approvals accelerate as CCS permit applications slow",
        "publication_date": "2026-06-03T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://ethanolproducer.com/articles/epa-approves-class-vi-permit-for-purefield",
        "headline": "EPA approves Class VI permit for PureField CCS project",
        "publication_date": "2026-04-10T00:00:00-05:00",
        "hint": "out_of_window",
    },

    # ── QUERY n: CCUS hub / FID ────────────────────────────────────────────────
    {
        "url": "https://discoveryalert.com.au/india-ccus-scheme-approval-carbon-capture-investment-2026/",
        "headline": "India's CCUS Scheme Approval: A $2.2 Billion Milestone for 2026",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://www.iea.org/commentaries/policy-and-financing-momentum-sustain-ccus-progress-despite-setbacks",
        "headline": "Policy and financing momentum sustain CCUS progress despite setbacks",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY o: Direct air capture offtake ──────────────────────────────────
    {
        "url": "https://www.newswire.ca/news-releases/deep-sky-announces-direct-air-capture-carbon-removal-agreement-with-td-bank-group-advancing-canada-s-leadership-in-carbon-removal-899228119.html",
        "headline": "Deep Sky Announces Direct Air Capture Carbon Removal Agreement with TD Bank Group, Advancing Canada's Leadership in Carbon Removal",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://esgnews.com/charm-industrial-secures-61500-ton-carbon-removal-deal-and-20-million-financing-from-jpmorganchase/",
        "headline": "Charm Industrial Secures 61,500-Ton Carbon Removal Deal and $20 Million Financing From JPMorganChase",
        "publication_date": "2026-06-04T00:00:00-05:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://carbonherald.com/jpmorganchase-deepens-charm-industrial-partnership-with-a-new-cdr-deal-and-debt-financing/",
        "headline": "JPMorganChase Deepens Charm Industrial Partnership With A New CDR Deal And Debt Financing",
        "publication_date": "2026-06-04T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.esgtoday.com/jpmorgan-signs-carbon-removal-financing-deal-with-charm-industrial/",
        "headline": "JPMorgan Signs Carbon Removal, Financing Deal with Charm Industrial",
        "publication_date": "2026-06-04T00:00:00-05:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://carboncredits.com/jpmorgan-backs-carbon-removal-growth-with-new-charm-industrial-deal/",
        "headline": "JPMorgan Backs Carbon Removal Growth With New Charm Industrial Deal",
        "publication_date": "2026-06-04T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.esgdive.com/news/jpmorgan-signs-carbon-offtake-financing-deal-charm-industrial/822156/",
        "headline": "JPMorgan signs carbon offtake and financing deal with Charm Industrial",
        "publication_date": "2026-06-04T00:00:00-05:00",
        "hint": "out_of_window",
    },

    # ── QUERY p: Blue ammonia / blue hydrogen ─────────────────────────────────
    {
        "url": "https://enkiai.com/saudi-aramco-hydrogen-initiatives-for-2025-key-projects-strategies-and-partnerships/",
        "headline": "Blue Hydrogen: Aramco's 2026 Strategy to Lead Energy Trade",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://news.sustainability-directory.com/industry/massive-blue-ammonia-project-validates-carbon-capture-for-global-fertilizer-scale/",
        "headline": "Massive Blue Ammonia Project Validates Carbon Capture for Global Fertilizer Scale",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY q: Cement / steel carbon capture ────────────────────────────────
    {
        "url": "https://carbonherald.com/mci-carbon-launches-worlds-first-industrial-carbon-refinery/",
        "headline": "MCi Carbon Launches World's First Industrial Carbon Refinery",
        "publication_date": "2026-06-18T00:00:00+10:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://decarbonisationtechnology.com/news/2899/mci-carbon-opens-the-worlds-first-carbon-refinery-myrtle-in-australia",
        "headline": "MCi Carbon opens the world's first carbon refinery MYRTLE in Australia",
        "publication_date": "2026-06-18T00:00:00+10:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.azocleantech.com/news.aspx?newsID=36435",
        "headline": "Australia Opens the World's First Carbon Refinery MYRTLE – MCi Carbon Gives Global Heavy Industry a Profitable Pathway to Decarbonize",
        "publication_date": "2026-06-18T00:00:00+10:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.australianmanufacturing.com.au/australia-opens-world-first-carbon-refinery-as-manufacturing-decarbonisation-push-accelerates/",
        "headline": "Australia opens world-first carbon refinery as manufacturing decarbonisation push accelerates",
        "publication_date": "2026-06-18T00:00:00+10:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.globalcement.com/news/analysis/20811-update-on-carbon-capture-in-cement-may-2026",
        "headline": "Update on carbon capture in cement, May 2026",
        "publication_date": "2026-05-01T00:00:00+00:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://enkiai.com/carbon-capture/us-steel-carbon-to-chemicals-2/",
        "headline": "U.S. Steel Carbon Capture 2026, 750k ton Carbon Free Deal",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY r: CO2 shipping / pipeline milestone ────────────────────────────
    {
        "url": "https://carbonherald.com/misc-and-k-line-secure-second-northern-lights-charter-for-co2-carrier/",
        "headline": "MISC And K LINE Secure Second Northern Lights Charter For CO2 Carrier",
        "publication_date": "2026-06-03T00:00:00+02:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.mynewsdesk.com/burckhardtcompression/pressreleases/burckhardt-compression-secures-milestone-order-for-first-industrial-scale-liquefied-co2-carrier-supporting-northern-lights-ccs-project-3454894",
        "headline": "Burckhardt Compression secures milestone order for first industrial scale Liquefied CO₂ carrier supporting Northern Lights CCS project",
        "publication_date": "2026-06-18T00:00:00+02:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://www.worldpipelines.com/contracts-and-tenders/27062025/slb-onesubsea-secures-epc-contract-for-northern-lights-co2-transport-and-storage-project-expansion/",
        "headline": "SLB OneSubsea secures EPC contract for Northern Lights CO2 transport and storage project expansion",
        "publication_date": "2025-06-27T00:00:00+02:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://en.clickpetroleoegas.com.br/european-ship-will-transport-captured-co-to-be-stored-under-the-north-sea-as-the-greensand-project-prepares-the-first-industrial-offshore-st-ctl01/",
        "headline": "European ship will transport captured CO₂ to be stored under the North Sea as the Greensand project prepares the first industrial offshore storage in the EU",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY f: Japan / Tomakomai ────────────────────────────────────────────
    {
        "url": "https://drillingcontractor.org/inpex-jv-wins-approval-to-drill-two-ccs-exploration-wells-offshore-japan-77867",
        "headline": "INPEX JV wins approval to drill two CCS exploration wells offshore Japan",
        "publication_date": "2026-04-27T00:00:00+09:00",
        "hint": "out_of_window",
    },
    {
        "url": "https://spectra.mhi.com/how-japan-aims-to-become-a-ccs-powerhouse",
        "headline": "How Japan aims to become a CCS powerhouse",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── QUERY h: Africa ────────────────────────────────────────────────────────
    # No breaking news found in-window; only general/background sources.

    # ── Alberta / Canada policy – surfaced from multiple queries ──────────────
    {
        "url": "https://carbonherald.com/alberta-carbon-tax-change-threatens-400m-carbon-capture-facility/",
        "headline": "Alberta Carbon Tax Change Threatens $400M Carbon Capture Facility",
        "publication_date": "2026-06-29T00:00:00-06:00",
        "hint": "in_window",
    },
    {
        "url": "https://www.cbc.ca/news/canada/calgary/bakx-varme-edmonton-smith-carney-carbon-tax-tier-9.7247705",
        "headline": "'Mayday to Ottawa': $400M carbon capture facility could be cancelled after changes to Alberta's carbon tax",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://policyoptions.irpp.org/2026/06/alberta-carbon-floor/",
        "headline": "A weak carbon-price floor will not fix Alberta's emissions market",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://thenarwhal.ca/alberta-industrial-carbon-tax-email/",
        "headline": "Alberta considering killing its industrial carbon tax: email",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://thenarwhal.ca/alberta-carbon-tax-documents/",
        "headline": "Alberta moves to weaken its carbon tax system: document",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://carbon-pulse.com/390510/",
        "headline": "EXCLUSIVE: Alberta government says remains committed to industrial carbon pricing",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://taxnews.ey.com/news/2026-1180-canada-alberta-revises-industrial-carbon-prices",
        "headline": "Canada | Alberta revises industrial carbon prices",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://www.newswire.ca/news-releases/industrial-carbon-tax-and-carbon-capture-requirements-increase-the-cost-to-produce-energy-making-alberta-uncompetitive-with-u-s-counterparts-813283306.html",
        "headline": "Industrial carbon tax and carbon capture requirements increase the cost to produce energy, making Alberta uncompetitive with U.S. counterparts",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://ieefa.org/resources/financial-risks-carbon-capture-and-storage-canada-concerns-about-pathways-project-and",
        "headline": "Financial risks of carbon capture and storage in Canada: Concerns about the Pathways Project and Public Energy Policy",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── 45Q / One Big Beautiful Bill – Global CCS Institute ──────────────────
    {
        "url": "https://www.globalccsinstitute.com/u-s-preserves-and-increases-45q-credit-in-one-big-beautiful-bill-act/",
        "headline": "U.S. Preserves and Increases 45Q Credit in \"One Big Beautiful Bill Act\"",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://payneinstitute.mines.edu/keeping-up-with-carbon-key-changes-for-45q-tax-credits-under-one-big-beautiful-bill-act-and-possible-impacts/",
        "headline": "Keeping Up with Carbon: Key Changes for 45Q Tax Credits Under \"One Big Beautiful Bill Act\" and Possible Impacts",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://carboncapturecoalition.org/blog/senate-finance-committee-preserves-45q-but-value-of-credit-will-continue-to-erode-until-2028/",
        "headline": "Senate Finance Committee Preserves 45Q, But Value of Credit Will Continue to Erode Until 2028",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── ADM / Super6 Carbon ───────────────────────────────────────────────────
    {
        "url": "https://carbonherald.com/adm-teams-up-with-super6-carbon-to-monetise-carbon-removal-at-decatur-site/",
        "headline": "ADM Teams Up with Super6 Carbon To Monetize Carbon Removal At Decatur Site",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://www.ccarbon.info/news/adm-and-super6-carbon-partner-to-advance-large-scale-carbon-removal-at-decatur-ccs-facility/",
        "headline": "ADM And Super6 Carbon Partner To Advance Large-Scale Carbon Removal At Decatur CCS Facility",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://carboncapturemagazine.com/articles/adm-super6-carbon-announce-plans-to-produce-cdr-credits-in-decatur",
        "headline": "ADM, Super6 Carbon Announce Plans to Produce CDR Credits in Decatur",
        "publication_date": None,
        "hint": "no_pub_date",
    },

    # ── Lafarge Canada / Hyperion ─────────────────────────────────────────────
    {
        "url": "https://carbonherald.com/lafarge-canada-and-hyperion-team-up-on-pioneering-carbon-recycling-technology/",
        "headline": "Lafarge Canada And Hyperion Team Up On Pioneering Carbon Recycling Technology",
        "publication_date": "2024-12-01T00:00:00+00:00",
        "hint": "out_of_window",
    },

    # ── Deep Sky Manitoba ─────────────────────────────────────────────────────
    {
        "url": "https://carbonherald.com/deep-sky-on-its-way-to-build-one-of-the-worlds-largest-cdr-facilities-in-manitoba-canada/",
        "headline": "Deep Sky On Its Way To Build One Of The World's Largest CDR Facilities In Manitoba, Canada",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://www.prnewswire.com/news-releases/deep-sky-to-build-500-000-tonne-carbon-removal-facility--one-of-the-worlds-largest--in-manitoba-canada-302579674.html",
        "headline": "Deep Sky to build 500,000 tonne carbon removal facility – one of the world's largest – in Manitoba Canada",
        "publication_date": "2025-10-01T00:00:00-04:00",
        "hint": "out_of_window",
    },

    # ── Tanpaifang CCUS China (May 2026) ──────────────────────────────────────
    {
        "url": "http://www.tanpaifang.com/CCUS/202605/27118328.html",
        "headline": "\"CCUS碳捕集第一股\" 即将在港股上市",
        "publication_date": "2026-05-27T00:00:00+08:00",
        "hint": "out_of_window",
    },

    # ── Greensand / Denmark ───────────────────────────────────────────────────
    {
        "url": "https://carbonherald.com/denmark-approves-its-first-commercial-co2-storage-facility/",
        "headline": "Denmark Approves Its First Commercial CO2 Storage Facility",
        "publication_date": None,
        "hint": "no_pub_date",
    },
    {
        "url": "https://www.ccs-europe.eu/greensand_ccs",
        "headline": "Greensand CCS Project in Denmark Reaches Final Investment Decision",
        "publication_date": "2024-12-01T00:00:00+01:00",
        "hint": "out_of_window",
    },

    # ── Nine countries / CCSA ─────────────────────────────────────────────────
    # Not directly surfaced as a URL but mentioned in snippets as June 26 – not in window.

    # ── UK North Sea / Northern Endurance ─────────────────────────────────────
    {
        "url": "https://www.equinor.com/news/20241210-approve-execution-of-uks-first-ccs-projects",
        "headline": "Equinor and partners approve execution of UK's first carbon capture and storage projects",
        "publication_date": "2024-12-10T00:00:00+01:00",
        "hint": "out_of_window",
    },

    # ── EY / Alberta tax alert ────────────────────────────────────────────────
    {
        "url": "https://www.ey.com/en_ca/technical/tax/tax-alerts/2026/tax-alert-2026-no-33",
        "headline": "EY Tax Alert 2026 no 33 – Alberta revises industrial carbon prices",
        "publication_date": None,
        "hint": "no_pub_date",
    },

]


def build_entry(raw: dict) -> dict:
    url = raw["url"]
    headline = raw["headline"]
    pub_date = raw.get("publication_date")
    hint = raw.get("hint", "")

    canonical = canonicalize(url)
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    sd = source_domain(url)
    fk = fuzzy_key(headline)

    iw = in_window(pub_date) if pub_date else False
    kept = iw

    if hint == "in_window" or iw:
        reject = None
    elif pub_date is None or hint == "no_pub_date":
        reject = "no_pub_date"
    else:
        reject = "out_of_window"

    return {
        "url": url,
        "canonical_url": canonical,
        "fuzzy_key": fk,
        "source_domain": sd,
        "headline": headline,
        "publication_date": pub_date,
        "in_window": iw,
        "kept": kept,
        "reject_reason": reject,
        "found_via": "concept_query",
    }


def main():
    # Deduplicate by canonical URL
    seen = {}
    for raw in RAW:
        canonical = canonicalize(raw["url"])
        if canonical not in seen:
            seen[canonical] = raw

    audit_trace = [build_entry(r) for r in seen.values()]

    out_path = os.path.join(os.path.dirname(__file__), f"audit/{TODAY}-shadow.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(audit_trace, f, indent=2, ensure_ascii=False)

    total = len(audit_trace)
    kept = sum(1 for e in audit_trace if e["kept"])
    domains = {e["source_domain"] for e in audit_trace}
    in_win = [e for e in audit_trace if e["in_window"]]

    print(f"Shadow sampler for Tuesday {TODAY}:")
    print(f"  Total considered: {total}")
    print(f"  In-window (kept): {kept}")
    print(f"  Distinct source domains: {len(domains)}")
    print(f"  In-window items:")
    for e in in_win:
        print(f"    [{e['source_domain']}] {e['headline'][:80]}  ({e['publication_date']})")
    print(f"  Output: {out_path}")


if __name__ == "__main__":
    main()
