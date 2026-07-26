"""Country-name -> ISO2 + tile-grid lookup for the dashboard's world-map view.

Single source of truth for every country string that appears in the news-facts
corpus, storage-baseline.json, and reference-baseline-countries.json. Hand-authored
and reviewed like fx_rates.json, because the corpus's country strings are curated
free text (see EXTRACTION_SPEC.md's country-normalisation notes), not raw ISO
input — there is no upstream guarantee of ISO-3166 spelling to key off.

Country outlines themselves live in the generated scripts/_worldmap.py, keyed by
the ISO codes below. Adding a new country: add it to COUNTRY_ISO and to
CONTINENT_GROUPS. If its ISO code is absent from _worldmap.COUNTRY_PATH it is a
microstate too small to draw at world scale — add it to EXTRA_POINTS in
scripts/gen_worldmap.py and to MICRO_ISO in build_dashboard.py so it still gets a
visible marker.
"""

# country name (as normalised per EXTRACTION_SPEC.md) -> ISO 3166-1 alpha-2
COUNTRY_ISO = {
    "United States": "US",
    "United Kingdom": "GB",
    "Canada": "CA",
    "Japan": "JP",
    "Australia": "AU",
    "Netherlands": "NL",
    "China": "CN",
    "Norway": "NO",
    "Germany": "DE",
    "France": "FR",
    "Malaysia": "MY",
    "Denmark": "DK",
    "India": "IN",
    "Indonesia": "ID",
    "Belgium": "BE",
    "Spain": "ES",
    "South Korea": "KR",
    "Brazil": "BR",
    "Finland": "FI",
    "Poland": "PL",
    "United Arab Emirates": "AE",
    "Sweden": "SE",
    "Singapore": "SG",
    "Romania": "RO",
    "Oman": "OM",
    "Nigeria": "NG",
    "Italy": "IT",
    "Switzerland": "CH",
    "Kenya": "KE",
    "Saudi Arabia": "SA",
    "Thailand": "TH",
    "Vietnam": "VN",
    "Qatar": "QA",
    "Czechia": "CZ",
    "Angola": "AO",
    "Egypt": "EG",
    "Turkey": "TR",
    "Croatia": "HR",
    "Colombia": "CO",
    "Morocco": "MA",
    "Mozambique": "MZ",
    "New Zealand": "NZ",
    # Not in the news corpus, but present in storage-baseline.json / reference-baseline.json.
    "Iceland": "IS",
    "South Africa": "ZA",
    # Present in the GCCSI facilities list (reference-baseline-countries.json).
    "Bahrain": "BH",
    "Bulgaria": "BG",
    "Greece": "GR",
    "Hungary": "HU",
    "Latvia": "LV",
    "Libya": "LY",
    "Lithuania": "LT",
    "Papua New Guinea": "PG",
    "Russia": "RU",
    "Timor-Leste": "TL",
}

# Strings that appear in the corpus but are not a single mappable country. Excluded
# from TILE_GRID by design; the build script surfaces these as a separate badge
# rather than attributing them to member-state tiles (see the map's source-caption
# convention — never invent a per-country split the source data didn't state).
NON_COUNTRY_TOKENS = {"European Union"}

# Continent grouping, used for the dashboard's per-region roll-up table.
# Every country in COUNTRY_ISO must appear in exactly one group, or it silently
# drops out of the regional totals — there is a test for this.
CONTINENT_GROUPS = {
    "Canada": "Americas", "United States": "Americas",
    "Colombia": "Americas", "Brazil": "Americas",

    "Iceland": "Europe", "Norway": "Europe", "Sweden": "Europe", "Finland": "Europe",
    "United Kingdom": "Europe", "Denmark": "Europe", "Netherlands": "Europe",
    "Germany": "Europe", "Poland": "Europe", "Belgium": "Europe", "Switzerland": "Europe",
    "Czechia": "Europe", "Romania": "Europe", "France": "Europe", "Italy": "Europe",
    "Croatia": "Europe", "Spain": "Europe",

    "Turkey": "Middle East & Africa", "Morocco": "Middle East & Africa",
    "Egypt": "Middle East & Africa", "Saudi Arabia": "Middle East & Africa",
    "Qatar": "Middle East & Africa", "United Arab Emirates": "Middle East & Africa",
    "Oman": "Middle East & Africa", "Nigeria": "Middle East & Africa",
    "Kenya": "Middle East & Africa", "Angola": "Middle East & Africa",
    "Mozambique": "Middle East & Africa", "South Africa": "Middle East & Africa",

    "South Korea": "Asia-Pacific", "Japan": "Asia-Pacific", "China": "Asia-Pacific",
    "India": "Asia-Pacific", "Vietnam": "Asia-Pacific", "Thailand": "Asia-Pacific",
    "Malaysia": "Asia-Pacific", "Singapore": "Asia-Pacific", "Indonesia": "Asia-Pacific",
    "Australia": "Asia-Pacific", "New Zealand": "Asia-Pacific",
    "Papua New Guinea": "Asia-Pacific", "Timor-Leste": "Asia-Pacific",

    "Greece": "Europe", "Hungary": "Europe", "Bulgaria": "Europe",
    "Latvia": "Europe", "Lithuania": "Europe",
    # Russia spans Europe and Asia; grouped with Europe to match the GCCSI
    # report's own regional chapters, which discuss it under Europe.
    "Russia": "Europe",

    "Bahrain": "Middle East & Africa", "Libya": "Middle East & Africa",
}

GROUP_ORDER = ["Americas", "Europe", "Middle East & Africa", "Asia-Pacific"]

def split_compound(name):
    """'United States/Canada' -> ['United States', 'Canada']. storage-baseline.json's
    one compound country row is attributed to BOTH member countries — never dropped,
    never arbitrarily assigned to just one."""
    if not name:
        return []
    return [p.strip() for p in name.split("/")] if "/" in name else [name]


def iso2(name):
    return COUNTRY_ISO.get(name)
