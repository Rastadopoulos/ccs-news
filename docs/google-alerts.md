# Google Alerts — canonical configuration (sampler C)

30 alerts delivered to `co2crc.ccs.alerts@gmail.com`, polled every 30 min by `scripts/alerts_ingest.py` via IMAP. The ingester filters by CCS keyword regex (`scripts/_canon.py`) and applies the same 24h/72h recency window as the briefing routine.

This file is the canonical list. If you add, remove, or modify an alert in the Google Alerts UI, update this file in the same commit so the repo stays in sync.

## Setup checklist (one-time, already complete)

1. Dedicated Gmail account `co2crc.ccs.alerts@gmail.com`, used for nothing else.
2. IMAP enabled (Gmail settings → Forwarding and POP/IMAP).
3. 2-Factor Authentication enabled on the account.
4. App password created at https://myaccount.google.com/apppasswords (label `ccs-news-audit`).
5. Repo secrets `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` set — see `docs/secrets.md`.
6. Repo variable `ALERTS_INGEST_ENABLED` = `true` set in repo Settings → Variables.
7. Each alert below configured at https://www.google.com/alerts with:
   - Frequency: **As-it-happens**
   - Sources: **Automatic**
   - Language: **English**
   - Region: **Any region**
   - How many: **All results**
   - Deliver to: `co2crc.ccs.alerts@gmail.com`

## The 30 alerts, grouped by category

### Under-represented regions (5)

```
"Sinopec" OR "CNPC" OR "CNOOC" "carbon capture" OR "carbon storage"
"ADNOC" OR "Aramco" OR "QatarEnergy" "carbon capture" OR "carbon storage"
"Petronas" OR "Pertamina" "CCS" OR "CCUS" OR "carbon capture"
"ONGC" OR "Reliance" "carbon capture" OR "CCS"
"Petrobras" "carbon" OR "CCS" OR "CO2"
```

### Marquee projects (5)

```
"Otway International Test Centre" OR "Moomba CCS" OR "Bonaparte CCS" OR "CarbonNet"
"Northern Lights" "carbon" OR "Porthos CCS" OR "Aramis CCS" OR "Greensand"
"Stratos" "1PointFive" OR "Bayou Bend" OR "Pathways Alliance" OR "Polaris CCS"
"HyNet" OR "Net Zero Teesside" OR "Acorn CCS" OR "Viking CCS"
"Tomakomai" OR "Kasawari" OR "Lang Lebah" OR "Tangguh CCS"
```

### Multinational strategy (5)

Pair company names with strategy-flavoured keywords to catch JV / MoU / roadmap / investment items, not just facility-level press releases.

```
"Mitsui" OR "Mitsubishi Corp" "carbon capture" OR "carbon storage" OR "CCS"
"Itochu" OR "Sumitomo" OR "Marubeni" "CCS" OR "carbon capture"
"JERA" OR "INPEX" "carbon capture" OR "CCS" OR "MoU"
"BP" OR "Shell" OR "TotalEnergies" "CCS strategy" OR "carbon capture investment"
"Eni" OR "Equinor" "CCS" "partnership" OR "JV" OR "consortium"
```

### Majors paired with regional expansion (3)

Designed to surface "X enters Y market" stories.

```
"TotalEnergies" "Indonesia" OR "Malaysia" OR "Thailand" OR "Vietnam" "carbon"
"Chevron" "Asia" OR "Middle East" "CCS" OR "carbon capture"
"BP" "Brazil" OR "Mexico" OR "Argentina" "carbon"
```

### DAC & CDR developers (2)

```
"Climeworks" OR "Heirloom" OR "Carbon Engineering" OR "CarbonCapture Inc"
"direct air capture" "offtake" OR "FID" OR "purchase agreement"
```

### Policy & funding (3)

```
"Class VI permit" OR "Class VI well" OR "EPA CCS"
"Section 45Q" OR "EU CCS Directive" OR "Net-Zero Industry Act" OR "China carbon market" "CCS"
"DOE FECM" OR "carbon capture grant" OR "carbon management program"
```

### London Protocol, transboundary CCS, and Australian sea-dumping (6)

Lower volume than the other categories but very high signal — every cross-border CCS deal cites this framework, and Bayu-Undan is the canonical Australia-related case.

```
"London Protocol" "CO2" OR "carbon dioxide" OR "CCS" OR "sub-seabed"
"transboundary CO2" OR "cross-border CCS" OR "cross-border carbon storage" OR "CO2 export"
"Bayu-Undan" OR "Bayu Undan" "CCS" OR "carbon" OR "CO2" OR "storage"
"Timor-Leste" OR "Timor Leste" "carbon" OR "CCS" OR "CO2" OR "Bayu"
"sea dumping" OR "dumping at sea" "carbon" OR "CO2" OR "CCS"
"liquid CO2 carrier" OR "CO2 shipping" OR "CO2 vessel" OR "CO2 ship"
```

### CO2CRC name watch (1)

```
"CO2CRC"
```

## Maintenance

- **Quarterly review**: scan the Saturday recall audit's source-coverage matrix. Alerts that consistently produce no items captured by sampler A (the production routine already had them) but whose items are also rejected by the keyword regex are candidates to drop. Alerts that produce high-quality misses (items A missed that you valued) are confirmed keepers.
- **Adding a new alert**: configure in the Google Alerts UI, append to the relevant section of this file in the same commit. Use the existing format (one quoted query string per line in the code block) so the file stays diff-friendly.
- **Removing an alert**: delete in the Google Alerts UI, remove from this file in the same commit.
- **Boolean operators**: `OR` must be uppercase. Quoted phrases force exact-phrase matching. Unquoted multi-word tokens become fuzzy AND.

## Why these queries and not broader ones

The set deliberately avoids broad single-token alerts like `"carbon capture"` or `"CCS"`. These would duplicate the production routine's own searches and add a lot of noise without adding measurement value. The alerts here are tilted toward what the routine is structurally less good at: non-Western operators, multinational strategy news, niche legal frameworks. That's where independent sampling actually moves the recall number.
